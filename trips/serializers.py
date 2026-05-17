# trips/serializers.py
from rest_framework import serializers
from .models import Trip, TripStop, TripExpense


class TripStopSerializer(serializers.ModelSerializer):
    """Serializer for Trip Stops"""
    
    class Meta:
        model = TripStop
        fields = [
            'id', 'trip', 'stop_number', 'location',
            'contact_person', 'contact_phone',
            'is_completed', 'arrival_time', 'departure_time',
            'odometer_reading', 'items_delivered',
            'delivery_proof_photo', 'recipient_signature', 'notes',
        ]
        read_only_fields = ['id']


class TripExpenseSerializer(serializers.ModelSerializer):
    """Serializer for Trip Expenses"""
    
    verified_by_name = serializers.CharField(source='verified_by.full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = TripExpense
        fields = [
            'id', 'trip', 'expense_type', 'amount', 'description',
            'expense_date', 'location', 'receipt',
            'is_verified', 'verified_by', 'verified_by_name',
            'created_at', 'created_by', 'created_by_name',
        ]
        read_only_fields = [
            'id', 'verified_by_name', 'created_by_name',
            'is_verified', 'verified_by', 'created_at',
        ]


class TripSerializer(serializers.ModelSerializer):
    """Serializer for Trips"""
    
    # Related data
    stops = TripStopSerializer(many=True, read_only=True)
    detailed_expenses = TripExpenseSerializer(many=True, read_only=True)
    
    # Read-only calculated fields
    vehicle_registration = serializers.CharField(source='vehicle.registration_number', read_only=True)
    driver_name = serializers.CharField(source='driver.user.full_name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
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
            'id', 'trip_number', 'company', 'company_name',
            'vehicle', 'vehicle_registration', 'driver', 'driver_name',
            'pickup_location', 'destination', 'waypoints',
            'planned_departure_time', 'planned_arrival_time', 'planned_distance_km',
            'actual_departure_time', 'actual_arrival_time',
            'start_odometer', 'end_odometer',
            'start_odometer_photo', 'end_odometer_photo',
            'cargo_description', 'cargo_weight',
            'number_of_stops', 'deliveries_completed',
            'revenue_model', 'revenue_amount', 'rate_per_km',
            'fuel_cost', 'toll_cost', 'other_expenses',
            'status', 'is_flagged', 'flag_reason',
            'is_approved', 'approved_by', 'approved_by_name', 'approved_at',
            'customer_name', 'customer_contact', 'customer_reference',
            'driver_notes', 'manager_notes',
            'distance_km', 'distance_is_estimated', 'duration_hours', 'total_expenses',
            'profit', 'profit_margin', 'revenue_per_km', 'cost_per_km',
            'stops', 'detailed_expenses',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
        ]
        read_only_fields = [
            'id', 'trip_number', 'company', 'company_name', 'vehicle_registration',
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