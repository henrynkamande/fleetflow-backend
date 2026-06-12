from .models import Trip


def fleet_owner_for_trip_user(user):
    if user.is_fleet_owner:
        return user
    return getattr(user, 'fleet_owner', None) or getattr(getattr(user, 'driver_profile', None), 'fleet_owner', None)


def build_trip_list_queryset(user, params):
    fleet_owner = fleet_owner_for_trip_user(user)
    if not fleet_owner:
        return fleet_owner, Trip.objects.none()

    trips = Trip.objects.filter(fleet_owner=fleet_owner)

    status_filter = params.get('status')
    vehicle_id = params.get('vehicle')
    driver_id = params.get('driver')
    is_flagged = params.get('is_flagged')
    date_from = params.get('date_from')
    date_to = params.get('date_to')

    if status_filter:
        trips = trips.filter(status=status_filter)
    if vehicle_id:
        trips = trips.filter(vehicle_id=vehicle_id)
    if driver_id:
        trips = trips.filter(driver_id=driver_id)
    if is_flagged is not None:
        trips = trips.filter(is_flagged=str(is_flagged).lower() == 'true')
    if date_from:
        trips = trips.filter(planned_departure_time__date__gte=date_from)
    if date_to:
        trips = trips.filter(planned_departure_time__date__lte=date_to)

    if user.is_driver:
        trips = trips.filter(driver=user.driver_profile)

    return fleet_owner, trips.select_related(
        'vehicle',
        'driver',
        'driver__user',
        'fleet_owner',
    ).order_by('-planned_departure_time')
