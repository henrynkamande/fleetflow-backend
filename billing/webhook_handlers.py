from __future__ import annotations

import logging
from typing import Any, Callable

from django.utils import timezone

from oauth.models import Company

from .stripe_service import apply_subscription_state, get_stripe_client

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], None]


def _company_from_metadata(metadata: dict[str, Any] | None) -> Company | None:
    if not metadata:
        return None
    company_id = metadata.get('company_id')
    if not company_id:
        return None
    try:
        return Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        logger.warning('Webhook company_id not found: %s', company_id)
        return None


def handle_checkout_session_completed(event: dict[str, Any]) -> None:
    session = event['data']['object']
    company = _company_from_metadata(session.get('metadata'))
    if not company:
        company = _company_from_metadata({'company_id': session.get('client_reference_id')})
    if not company:
        return

    subscription_id = session.get('subscription')
    if not subscription_id:
        return

    client = get_stripe_client()
    subscription = client.subscriptions.retrieve(subscription_id)
    apply_subscription_state(company, subscription)


def handle_customer_subscription_event(event: dict[str, Any]) -> None:
    subscription = event['data']['object']
    company = _company_from_metadata(subscription.get('metadata'))
    if not company and subscription.get('customer'):
        company = Company.objects.filter(stripe_customer_id=subscription['customer']).first()
    if not company:
        return
    apply_subscription_state(company, subscription)


def handle_invoice_paid(event: dict[str, Any]) -> None:
    invoice = event['data']['object']
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        return
    company = Company.objects.filter(stripe_subscription_id=subscription_id).first()
    if not company:
        customer_id = invoice.get('customer')
        if customer_id:
            company = Company.objects.filter(stripe_customer_id=customer_id).first()
    if not company:
        return
    company.billing_status = Company.BillingStatus.ACTIVE
    company.subscription_plan = 'active'
    company.save(update_fields=['billing_status', 'subscription_plan', 'updated_at'])


def handle_invoice_payment_failed(event: dict[str, Any]) -> None:
    invoice = event['data']['object']
    company = None
    subscription_id = invoice.get('subscription')
    if subscription_id:
        company = Company.objects.filter(stripe_subscription_id=subscription_id).first()
    if not company and invoice.get('customer'):
        company = Company.objects.filter(stripe_customer_id=invoice['customer']).first()
    if not company:
        return
    company.billing_status = Company.BillingStatus.PAST_DUE
    company.subscription_plan = 'past_due'
    company.save(update_fields=['billing_status', 'subscription_plan', 'updated_at'])


EVENT_HANDLERS: dict[str, Handler] = {
    'checkout.session.completed': handle_checkout_session_completed,
    'customer.subscription.created': handle_customer_subscription_event,
    'customer.subscription.updated': handle_customer_subscription_event,
    'customer.subscription.deleted': handle_customer_subscription_event,
    'invoice.paid': handle_invoice_paid,
    'invoice.payment_failed': handle_invoice_payment_failed,
}


def dispatch_stripe_event(event: dict[str, Any]) -> None:
    handler = EVENT_HANDLERS.get(event['type'])
    if handler:
        handler(event)
    else:
        logger.debug('Unhandled Stripe event type: %s', event.get('type'))
