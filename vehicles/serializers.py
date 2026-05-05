# vehicles/serializers.py
from rest_framework import serializers
from .models import Vehicle, VehicleDocument, VehicleServiceRecord, VehicleExpense, FuelLog


class VehicleSerializer(serializers.ModelSerializer):
    """Serializer for Vehicle"""
    
    company_name = serializers.CharField(source='company.name', read_only=True)
    assigned_driver_name = serializers.CharField(source='assigned_driver.user.full_name', read_only=True)
    is_insurance_expired = serializers.BooleanField(read_only=True)
    is_registration_expired = serializers.BooleanField(read_only=True)
    is_service_due = serializers.BooleanField(read_only=True)
    age_years = serializers.IntegerField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'company', 'company_name', 'assigned_driver', 'assigned_driver_name',
            'registration_number', 'make', 'model', 'year', 'color',
            'vehicle_type', 'vin', 'engine_number',
            'load_capacity', 'seating_capacity', 'fuel_type', 'fuel_tank_capacity',
            'insurance_provider', 'insurance_policy_number',
            'insurance_expiry_date', 'registration_expiry_date',
            'last_service_date', 'last_service_odometer',
            'next_service_date', 'next_service_odometer', 'service_interval_km',
            'status', 'current_odometer',
            'purchase_date', 'purchase_price', 'current_value',
            'image', 'notes', 'is_active',
            'is_insurance_expired', 'is_registration_expired',
            'is_service_due', 'age_years',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
        ]
        read_only_fields = [
            'id', 'company_name', 'assigned_driver_name', 'created_by_name',
            'is_insurance_expired', 'is_registration_expired',
            'is_service_due', 'age_years', 'created_at', 'updated_at',
        ]
    
    def validate_registration_number(self, value):
        """Validate registration number uniqueness"""
        if self.instance:
            if Vehicle.objects.filter(registration_number=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("A vehicle with this registration number already exists.")
        else:
            if Vehicle.objects.filter(registration_number=value).exists():
                raise serializers.ValidationError("A vehicle with this registration number already exists.")
        return value
    
    def validate_assigned_driver(self, value):
        """Validate that the assigned driver belongs to the same company"""
        request = self.context.get('request')
        if request and request.user and value:
            if value.user.company != request.user.company:
                raise serializers.ValidationError("Driver must belong to your company.")
        return value


class VehicleDocumentSerializer(serializers.ModelSerializer):
    """Serializer for Vehicle Documents"""
    
    vehicle_registration = serializers.CharField(source='vehicle.registration_number', read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = VehicleDocument
        fields = [
            'id', 'vehicle', 'vehicle_registration',
            'document_type', 'title', 'document_number',
            'file', 'issue_date', 'expiry_date', 'notes',
            'is_expired', 'uploaded_at', 'uploaded_by', 'uploaded_by_name',
        ]
        read_only_fields = [
            'id', 'vehicle_registration', 'uploaded_by_name',
            'is_expired', 'uploaded_at',
        ]


class VehicleServiceRecordSerializer(serializers.ModelSerializer):
    """Serializer for Vehicle Service Records"""
    
    vehicle_registration = serializers.CharField(source='vehicle.registration_number', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = VehicleServiceRecord
        fields = [
            'id', 'vehicle', 'vehicle_registration',
            'service_type', 'service_date', 'odometer_reading',
            'service_provider', 'description', 'cost',
            'parts_replaced', 'next_service_date', 'next_service_odometer',
            'receipt', 'created_at', 'created_by', 'created_by_name',
        ]
        read_only_fields = [
            'id', 'vehicle_registration', 'created_by_name', 'created_at',
        ]


class VehicleExpenseSerializer(serializers.ModelSerializer):
    """Serializer for Vehicle Expenses"""
    
    vehicle_registration = serializers.CharField(source='vehicle.registration_number', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = VehicleExpense
        fields = [
            'id', 'vehicle', 'vehicle_registration',
            'expense_type', 'amount', 'description',
            'expense_date', 'odometer_reading',
            'receipt', 'created_at', 'created_by', 'created_by_name',
        ]
        read_only_fields = [
            'id', 'vehicle_registration', 'created_by_name', 'created_at',
        ]


class FuelLogSerializer(serializers.ModelSerializer):
    """Serializer for Fuel Logs"""
    
    vehicle_registration = serializers.CharField(source='vehicle.registration_number', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    cost_per_km = serializers.FloatField(read_only=True)
    
    class Meta:
        model = FuelLog
        fields = [
            'id', 'vehicle', 'vehicle_registration',
            'fill_date', 'odometer_reading', 'liters',
            'price_per_liter', 'total_cost', 'fuel_station',
            'is_full_tank', 'notes', 'cost_per_km',
            'created_at', 'created_by', 'created_by_name',
        ]
        read_only_fields = [
            'id', 'vehicle_registration', 'created_by_name',
            'cost_per_km', 'created_at',
        ]