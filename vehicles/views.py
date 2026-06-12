# vehicles/views.py
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
import logging

from fleetflow.pagination import paginate_queryset, parse_page_params
from .services import queue_vehicle_write_followups

from .models import Vehicle
from .serializers import VehicleSerializer, VehicleListSerializer

logger = logging.getLogger(__name__)


def _fleet_owner_for_user(user):
    if user.is_fleet_owner:
        return user
    return getattr(user, 'fleet_owner', None) or getattr(getattr(user, 'driver_profile', None), 'fleet_owner', None)


def _parse_bool_param(value):
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in ('true', '1', 'yes'):
        return True
    if normalized in ('false', '0', 'no'):
        return False
    return None


# ============================================================================
# VEHICLE ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_vehicles(request):
    """List all vehicles in the fleet owner's company."""
    user = request.user

    fleet_owner = _fleet_owner_for_user(user)

    if not fleet_owner:
        page, page_size = parse_page_params(request)
        return Response(
            {
                'count': 0,
                'page': page,
                'page_size': page_size,
                'total_pages': 0,
                'vehicles': [],
            },
            status=status.HTTP_200_OK,
        )

    # Filter by query params
    vehicles = Vehicle.objects.filter(fleet_owner=fleet_owner)
    
    status_filter = request.query_params.get('status', None)
    type_filter = request.query_params.get('vehicle_type', None)
    driver_id = request.query_params.get('assigned_driver', None)
    search = (request.query_params.get('search') or '').strip()
    is_active = _parse_bool_param(request.query_params.get('is_active'))
    make = (request.query_params.get('make') or '').strip()
    model = (request.query_params.get('model') or '').strip()
    year = request.query_params.get('year', None)
    
    if status_filter:
        vehicles = vehicles.filter(status=status_filter)
    if type_filter:
        vehicles = vehicles.filter(vehicle_type=type_filter)
    if driver_id:
        if driver_id == 'unassigned':
            vehicles = vehicles.filter(assigned_driver__isnull=True)
        else:
            vehicles = vehicles.filter(assigned_driver_id=driver_id)
    if is_active is not None:
        vehicles = vehicles.filter(is_active=is_active)
    if make:
        vehicles = vehicles.filter(make__icontains=make)
    if model:
        vehicles = vehicles.filter(model__icontains=model)
    if year:
        try:
            vehicles = vehicles.filter(year=int(year))
        except (TypeError, ValueError):
            vehicles = vehicles.none()
    if search:
        vehicles = vehicles.filter(
            Q(registration_number__icontains=search)
            | Q(make__icontains=search)
            | Q(model__icontains=search)
            | Q(assigned_driver__user__first_name__icontains=search)
            | Q(assigned_driver__user__last_name__icontains=search)
            | Q(assigned_driver__user__email__icontains=search)
        )

    vehicles = vehicles.select_related('assigned_driver', 'assigned_driver__user', 'fleet_owner').order_by('-created_at')
    page_obj, meta = paginate_queryset(request, vehicles)
    serializer = VehicleListSerializer(
        page_obj.object_list,
        many=True,
        context={'request': request},
        fields=request.query_params.get('fields'),
    )

    return Response({
        **meta,
        'vehicles': serializer.data,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_vehicle(request):
    """Add a new vehicle to the fleet."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can add vehicles.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from billing.access import allow_trial_without_payment, owner_has_platform_access
    if not owner_has_platform_access(user):
        if allow_trial_without_payment():
            from billing.stripe_service import start_local_trial

            start_local_trial(user)
        else:
            return Response(
                {
                    'error': 'Active trial or subscription required.',
                    'code': 'billing_required',
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

    serializer = VehicleSerializer(data=request.data, context={'request': request, 'fleet_owner': user})
    
    if serializer.is_valid():
        vehicle = serializer.save(
            fleet_owner=user,
            created_by=user
        )

        queue_vehicle_write_followups(fleet_owner_id=user.id)
        
        logger.info(f"Vehicle added by {user.email}: {vehicle.registration_number}")
        
        return Response({
            'message': 'Vehicle added successfully.',
            'vehicle': VehicleSerializer(vehicle, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vehicle(request, vehicle_id):
    """Get a specific vehicle's details."""
    user = request.user
    fleet_owner = _fleet_owner_for_user(user)
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, fleet_owner=fleet_owner)
    
    serializer = VehicleSerializer(vehicle, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_vehicle(request, vehicle_id):
    """Update vehicle details."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can update vehicles.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    fleet_owner = user
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, fleet_owner=fleet_owner)
    serializer = VehicleSerializer(
        vehicle,
        data=request.data,
        partial=request.method == 'PATCH',
        context={'request': request, 'fleet_owner': fleet_owner}
    )
    
    if serializer.is_valid():
        serializer.save()
        logger.info(f"Vehicle updated by {user.email}: {vehicle.registration_number}")
        return Response({
            'message': 'Vehicle updated successfully.',
            'vehicle': serializer.data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_vehicle(request, vehicle_id):
    """Delete a vehicle."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can delete vehicles.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from django.db.models.deletion import ProtectedError

    vehicle = get_object_or_404(Vehicle, id=vehicle_id, fleet_owner=user)
    reg_number = vehicle.registration_number
    vehicle_data = VehicleSerializer(vehicle, context={'request': request}).data
    try:
        vehicle.delete()
    except ProtectedError:
        return Response(
            {
                'error': (
                    'This vehicle cannot be deleted because it is linked to existing trips. '
                    'Remove or reassign those trips first.'
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    queue_vehicle_write_followups(fleet_owner_id=user.id)
    
    logger.info(f"Vehicle deleted by {user.email}: {reg_number}")
    
    return Response({
        'message': f'Vehicle {reg_number} has been deleted.',
        'vehicle': vehicle_data,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_driver(request, vehicle_id):
    """Assign a driver to a vehicle."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can assign drivers.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, fleet_owner=user)
    driver_id = request.data.get('driver_id')
    
    if not driver_id:
        return Response({
            'error': 'Driver ID is required.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    from oauth.models import DriverProfile
    driver = get_object_or_404(DriverProfile, pk=driver_id, fleet_owner=user)
    
    vehicle.assigned_driver = driver
    vehicle.save(update_fields=['assigned_driver'])
    
    logger.info(f"Driver {driver.user.full_name} assigned to {vehicle.registration_number}")
    
    return Response({
        'message': f'Driver assigned successfully.',
        'vehicle': VehicleSerializer(vehicle, context={'request': request}).data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unassign_driver(request, vehicle_id):
    """Remove driver assignment from a vehicle."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can unassign drivers.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, fleet_owner=user)
    vehicle.assigned_driver = None
    vehicle.save(update_fields=['assigned_driver'])
    
    return Response({
        'message': 'Driver unassigned successfully.',
        'vehicle': VehicleSerializer(vehicle, context={'request': request}).data
    }, status=status.HTTP_200_OK)