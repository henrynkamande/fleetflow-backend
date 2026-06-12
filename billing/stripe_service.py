from __future__ import annotations

import logging
from typing import Any

import stripe
from datetime import datetime, timedelta, timezone as dt_timezone

from django.utils import timezone

from oauth.models import User

from . import conf

logger = logging.getLogger(__name__)


def get_stripe_client() -> stripe.StripeClient:
    if not conf.stripe_configured():
        raise RuntimeError('Stripe is not configured (missing STRIPE_SECRET_KEY).')
    return stripe.StripeClient(
        conf.STRIPE_SECRET_KEY,
        stripe_version=conf.STRIPE_API_VERSION,
    )


def billable_vehicle_count(owner: User) -> int:
    count = owner.vehicles.count() if hasattr(owner, 'vehicles') else 0
    return max(1, count)


def get_or_create_stripe_customer(owner: User) -> str:
    if owner.stripe_customer_id:
        return owner.stripe_customer_id

    client = get_stripe_client()
    customer = client.customers.create(
        params={
            'email': owner.email,
            'name': owner.get_full_name(),
            'metadata': {
                'fleet_owner_id': str(owner.id),
            },
        }
    )
    owner.stripe_customer_id = customer.id
    owner.save(update_fields=['stripe_customer_id', 'updated_at'])
    return customer.id


def resolve_price_id(client: stripe.StripeClient) -> str:
    if conf.STRIPE_PRICE_ID:
        return conf.STRIPE_PRICE_ID

    lookup_key = 'fleetflow_per_vehicle_monthly'
    prices = client.prices.list(params={'lookup_keys': [lookup_key], 'active': True, 'limit': 1})
    if prices.data:
        return prices.data[0].id

    product = client.products.create(
        params={
            'name': 'FleetFlow per vehicle',
            'metadata': {'fleetflow': 'per_vehicle'},
        }
    )
    price = client.prices.create(
        params={
            'product': product.id,
            'unit_amount': conf.BILLING_UNIT_AMOUNT_CENTS,
            'currency': conf.BILLING_CURRENCY,
            'recurring': {'interval': 'month'},
            'lookup_key': lookup_key,
            'transfer_lookup_key': True,
        }
    )
    return price.id


def create_trial_checkout_session(
    owner: User,
    *,
    success_url: str,
    cancel_url: str,
) -> stripe.checkout.Session:
    client = get_stripe_client()
    customer_id = get_or_create_stripe_customer(owner)
    price_id = resolve_price_id(client)
    quantity = billable_vehicle_count(owner)

    return client.checkout.sessions.create(
        params={
            'mode': 'subscription',
            'customer': customer_id,
            'client_reference_id': str(owner.id),
            'payment_method_collection': 'always',
            'line_items': [{'price': price_id, 'quantity': quantity}],
            'subscription_data': {
                'trial_period_days': conf.BILLING_TRIAL_DAYS,
                'trial_settings': {
                    'end_behavior': {
                        'missing_payment_method': 'cancel',
                    },
                },
                'metadata': {'fleet_owner_id': str(owner.id)},
            },
            'success_url': success_url,
            'cancel_url': cancel_url,
            'metadata': {'fleet_owner_id': str(owner.id)},
        }
    )


def confirm_checkout_session(owner: User, session_id: str) -> User:
    """Apply subscription state from a completed Checkout session (webhook fallback)."""
    client = get_stripe_client()
    session = _as_dict(client.checkout.sessions.retrieve(session_id))
    session_owner_id = (session.get('metadata') or {}).get('fleet_owner_id') or session.get(
        'client_reference_id'
    )
    if not session_owner_id or str(session_owner_id) != str(owner.id):
        raise PermissionError('Checkout session does not belong to this fleet owner.')

    if session.get('status') != 'complete':
        raise ValueError('Checkout is not complete yet.')

    subscription_id = session.get('subscription')
    if not subscription_id:
        raise ValueError('Checkout session has no subscription.')

    subscription = client.subscriptions.retrieve(subscription_id)
    apply_subscription_state(owner, subscription)
    owner.refresh_from_db()
    return owner


def start_local_trial(owner: User) -> User:
    """Activate trial without Stripe (dev / billing not enforced)."""
    if owner.billing_status in (
        User.BillingStatus.TRIALING,
        User.BillingStatus.ACTIVE,
    ):
        return owner

    owner.billing_status = User.BillingStatus.TRIALING
    owner.subscription_plan = 'trial'
    owner.trial_ends_at = timezone.now() + timedelta(days=conf.BILLING_TRIAL_DAYS)
    owner.billing_quantity = billable_vehicle_count(owner)
    owner.save(
        update_fields=[
            'billing_status',
            'subscription_plan',
            'trial_ends_at',
            'billing_quantity',
            'updated_at',
        ]
    )
    return owner


def create_billing_portal_session(owner: User, *, return_url: str) -> stripe.billing_portal.Session:
    if not owner.stripe_customer_id:
        raise ValueError('Fleet owner has no Stripe customer yet.')
    client = get_stripe_client()
    return client.billing_portal.sessions.create(
        params={
            'customer': owner.stripe_customer_id,
            'return_url': return_url,
        }
    )


def sync_subscription_quantity(owner: User) -> None:
    if not owner.stripe_subscription_id:
        return

    client = get_stripe_client()
    quantity = billable_vehicle_count(owner)
    subscription = client.subscriptions.retrieve(owner.stripe_subscription_id)
    item_id = subscription['items']['data'][0]['id']

    client.subscription_items.update(
        item_id,
        params={'quantity': quantity},
    )
    owner.billing_quantity = quantity
    owner.save(update_fields=['billing_quantity', 'updated_at'])
    logger.info('Synced Stripe quantity=%s for fleet owner %s', quantity, owner.id)


def _as_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    return dict(obj)


def apply_subscription_state(owner: User, subscription: dict[str, Any] | Any) -> None:
    subscription = _as_dict(subscription)
    status = subscription.get('status')
    owner.stripe_subscription_id = subscription.get('id') or owner.stripe_subscription_id

    trial_end = subscription.get('trial_end')
    if trial_end:
        owner.trial_ends_at = datetime.fromtimestamp(trial_end, tz=dt_timezone.utc)

    if status == 'trialing':
        owner.billing_status = User.BillingStatus.TRIALING
        owner.subscription_plan = 'trial'
    elif status == 'active':
        owner.billing_status = User.BillingStatus.ACTIVE
        owner.subscription_plan = 'active'
    elif status in ('past_due', 'unpaid'):
        owner.billing_status = User.BillingStatus.PAST_DUE
        owner.subscription_plan = 'past_due'
    elif status == 'canceled':
        owner.billing_status = User.BillingStatus.CANCELED
        owner.subscription_plan = 'canceled'
    else:
        owner.billing_status = User.BillingStatus.INCOMPLETE
        owner.subscription_plan = status or 'incomplete'

    items = subscription.get('items', {}).get('data', [])
    if items:
        owner.billing_quantity = items[0].get('quantity') or owner.billing_quantity

    owner.save(
        update_fields=[
            'stripe_subscription_id',
            'trial_ends_at',
            'billing_status',
            'subscription_plan',
            'billing_quantity',
            'updated_at',
        ]
    )
