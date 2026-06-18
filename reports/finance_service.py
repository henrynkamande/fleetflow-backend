"""
Trip-backed financial aggregations for fleet owner dashboards.
Single source of truth: trips (revenue + fuel/toll/other expenses).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Q
from django.utils import timezone

from trips.models import Trip

PAYMENT_MODE_LABELS = {
    Trip.DriverPaymentMode.MONTHLY_FIXED: 'Paid Monthly',
    Trip.DriverPaymentMode.WEEKLY_TRIPS: 'Weekly Payment',
    Trip.DriverPaymentMode.FIXED_DAILY: 'Fixed Pay Daily',
    Trip.DriverPaymentMode.PER_TRIP: 'Per Trip',
}


def _decimal(value) -> Decimal:
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money_float(value: Decimal | int | float) -> float:
    return float(_decimal(value).quantize(Decimal('0.01')))


def parse_period(
    date_from: str | None,
    date_to: str | None,
    period: str | None,
) -> tuple[date, date]:
    today = timezone.localdate()
    if date_from and date_to:
        return date.fromisoformat(date_from), date.fromisoformat(date_to)
    if period == 'ytd':
        return date(today.year, 1, 1), today
    if period == '90d':
        return today - timedelta(days=90), today
    if period == '7d':
        return today - timedelta(days=7), today
    if period == '30d':
        return today - timedelta(days=30), today
    # default: last 6 months
    start = today.replace(day=1)
    for _ in range(5):
        start = (start - timedelta(days=1)).replace(day=1)
    return start, today


def previous_period(start: date, end: date) -> tuple[date, date]:
    length = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    return prev_start, prev_end


@dataclass
class FinanceFilters:
    fleet_owner_id: Any
    start: date
    end: date
    vehicle_id: str | None = None
    driver_id: str | None = None


def base_trips(filters: FinanceFilters):
    qs = (
        Trip.objects.filter(fleet_owner_id=filters.fleet_owner_id)
        .exclude(status=Trip.TripStatus.CANCELLED)
        .select_related('vehicle', 'driver', 'driver__user', 'customer')
    )
    # Include trips scheduled in range, or logged in range (e.g. planned departure slightly in the future).
    qs = qs.filter(
        Q(
            planned_departure_time__date__gte=filters.start,
            planned_departure_time__date__lte=filters.end,
        )
        | Q(
            created_at__date__gte=filters.start,
            created_at__date__lte=filters.end,
        )
    )
    if filters.vehicle_id:
        qs = qs.filter(vehicle_id=filters.vehicle_id)
    if filters.driver_id:
        qs = qs.filter(driver_id=filters.driver_id)
    return qs.order_by('-planned_departure_time')


def trip_income_status(trip: Trip) -> str:
    if trip.income_status == Trip.IncomeStatus.PAID:
        return 'Paid'
    if trip.income_status == Trip.IncomeStatus.PARTIAL:
        return 'Partial'
    if trip.income_status == Trip.IncomeStatus.OVERDUE:
        return 'Overdue'
    return 'Pending'


def trip_expense_status(trip: Trip) -> str:
    if trip.status == Trip.TripStatus.COMPLETED:
        return 'paid'
    if trip.status == Trip.TripStatus.FLAGGED:
        return 'overdue'
    return 'pending'


def _period_key(dt: datetime, granularity: str) -> str:
    if granularity == 'yearly':
        return str(dt.year)
    if granularity == 'quarterly':
        q = (dt.month - 1) // 3 + 1
        return f'{dt.year}-Q{q}'
    return dt.strftime('%Y-%m')


def _period_label(key: str, granularity: str) -> str:
    if granularity == 'yearly':
        return key
    if granularity == 'quarterly':
        year, q = key.split('-Q')
        return f'Q{q} {year}'
    try:
        y, m = key.split('-')
        d = date(int(y), int(m), 1)
        return d.strftime('%b %Y')
    except ValueError:
        return key


def sum_trip_financials(trips) -> dict[str, Decimal]:
    revenue = Decimal('0')
    expenses = Decimal('0')
    for trip in trips:
        revenue += _decimal(trip.revenue_amount)
        expenses += (
            _decimal(trip.fuel_cost)
            + _decimal(trip.driver_payment)
            + _decimal(trip.toll_cost)
            + _decimal(trip.other_expenses)
        )
    profit = revenue - expenses
    return {'revenue': revenue, 'expenses': expenses, 'profit': profit}


def pct_change(current: Decimal, previous: Decimal) -> float | None:
    if previous == 0:
        return None if current == 0 else 100.0
    return float(((current - previous) / previous) * 100)


def build_driver_payout_modes(trips) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for trip in trips:
        mode = trip.driver_payment_mode or Trip.DriverPaymentMode.PER_TRIP
        if mode not in buckets:
            buckets[mode] = {
                'mode': mode,
                'label': PAYMENT_MODE_LABELS.get(mode, mode.replace('_', ' ').title()),
                'total': Decimal('0'),
                'trip_count': 0,
            }
        buckets[mode]['total'] += _decimal(trip.driver_payment)
        buckets[mode]['trip_count'] += 1

    ordered_modes = [
        Trip.DriverPaymentMode.MONTHLY_FIXED,
        Trip.DriverPaymentMode.WEEKLY_TRIPS,
        Trip.DriverPaymentMode.FIXED_DAILY,
        Trip.DriverPaymentMode.PER_TRIP,
    ]
    return [
        {
            'mode': mode,
            'label': buckets[mode]['label'],
            'total': _money_float(buckets[mode]['total']),
            'trip_count': buckets[mode]['trip_count'],
        }
        for mode in ordered_modes
        if mode in buckets
    ]


def build_summary(filters: FinanceFilters, prev_filters: FinanceFilters) -> dict:
    current_trips = list(base_trips(filters))
    prev_trips = list(base_trips(prev_filters))
    cur = sum_trip_financials(current_trips)
    prev = sum_trip_financials(prev_trips)

    collected = Decimal('0')
    outstanding = Decimal('0')
    overdue = Decimal('0')
    for trip in current_trips:
        amount = _decimal(trip.revenue_amount)
        status = trip_income_status(trip)
        if status == 'Paid':
            collected += amount
        elif status == 'Overdue':
            overdue += amount
        else:
            outstanding += amount

    return {
        'period': {'date_from': filters.start.isoformat(), 'date_to': filters.end.isoformat()},
        'trip_count': len(current_trips),
        'revenue_total': _money_float(cur['revenue']),
        'expenses_total': _money_float(cur['expenses']),
        'profit_total': _money_float(cur['profit']),
        'collected': _money_float(collected),
        'outstanding': _money_float(outstanding),
        'overdue': _money_float(overdue),
        'revenue_change_pct': pct_change(cur['revenue'], prev['revenue']),
        'expenses_change_pct': pct_change(cur['expenses'], prev['expenses']),
        'profit_change_pct': pct_change(cur['profit'], prev['profit']),
    }


def build_income_payload(filters: FinanceFilters, granularity: str = 'monthly') -> dict:
    trips = list(base_trips(filters))
    summary = build_summary(filters, FinanceFilters(
        fleet_owner_id=filters.fleet_owner_id,
        start=previous_period(filters.start, filters.end)[0],
        end=previous_period(filters.start, filters.end)[1],
        vehicle_id=filters.vehicle_id,
        driver_id=filters.driver_id,
    ))

    trend_buckets: dict[str, Decimal] = defaultdict(lambda: Decimal('0'))
    client_buckets: dict[str, Decimal] = defaultdict(lambda: Decimal('0'))

    records = []
    for trip in trips:
        amount = _decimal(trip.revenue_amount)
        client = (
            (trip.customer.name if trip.customer_id and trip.customer else '')
            or (trip.customer_name or '').strip()
            or 'Unassigned client'
        )
        client_buckets[client] += amount
        dt = trip.planned_departure_time
        if dt:
            trend_buckets[_period_key(dt, granularity)] += amount

        records.append({
            'invoice_id': trip.trip_number,
            'trip_id': str(trip.id),
            'trip_number': trip.trip_number,
            'client': client,
            'driver_name': trip.driver.user.full_name if trip.driver_id and trip.driver else None,
            'vehicle_registration': trip.vehicle.registration_number if trip.vehicle_id else None,
            'date': (trip.actual_arrival_time or trip.planned_departure_time).date().isoformat()
            if (trip.actual_arrival_time or trip.planned_departure_time)
            else filters.end.isoformat(),
            'amount': _money_float(amount),
            'status': trip_income_status(trip),
            'trip_status': trip.status,
        })

    trend = [
        {'period': _period_label(k, granularity), 'period_key': k, 'amount': _money_float(v)}
        for k, v in sorted(trend_buckets.items())
    ]

    top_clients = sorted(
        [{'name': name, 'total': _money_float(total)} for name, total in client_buckets.items()],
        key=lambda x: x['total'],
        reverse=True,
    )[:8]

    return {
        'summary': summary,
        'trend': trend,
        'top_clients': top_clients,
        'records': records,
    }


def build_expenses_payload(filters: FinanceFilters, granularity: str = 'monthly') -> dict:
    trips = list(base_trips(filters))
    prev_start, prev_end = previous_period(filters.start, filters.end)
    prev_filters = FinanceFilters(
        fleet_owner_id=filters.fleet_owner_id,
        start=prev_start,
        end=prev_end,
        vehicle_id=filters.vehicle_id,
        driver_id=filters.driver_id,
    )
    summary = build_summary(filters, prev_filters)

    category_totals = {
        'Fuel': Decimal('0'),
        'Driver payment': Decimal('0'),
        'Tolls': Decimal('0'),
        'Other': Decimal('0'),
    }
    trend_buckets: dict[str, Decimal] = defaultdict(lambda: Decimal('0'))
    records = []

    for trip in trips:
        fuel = _decimal(trip.fuel_cost)
        driver_payment = _decimal(trip.driver_payment)
        toll = _decimal(trip.toll_cost)
        other = _decimal(trip.other_expenses)
        total = fuel + driver_payment + toll + other
        category_totals['Fuel'] += fuel
        category_totals['Driver payment'] += driver_payment
        category_totals['Tolls'] += toll
        category_totals['Other'] += other

        dt = trip.planned_departure_time
        if dt:
            trend_buckets[_period_key(dt, granularity)] += total

        def add_line(category: str, amount: Decimal):
            if amount <= 0:
                return
            records.append({
                'id': f'{trip.trip_number}-{category.lower()}',
                'trip_id': str(trip.id),
                'trip_number': trip.trip_number,
                'category': category,
                'date': dt.date().isoformat() if dt else filters.end.isoformat(),
                'amount': _money_float(amount),
                'status': trip_expense_status(trip),
                'vendor': trip.vehicle.registration_number if trip.vehicle_id else None,
                'notes': trip.manager_notes or trip.cargo_description,
            })

        add_line('Fuel', fuel)
        add_line('Driver payment', driver_payment)
        add_line('Tolls', toll)
        add_line('Other', other)

    trend = [
        {'period': _period_label(k, granularity), 'period_key': k, 'total': _money_float(v)}
        for k, v in sorted(trend_buckets.items())
    ]

    by_category = [
        {'category': cat, 'total': _money_float(amt)}
        for cat, amt in category_totals.items()
        if amt > 0
    ]

    return {
        'summary': summary,
        'trend': trend,
        'by_category': by_category,
        'driver_payouts_by_mode': build_driver_payout_modes(trips),
        'records': records,
    }


def build_pl_payload(filters: FinanceFilters, granularity: str = 'monthly') -> dict:
    trips = list(base_trips(filters))
    prev_start, prev_end = previous_period(filters.start, filters.end)
    prev_filters = FinanceFilters(
        fleet_owner_id=filters.fleet_owner_id,
        start=prev_start,
        end=prev_end,
        vehicle_id=filters.vehicle_id,
        driver_id=filters.driver_id,
    )
    summary = build_summary(filters, prev_filters)

    trend_buckets: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {'revenue': Decimal('0'), 'expenses': Decimal('0')}
    )

    trip_revenue = Decimal('0')
    trip_expenses = Decimal('0')

    for trip in trips:
        rev = _decimal(trip.revenue_amount)
        exp = (
            _decimal(trip.fuel_cost)
            + _decimal(trip.driver_payment)
            + _decimal(trip.toll_cost)
            + _decimal(trip.other_expenses)
        )
        trip_revenue += rev
        trip_expenses += exp
        dt = trip.planned_departure_time
        if dt:
            key = _period_key(dt, granularity)
            trend_buckets[key]['revenue'] += rev
            trend_buckets[key]['expenses'] += exp

    trend = [
        {
            'period': _period_label(k, granularity),
            'period_key': k,
            'revenue': _money_float(v['revenue']),
            'expenses': _money_float(v['expenses']),
            'profit': _money_float(v['revenue'] - v['expenses']),
        }
        for k, v in sorted(trend_buckets.items())
    ]

    revenue_total = trip_revenue if trip_revenue > 0 else Decimal('1')
    fuel_sum = sum((_decimal(t.fuel_cost) for t in trips), Decimal('0'))
    driver_payment_sum = sum((_decimal(t.driver_payment) for t in trips), Decimal('0'))
    toll_sum = sum((_decimal(t.toll_cost) for t in trips), Decimal('0'))
    other_sum = sum((_decimal(t.other_expenses) for t in trips), Decimal('0'))

    def pct(part: Decimal) -> float:
        return _money_float(part / revenue_total * Decimal('100'))

    statement = [
        {'section': 'Income', 'account': 'Trip revenue', 'amount': _money_float(trip_revenue), 'percent_of_revenue': 100.0 if trip_revenue > 0 else 0.0},
        {'section': 'Expenses', 'account': 'Fuel', 'amount': _money_float(fuel_sum), 'percent_of_revenue': pct(fuel_sum)},
        {'section': 'Expenses', 'account': 'Driver payment', 'amount': _money_float(driver_payment_sum), 'percent_of_revenue': pct(driver_payment_sum)},
        {'section': 'Expenses', 'account': 'Tolls', 'amount': _money_float(toll_sum), 'percent_of_revenue': pct(toll_sum)},
        {'section': 'Expenses', 'account': 'Other trip costs', 'amount': _money_float(other_sum), 'percent_of_revenue': pct(other_sum)},
    ]

    return {
        'summary': summary,
        'trend': trend,
        'statement': statement,
        'driver_payouts_by_mode': build_driver_payout_modes(trips),
    }


_ACTIVE_TRIP_STATUSES = (
    Trip.TripStatus.ONGOING,
    Trip.TripStatus.PLANNED,
    Trip.TripStatus.DELAYED,
    Trip.TripStatus.FLAGGED,
)


def _trip_display_status(status: str) -> str:
    if status == Trip.TripStatus.DELAYED:
        return 'Delayed'
    if status == Trip.TripStatus.FLAGGED:
        return 'Flagged'
    return 'On Schedule'


def build_overview_payload(filters: FinanceFilters) -> dict:
    """Single payload for fleet owner dashboard (KPIs, active trips, P&L slice, leaderboards)."""
    prev_start, prev_end = previous_period(filters.start, filters.end)
    prev_filters = FinanceFilters(
        fleet_owner_id=filters.fleet_owner_id,
        start=prev_start,
        end=prev_end,
        vehicle_id=filters.vehicle_id,
        driver_id=filters.driver_id,
    )
    summary = build_summary(filters, prev_filters)
    current_trips = list(base_trips(filters))
    prev_trip_count = base_trips(prev_filters).count()

    active_trips_qs = Trip.objects.filter(fleet_owner_id=filters.fleet_owner_id, status__in=_ACTIVE_TRIP_STATUSES)
    active_trip_count = active_trips_qs.count()
    ongoing_qs = (
        active_trips_qs
        .select_related('vehicle', 'driver', 'driver__user')
        .order_by('-planned_departure_time')[:12]
    )
    ongoing_trips = []
    for trip in ongoing_qs:
        driver_name = trip.driver.user.full_name if trip.driver_id and trip.driver else 'Unassigned'
        vehicle_label = trip.vehicle.registration_number if trip.vehicle_id and trip.vehicle else 'No vehicle'
        ongoing_trips.append({
            'trip_id': trip.trip_number,
            'trip_uuid': str(trip.id),
            'driver_vehicle': f'{driver_name} • {vehicle_label}',
            'route': f'{trip.pickup_location} → {trip.destination}',
            'status': _trip_display_status(trip.status),
            'trip_status': trip.status,
        })

    fuel_sum = Decimal('0')
    driver_payment_sum = Decimal('0')
    toll_sum = Decimal('0')
    other_sum = Decimal('0')
    for trip in current_trips:
        fuel_sum += _decimal(trip.fuel_cost)
        driver_payment_sum += _decimal(trip.driver_payment)
        toll_sum += _decimal(trip.toll_cost)
        other_sum += _decimal(trip.other_expenses)

    expense_total = fuel_sum + driver_payment_sum + toll_sum + other_sum
    max_expense = max(fuel_sum, driver_payment_sum, toll_sum, other_sum, Decimal('1'))

    def expense_ratio(part: Decimal) -> float:
        return float((part / max_expense * Decimal('100')).quantize(Decimal('0.1')))

    expense_breakdown = [
        {'label': 'Fuel Costs', 'amount': _money_float(fuel_sum), 'ratio': expense_ratio(fuel_sum), 'tone': 'warning'},
        {'label': 'Driver Payments', 'amount': _money_float(driver_payment_sum), 'ratio': expense_ratio(driver_payment_sum), 'tone': 'negative'},
        {'label': 'Tolls', 'amount': _money_float(toll_sum), 'ratio': expense_ratio(toll_sum), 'tone': 'negative'},
        {
            'label': 'Maintenance & Other',
            'amount': _money_float(other_sum),
            'ratio': expense_ratio(other_sum),
            'tone': 'negative',
        },
    ]

    driver_stats: dict[Any, dict] = {}
    for trip in current_trips:
        if not trip.driver_id or not trip.driver:
            continue
        key = trip.driver_id
        if key not in driver_stats:
            on_time = float(trip.driver.on_time_percentage) if trip.driver else 0.0
            driver_stats[key] = {
                'driver_id': str(key),
                'name': trip.driver.user.full_name,
                'trip_count': 0,
                'on_time_pct': on_time,
            }
        driver_stats[key]['trip_count'] += 1

    top_drivers = sorted(
        driver_stats.values(),
        key=lambda d: (d['on_time_pct'], d['trip_count']),
        reverse=True,
    )[:3]

    vehicle_stats: dict[Any, dict] = {}
    for trip in current_trips:
        if not trip.vehicle_id or not trip.vehicle:
            continue
        key = trip.vehicle_id
        rev = _decimal(trip.revenue_amount)
        exp = (
            _decimal(trip.fuel_cost)
            + _decimal(trip.driver_payment)
            + _decimal(trip.toll_cost)
            + _decimal(trip.other_expenses)
        )
        profit = rev - exp
        dist = trip.distance_km or trip.planned_distance_km or 0
        if key not in vehicle_stats:
            vehicle_stats[key] = {
                'vehicle_id': str(key),
                'name': f'{trip.vehicle.make} {trip.vehicle.model}'.strip() or trip.vehicle.registration_number,
                'registration': trip.vehicle.registration_number,
                'distance_km': 0,
                'net_profit': Decimal('0'),
            }
        vehicle_stats[key]['distance_km'] += int(dist or 0)
        vehicle_stats[key]['net_profit'] += profit

    sorted_vehicles = sorted(
        vehicle_stats.values(),
        key=lambda v: v['net_profit'],
        reverse=True,
    )
    top_vehicles = sorted_vehicles[:3]
    for v in top_vehicles:
        v['net_profit'] = _money_float(v['net_profit'])
    most_profitable_vehicle = sorted_vehicles[0].copy() if sorted_vehicles else None
    worst_performing_vehicle = sorted_vehicles[-1].copy() if sorted_vehicles else None
    if most_profitable_vehicle:
        most_profitable_vehicle['net_profit'] = _money_float(most_profitable_vehicle['net_profit'])
    if worst_performing_vehicle:
        worst_performing_vehicle['net_profit'] = _money_float(worst_performing_vehicle['net_profit'])

    return {
        'summary': summary,
        'trip_count_change': summary['trip_count'] - prev_trip_count,
        'active_trip_count': active_trip_count,
        'ongoing_trips': ongoing_trips,
        'expense_breakdown': expense_breakdown,
        'driver_payouts_by_mode': build_driver_payout_modes(current_trips),
        'expense_total': _money_float(expense_total),
        'top_drivers': top_drivers,
        'top_vehicles': top_vehicles,
        'most_profitable_vehicle': most_profitable_vehicle,
        'worst_performing_vehicle': worst_performing_vehicle,
    }
