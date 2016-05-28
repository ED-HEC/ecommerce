from __future__ import unicode_literals

import logging
import time
from optparse import make_option

from dateutil import parser
from django.core.management import BaseCommand, CommandError
from edx_rest_api_client.client import EdxRestApiClient
from oscar.core.loading import get_model
from slumber.exceptions import HttpClientError

from ecommerce.courses.models import Course

logger = logging.getLogger(__name__)
Partner = get_model('partner', 'Partner')


class Command(BaseCommand):
    """Update seat expire dates."""

    help = 'Update seat expire with the course enrollment end date.'
    option_list = BaseCommand.option_list + (
        make_option(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
            help='Save the data to the database. If this is not set, '
                 'expires date will not be updated'),
        make_option(
            '--partner-code',
            action='store',
            dest='partner_code',
            type=str,
            help='Partner code for the Site whose courses should be updated.'),
    )

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)
    enrollment_date_not_found = set()
    pause_time = 5
    max_tries = 5

    def handle(self, *args, **options):
        seats_to_update = ['honor', 'audit', 'no-id-professional', 'professional']
        save_to_db = options.get('commit', False)
        site_configuration = Partner.objects.get(code__iexact=options['partner_code']).siteconfiguration_set.first()
        courses_enrollment_info = self._get_courses_enrollment_info(site_configuration)

        if not courses_enrollment_info:
            msg = 'No course enrollment information found.'
            logger.error(msg)
            raise CommandError(msg)

        courses = Course.objects.all().order_by('id')
        logger.info('[%d] courses found for update.', courses.count())

        for course in courses:
            enrollment_end_date = courses_enrollment_info.get(course.id)

            # Only proceed if course enrollment information is present
            if not enrollment_end_date:
                logger.error('Enrollment missing for course [%s]', course.id)
                continue

            if save_to_db:
                course_seats = course.seat_products.filter(
                    attributes__name='certificate_type',
                    attribute_values__value_text__in=seats_to_update
                )
                expires = parser.parse(enrollment_end_date)
                course_seats.update(expires=expires)
                logger.info(
                    'Updated expiration date for [%s] seats: [%s]',
                    course.id,
                    ', '.join([str(seat.id) for seat in course_seats]),
                )

    def _get_courses_enrollment_info(self, site_configuration):
        """
        Retrieve the enrollment information for all the courses.

        Arguments:
            site_configuration (SiteConfiguration): Configuration for the site whose courses should be updated.

        Returns:
            Dictionary representing the key-value pair (course_key, enrollment_end) of course.
        """

        def _parse_response(api_response):
            response_data = api_response.get('results', [])

            # Map course_id with enrollment end date.
            courses_enrollment = dict(
                (course_info['course_id'], course_info['enrollment_end'])
                for course_info in response_data
            )
            return courses_enrollment, api_response['pagination'].get('next', None)

        querystring = {'page_size': 50}
        api = EdxRestApiClient(site_configuration.build_lms_url('api/courses/v1/'))
        course_enrollments = {}

        page = 0
        throttling_attempts = 0
        next_page = True
        while next_page:
            page += 1
            querystring['page'] = page
            try:
                response = api.courses().get(**querystring)
                throttling_attempts = 0
            except HttpClientError as exc:
                # this is a known limitation; If we get HTTP429, we need to pause execution for a few seconds
                # before re-requesting the data. raise any other errors
                if exc.response.status_code == 429 and throttling_attempts < self.max_tries:
                    logger.warning(
                        'API calls are being rate-limited. Waiting for [%d] seconds before retrying...',
                        self.pause_time
                    )
                    time.sleep(self.pause_time)
                    page -= 1
                    throttling_attempts += 1
                    logger.info('Retrying [%d]...', throttling_attempts)
                    continue
                else:
                    raise
            enrollment_info, next_page = _parse_response(response)
            course_enrollments.update(enrollment_info)
        return course_enrollments
