import os

from django.conf import settings


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.lower() in ('true', '1', 'yes')


STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# Stripe Price ID for per-vehicle monthly unit (create in Dashboard or via API).
STRIPE_PRICE_ID = os.environ.get('STRIPE_PRICE_ID', '')

BILLING_TRIAL_DAYS = int(os.environ.get('BILLING_TRIAL_DAYS', '7'))
BILLING_CURRENCY = os.environ.get('BILLING_CURRENCY', 'usd').lower()
# Display / fallback unit amount in cents when STRIPE_PRICE_ID is not set (500 KES ≈ $4 USD).
BILLING_UNIT_AMOUNT_CENTS = int(os.environ.get('BILLING_UNIT_AMOUNT_CENTS', '400'))

BILLING_ENFORCE = _env_bool('BILLING_ENFORCE', default=True)

STRIPE_API_VERSION = os.environ.get('STRIPE_API_VERSION', '2026-04-22.dahlia')


def stripe_configured() -> bool:
    return bool(STRIPE_SECRET_KEY and STRIPE_SECRET_KEY.startswith('sk_'))


def frontend_base_url() -> str:
    return getattr(settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')
