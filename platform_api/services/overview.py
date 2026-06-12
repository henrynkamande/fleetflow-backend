from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import Count

from oauth.models import User
from platform_api.services.platform_finance import (
    fleet_operations_finance_for_period,
    platform_finance_for_period,
)
from vehicles.models import Vehicle
from reports.finance_service import parse_period, previous_period


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
    owners_qs = User.objects.filter(role=User.Role.FLEET_OWNER)
    total_companies = owners_qs.count()
    new_companies = owners_qs.filter(date_joined__date__gte=start, date_joined__date__lte=end).count()

    billing_breakdown = {status: 0 for status, _ in User.BillingStatus.choices}
    for row in owners_qs.values('billing_status').annotate(count=Count('id')):
        billing_breakdown[row['billing_status']] = row['count']

    active_users_qs = User.objects.exclude(role=User.Role.PLATFORM_ADMIN).filter(is_active=True)
    fleet_owners = active_users_qs.filter(role=User.Role.FLEET_OWNER).count()
    drivers_total = active_users_qs.filter(role=User.Role.DRIVER).count()
    drivers_verified = active_users_qs.filter(role=User.Role.DRIVER, is_verified=True).count()
    drivers_unverified = drivers_total - drivers_verified

    vehicles_total = Vehicle.objects.count()

    cur_fin = fleet_operations_finance_for_period(start, end)
    prev_fin = fleet_operations_finance_for_period(prev_start, prev_end)
    cur_platform_fin = platform_finance_for_period(start, end)

    from billing import conf as billing_conf

    unit_cents = billing_conf.BILLING_UNIT_AMOUNT_CENTS
    active_subs = owners_qs.filter(billing_status=User.BillingStatus.ACTIVE)
    trialing_subs = owners_qs.filter(billing_status=User.BillingStatus.TRIALING)
    pending_payment = owners_qs.filter(
        billing_status__in=[
            User.BillingStatus.INCOMPLETE,
            User.BillingStatus.PAST_DUE,
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

    return {
        'period': {'start': start.isoformat(), 'end': end.isoformat(), 'preset': period or '30d'},
        'companies': {
            'total': total_companies,
            'new_in_period': new_companies,
            'billing_breakdown': billing_breakdown,
        },
        'users': {
            'total': fleet_owners + drivers_total,
            'fleet_owners': fleet_owners,
            'drivers': drivers_total,
            'drivers_verified': drivers_verified,
            'drivers_unverified': drivers_unverified,
        },
        'fleet_ops': {
            'vehicles': vehicles_total,
            'revenue': _money(cur_fin['revenue']),
            'expenses': _money(cur_fin['expenses']),
            'profit': _money(cur_fin['profit']),
            'revenue_previous': _money(prev_fin['revenue']),
            'trip_count': cur_fin['trip_count'],
            'platform_system_expenses': _money(cur_platform_fin['expenses']),
            'subscription_revenue_estimate': _money(cur_platform_fin['revenue']),
        },
        'subscriptions': {
            'active': active_subs.count(),
            'trialing': trialing_subs.count(),
            'pending_payment': pending_payment.count(),
            'mrr': _money(mrr_cents / 100),
            'outstanding_revenue': _money(outstanding_cents / 100),
        },
    }


def paginate_recent_signups(page: int, page_size: int) -> dict:
    qs = User.objects.filter(role=User.Role.FLEET_OWNER).order_by('-date_joined')
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    results = []
    for owner in page_obj.object_list:
        results.append(
            {
                'id': str(owner.id),
                'name': owner.get_full_name(),
                'owner_email': owner.email if owner else None,
                'subscription_plan': owner.subscription_plan,
                'billing_status': owner.billing_status,
                'created_at': owner.date_joined.isoformat(),
            }
        )
    return {
        'count': paginator.count,
        'page': page,
        'page_size': page_size,
        'results': results,
    }


def paginate_recent_activity(page: int, page_size: int) -> dict:
    qs = User.objects.exclude(role=User.Role.PLATFORM_ADMIN).order_by('-date_joined')
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    results = []
    for user in page_obj.object_list:
        name = (user.get_full_name() or '').strip()
        if not name:
            name = user.first_name or user.last_name or 'User'
        results.append(
            {
                'id': str(user.id),
                'type': 'user_joined',
                'at': user.date_joined.isoformat(),
                'title': name,
                'role': user.role,
            }
        )
    return {
        'count': paginator.count,
        'page': page,
        'page_size': page_size,
        'results': results,
    }


def annotate_companies_queryset(qs):
    return qs.annotate(
        driver_count=Count('managed_users', distinct=True),
        vehicle_count=Count('vehicles', distinct=True),
        trip_count=Count('trips', distinct=True),
    )


def serialize_company_list_item(owner) -> dict:
    return {
        'id': str(owner.id),
        'name': owner.get_full_name(),
        'owner_email': owner.email if owner else None,
        'owner_name': owner.get_full_name() if owner else None,
        'subscription_plan': owner.subscription_plan,
        'billing_status': owner.billing_status,
        'driver_count': getattr(owner, 'driver_count', 0),
        'vehicle_count': getattr(owner, 'vehicle_count', 0),
        'trip_count': getattr(owner, 'trip_count', 0),
        'created_at': owner.date_joined.isoformat(),
        'is_active': owner.is_active,
    }
