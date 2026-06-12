"""Fleet-owner workspace compatibility helpers.

The old schema used a separate Company table as the workspace boundary. The
new schema uses the fleet-owner User row directly.
"""
from __future__ import annotations

from .models import User


def company_members_queryset(fleet_owner: User, company=None):
    """Compatibility wrapper for old callers; companies were removed."""
    return User.objects.filter(fleet_owner=fleet_owner)


def resolve_user_company(user: User) -> User | None:
    """Return the fleet owner for old company-style callers."""
    if user.is_fleet_owner:
        return user
    return user.fleet_owner


def ensure_fleet_owner_company(user: User) -> User | None:
    """Compatibility wrapper: the fleet owner user is now the workspace."""
    return user if user.is_fleet_owner else None
