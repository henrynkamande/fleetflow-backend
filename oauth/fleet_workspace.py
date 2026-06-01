"""Fleet-owner workspace helpers (optional formal company registration)."""
from __future__ import annotations

import uuid

from django.db.models import Q

from .models import Company, User


def _company_id_lookup_values(company_id) -> set[str]:
    """MongoDB may store UUIDs with or without dashes; match all common forms."""
    if company_id is None:
        return set()
    raw = str(company_id).strip()
    values = {raw, raw.lower(), raw.upper()}
    try:
        parsed = uuid.UUID(raw)
    except ValueError:
        try:
            parsed = uuid.UUID(hex=raw.replace('-', ''))
        except ValueError:
            return values
    values.add(str(parsed))
    values.add(str(parsed).replace('-', ''))
    values.add(str(parsed).replace('-', '').lower())
    return values


def company_members_queryset(fleet_owner: User, company: Company):
    """
    Users belonging to a fleet workspace for list/assignment APIs.
    Includes drivers invited by the owner when company FK ids differ (Mongo UUID formats).
    """
    company_q = Q()
    for cid in _company_id_lookup_values(company.id):
        company_q |= Q(company_id=cid)

    invited_q = Q(role=User.Role.DRIVER)
    owner_id_q = Q()
    for owner_id in _company_id_lookup_values(fleet_owner.pk):
        owner_id_q |= Q(invited_by_id=owner_id)
    invited_q &= owner_id_q
    return User.objects.filter(company_q | invited_q).distinct()


def resolve_user_company(user: User) -> Company | None:
    """Company row for API responses: FK, owned company, or auto workspace."""
    if user.is_fleet_owner:
        owned = Company.objects.filter(owner=user).order_by('created_at').first()
        if owned:
            if user.company_id != owned.id:
                user.company = owned
                user.save(update_fields=['company'])
            return owned
        if user.company_id:
            return user.company
        return None
    return user.company


def ensure_fleet_owner_company(user: User) -> Company | None:
    """
    Ensure the fleet owner has a company row for multi-tenant fleet data.
    Creates a minimal workspace company when none exists (informal fleets).
    """
    if not user.is_fleet_owner:
        return None

    owned = Company.objects.filter(owner=user).order_by('created_at').first()
    if owned:
        if user.company_id != owned.id:
            user.company = owned
            user.save(update_fields=['company'])
        return owned

    if user.company_id:
        return user.company

    name = (user.get_full_name() or '').strip()
    company_name = f"{name}'s Fleet" if name else 'My Fleet'

    company = Company.objects.create(
        owner=user,
        name=company_name,
        contact_email=user.email,
        contact_phone=user.phone_number or None,
    )
    user.company = company
    user.save(update_fields=['company'])

    if hasattr(user, 'fleet_owner_profile'):
        profile = user.fleet_owner_profile
        if not profile.company_name:
            profile.company_name = company_name
            profile.save(update_fields=['company_name'])

    return company
