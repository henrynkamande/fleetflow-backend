# trips/views.py
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.utils import timezone
import logging
import uuid as uuid_lib

from fleetflow.pagination import paginate_queryset

from .list_stats import build_trip_list_stats
from .models import Trip
from .services import build_trip_list_queryset
from .serializers import (
    TripSerializer, TripListSerializer,
    TripStartSerializer, TripCompleteSerializer, TripApproveSerializer
)

logger = logging.getLogger(__name__)


def _fleet_owner_for_user(user):
    if user.is_fleet_owner:
        return user
    return getattr(user, 'fleet_owner', None) or getattr(getattr(user, 'driver_profile', None), 'fleet_owner', None)


def _resolve_trip(user, trip_ref: str) -> Trip:
    """Look up a trip by UUID primary key or human-readable trip_number."""
    fleet_owner = _fleet_owner_for_user(user)
    if not fleet_owner:
        raise Http404
    qs = Trip.objects.filter(fleet_owner=fleet_owner)
    try:
        uid = uuid_lib.UUID(str(trip_ref))
        return get_object_or_404(qs, id=uid)
    except ValueError:
        return get_object_or_404(qs, trip_number=trip_ref)


# ============================================================================
# TRIP ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_trips(request):
    """List all trips for the company."""
    user = request.user

    fleet_owner, trips = build_trip_list_queryset(user, request.query_params)
    if not fleet_owner:
        return Response({'count': 0, 'trips': []}, status=status.HTTP_200_OK)

    stats = None
    if request.query_params.get('include_stats', '').lower() in ('1', 'true', 'yes'):
        stats = build_trip_list_stats(trips)

    page_obj, meta = paginate_queryset(request, trips)
    serializer = TripListSerializer(page_obj.object_list, many=True, context={'request': request})

    payload = {
        **meta,
        'trips': serializer.data,
    }
    if stats is not None:
        payload['stats'] = stats
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_trip(request):
    """Create a new trip."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({'error': 'Only fleet owners can create trips.'}, status=status.HTTP_403_FORBIDDEN)
    
    serializer = TripSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        # Validate vehicle belongs to fleet owner.
        vehicle = serializer.validated_data.get('vehicle')
        if vehicle.fleet_owner_id != user.id:
            return Response({'error': 'Vehicle does not belong to your fleet.'}, status=status.HTTP_403_FORBIDDEN)

        driver = serializer.validated_data.get('driver')
        if driver is not None and driver.fleet_owner_id != user.id:
            return Response({'error': 'Driver does not belong to your fleet.'}, status=status.HTTP_403_FORBIDDEN)

        trip = serializer.save(fleet_owner=user, created_by=user)
        
        logger.info(f"Trip created by {user.email}: {trip.trip_number}")
        
        return Response({
            'message': 'Trip created successfully.',
            'trip': TripSerializer(trip, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_trip(request, trip_ref):
    """Get trip details by UUID or trip_number (e.g. TRIP-20260517-0001)."""
    user = request.user
    trip = _resolve_trip(user, trip_ref)

    if user.is_driver and trip.driver != user.driver_profile:
        return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = TripSerializer(trip, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_trip(request, trip_ref):
    """Update trip details (fleet owner, or driver on assigned trip)."""
    user = request.user
    trip = _resolve_trip(user, trip_ref)

    if not user.is_fleet_owner and trip.driver != user.driver_profile:
        return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)

    if user.is_fleet_owner and trip.status not in (
        Trip.TripStatus.PLANNED,
        Trip.TripStatus.DELAYED,
    ):
        return Response(
            {'error': 'Only planned or delayed trips can be edited. Cancel the trip or contact support.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    fleet_owner = _fleet_owner_for_user(user)
    serializer = TripSerializer(
        trip, data=request.data, partial=request.method == 'PATCH',
        context={'request': request, 'fleet_owner': fleet_owner},
    )

    if serializer.is_valid():
        vehicle = serializer.validated_data.get('vehicle')
        if vehicle and fleet_owner and vehicle.fleet_owner_id != fleet_owner.id:
            return Response({'error': 'Vehicle does not belong to your fleet.'}, status=status.HTTP_403_FORBIDDEN)
        driver = serializer.validated_data.get('driver')
        if driver is not None and fleet_owner and driver.fleet_owner_id != fleet_owner.id:
            return Response({'error': 'Driver does not belong to your fleet.'}, status=status.HTTP_403_FORBIDDEN)

        serializer.save()
        logger.info(f"Trip updated by {user.email}: {trip.trip_number}")
        return Response({
            'message': 'Trip updated successfully.',
            'trip': TripSerializer(trip, context={'request': request}).data
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_trip(request, trip_id):
    """Start a trip (driver only)."""
    user = request.user
    
    if not user.is_driver:
        return Response({'error': 'Only drivers can start trips.'}, status=status.HTTP_403_FORBIDDEN)
    
    trip = get_object_or_404(Trip, id=trip_id, driver=user.driver_profile, status=Trip.TripStatus.PLANNED)
    
    serializer = TripStartSerializer(data=request.data)
    if serializer.is_valid():
        trip.start_trip(
            odometer=serializer.validated_data['odometer'],
            photo=serializer.validated_data.get('photo')
        )
        
        logger.info(f"Trip started by {user.email}: {trip.trip_number}")
        
        return Response({
            'message': 'Trip started successfully.',
            'trip': TripSerializer(trip, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_trip(request, trip_id):
    """Complete a trip (driver only)."""
    user = request.user
    
    if not user.is_driver:
        return Response({'error': 'Only drivers can complete trips.'}, status=status.HTTP_403_FORBIDDEN)
    
    trip = get_object_or_404(Trip, id=trip_id, driver=user.driver_profile, status=Trip.TripStatus.ONGOING)
    
    serializer = TripCompleteSerializer(data=request.data)
    if serializer.is_valid():
        trip.complete_trip(
            odometer=serializer.validated_data['odometer'],
            photo=serializer.validated_data.get('photo'),
            notes=serializer.validated_data.get('notes')
        )
        
        logger.info(f"Trip completed by {user.email}: {trip.trip_number}")
        
        return Response({
            'message': 'Trip completed successfully.',
            'trip': TripSerializer(trip, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_trip(request, trip_ref):
    """Permanently remove a trip (fleet owner). Ongoing trips must be completed or cancelled first."""
    user = request.user

    if not user.is_fleet_owner:
        return Response({'error': 'Only fleet owners can delete trips.'}, status=status.HTTP_403_FORBIDDEN)

    trip = _resolve_trip(user, trip_ref)

    if trip.status == Trip.TripStatus.ONGOING:
        return Response(
            {'error': 'Complete or cancel this trip before deleting it.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    trip_number = trip.trip_number
    trip.delete()

    logger.info(f"Trip deleted by {user.email}: {trip_number}")

    return Response(
        {'message': f'Trip {trip_number} has been deleted.'},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_trip(request, trip_ref):
    """Cancel a trip (fleet owner)."""
    user = request.user

    if not user.is_fleet_owner:
        return Response({'error': 'Only fleet owners can cancel trips.'}, status=status.HTTP_403_FORBIDDEN)

    trip = _resolve_trip(user, trip_ref)

    if trip.status in (Trip.TripStatus.COMPLETED, Trip.TripStatus.CANCELLED):
        return Response(
            {'error': 'This trip cannot be cancelled.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    reason = request.data.get('reason', 'Cancelled by fleet owner')
    trip.cancel_trip(reason)
    
    logger.info(f"Trip cancelled by {user.email}: {trip.trip_number}")
    
    return Response({
        'message': 'Trip cancelled successfully.',
        'trip': TripSerializer(trip, context={'request': request}).data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_trip(request, trip_id):
    """Approve a flagged trip (fleet owner only)."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({'error': 'Only fleet owners can approve trips.'}, status=status.HTTP_403_FORBIDDEN)
    
    trip = get_object_or_404(Trip, id=trip_id, fleet_owner=user, is_flagged=True)
    
    serializer = TripApproveSerializer(data=request.data)
    if serializer.is_valid():
        if serializer.validated_data['approved']:
            trip.approve_trip(approved_by=user)
            if serializer.validated_data.get('notes'):
                trip.manager_notes = serializer.validated_data['notes']
                trip.save()
            message = 'Trip approved successfully.'
        else:
            trip.status = Trip.TripStatus.CANCELLED
            trip.manager_notes = serializer.validated_data.get('notes', 'Rejected by manager')
            trip.save()
            message = 'Trip rejected and cancelled.'
        
        logger.info(f"Trip {trip.trip_number} {'approved' if serializer.validated_data['approved'] else 'rejected'} by {user.email}")
        
        return Response({
            'message': message,
            'trip': TripSerializer(trip, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)