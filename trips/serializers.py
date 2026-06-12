# trips/serializers.py
from rest_framework import serializers
from .models import Trip


class TripSerializer(serializers.ModelSerializer):
    """Serializer for Trips"""
    
    # Read-only calculated fields
    vehicle_registration = serializers.CharField(source='vehicle.registration_number', read_only=True)
    driver_name = serializers.CharField(source='driver.user.full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.full_name', read_only=True)
    
    # Computed properties
    distance_km = serializers.IntegerField(read_only=True)
    distance_is_estimated = serializers.BooleanField(read_only=True)
    duration_hours = serializers.FloatField(read_only=True)
    total_expenses = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    profit = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    profit_margin = serializers.FloatField(read_only=True)
    revenue_per_km = serializers.FloatField(read_only=True)
    cost_per_km = serializers.FloatField(read_only=True)
    
    class Meta:
        model = Trip
        fields = [
            'id', 'trip_number', 'fleet_owner',
            'vehicle', 'vehicle_registration', 'driver', 'driver_name',
            'pickup_location', 'destination', 'waypoints',
            'planned_departure_time', 'planned_arrival_time', 'planned_distance_km',
            'actual_departure_time', 'actual_arrival_time',
            'start_odometer', 'end_odometer',
            'start_odometer_photo', 'end_odometer_photo',
            'cargo_description', 'cargo_weight',
            'number_of_stops', 'deliveries_completed',
            'revenue_model', 'revenue_amount', 'rate_per_km',
            'fuel_cost', 'driver_payment', 'toll_cost', 'other_expenses',
            'status', 'is_flagged', 'flag_reason',
            'is_approved', 'approved_by', 'approved_by_name', 'approved_at',
            'customer_name', 'customer_contact', 'customer_reference',
            'driver_notes', 'manager_notes',
            'distance_km', 'distance_is_estimated', 'duration_hours', 'total_expenses',
            'profit', 'profit_margin', 'revenue_per_km', 'cost_per_km',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
        ]
        read_only_fields = [
            'id', 'trip_number', 'fleet_owner', 'vehicle_registration',
            'driver_name', 'created_by_name', 'approved_by_name',
            'distance_km', 'distance_is_estimated', 'duration_hours', 'total_expenses',
            'profit', 'profit_margin', 'revenue_per_km', 'cost_per_km',
            'is_flagged', 'flag_reason', 'is_approved',
            'approved_by', 'approved_at', 'created_at', 'updated_at',
        ]
    
    def validate(self, data):
        """Validate trip data"""
        # Validate end odometer > start odometer
        if data.get('start_odometer') and data.get('end_odometer'):
            if data['end_odometer'] < data['start_odometer']:
                raise serializers.ValidationError({
                    "end_odometer": "End odometer must be greater than start odometer."
                })
        
        # Validate arrival after departure
        if data.get('actual_departure_time') and data.get('actual_arrival_time'):
            if data['actual_arrival_time'] < data['actual_departure_time']:
                raise serializers.ValidationError({
                    "actual_arrival_time": "Arrival time must be after departure time."
                })
        
        return data


class TripListSerializer(serializers.ModelSerializer):
    """Compact trip row for list pages; excludes nested stops and expenses."""

    vehicle_registration = serializers.CharField(source='vehicle.registration_number', read_only=True)
    driver_name = serializers.CharField(source='driver.user.full_name', read_only=True)
    distance_km = serializers.IntegerField(read_only=True)
    distance_is_estimated = serializers.BooleanField(read_only=True)
    total_expenses = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    profit = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Trip
        fields = [
            'id', 'trip_number', 'status', 'pickup_location', 'destination',
            'vehicle', 'vehicle_registration', 'driver', 'driver_name',
            'planned_departure_time', 'actual_departure_time', 'actual_arrival_time',
            'planned_distance_km', 'is_flagged', 'flag_reason', 'distance_km',
            'distance_is_estimated', 'revenue_amount', 'fuel_cost', 'driver_payment',
            'toll_cost', 'other_expenses', 'total_expenses', 'profit', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class TripStartSerializer(serializers.Serializer):
    """Serializer for starting a trip"""
    
    odometer = serializers.IntegerField(required=True, min_value=0)
    photo = serializers.ImageField(required=False)


class TripCompleteSerializer(serializers.Serializer):
    """Serializer for completing a trip"""
    
    odometer = serializers.IntegerField(required=True, min_value=0)
    photo = serializers.ImageField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class TripApproveSerializer(serializers.Serializer):
    """Serializer for approving a flagged trip"""
    
    approved = serializers.BooleanField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True)