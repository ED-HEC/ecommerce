from __future__ import unicode_literals

import logging

import six
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, View
from oscar.apps.partner import strategy
from oscar.apps.payment.exceptions import PaymentError, UserCancelled, TransactionDeclined
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.exceptions import InvalidSignatureError, InvalidBasketError
from ecommerce.extensions.payment.forms import PaymentForm
from ecommerce.extensions.payment.processors.cybersource import Cybersource
from ecommerce.extensions.payment.utils import clean_field_value

# Added by EDUlib
from ecommerce.extensions.payment.processors.paysafe import Paysafe
from ecommerce.notifications.notifications import send_notification
from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.models import Course
# Added by EDUlib

logger = logging.getLogger(__name__)

Applicator = get_class('offer.utils', 'Applicator')
Basket = get_model('basket', 'Basket')
BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
Order = get_model('order', 'Order')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')

# Added by EDUlib
class PaysafeNotifyView(EdxOrderPlacementMixin, View):
    """ Validates a response from Paysafe and processes the associated basket/order appropriately. """
    @property
    def payment_processor(self):
        return Paysafe(self.request.site)

    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(PaysafeNotifyView, self).dispatch(request, *args, **kwargs)

    def _get_billing_address(self, response):
        return BillingAddress(
            first_name=response['req_bill_to_forename'],
            last_name=response['req_bill_to_surname'],
            line1=response['req_bill_to_address_line1'],

            # Address line 2 is optional
            line2=response.get('req_bill_to_address_line2', ''),

            # Oscar uses line4 for city
            line4=response['req_bill_to_address_city'],
            postcode=response['req_bill_to_address_postal_code'],
            # State is optional
            state=response.get('req_bill_to_address_state', ''),
            country=Country.objects.get(
                iso_3166_1_a2=response['req_bill_to_address_country']))

    def _get_basket(self, basket_id):
        if not basket_id:
            return None

        try:
            basket_id = int(basket_id)
            basket = Basket.objects.get(id=basket_id)
            basket.strategy = strategy.Default()
            Applicator().apply(basket, basket.owner, self.request)
            return basket
        except (ValueError, ObjectDoesNotExist):
            return None

    def get(self, request):
        """Process a Paysafe merchant notification and place an order for paid products as appropriate."""

        # Added by EDUlib
        #####print("--------------------------")
        #####print("Entering get from views.py")
        #####print("--------------------------")
        #####print("===== valeur de request dans views.py =====")
        #####print(request)
        #####print("===== valeur de request dans views.py =====")
        # Added by EDUlib

        # Note (CCB): Orders should not be created until the payment processor has validated the response's signature.
        # This validation is performed in the handle_payment method. After that method succeeds, the response can be
        # safely assumed to have originated from Paysafe.

        # Added by EDUlib
        response = request.GET.dict()
        #####print("===== valeur de response dans get de views.py =====")
        #####print(response)
        #####print("===== valeur de response dans get de views.py =====")
        #####print("===== valeur de request.META['QUERY_STRING'] dans get de views.py =====")
        #####print(request.META['QUERY_STRING'])
        #####print("===== valeur de request.META['QUERY_STRING'] dans get de views.py =====")
        # Added by EDUlib

        basket = None
        transaction_id = None

        try:
            # Added by EDUlib
            order_number = response.get('orderNum')
            #####print("===== valeur de order_number dans get de views.py =====")
            #####print(order_number)
            #####print("===== valeur de order_number dans get de views.py =====")
            # Added by EDUlib

            # Added by EDUlib
            transaction_id = response.get('id')
            #####print("===== valeur de transaction_id dans get de views.py =====")
            #####print(transaction_id)
            #####print("===== valeur de transaction_id dans get de views.py =====")
            # Added by EDUlib

            # Added by EDUlib
            basket_id = OrderNumberGenerator().basket_id(order_number)
            #####print("===== valeur de basket_id dans get de views.py =====")
            #####print(basket_id)
            #####print("===== valeur de basket_id dans get de views.py =====")
            # Added by EDUlib

            ##### TEST 31 05 2016 #####
            #####conn = sqlite3.connect('/home/ubuntu/ecommerce/ecommerce/extensions/payment/processors/test.db')
            #####print "Opened database successfully";

            #####cursor = conn.execute("SELECT REFNUM, ID from NETBANX WHERE REFNUM=:valeur", {"valeur": order_number})
            #####for row in cursor:
            #####    print "REFNUM = ", row[0]
            #####    print "ID = ", row[1],  "\n"

            #####transaction_id = row[1]
            #####print("===== valeur de transaction_id dans get de views.py =====")
            #####print(transaction_id)
            #####print("===== valeur de transaction_id dans get de views.py =====")

            #####print "Operation done successfully";
            #####conn.close()
            ##### TEST 31 05 2016 #####

            logger.info(
                'Received Paysafe merchant notification for transaction [%s], associated with basket [%d].',
                transaction_id,
                basket_id
            )

            basket = self._get_basket(basket_id)

            # Added by EDUlib
            # creation du receipt_page_url
            receipt_page_url = u'{}?orderNum={}'.format(self.payment_processor.receipt_page_url, basket.order_number)
            #####print("valeur de receipt_url = %s", receipt_page_url)
            # Added by EDUlib

            if not basket:
                logger.error('Received payment for non-existent basket [%s].', basket_id)
                return HttpResponse(status=400)
        finally:
            # Store the response in the database regardless of its authenticity.
            ppr = self.payment_processor.record_processor_response(response, transaction_id=transaction_id,
                                                                   basket=basket)

        try:
            # Explicitly delimit operations which will be rolled back if an exception occurs.
            with transaction.atomic():
                try:
                    self.handle_payment(response, basket)
                except InvalidSignatureError:
                    logger.exception(
                        'Received an invalid CyberSource response. The payment response was recorded in entry [%d].',
                        ppr.id
                    )
                    return HttpResponse(status=400)
                except (UserCancelled, TransactionDeclined) as exception:
                    logger.info(
                        'Paysafe payment did not complete for basket [%d] because [%s]. '
                        'The payment response was recorded in entry [%d].',
                        basket.id,
                        exception.__class__.__name__,
                        ppr.id
                    )
                    return HttpResponse()
                except PaymentError:
                    logger.exception(
                        'Paysafe payment failed for basket [%d]. The payment response was recorded in entry [%d].',
                        basket.id,
                        ppr.id
                    )
                    return HttpResponse()
        except:  # pylint: disable=bare-except
            logger.exception('Attempts to handle payment for basket [%d] failed.', basket.id)
            return HttpResponse(status=500)

        try:
            # Note (CCB): In the future, if we do end up shipping physical products, we will need to
            # properly implement shipping methods. For more, see
            # http://django-oscar.readthedocs.org/en/latest/howto/how_to_configure_shipping.html.
            shipping_method = NoShippingRequired()
            shipping_charge = shipping_method.calculate(basket)

            # Note (CCB): This calculation assumes the payment processor has not sent a partial authorization,
            # thus we use the amounts stored in the database rather than those received from the payment processor.
            order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

            user = basket.owner

            billing_address = "whatever whenever"

            #return self.handle_order_placement(
            #    order_number,
            #    user,
            #    basket,
            #    None,
            #    shipping_method,
            #    shipping_charge,
            #    None,
            #    order_total,
            #    response
            #)

            self.handle_order_placement(
                order_number,
                user,
                basket,
                None,
                shipping_method,
                shipping_charge,
                None,
                order_total
            )

            # Added by EDUlib
            #####print("-------------------------")
            #####print("Leaving get from views.py")
            #####print("-------------------------")
            # Added by EDUlib

            # Added by EDUlib
            # modification du return vers le receipt_page_url
            # il faut peut-etre modifier tout les retour http dans get finalement
            #return HttpResponse()
            return redirect(receipt_page_url)
        except:  # pylint: disable=bare-except
            logger.exception(self.order_placement_failure_msg, basket.id)
            return HttpResponse(status=500)
            # Added by EDUlib
            logger.exception(self.order_placement_failure_msg, basket.id)
            return HttpResponse(status=500)