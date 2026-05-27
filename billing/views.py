import logging

import stripe
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from oauth.fleet_workspace import ensure_fleet_owner_company
from oauth.models import Company

from . import conf
from .access import company_has_platform_access, company_requires_checkout
from .stripe_service import (
    billable_vehicle_count,
    confirm_checkout_session,
    create_billing_portal_session,
    create_trial_checkout_session,
)

stripe_configured = conf.stripe_configured
from .webhook_handlers import dispatch_stripe_event

logger = logging.getLogger(__name__)


def _public_pricing_payload() -> dict:
    amount_usd = conf.BILLING_UNIT_AMOUNT_CENTS / 100
    return {
        'currency': conf.BILLING_CURRENCY,
        'unit_amount_cents': conf.BILLING_UNIT_AMOUNT_CENTS,
        'unit_amount_display': f'${amount_usd:.2f}',
        'per_vehicle_label': f'${amount_usd:.0f} USD per vehicle / month',
        'trial_days': conf.BILLING_TRIAL_DAYS,
        'note': 'Converted from KES 500 per vehicle at approximately 4 USD.',
    }


@api_view(['GET'])
@permission_classes([AllowAny])
def billing_config(request):
    return Response(
        {
            'stripe_publishable_key': conf.STRIPE_PUBLISHABLE_KEY if stripe_configured() else '',
            'stripe_configured': stripe_configured(),
            'billing_enforced': conf.BILLING_ENFORCE and stripe_configured(),
            'pricing': _public_pricing_payload(),
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def billing_status(request):
    user = request.user
    if not user.is_fleet_owner:
        return Response({'detail': 'Only fleet owners manage billing.'}, status=status.HTTP_403_FORBIDDEN)

    company = ensure_fleet_owner_company(user)
    if not company:
        return Response({'detail': 'No company workspace.'}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            'billing_status': company.billing_status,
            'subscription_plan': company.subscription_plan,
            'trial_ends_at': company.trial_ends_at,
            'vehicle_count': billable_vehicle_count(company),
            'billing_quantity': company.billing_quantity,
            'has_access': company_has_platform_access(company),
            'requires_checkout': company_requires_checkout(company),
            'stripe_configured': stripe_configured(),
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):
    user = request.user
    if not user.is_fleet_owner:
        return Response({'detail': 'Only fleet owners can start a trial.'}, status=status.HTTP_403_FORBIDDEN)
    if not stripe_configured():
        return Response({'detail': 'Billing is not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    company = ensure_fleet_owner_company(user)
    if not company:
        return Response({'detail': 'No company workspace.'}, status=status.HTTP_400_BAD_REQUEST)

    success_url = request.data.get('success_url') or f'{conf.frontend_base_url()}/onboarding/billing-success?session_id={{CHECKOUT_SESSION_ID}}'
    cancel_url = request.data.get('cancel_url') or f'{conf.frontend_base_url()}/onboarding/start-trial'

    try:
        session = create_trial_checkout_session(
            company,
            user,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except Exception as exc:
        logger.exception('Failed to create Stripe Checkout session')
        return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    return Response({'checkout_url': session.url, 'session_id': session.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_checkout(request):
    user = request.user
    if not user.is_fleet_owner:
        return Response({'detail': 'Only fleet owners can confirm checkout.'}, status=status.HTTP_403_FORBIDDEN)
    if not stripe_configured():
        return Response({'detail': 'Billing is not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    session_id = (request.data.get('session_id') or '').strip()
    if not session_id:
        return Response({'detail': 'session_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    company = ensure_fleet_owner_company(user)
    if not company:
        return Response({'detail': 'No company workspace.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        company = confirm_checkout_session(company, session_id)
    except PermissionError:
        return Response({'detail': 'Invalid checkout session.'}, status=status.HTTP_403_FORBIDDEN)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        logger.exception('Failed to confirm Stripe Checkout session')
        return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    return Response(
        {
            'billing_status': company.billing_status,
            'has_access': company_has_platform_access(company),
            'requires_checkout': company_requires_checkout(company),
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_portal_session(request):
    user = request.user
    if not user.is_fleet_owner:
        return Response({'detail': 'Only fleet owners manage billing.'}, status=status.HTTP_403_FORBIDDEN)
    if not stripe_configured():
        return Response({'detail': 'Billing is not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    company = ensure_fleet_owner_company(user)
    if not company or not company.stripe_customer_id:
        return Response({'detail': 'Complete trial checkout first.'}, status=status.HTTP_400_BAD_REQUEST)

    return_url = request.data.get('return_url') or f'{conf.frontend_base_url()}/dashboard/settings'
    try:
        portal = create_billing_portal_session(company, return_url=return_url)
    except Exception as exc:
        logger.exception('Failed to create billing portal session')
        return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    return Response({'portal_url': portal.url})


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):
    if not conf.STRIPE_WEBHOOK_SECRET:
        return Response({'detail': 'Webhook secret not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, conf.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.warning('Stripe webhook: invalid payload')
        return Response({'detail': 'Invalid payload'}, status=status.HTTP_400_BAD_REQUEST)
    except stripe.error.SignatureVerificationError:
        logger.warning(
            'Stripe webhook: invalid signature (use whsec from `stripe listen` for local forwarding, '
            'or the Dashboard signing secret for that endpoint — they must match the sender)'
        )
        return Response({'detail': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        dispatch_stripe_event(event)
    except Exception:
        logger.exception('Stripe webhook handler failed for %s', event.get('type'))
        return Response({'detail': 'Handler error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'received': True})
