from django.db.models import Q, Sum
from django.core.cache import cache
from django.utils.crypto import salted_hmac
from django.utils import timezone

from .models import Trip


def build_trip_list_stats(queryset) -> dict:
    """Aggregate stats for the filtered trip queryset (not limited to the current page)."""
    sql, params = queryset.query.sql_with_params()
    cache_key = 'trip-list-stats:' + salted_hmac(
        'trip-list-stats',
        f'{sql}:{params}',
    ).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    today = timezone.localdate()
    active = queryset.filter(
        status__in=(Trip.TripStatus.ONGOING, Trip.TripStatus.DELAYED),
    ).count()
    completed_today = queryset.filter(
        status=Trip.TripStatus.COMPLETED,
    ).filter(
        Q(actual_arrival_time__date=today) | Q(updated_at__date=today),
    ).count()
    flagged = queryset.filter(Q(is_flagged=True) | Q(status=Trip.TripStatus.FLAGGED)).count()
    open_revenue = (
        queryset.filter(
            status__in=(
                Trip.TripStatus.PLANNED,
                Trip.TripStatus.ONGOING,
                Trip.TripStatus.DELAYED,
            ),
        ).aggregate(total=Sum('revenue_amount'))['total']
        or 0
    )
    stats = {
        'active': active,
        'completed_today': completed_today,
        'flagged': flagged,
        'open_revenue': str(open_revenue),
    }
    cache.set(cache_key, stats, 60)
    return stats
