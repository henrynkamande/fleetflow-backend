from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from oauth.models import Company, KYCDocument, User
from reports.finance_service import parse_period, previous_period, sum_trip_financials
from trips.models import Trip
from vehicles.models import Vehicle


def _money(value) -> float:
    from decimal import Decimal

    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value.quantize(Decimal('0.01')))
    return float(value)


def build_platform_overview(period: str | None) -> dict:
    start, end = parse_period(None, None, period)
    prev_start, prev_end = previous_period(start, end)
    companies_qs = Company.objects.all()
    total_companies = companies_qs.count()
    new_companies = companies_qs.filter(created_at__date__gte=start, created_at__date__lte=end).count()

    billing_breakdown = {status: 0 for status, _ in Company.BillingStatus.choices}
    for row in companies_qs.values('billing_status').annotate(count=Count('id')):
        billing_breakdown[row['billing_status']] = row['count']

    users_qs = User.objects.exclude(role=User.Role.PLATFORM_ADMIN)
    total_users = users_qs.count()
    active_users_qs = users_qs.filter(is_active=True)
    fleet_owners = active_users_qs.filter(role=User.Role.FLEET_OWNER).count()
    drivers_total = active_users_qs.filter(role=User.Role.DRIVER).count()
    drivers_verified = active_users_qs.filter(role=User.Role.DRIVER, is_verified=True).count()
    drivers_unverified = drivers_total - drivers_verified

    vehicles_total = Vehicle.objects.count()
    trips_total = Trip.objects.exclude(status=Trip.TripStatus.CANCELLED).count()
    trips_in_period = Trip.objects.filter(
        planned_departure_time__date__gte=start,
        planned_departure_time__date__lte=end,
    ).exclude(status=Trip.TripStatus.CANCELLED)
    trip_count = trips_in_period.count()

    all_period_trips = list(
        Trip.objects.filter(
            planned_departure_time__date__gte=start,
            planned_departure_time__date__lte=end,
        ).exclude(status=Trip.TripStatus.CANCELLED)
    )
    # Platform-wide trip financials (all companies)
    cur_fin = sum_trip_financials(all_period_trips)
    prev_fin = sum_trip_financials(
        list(
            Trip.objects.filter(
                planned_departure_time__date__gte=prev_start,
                planned_departure_time__date__lte=prev_end,
            ).exclude(status=Trip.TripStatus.CANCELLED)
        )
    )

    kyc_pending = KYCDocument.objects.filter(
        verification_status=KYCDocument.VerificationStatus.PENDING
    ).count()

    recent_signups = []
    for company in (
        companies_qs.select_related('owner')
        .order_by('-created_at')[:10]
    ):
        owner = company.owner
        recent_signups.append(
            {
                'id': str(company.id),
                'name': company.name,
                'owner_email': owner.email if owner else None,
                'subscription_plan': company.subscription_plan,
                'billing_status': company.billing_status,
                'created_at': company.created_at.isoformat(),
            }
        )

    from billing import conf as billing_conf

    unit_cents = billing_conf.BILLING_UNIT_AMOUNT_CENTS
    active_subs = companies_qs.filter(billing_status=Company.BillingStatus.ACTIVE)
    trialing_subs = companies_qs.filter(billing_status=Company.BillingStatus.TRIALING)
    pending_payment = companies_qs.filter(
        billing_status__in=[
            Company.BillingStatus.INCOMPLETE,
            Company.BillingStatus.PAST_DUE,
        ]
    )
    mrr_cents = 0
    for row in active_subs.values('billing_quantity'):
        qty = row.get('billing_quantity') or 0
        mrr_cents += int(qty) * unit_cents
    outstanding_cents = 0
    for row in pending_payment.values('billing_quantity'):
        qty = row.get('billing_quantity') or 0
        outstanding_cents += int(qty) * unit_cents

    recent_activity = []
    for user in User.objects.exclude(role=User.Role.PLATFORM_ADMIN).order_by('-date_joined')[:8]:
        recent_activity.append(
            {
                'type': 'user_joined',
                'at': user.date_joined.isoformat(),
                'title': user.get_full_name(),
                'detail': f'{user.role} · {user.email}',
            }
        )

    attention = []
    trial_cutoff = timezone.now() + timedelta(days=7)
    for company in companies_qs.select_related('owner').filter(
        Q(billing_status__in=[Company.BillingStatus.PAST_DUE, Company.BillingStatus.INCOMPLETE])
        | Q(billing_status=Company.BillingStatus.TRIALING, trial_ends_at__lte=trial_cutoff)
    )[:15]:
        attention.append(
            {
                'id': str(company.id),
                'name': company.name,
                'billing_status': company.billing_status,
                'trial_ends_at': company.trial_ends_at.isoformat() if company.trial_ends_at else None,
                'owner_email': company.owner.email if company.owner_id else None,
            }
        )

    return {
        'period': {'start': start.isoformat(), 'end': end.isoformat(), 'preset': period or '30d'},
        'companies': {
            'total': total_companies,
            'new_in_period': new_companies,
            'billing_breakdown': billing_breakdown,
        },
        'users': {
            'total': total_users,
            'fleet_owners': fleet_owners,
            'drivers': drivers_total,
            'drivers_verified': drivers_verified,
            'drivers_unverified': drivers_unverified,
        },
        'fleet_ops': {
            'vehicles': vehicles_total,
            'trips_total': trips_total,
            'trips_in_period': trip_count,
            'revenue': _money(cur_fin['revenue']),
            'expenses': _money(cur_fin['expenses']),
            'profit': _money(cur_fin['profit']),
            'revenue_previous': _money(prev_fin['revenue']),
        },
        'subscriptions': {
            'active': active_subs.count(),
            'trialing': trialing_subs.count(),
            'pending_payment': pending_payment.count(),
            'mrr': _money(mrr_cents / 100),
            'outstanding_revenue': _money(outstanding_cents / 100),
        },
        'recent_activity': recent_activity,
        'risk': {
            'kyc_pending': kyc_pending,
        },
        'recent_signups': recent_signups,
        'companies_needing_attention': attention,
    }


def annotate_companies_queryset(qs):
    return qs.annotate(
        driver_count=Count('users', filter=Q(users__role=User.Role.DRIVER), distinct=True),
        vehicle_count=Count('vehicles', distinct=True),
        trip_count=Count('trips', distinct=True),
    ).select_related('owner')


def serialize_company_list_item(company) -> dict:
    owner = company.owner
    return {
        'id': str(company.id),
        'name': company.name,
        'owner_email': owner.email if owner else None,
        'owner_name': owner.get_full_name() if owner else None,
        'subscription_plan': company.subscription_plan,
        'billing_status': company.billing_status,
        'driver_count': getattr(company, 'driver_count', 0),
        'vehicle_count': getattr(company, 'vehicle_count', 0),
        'trip_count': getattr(company, 'trip_count', 0),
        'created_at': company.created_at.isoformat(),
        'is_active': company.is_active,
    }
