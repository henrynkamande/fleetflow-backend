"""Background follow-up work for request handlers."""

import logging

from oauth.models import FleetOwnerProfile, User
from vehicles.models import Vehicle

logger = logging.getLogger(__name__)


def refresh_fleet_owner_vehicle_count(fleet_owner_id) -> None:
    count = Vehicle.objects.filter(fleet_owner_id=fleet_owner_id).count()
    profile, _ = FleetOwnerProfile.objects.get_or_create(user_id=fleet_owner_id)
    profile.total_vehicles = count
    profile.save(update_fields=['total_vehicles'])


def refresh_fleet_owner_active_driver_count(fleet_owner_id) -> None:
    count = User.objects.filter(
        fleet_owner_id=fleet_owner_id,
        role=User.Role.DRIVER,
        is_active=True,
    ).count()
    profile, _ = FleetOwnerProfile.objects.get_or_create(user_id=fleet_owner_id)
    profile.active_drivers = count
    profile.save(update_fields=['active_drivers'])


def sync_subscription_quantity_for_owner(fleet_owner_id) -> None:
    from billing.stripe_service import sync_subscription_quantity

    owner = User.objects.filter(pk=fleet_owner_id, role=User.Role.FLEET_OWNER).first()
    if owner is None:
        logger.info('Skipped subscription quantity sync; fleet owner %s no longer exists', fleet_owner_id)
        return
    sync_subscription_quantity(owner)
