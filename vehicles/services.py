from fleetflow.background import run_after_commit
from fleetflow.followups import (
    refresh_fleet_owner_vehicle_count,
    sync_subscription_quantity_for_owner,
)


def queue_vehicle_write_followups(*, fleet_owner_id) -> None:
    run_after_commit(
        'refresh-vehicle-count',
        refresh_fleet_owner_vehicle_count,
        fleet_owner_id,
    )
    run_after_commit(
        'sync-subscription-quantity',
        sync_subscription_quantity_for_owner,
        fleet_owner_id,
    )
