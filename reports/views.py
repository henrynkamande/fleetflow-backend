from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from oauth.fleet_workspace import ensure_fleet_owner_company

from .finance_service import (
    FinanceFilters,
    build_expenses_payload,
    build_income_payload,
    build_overview_payload,
    build_pl_payload,
    parse_period,
)


def _require_fleet_owner(user):
    if not user.is_fleet_owner:
        return None, Response(
            {'error': 'Only fleet owners can access financial reports.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    company = ensure_fleet_owner_company(user)
    if not company:
        return None, Response(
            {'error': 'Unable to resolve fleet company.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return company, None


def _filters_from_request(request, company) -> FinanceFilters:
    start, end = parse_period(
        request.query_params.get('date_from'),
        request.query_params.get('date_to'),
        request.query_params.get('period'),
    )
    return FinanceFilters(
        company_id=company.id,
        start=start,
        end=end,
        vehicle_id=request.query_params.get('vehicle') or None,
        driver_id=request.query_params.get('driver') or None,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def finance_income(request):
    company, err = _require_fleet_owner(request.user)
    if err:
        return err
    filters = _filters_from_request(request, company)
    granularity = request.query_params.get('granularity', 'monthly')
    if granularity not in ('monthly', 'quarterly', 'yearly'):
        granularity = 'monthly'
    return Response(build_income_payload(filters, granularity=granularity))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def finance_expenses(request):
    company, err = _require_fleet_owner(request.user)
    if err:
        return err
    filters = _filters_from_request(request, company)
    granularity = request.query_params.get('granularity', 'monthly')
    if granularity not in ('monthly', 'quarterly', 'yearly'):
        granularity = 'monthly'
    return Response(build_expenses_payload(filters, granularity=granularity))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def finance_pl(request):
    company, err = _require_fleet_owner(request.user)
    if err:
        return err
    filters = _filters_from_request(request, company)
    granularity = request.query_params.get('granularity', 'monthly')
    if granularity not in ('monthly', 'quarterly', 'yearly'):
        granularity = 'monthly'
    return Response(build_pl_payload(filters, granularity=granularity))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def finance_overview(request):
    company, err = _require_fleet_owner(request.user)
    if err:
        return err
    filters = _filters_from_request(request, company)
    return Response(build_overview_payload(filters))
