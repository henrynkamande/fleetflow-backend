from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from oauth.models import User


def _attention_owners():
    trial_cutoff = timezone.now() + timedelta(days=7)
    return (
        User.objects.filter(role=User.Role.FLEET_OWNER)
        .filter(
            Q(billing_status__in=[User.BillingStatus.PAST_DUE, User.BillingStatus.INCOMPLETE])
            | Q(billing_status=User.BillingStatus.TRIALING, trial_ends_at__lte=trial_cutoff)
        )
        .order_by('trial_ends_at', 'email')
    )


def collect_platform_notifications() -> list[dict]:
    """Derived alerts for platform admins (no separate notification store)."""
    items: list[dict] = []
    for owner in _attention_owners():
        status = owner.billing_status
        owner_name = owner.get_full_name() or owner.email
        if status == User.BillingStatus.TRIALING and owner.trial_ends_at:
            title = f'Trial ending soon: {owner_name}'
            detail = f'Trial ends {owner.trial_ends_at.date().isoformat()}'
            notif_type = 'trial_ending'
        elif status == User.BillingStatus.PAST_DUE:
            title = f'Past due billing: {owner_name}'
            detail = owner.email
            notif_type = 'billing_past_due'
        else:
            title = f'Payment action required: {owner_name}'
            detail = owner.email
            notif_type = 'billing_incomplete'

        items.append(
            {
                'id': f'fleet-owner-{owner.id}',
                'type': notif_type,
                'severity': 'warning',
                'title': title,
                'detail': detail,
                'at': (owner.updated_at or owner.date_joined).isoformat(),
                'href': f'/dashboard/admin/companies/{owner.id}',
            }
        )

    inactive_owners = User.objects.filter(
        role=User.Role.FLEET_OWNER,
        is_active=False,
    ).count()
    if inactive_owners:
        items.append(
            {
                'id': 'inactive-fleet-owners',
                'type': 'inactive_users',
                'severity': 'info',
                'title': f'{inactive_owners} inactive fleet owner account(s)',
                'detail': 'Accounts are disabled but still in the system.',
                'at': timezone.now().isoformat(),
                'href': '/dashboard/admin/users',
            }
        )

    return items


def paginate_notifications(page: int, page_size: int) -> dict:
    all_items = collect_platform_notifications()
    total = len(all_items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        'count': total,
        'page': page,
        'page_size': page_size,
        'results': all_items[start:end],
    }
