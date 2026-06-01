from __future__ import annotations

import logging
from typing import Any

import stripe
from datetime import datetime, timedelta, timezone as dt_timezone

from django.utils import timezone

from oauth.models import Company, User

from . import conf

logger = logging.getLogger(__name__)


def get_stripe_client() -> stripe.StripeClient:
    if not conf.stripe_configured():
        raise RuntimeError('Stripe is not configured (missing STRIPE_SECRET_KEY).')
    return stripe.StripeClient(
        conf.STRIPE_SECRET_KEY,
        stripe_version=conf.STRIPE_API_VERSION,
    )


def billable_vehicle_count(company: Company) -> int:
    count = company.vehicles.count() if hasattr(company, 'vehicles') else 0
    return max(1, count)


def get_or_create_stripe_customer(company: Company, owner: User) -> str:
    if company.stripe_customer_id:
        return company.stripe_customer_id

    client = get_stripe_client()
    customer = client.customers.create(
        params={
            'email': owner.email,
            'name': company.name,
            'metadata': {
                'company_id': str(company.id),
                'owner_user_id': str(owner.id),
            },
        }
    )
    company.stripe_customer_id = customer.id
    company.save(update_fields=['stripe_customer_id', 'updated_at'])
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
    company: Company,
    owner: User,
    *,
    success_url: str,
    cancel_url: str,
) -> stripe.checkout.Session:
    client = get_stripe_client()
    customer_id = get_or_create_stripe_customer(company, owner)
    price_id = resolve_price_id(client)
    quantity = billable_vehicle_count(company)

    return client.checkout.sessions.create(
        params={
            'mode': 'subscription',
            'customer': customer_id,
            'client_reference_id': str(company.id),
            'line_items': [{'price': price_id, 'quantity': quantity}],
            'subscription_data': {
                'trial_period_days': conf.BILLING_TRIAL_DAYS,
                'metadata': {'company_id': str(company.id)},
            },
            'success_url': success_url,
            'cancel_url': cancel_url,
            'metadata': {'company_id': str(company.id)},
        }
    )


def confirm_checkout_session(company: Company, session_id: str) -> Company:
    """Apply subscription state from a completed Checkout session (webhook fallback)."""
    client = get_stripe_client()
    session = _as_dict(client.checkout.sessions.retrieve(session_id))
    session_company_id = (session.get('metadata') or {}).get('company_id') or session.get(
        'client_reference_id'
    )
    if not session_company_id or str(session_company_id) != str(company.id):
        raise PermissionError('Checkout session does not belong to this company.')

    if session.get('status') != 'complete':
        raise ValueError('Checkout is not complete yet.')

    subscription_id = session.get('subscription')
    if not subscription_id:
        raise ValueError('Checkout session has no subscription.')

    subscription = client.subscriptions.retrieve(subscription_id)
    apply_subscription_state(company, subscription)
    company.refresh_from_db()
    return company


def start_local_trial(company: Company) -> Company:
    """Activate trial without Stripe (dev / billing not enforced)."""
    if company.billing_status in (
        Company.BillingStatus.TRIALING,
        Company.BillingStatus.ACTIVE,
    ):
        return company

    company.billing_status = Company.BillingStatus.TRIALING
    company.subscription_plan = 'trial'
    company.trial_ends_at = timezone.now() + timedelta(days=conf.BILLING_TRIAL_DAYS)
    company.billing_quantity = billable_vehicle_count(company)
    company.save(
        update_fields=[
            'billing_status',
            'subscription_plan',
            'trial_ends_at',
            'billing_quantity',
            'updated_at',
        ]
    )
    return company


def create_billing_portal_session(company: Company, *, return_url: str) -> stripe.billing_portal.Session:
    if not company.stripe_customer_id:
        raise ValueError('Company has no Stripe customer yet.')
    client = get_stripe_client()
    return client.billing_portal.sessions.create(
        params={
            'customer': company.stripe_customer_id,
            'return_url': return_url,
        }
    )


def sync_subscription_quantity(company: Company) -> None:
    if not company.stripe_subscription_id:
        return

    client = get_stripe_client()
    quantity = billable_vehicle_count(company)
    subscription = client.subscriptions.retrieve(company.stripe_subscription_id)
    item_id = subscription['items']['data'][0]['id']

    client.subscription_items.update(
        item_id,
        params={'quantity': quantity},
    )
    company.billing_quantity = quantity
    company.save(update_fields=['billing_quantity', 'updated_at'])
    logger.info('Synced Stripe quantity=%s for company %s', quantity, company.id)


def _as_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    return dict(obj)


def apply_subscription_state(company: Company, subscription: dict[str, Any] | Any) -> None:
    subscription = _as_dict(subscription)
    status = subscription.get('status')
    company.stripe_subscription_id = subscription.get('id') or company.stripe_subscription_id

    trial_end = subscription.get('trial_end')
    if trial_end:
        company.trial_ends_at = datetime.fromtimestamp(trial_end, tz=dt_timezone.utc)

    if status == 'trialing':
        company.billing_status = Company.BillingStatus.TRIALING
        company.subscription_plan = 'trial'
    elif status == 'active':
        company.billing_status = Company.BillingStatus.ACTIVE
        company.subscription_plan = 'active'
    elif status in ('past_due', 'unpaid'):
        company.billing_status = Company.BillingStatus.PAST_DUE
        company.subscription_plan = 'past_due'
    elif status == 'canceled':
        company.billing_status = Company.BillingStatus.CANCELED
        company.subscription_plan = 'canceled'
    else:
        company.billing_status = Company.BillingStatus.INCOMPLETE
        company.subscription_plan = status or 'incomplete'

    items = subscription.get('items', {}).get('data', [])
    if items:
        company.billing_quantity = items[0].get('quantity') or company.billing_quantity

    company.save(
        update_fields=[
            'stripe_subscription_id',
            'trial_ends_at',
            'billing_status',
            'subscription_plan',
            'billing_quantity',
            'updated_at',
        ]
    )
