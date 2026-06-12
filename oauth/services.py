from fleetflow.background import run_after_commit
from fleetflow.followups import refresh_fleet_owner_active_driver_count


def queue_driver_write_followups(*, fleet_owner_id) -> None:
    run_after_commit(
        'refresh-active-driver-count',
        refresh_fleet_owner_active_driver_count,
        fleet_owner_id,
    )
