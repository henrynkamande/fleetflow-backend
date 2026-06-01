# vehicles/views.py
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
import logging

from oauth.fleet_workspace import ensure_fleet_owner_company
from fleetflow.pagination import paginate_queryset

from .models import Vehicle, VehicleDocument, VehicleServiceRecord, VehicleExpense, FuelLog
from .serializers import (
    VehicleSerializer, VehicleDocumentSerializer,
    VehicleServiceRecordSerializer, VehicleExpenseSerializer,
    FuelLogSerializer
)

logger = logging.getLogger(__name__)


# ============================================================================
# VEHICLE ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_vehicles(request):
    """List all vehicles in the fleet owner's company."""
    user = request.user

    if user.is_fleet_owner:
        company = ensure_fleet_owner_company(user)
    else:
        company = user.company

    if not company:
        return Response({'count': 0, 'vehicles': []}, status=status.HTTP_200_OK)

    # Filter by query params
    vehicles = Vehicle.objects.filter(company=company)
    
    status_filter = request.query_params.get('status', None)
    type_filter = request.query_params.get('vehicle_type', None)
    driver_id = request.query_params.get('assigned_driver', None)
    
    if status_filter:
        vehicles = vehicles.filter(status=status_filter)
    if type_filter:
        vehicles = vehicles.filter(vehicle_type=type_filter)
    if driver_id:
        vehicles = vehicles.filter(assigned_driver_id=driver_id)

    vehicles = vehicles.select_related('assigned_driver', 'assigned_driver__user', 'company').order_by('-created_at')
    page_obj, meta = paginate_queryset(request, vehicles)
    serializer = VehicleSerializer(page_obj.object_list, many=True, context={'request': request})

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
    
    company = ensure_fleet_owner_company(user)
    if not company:
        return Response({'error': 'Unable to create fleet workspace.'}, status=status.HTTP_400_BAD_REQUEST)

    from billing.access import company_has_platform_access
    if not company_has_platform_access(company):
        return Response(
            {
                'error': 'Active trial or subscription required.',
                'code': 'billing_required',
            },
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )

    serializer = VehicleSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        vehicle = serializer.save(
            company=company,
            created_by=user
        )

        # Update fleet owner's total vehicles count
        fleet_owner_profile = user.fleet_owner_profile
        fleet_owner_profile.total_vehicles = Vehicle.objects.filter(
            company=company
        ).count()
        fleet_owner_profile.save(update_fields=['total_vehicles'])

        try:
            from billing.stripe_service import sync_subscription_quantity
            sync_subscription_quantity(company)
        except Exception:
            logger.exception('Failed to sync Stripe subscription quantity after vehicle create')
        
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
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, company=user.company)
    
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
    
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, company=user.company)
    serializer = VehicleSerializer(
        vehicle,
        data=request.data,
        partial=request.method == 'PATCH',
        context={'request': request}
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
    
    company = ensure_fleet_owner_company(user)
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, company=company)
    reg_number = vehicle.registration_number
    vehicle.delete()

    try:
        from billing.stripe_service import sync_subscription_quantity
        sync_subscription_quantity(company)
    except Exception:
        logger.exception('Failed to sync Stripe subscription quantity after vehicle delete')
    
    logger.info(f"Vehicle deleted by {user.email}: {reg_number}")
    
    return Response({
        'message': f'Vehicle {reg_number} has been deleted.'
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
    
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, company=user.company)
    driver_id = request.data.get('driver_id')
    
    if not driver_id:
        return Response({
            'error': 'Driver ID is required.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    from oauth.models import DriverProfile
    driver = get_object_or_404(DriverProfile, pk=driver_id, user__company=user.company)
    
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
    
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, company=user.company)
    vehicle.assigned_driver = None
    vehicle.save(update_fields=['assigned_driver'])
    
    return Response({
        'message': 'Driver unassigned successfully.',
        'vehicle': VehicleSerializer(vehicle, context={'request': request}).data
    }, status=status.HTTP_200_OK)