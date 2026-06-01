from rest_framework import serializers

from platform_api.models import PlatformSystemExpense


class PlatformSystemExpenseSerializer(serializers.ModelSerializer):
    added_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PlatformSystemExpense
        fields = [
            'id',
            'name',
            'description',
            'category',
            'amount',
            'recorded_at',
            'added_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'added_by_name', 'created_at', 'updated_at']

    def get_added_by_name(self, obj):
        if obj.created_by_id:
            return obj.created_by.get_full_name()
        return None
