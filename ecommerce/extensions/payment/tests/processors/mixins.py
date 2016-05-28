# -*- coding: utf-8 -*-
"""Base class for payment processor implementation test classes."""
from __future__ import unicode_literals

import ddt
from django.conf import settings
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.extensions.test.factories import create_basket, PartnerFactory
from ecommerce.tests.factories import SiteConfigurationFactory

Partner = get_model('partner', 'Partner')


@ddt.ddt
class PaymentProcessorTestCaseMixin(RefundTestMixin, CourseCatalogTestMixin, PaymentEventsMixin):
    """ Mixin for payment processor tests. """

    # Subclasses should set this value. It will be used to instantiate the processor in setUp.
    processor_class = None

    # This value is used to test the NAME attribute on the processor.
    processor_name = None

    CERTIFICATE_TYPE = 'test-certificate-type'

    def setUp(self):
        super(PaymentProcessorTestCaseMixin, self).setUp()

        self.course = Course.objects.create(id='a/b/c', name='Demo Course')
        self.product = self.course.create_or_update_seat(self.CERTIFICATE_TYPE, False, 20, self.partner)

        self.processor = self.processor_class(self.site)  # pylint: disable=not-callable
        self.basket = create_basket(self.site, empty=True)
        self.basket.add_product(self.product)
        self.basket.owner = factories.UserFactory()
        self.basket.save()

    @ddt.data('edX', 'other')
    def test_configuration(self, partner_code):
        """ Verifies configuration is read from settings. """
        Partner.objects.all().delete()
        partner = PartnerFactory(short_code=partner_code)
        site_configuration = SiteConfigurationFactory(partner=partner)
        processor = self.processor_class(site_configuration.site)   # pylint: disable=not-callable

        self.assertDictEqual(
            processor.configuration,
            settings.PAYMENT_PROCESSOR_CONFIG[partner_code.lower()][self.processor.NAME]
        )

    def test_name(self):
        """Test that the name constant on the processor class is correct."""
        self.assertEqual(self.processor.NAME, self.processor_name)

    def test_get_transaction_parameters(self):
        """ Verify the processor returns the appropriate parameters required to complete a transaction. """
        raise NotImplementedError

    def test_handle_processor_response(self):
        """ Verify that the processor creates the appropriate PaymentEvent and Source objects. """
        raise NotImplementedError

    def test_issue_credit(self):
        """ Verify the payment processor responds appropriately to requests to issue credit. """
        raise NotImplementedError

    def test_issue_credit_error(self):
        """ Verify the payment processor responds appropriately if the payment gateway cannot issue a credit. """
        raise NotImplementedError
