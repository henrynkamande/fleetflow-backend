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

from oauth.fleet_workspace import ensure_fleet_owner_company
from fleetflow.pagination import paginate_queryset

from .list_stats import build_trip_list_stats
from .models import Trip, TripStop, TripExpense
from .serializers import (
    TripSerializer, TripStopSerializer, TripExpenseSerializer,
    TripStartSerializer, TripCompleteSerializer, TripApproveSerializer
)

logger = logging.getLogger(__name__)


def _company_for_user(user):
    if user.is_fleet_owner:
        return ensure_fleet_owner_company(user)
    return user.company


def _resolve_trip(user, trip_ref: str) -> Trip:
    """Look up a trip by UUID primary key or human-readable trip_number."""
    company = _company_for_user(user)
    if not company:
        raise Http404
    qs = Trip.objects.filter(company=company)
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

    if user.is_fleet_owner:
        company = ensure_fleet_owner_company(user)
    else:
        company = user.company

    if not company:
        return Response({'count': 0, 'trips': []}, status=status.HTTP_200_OK)

    trips = Trip.objects.filter(company=company)
    
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

    trips = trips.select_related('vehicle', 'driver', 'driver__user').order_by('-planned_departure_time')

    stats = None
    if request.query_params.get('include_stats', '').lower() in ('1', 'true', 'yes'):
        stats = build_trip_list_stats(trips)

    page_obj, meta = paginate_queryset(request, trips)
    serializer = TripSerializer(page_obj.object_list, many=True, context={'request': request})

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
    
    company = ensure_fleet_owner_company(user)
    if not company:
        return Response({'error': 'Unable to create fleet workspace.'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = TripSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        # Validate vehicle belongs to company
        vehicle = serializer.validated_data.get('vehicle')
        if vehicle.company_id != company.id:
            return Response({'error': 'Vehicle does not belong to your company.'}, status=status.HTTP_403_FORBIDDEN)

        driver = serializer.validated_data.get('driver')
        if driver is not None and driver.user.company_id != company.id:
            return Response({'error': 'Driver does not belong to your company.'}, status=status.HTTP_403_FORBIDDEN)

        trip = serializer.save(company=company, created_by=user)
        
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

    company = _company_for_user(user)
    serializer = TripSerializer(
        trip, data=request.data, partial=request.method == 'PATCH',
        context={'request': request, 'company': company},
    )

    if serializer.is_valid():
        vehicle = serializer.validated_data.get('vehicle')
        if vehicle and company and vehicle.company_id != company.id:
            return Response({'error': 'Vehicle does not belong to your company.'}, status=status.HTTP_403_FORBIDDEN)
        driver = serializer.validated_data.get('driver')
        if driver is not None and company and driver.user.company_id != company.id:
            return Response({'error': 'Driver does not belong to your company.'}, status=status.HTTP_403_FORBIDDEN)

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