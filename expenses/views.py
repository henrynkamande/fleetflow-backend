from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from fleetflow.pagination import paginate_queryset

from .models import Expense
from .serializers import ExpenseSerializer


def _expense_queryset(user):
    if user.is_platform_admin:
        return Expense.objects.all()
    if user.is_fleet_owner:
        return Expense.objects.filter(fleet_owner=user)
    return Expense.objects.filter(trip__driver=getattr(user, 'driver_profile', None))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_expenses(request):
    qs = _expense_queryset(request.user)
    scope = request.query_params.get('scope')
    category = request.query_params.get('category')
    status_filter = request.query_params.get('status')
    vehicle = request.query_params.get('vehicle')
    trip = request.query_params.get('trip')
    search = (request.query_params.get('search') or '').strip()

    if scope:
        qs = qs.filter(scope=scope)
    if category:
        qs = qs.filter(category=category)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if vehicle:
        qs = qs.filter(vehicle_id=vehicle)
    if trip:
        qs = qs.filter(trip_id=trip)
    if search:
        qs = qs.filter(
            Q(description__icontains=search)
            | Q(vendor__icontains=search)
            | Q(notes__icontains=search)
        )

    qs = qs.select_related('fleet_owner', 'vehicle', 'trip', 'created_by')
    page_obj, meta = paginate_queryset(request, qs)
    serializer = ExpenseSerializer(page_obj.object_list, many=True, context={'request': request})
    return Response({**meta, 'expenses': serializer.data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_expense(request):
    user = request.user
    if not (user.is_fleet_owner or user.is_platform_admin):
        return Response({'error': 'Only fleet owners and platform admins can create expenses.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = ExpenseSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        fleet_owner = None if user.is_platform_admin and serializer.validated_data.get('scope') == Expense.Scope.PLATFORM else user
        expense = serializer.save(fleet_owner=fleet_owner, created_by=user)
        return Response({'message': 'Expense created successfully.', 'expense': ExpenseSerializer(expense).data}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def expense_detail(request, expense_id):
    expense = get_object_or_404(_expense_queryset(request.user), pk=expense_id)

    if request.method == 'GET':
        return Response(ExpenseSerializer(expense, context={'request': request}).data)

    if request.method == 'DELETE':
        expense.delete()
        return Response({'message': 'Expense deleted successfully.'})

    serializer = ExpenseSerializer(expense, data=request.data, partial=True, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response({'message': 'Expense updated successfully.', 'expense': serializer.data})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
