"""Fleet-owner workspace helpers (optional formal company registration)."""
from __future__ import annotations

from .models import Company, User


def resolve_user_company(user: User) -> Company | None:
    """Company row for API responses: FK, owned company, or auto workspace."""
    if user.is_fleet_owner:
        if user.company_id:
            owned = Company.objects.filter(owner=user).first()
            if owned and user.company_id != owned.id:
                user.company = owned
                user.save(update_fields=['company'])
                return owned
            return user.company
        return Company.objects.filter(owner=user).first()
    return user.company


def ensure_fleet_owner_company(user: User) -> Company | None:
    """
    Ensure the fleet owner has a company row for multi-tenant fleet data.
    Creates a minimal workspace company when none exists (informal fleets).
    """
    if not user.is_fleet_owner:
        return None
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
