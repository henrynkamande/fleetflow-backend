from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from oauth.models import Company, User
from oauth.serializers import CompanySerializer, UserSerializer
from platform_api.permissions import IsPlatformAdmin
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
    qs = User.objects.all().order_by('-date_joined')
    role = request.query_params.get('role')
    if role:
        qs = qs.filter(role=role)
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
