from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from billing import conf as billing_conf
from oauth.models import Company, User
from oauth.serializers import CompanySerializer, UserSerializer
from platform_api.models import PlatformSystemExpense
from platform_api.permissions import IsPlatformAdmin
from platform_api.serializers_expenses import PlatformSystemExpenseSerializer
from platform_api.services.overview import (
    annotate_companies_queryset,
    build_platform_overview,
    serialize_company_list_item,
)
from reports.finance_service import FinanceFilters, build_summary, parse_period, previous_period
from trips.models import Trip
from vehicles.models import Vehicle


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_overview(request):
    period = request.query_params.get('period', '30d')
    return Response(build_platform_overview(period))


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_companies(request):
    qs = annotate_companies_queryset(Company.objects.all().order_by('-created_at'))
    search = (request.query_params.get('search') or '').strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(owner__email__icontains=search)
            | Q(contact_email__icontains=search)
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
    company = get_object_or_404(
        annotate_companies_queryset(Company.objects.all()),
        pk=company_id,
    )
    period = request.query_params.get('period', '30d')
    start, end = parse_period(None, None, period)
    filters = FinanceFilters(company_id=company.id, start=start, end=end)
    prev_start, prev_end = previous_period(start, end)
    prev_filters = FinanceFilters(company_id=company.id, start=prev_start, end=prev_end)
    finance = build_summary(filters, prev_filters)

    drivers = User.objects.filter(company=company, role=User.Role.DRIVER).order_by('-date_joined')[:50]
    vehicles = Vehicle.objects.filter(company=company).order_by('-created_at')[:50]
    recent_trips = (
        Trip.objects.filter(company=company)
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
            'company': CompanySerializer(company, context={'request': request}).data,
            'counts': {
                'drivers': getattr(company, 'driver_count', 0),
                'vehicles': getattr(company, 'vehicle_count', 0),
                'trips': getattr(company, 'trip_count', 0),
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
    paginator = Paginator(qs.select_related('company'), page_size)
    page_obj = paginator.get_page(page)

    results = []
    for user in page_obj.object_list:
        row = UserSerializer(user, context={'request': request}).data
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
        User.objects.exclude(role=User.Role.PLATFORM_ADMIN).select_related('company'),
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


def _serialize_platform_vehicle(vehicle: Vehicle) -> dict:
    company = vehicle.company
    owner = company.owner if company else None
    vehicle_name = f'{vehicle.make} {vehicle.model}'.strip() or vehicle.registration_number
    return {
        'id': str(vehicle.id),
        'vehicle_name': vehicle_name,
        'registration_number': vehicle.registration_number,
        'vehicle_type': vehicle.vehicle_type,
        'status': vehicle.status,
        'company_id': str(company.id) if company else None,
        'company_name': company.name if company else None,
        'assigned_owner_name': owner.get_full_name() if owner else None,
        'assigned_owner_email': owner.email if owner else None,
        'created_at': vehicle.created_at.isoformat(),
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_vehicles(request):
    qs = Vehicle.objects.select_related('company', 'company__owner').order_by('-created_at')
    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)
    search = (request.query_params.get('search') or '').strip()
    if search:
        qs = qs.filter(
            Q(registration_number__icontains=search)
            | Q(make__icontains=search)
            | Q(model__icontains=search)
            | Q(company__name__icontains=search)
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

    return Response(
        {
            'count': paginator.count,
            'page': page,
            'page_size': page_size,
            'stats': stats,
            'results': [_serialize_platform_vehicle(v) for v in page_obj.object_list],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_vehicle_detail(request, vehicle_id):
    vehicle = get_object_or_404(
        Vehicle.objects.select_related('company', 'company__owner'),
        pk=vehicle_id,
    )
    return Response(_serialize_platform_vehicle(vehicle))


def _subscription_row(company: Company) -> dict:
    unit = billing_conf.BILLING_UNIT_AMOUNT_CENTS / 100
    qty = company.billing_quantity or 0
    monthly = float(qty * unit)
    billing = company.billing_status
    payment_status = 'Paid' if billing == Company.BillingStatus.ACTIVE else 'Due'
    if billing in (Company.BillingStatus.TRIALING, Company.BillingStatus.NOT_STARTED):
        payment_status = 'N/A'
    elif billing == Company.BillingStatus.CANCELED:
        payment_status = 'Cancelled'
    trial_status = 'Active' if billing == Company.BillingStatus.TRIALING else 'No'
    renewal = company.trial_ends_at.isoformat() if company.trial_ends_at else None
    return {
        'company_id': str(company.id),
        'company_name': company.name,
        'subscription_plan': company.subscription_plan,
        'billing_status': billing,
        'payment_status': payment_status,
        'amount_paid': monthly if billing == Company.BillingStatus.ACTIVE else 0,
        'amount_due': monthly if billing in (Company.BillingStatus.PAST_DUE, Company.BillingStatus.INCOMPLETE) else 0,
        'renewal_date': renewal,
        'trial_status': trial_status,
        'vehicle_count': qty,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def platform_subscriptions(request):
    qs = Company.objects.all().select_related('owner').order_by('name')
    billing = request.query_params.get('billing_status')
    if billing:
        qs = qs.filter(billing_status=billing)
    search = (request.query_params.get('search') or '').strip()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(owner__email__icontains=search))

    unit = billing_conf.BILLING_UNIT_AMOUNT_CENTS
    active_qs = Company.objects.filter(billing_status=Company.BillingStatus.ACTIVE)
    mrr_cents = sum((c.billing_quantity or 0) * unit for c in active_qs.only('billing_quantity'))
    outstanding_qs = Company.objects.filter(
        billing_status__in=[Company.BillingStatus.PAST_DUE, Company.BillingStatus.INCOMPLETE]
    )
    outstanding_cents = sum((c.billing_quantity or 0) * unit for c in outstanding_qs.only('billing_quantity'))

    summary = {
        'active': active_qs.count(),
        'trialing': Company.objects.filter(billing_status=Company.BillingStatus.TRIALING).count(),
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
    agg = PlatformSystemExpense.objects.aggregate(total=Sum('amount'))
    month_agg = PlatformSystemExpense.objects.filter(recorded_at__gte=month_start).aggregate(
        total=Sum('amount')
    )
    year_agg = PlatformSystemExpense.objects.filter(recorded_at__gte=year_start).aggregate(
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

    qs = PlatformSystemExpense.objects.select_related('created_by').order_by('-recorded_at')
    category = request.query_params.get('category')
    if category:
        qs = qs.filter(category=category)
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    if date_from:
        qs = qs.filter(recorded_at__gte=date_from)
    if date_to:
        qs = qs.filter(recorded_at__lte=date_to)
    search = (request.query_params.get('search') or '').strip()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))

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
    expense = get_object_or_404(PlatformSystemExpense, pk=expense_id)
    if request.method == 'DELETE':
        expense.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = PlatformSystemExpenseSerializer(expense, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)
