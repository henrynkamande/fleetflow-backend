from django.core.paginator import Paginator
from django.core.cache import cache
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billing import conf as billing_conf
from expenses.models import Expense
from oauth.models import User
from oauth.serializers import CompanySerializer, UserListSerializer, UserSerializer
from platform_api.permissions import IsPlatformAdmin
from platform_api.serializers_expenses import PlatformSystemExpenseSerializer
from platform_api.services.notifications import paginate_notifications
from platform_api.services.overview import (
    annotate_companies_queryset,
    build_platform_overview,
    paginate_recent_activity,
    paginate_recent_signups,
    serialize_company_list_item,
)
from reports.finance_service import FinanceFilters, build_summary, parse_period, previous_period
from trips.models import Trip
from vehicles.models import Vehicle


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_overview(request):
    period = request.query_params.get('period', '30d')
    cache_key = f'platform-overview:{period}'
    data = cache.get(cache_key)
    if data is None:
        data = build_platform_overview(period)
        cache.set(cache_key, data, 60)
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_overview_signups(request):
    page = max(1, int(request.query_params.get('page', 1)))
    page_size = min(50, max(1, int(request.query_params.get('page_size', 10))))
    return Response(paginate_recent_signups(page, page_size))


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_overview_activity(request):
    page = max(1, int(request.query_params.get('page', 1)))
    page_size = min(50, max(1, int(request.query_params.get('page_size', 10))))
    return Response(paginate_recent_activity(page, page_size))


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_notifications(request):
    page = max(1, int(request.query_params.get('page', 1)))
    page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))
    return Response(paginate_notifications(page, page_size))


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_companies(request):
    qs = annotate_companies_queryset(User.objects.filter(role=User.Role.FLEET_OWNER).order_by('-date_joined'))
    search = (request.query_params.get('search') or '').strip()
    if search:
        qs = qs.filter(
            Q(email__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )
    billing = request.query_params.get('billing_status')
    if billing:
        qs = qs.filter(billing_status=billing)

    page = max(1, int(request.query_params.get('page', 1)))
    page_size = min(100, max(1, int(request.query_params.get('page_size', 25))))
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    return Response(
        {
            'count': paginator.count,
            'page': page,
            'page_size': page_size,
            'results': [serialize_company_list_item(c) for c in page_obj.object_list],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_company_detail(request, company_id):
    owner = get_object_or_404(
        annotate_companies_queryset(User.objects.filter(role=User.Role.FLEET_OWNER)),
        pk=company_id,
    )
    period = request.query_params.get('period', '30d')
    start, end = parse_period(None, None, period)
    filters = FinanceFilters(fleet_owner_id=owner.id, start=start, end=end)
    prev_start, prev_end = previous_period(start, end)
    prev_filters = FinanceFilters(fleet_owner_id=owner.id, start=prev_start, end=prev_end)
    finance = build_summary(filters, prev_filters)

    drivers = User.objects.filter(fleet_owner=owner, role=User.Role.DRIVER).order_by('-date_joined')[:50]
    vehicles = Vehicle.objects.filter(fleet_owner=owner).order_by('-created_at')[:50]
    recent_trips = (
        Trip.objects.filter(fleet_owner=owner)
        .select_related('vehicle', 'driver', 'driver__user')
        .order_by('-planned_departure_time')[:20]
    )

    trip_rows = []
    for trip in recent_trips:
        trip_rows.append(
            {
                'id': str(trip.id),
                'trip_number': trip.trip_number,
                'status': trip.status,
                'pickup_location': trip.pickup_location,
                'destination': trip.destination,
                'planned_departure_time': trip.planned_departure_time.isoformat(),
                'revenue_amount': float(trip.revenue_amount or 0),
            }
        )

    return Response(
        {
            'company': CompanySerializer(owner, context={'request': request}).data,
            'counts': {
                'drivers': getattr(owner, 'driver_count', 0),
                'vehicles': getattr(owner, 'vehicle_count', 0),
                'trips': getattr(owner, 'trip_count', 0),
            },
            'finance_summary': finance,
            'drivers': UserSerializer(drivers, many=True, context={'request': request}).data,
            'vehicles': [
                {
                    'id': str(v.id),
                    'registration_number': v.registration_number,
                    'make': v.make,
                    'model': v.model,
                    'status': v.status,
                }
                for v in vehicles
            ],
            'recent_trips': trip_rows,
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_users(request):
    qs = User.objects.exclude(role=User.Role.PLATFORM_ADMIN).order_by('-date_joined')
    role = request.query_params.get('role')
    if role:
        qs = qs.filter(role=role)
    is_active_filter = request.query_params.get('is_active')
    if is_active_filter is not None:
        qs = qs.filter(is_active=is_active_filter.lower() in ('true', '1', 'yes'))
    search = (request.query_params.get('search') or '').strip()
    if search:
        qs = qs.filter(Q(email__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search))

    page = max(1, int(request.query_params.get('page', 1)))
    page_size = min(100, max(1, int(request.query_params.get('page_size', 25))))
    paginator = Paginator(qs.select_related('fleet_owner', 'driver_profile'), page_size)
    page_obj = paginator.get_page(page)

    results = []
    for user in page_obj.object_list:
        row = UserListSerializer(user, context={'request': request}).data
        results.append(row)

    return Response(
        {
            'count': paginator.count,
            'page': page,
            'page_size': page_size,
            'results': results,
        }
    )


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_user_detail(request, user_id):
    user = get_object_or_404(
        User.objects.exclude(role=User.Role.PLATFORM_ADMIN).select_related('fleet_owner', 'driver_profile'),
        pk=user_id,
    )
    if request.method == 'GET':
        return Response(UserSerializer(user, context={'request': request}).data)

    is_active = request.data.get('is_active')
    if is_active is None:
        return Response({'detail': 'is_active is required.'}, status=status.HTTP_400_BAD_REQUEST)
    user.is_active = bool(is_active)
    user.save(update_fields=['is_active', 'updated_at'])
    return Response(UserSerializer(user, context={'request': request}).data)


PLATFORM_VEHICLE_LIST_FIELDS = {
    'id',
    'vehicle_name',
    'registration_number',
    'vehicle_type',
    'status',
    'company_id',
    'company_name',
    'assigned_owner_name',
    'assigned_owner_email',
    'created_at',
}


def _selected_fields(request, allowed_fields: set[str]):
    raw_fields = request.query_params.get('fields')
    if not raw_fields:
        return None
    selected = {field.strip() for field in raw_fields.split(',') if field.strip()}
    selected &= allowed_fields
    return selected or None


def _filter_fields(row: dict, selected_fields):
    if not selected_fields:
        return row
    return {key: value for key, value in row.items() if key in selected_fields}


def _serialize_platform_vehicle(vehicle: Vehicle, *, fields=None) -> dict:
    owner = vehicle.fleet_owner
    vehicle_name = f'{vehicle.make} {vehicle.model}'.strip() or vehicle.registration_number
    row = {
        'id': str(vehicle.id),
        'vehicle_name': vehicle_name,
        'registration_number': vehicle.registration_number,
        'vehicle_type': vehicle.vehicle_type,
        'status': vehicle.status,
        'company_id': str(owner.id) if owner else None,
        'company_name': owner.get_full_name() if owner else None,
        'assigned_owner_name': owner.get_full_name() if owner else None,
        'assigned_owner_email': owner.email if owner else None,
        'created_at': vehicle.created_at.isoformat(),
    }
    return _filter_fields(row, fields)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_vehicles(request):
    qs = Vehicle.objects.select_related('fleet_owner').order_by('-created_at')
    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)
    vehicle_type = request.query_params.get('vehicle_type')
    if vehicle_type:
        qs = qs.filter(vehicle_type=vehicle_type)
    company_id = request.query_params.get('company_id')
    if company_id:
        qs = qs.filter(fleet_owner_id=company_id)
    owner_id = request.query_params.get('owner_id')
    if owner_id:
        qs = qs.filter(fleet_owner_id=owner_id)
    is_active_filter = request.query_params.get('is_active')
    if is_active_filter is not None:
        qs = qs.filter(is_active=is_active_filter.lower() in ('true', '1', 'yes'))
    search = (request.query_params.get('search') or '').strip()
    if search:
        qs = qs.filter(
            Q(registration_number__icontains=search)
            | Q(make__icontains=search)
            | Q(model__icontains=search)
            | Q(fleet_owner__first_name__icontains=search)
            | Q(fleet_owner__last_name__icontains=search)
            | Q(fleet_owner__email__icontains=search)
        )

    stats = {
        'total': Vehicle.objects.count(),
        'active': Vehicle.objects.filter(status=Vehicle.VehicleStatus.ACTIVE).count(),
        'inactive': Vehicle.objects.filter(status=Vehicle.VehicleStatus.INACTIVE).count(),
        'maintenance': Vehicle.objects.filter(
            status=Vehicle.VehicleStatus.UNDER_MAINTENANCE
        ).count(),
    }

    page = max(1, int(request.query_params.get('page', 1)))
    page_size = min(100, max(1, int(request.query_params.get('page_size', 25))))
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    selected_fields = _selected_fields(request, PLATFORM_VEHICLE_LIST_FIELDS)

    return Response(
        {
            'count': paginator.count,
            'page': page,
            'page_size': page_size,
            'stats': stats,
            'results': [_serialize_platform_vehicle(v, fields=selected_fields) for v in page_obj.object_list],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_vehicle_detail(request, vehicle_id):
    vehicle = get_object_or_404(
        Vehicle.objects.select_related('fleet_owner'),
        pk=vehicle_id,
    )
    return Response(_serialize_platform_vehicle(vehicle))


def _subscription_row(owner: User) -> dict:
    unit = billing_conf.BILLING_UNIT_AMOUNT_CENTS / 100
    qty = owner.billing_quantity or 0
    monthly = float(qty * unit)
    billing = owner.billing_status
    payment_status = 'Paid' if billing == User.BillingStatus.ACTIVE else 'Due'
    if billing in (User.BillingStatus.TRIALING, User.BillingStatus.NOT_STARTED):
        payment_status = 'N/A'
    elif billing == User.BillingStatus.CANCELED:
        payment_status = 'Cancelled'
    trial_status = 'Active' if billing == User.BillingStatus.TRIALING else 'No'
    renewal = owner.trial_ends_at.isoformat() if owner.trial_ends_at else None
    return {
        'company_id': str(owner.id),
        'company_name': owner.get_full_name(),
        'subscription_plan': owner.subscription_plan,
        'billing_status': billing,
        'payment_status': payment_status,
        'amount_paid': monthly if billing == User.BillingStatus.ACTIVE else 0,
        'amount_due': monthly if billing in (User.BillingStatus.PAST_DUE, User.BillingStatus.INCOMPLETE) else 0,
        'renewal_date': renewal,
        'trial_status': trial_status,
        'vehicle_count': qty,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_subscriptions(request):
    qs = User.objects.filter(role=User.Role.FLEET_OWNER).order_by('first_name', 'last_name')
    billing = request.query_params.get('billing_status')
    if billing:
        qs = qs.filter(billing_status=billing)
    search = (request.query_params.get('search') or '').strip()
    if search:
        qs = qs.filter(Q(email__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search))

    unit = billing_conf.BILLING_UNIT_AMOUNT_CENTS
    active_qs = User.objects.filter(role=User.Role.FLEET_OWNER, billing_status=User.BillingStatus.ACTIVE)
    mrr_cents = sum((c.billing_quantity or 0) * unit for c in active_qs.only('billing_quantity'))
    outstanding_qs = User.objects.filter(
        role=User.Role.FLEET_OWNER,
        billing_status__in=[User.BillingStatus.PAST_DUE, User.BillingStatus.INCOMPLETE]
    )
    outstanding_cents = sum((c.billing_quantity or 0) * unit for c in outstanding_qs.only('billing_quantity'))

    summary = {
        'active': active_qs.count(),
        'trialing': User.objects.filter(role=User.Role.FLEET_OWNER, billing_status=User.BillingStatus.TRIALING).count(),
        'pending_payment': outstanding_qs.count(),
        'mrr': mrr_cents / 100,
        'outstanding_revenue': outstanding_cents / 100,
    }

    page = max(1, int(request.query_params.get('page', 1)))
    page_size = min(100, max(1, int(request.query_params.get('page_size', 25))))
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    return Response(
        {
            'count': paginator.count,
            'page': page,
            'page_size': page_size,
            'summary': summary,
            'results': [_subscription_row(c) for c in page_obj.object_list],
        }
    )


def _expense_summary():
    now = timezone.now().date()
    month_start = now.replace(day=1)
    year_start = now.replace(month=1, day=1)
    platform_qs = Expense.objects.filter(scope=Expense.Scope.PLATFORM)
    agg = platform_qs.aggregate(total=Sum('amount'))
    month_agg = platform_qs.filter(expense_date__gte=month_start).aggregate(
        total=Sum('amount')
    )
    year_agg = platform_qs.filter(expense_date__gte=year_start).aggregate(
        total=Sum('amount')
    )
    total = float(agg['total'] or 0)
    year_total = float(year_agg['total'] or 0)
    months_elapsed = max(1, now.month)
    return {
        'total_expenses': total,
        'expenses_this_month': float(month_agg['total'] or 0),
        'expenses_this_year': year_total,
        'average_monthly_expense': year_total / months_elapsed,
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_system_expenses(request):
    if request.method == 'POST':
        serializer = PlatformSystemExpenseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expense = serializer.save(created_by=request.user)
        return Response(
            PlatformSystemExpenseSerializer(expense).data,
            status=status.HTTP_201_CREATED,
        )

    qs = Expense.objects.filter(scope=Expense.Scope.PLATFORM).select_related('created_by').order_by('-expense_date')
    category = request.query_params.get('category')
    if category:
        qs = qs.filter(category=category)
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    if date_from:
        qs = qs.filter(expense_date__gte=date_from)
    if date_to:
        qs = qs.filter(expense_date__lte=date_to)
    search = (request.query_params.get('search') or '').strip()
    if search:
        qs = qs.filter(Q(description__icontains=search) | Q(vendor__icontains=search))

    page = max(1, int(request.query_params.get('page', 1)))
    page_size = min(100, max(1, int(request.query_params.get('page_size', 50))))
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    return Response(
        {
            'count': paginator.count,
            'page': page,
            'page_size': page_size,
            'summary': _expense_summary(),
            'results': PlatformSystemExpenseSerializer(page_obj.object_list, many=True).data,
        }
    )


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_system_expense_detail(request, expense_id):
    expense = get_object_or_404(Expense, pk=expense_id, scope=Expense.Scope.PLATFORM)
    if request.method == 'DELETE':
        expense.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = PlatformSystemExpenseSerializer(expense, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)
