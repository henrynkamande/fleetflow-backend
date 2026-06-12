from rest_framework import serializers

from expenses.models import Expense


class PlatformSystemExpenseSerializer(serializers.ModelSerializer):
    added_by_name = serializers.SerializerMethodField()
    name = serializers.CharField(source='description')
    recorded_at = serializers.DateField(source='expense_date')

    class Meta:
        model = Expense
        fields = [
            'id',
            'name',
            'category',
            'amount',
            'recorded_at',
            'added_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'added_by_name', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['scope'] = Expense.Scope.PLATFORM
        validated_data['status'] = Expense.Status.PAID
        return super().create(validated_data)

    def get_added_by_name(self, obj):
        if obj.created_by_id:
            return obj.created_by.get_full_name()
        return None
