from __future__ import annotations

from datetime import date

from django.db.models import Sum

from billing import conf as billing_conf
from expenses.models import Expense
from oauth.models import User
from trips.models import Trip


def _decimal_sum(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def subscription_revenue_estimate(start: date, end: date) -> float:
    """
    Estimated subscription revenue for [start, end] from active billed seats.
    Uses monthly seat price prorated by calendar days in the range.
    """
    unit = billing_conf.BILLING_UNIT_AMOUNT_CENTS / 100
    days = (end - start).days + 1
    active = User.objects.filter(role=User.Role.FLEET_OWNER, billing_status=User.BillingStatus.ACTIVE).only(
        'billing_quantity'
    )
    monthly = sum((c.billing_quantity or 0) * unit for c in active)
    return monthly * (days / 30.0)


def platform_expenses_in_period(start: date, end: date) -> float:
    agg = Expense.objects.filter(
        scope=Expense.Scope.PLATFORM,
        expense_date__gte=start,
        expense_date__lte=end,
    ).aggregate(total=Sum('amount'))
    return _decimal_sum(agg['total'])


def platform_finance_for_period(start: date, end: date) -> dict:
    revenue = subscription_revenue_estimate(start, end)
    expenses = platform_expenses_in_period(start, end)
    return {
        'revenue': round(revenue, 2),
        'expenses': round(expenses, 2),
        'profit': round(revenue - expenses, 2),
    }


def fleet_operations_finance_for_period(start: date, end: date) -> dict:
    """
    Cross-fleet operational P&L, matching the fleet-owner dashboard source:
    trip revenue minus trip-level fuel, driver payment, toll, and other expenses.
    """
    trips = Trip.objects.exclude(status=Trip.TripStatus.CANCELLED).filter(
        planned_departure_time__date__gte=start,
        planned_departure_time__date__lte=end,
    )
    agg = trips.aggregate(
        revenue=Sum('revenue_amount'),
        fuel=Sum('fuel_cost'),
        driver_payment=Sum('driver_payment'),
        toll=Sum('toll_cost'),
        other=Sum('other_expenses'),
    )
    revenue = _decimal_sum(agg['revenue'])
    expenses = (
        _decimal_sum(agg['fuel'])
        + _decimal_sum(agg['driver_payment'])
        + _decimal_sum(agg['toll'])
        + _decimal_sum(agg['other'])
    )
    return {
        'revenue': round(revenue, 2),
        'expenses': round(expenses, 2),
        'profit': round(revenue - expenses, 2),
        'trip_count': trips.count(),
    }
