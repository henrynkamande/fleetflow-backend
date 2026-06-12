from __future__ import annotations

import logging
from typing import Any, Callable

from oauth.models import User

from .stripe_service import apply_subscription_state, get_stripe_client

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], None]


def _owner_from_metadata(metadata: dict[str, Any] | None) -> User | None:
    if not metadata:
        return None
    owner_id = metadata.get('fleet_owner_id')
    if not owner_id:
        return None
    try:
        return User.objects.get(pk=owner_id, role=User.Role.FLEET_OWNER)
    except User.DoesNotExist:
        logger.warning('Webhook fleet_owner_id not found: %s', owner_id)
        return None


def handle_checkout_session_completed(event: dict[str, Any]) -> None:
    session = event['data']['object']
    owner = _owner_from_metadata(session.get('metadata'))
    if not owner:
        owner = _owner_from_metadata({'fleet_owner_id': session.get('client_reference_id')})
    if not owner:
        return

    subscription_id = session.get('subscription')
    if not subscription_id:
        return

    client = get_stripe_client()
    subscription = client.subscriptions.retrieve(subscription_id)
    apply_subscription_state(owner, subscription)


def handle_customer_subscription_event(event: dict[str, Any]) -> None:
    subscription = event['data']['object']
    owner = _owner_from_metadata(subscription.get('metadata'))
    if not owner and subscription.get('customer'):
        owner = User.objects.filter(stripe_customer_id=subscription['customer'], role=User.Role.FLEET_OWNER).first()
    if not owner:
        return
    apply_subscription_state(owner, subscription)


def handle_invoice_paid(event: dict[str, Any]) -> None:
    invoice = event['data']['object']
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        return
    owner = User.objects.filter(stripe_subscription_id=subscription_id, role=User.Role.FLEET_OWNER).first()
    if not owner:
        customer_id = invoice.get('customer')
        if customer_id:
            owner = User.objects.filter(stripe_customer_id=customer_id, role=User.Role.FLEET_OWNER).first()
    if not owner:
        return
    owner.billing_status = User.BillingStatus.ACTIVE
    owner.subscription_plan = 'active'
    owner.save(update_fields=['billing_status', 'subscription_plan', 'updated_at'])


def handle_invoice_payment_failed(event: dict[str, Any]) -> None:
    invoice = event['data']['object']
    owner = None
    subscription_id = invoice.get('subscription')
    if subscription_id:
        owner = User.objects.filter(stripe_subscription_id=subscription_id, role=User.Role.FLEET_OWNER).first()
    if not owner and invoice.get('customer'):
        owner = User.objects.filter(stripe_customer_id=invoice['customer'], role=User.Role.FLEET_OWNER).first()
    if not owner:
        return
    owner.billing_status = User.BillingStatus.PAST_DUE
    owner.subscription_plan = 'past_due'
    owner.save(update_fields=['billing_status', 'subscription_plan', 'updated_at'])


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
