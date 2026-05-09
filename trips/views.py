# trips/views.py
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
import logging

from .models import Trip, TripStop, TripExpense
from .serializers import (
    TripSerializer, TripStopSerializer, TripExpenseSerializer,
    TripStartSerializer, TripCompleteSerializer, TripApproveSerializer
)

logger = logging.getLogger(__name__)


# ============================================================================
# TRIP ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_trips(request):
    """List all trips for the company."""
    user = request.user
    
    if not user.company:
        return Response({'error': 'No company found.'}, status=status.HTTP_400_BAD_REQUEST)
    
    trips = Trip.objects.filter(company=user.company)
    
    # Filters
    status_filter = request.query_params.get('status', None)
    vehicle_id = request.query_params.get('vehicle', None)
    driver_id = request.query_params.get('driver', None)
    is_flagged = request.query_params.get('is_flagged', None)
    date_from = request.query_params.get('date_from', None)
    date_to = request.query_params.get('date_to', None)
    
    if status_filter:
        trips = trips.filter(status=status_filter)
    if vehicle_id:
        trips = trips.filter(vehicle_id=vehicle_id)
    if driver_id:
        trips = trips.filter(driver_id=driver_id)
    if is_flagged is not None:
        trips = trips.filter(is_flagged=is_flagged.lower() == 'true')
    if date_from:
        trips = trips.filter(planned_departure_time__date__gte=date_from)
    if date_to:
        trips = trips.filter(planned_departure_time__date__lte=date_to)
    
    # Drivers can only see their own trips
    if user.is_driver:
        trips = trips.filter(driver=user.driver_profile)
    
    serializer = TripSerializer(trips, many=True, context={'request': request})
    
    return Response({
        'count': trips.count(),
        'trips': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_trip(request):
    """Create a new trip."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({'error': 'Only fleet owners can create trips.'}, status=status.HTTP_403_FORBIDDEN)
    
    if not user.company:
        return Response({'error': 'Please register your company first.'}, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = TripSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        # Validate vehicle belongs to company
        vehicle = serializer.validated_data.get('vehicle')
        if vehicle.company != user.company:
            return Response({'error': 'Vehicle does not belong to your company.'}, status=status.HTTP_403_FORBIDDEN)
        
        trip = serializer.save(company=user.company, created_by=user)
        
        logger.info(f"Trip created by {user.email}: {trip.trip_number}")
        
        return Response({
            'message': 'Trip created successfully.',
            'trip': TripSerializer(trip, context={'request': request}).data
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_trip(request, trip_id):
    """Get trip details."""
    user = request.user
    trip = get_object_or_404(Trip, id=trip_id, company=user.company)
    
    # Drivers can only see their own trips
    if user.is_driver and trip.driver != user.driver_profile:
        return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)
    
    serializer = TripSerializer(trip, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_trip(request, trip_id):
    """Update trip details."""
    user = request.user
    
    trip = get_object_or_404(Trip, id=trip_id, company=user.company)
    
    # Only fleet owners or assigned driver can update
    if not user.is_fleet_owner and trip.driver != user.driver_profile:
        return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)
    
    serializer = TripSerializer(
        trip, data=request.data, partial=request.method == 'PATCH',
        context={'request': request}
    )
    
    if serializer.is_valid():
        serializer.save()
        logger.info(f"Trip updated by {user.email}: {trip.trip_number}")
        return Response({
            'message': 'Trip updated successfully.',
            'trip': serializer.data
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_trip(request, trip_id):
    """Cancel a trip."""
    user = request.user
    trip = get_object_or_404(Trip, id=trip_id, company=user.company)
    
    reason = request.data.get('reason', 'Cancelled by user')
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
    
    trip = get_object_or_404(Trip, id=trip_id, company=user.company, is_flagged=True)
    
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