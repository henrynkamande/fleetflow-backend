from rest_framework import serializers

from .models import Expense


class ExpenseSerializer(serializers.ModelSerializer):
    vehicle_registration = serializers.CharField(source='vehicle.registration_number', read_only=True)
    trip_number = serializers.CharField(source='trip.trip_number', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = Expense
        fields = [
            'id',
            'fleet_owner',
            'vehicle',
            'vehicle_registration',
            'trip',
            'trip_number',
            'scope',
            'category',
            'status',
            'amount',
            'description',
            'vendor',
            'expense_date',
            'odometer_reading',
            'receipt',
            'notes',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'fleet_owner',
            'vehicle_registration',
            'trip_number',
            'created_by',
            'created_by_name',
            'created_at',
            'updated_at',
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        vehicle = attrs.get('vehicle') or getattr(self.instance, 'vehicle', None)
        trip = attrs.get('trip') or getattr(self.instance, 'trip', None)

        if user and user.is_fleet_owner:
            if vehicle and vehicle.fleet_owner_id != user.id:
                raise serializers.ValidationError({'vehicle': 'Vehicle does not belong to your fleet.'})
            if trip and trip.fleet_owner_id != user.id:
                raise serializers.ValidationError({'trip': 'Trip does not belong to your fleet.'})
        return attrs
