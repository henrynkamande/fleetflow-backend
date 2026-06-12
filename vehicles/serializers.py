# vehicles/serializers.py
from rest_framework import serializers
from .models import Vehicle


class FieldSelectionMixin:
    """Allow list endpoints to request a whitelisted subset via ?fields=a,b."""

    selectable_fields = None

    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        super().__init__(*args, **kwargs)

        if not fields:
            return

        allowed = set(self.selectable_fields or self.fields.keys())
        requested = {field.strip() for field in fields.split(',') if field.strip()}
        selected = requested & allowed
        if not selected:
            return

        for field_name in set(self.fields) - selected:
            self.fields.pop(field_name)


class VehicleSerializer(serializers.ModelSerializer):
    """Serializer for Vehicle"""
    
    assigned_driver_name = serializers.CharField(source='assigned_driver.user.full_name', read_only=True)
    is_insurance_expired = serializers.BooleanField(read_only=True)
    is_registration_expired = serializers.BooleanField(read_only=True)
    is_service_due = serializers.BooleanField(read_only=True)
    age_years = serializers.IntegerField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'fleet_owner', 'assigned_driver', 'assigned_driver_name',
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
            'id', 'fleet_owner', 'assigned_driver_name', 'created_by_name',
            'created_by',
            'is_insurance_expired', 'is_registration_expired',
            'is_service_due', 'age_years', 'created_at', 'updated_at',
        ]

    def _fleet_owner_for_validation(self):
        if self.instance:
            return self.instance.fleet_owner
        fleet_owner = self.context.get('fleet_owner')
        if fleet_owner:
            return fleet_owner
        request = self.context.get('request')
        if request and request.user:
            return request.user if request.user.is_fleet_owner else getattr(request.user, 'fleet_owner', None)
        return None
    
    def validate_registration_number(self, value):
        """Normalize and validate registration number uniqueness within the fleet."""
        value = value.strip().upper()
        fleet_owner = self._fleet_owner_for_validation()
        queryset = Vehicle.objects.filter(registration_number__iexact=value)
        if fleet_owner:
            queryset = queryset.filter(fleet_owner=fleet_owner)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise serializers.ValidationError("A vehicle with this registration number already exists in your fleet.")
        return value

    def validate_vin(self, value):
        """VIN is optional, but must be unique when provided."""
        if not value:
            return value

        value = value.strip().upper()
        queryset = Vehicle.objects.filter(vin__iexact=value)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise serializers.ValidationError("A vehicle with this VIN already exists.")
        return value
    
    def validate_assigned_driver(self, value):
        """Validate that the assigned driver belongs to the same fleet owner."""
        request = self.context.get('request')
        if request and request.user and value:
            if value.fleet_owner_id != request.user.id:
                raise serializers.ValidationError("Driver must belong to your fleet.")
        return value


class VehicleListSerializer(FieldSelectionMixin, serializers.ModelSerializer):
    """Compact vehicle row for list pages."""

    assigned_driver_name = serializers.CharField(source='assigned_driver.user.full_name', read_only=True)

    selectable_fields = {
        'id', 'registration_number', 'make', 'model', 'year', 'color',
        'vehicle_type', 'status', 'current_odometer', 'assigned_driver',
        'assigned_driver_name', 'is_active', 'created_at',
        'updated_at',
    }

    class Meta:
        model = Vehicle
        fields = [
            'id', 'registration_number', 'make', 'model', 'year', 'color',
            'vehicle_type', 'status', 'current_odometer', 'assigned_driver',
            'assigned_driver_name', 'is_active', 'created_at',
            'updated_at',
        ]
        read_only_fields = fields