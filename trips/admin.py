from django.contrib import admin

from .models import Customer, Trip


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'fleet_owner', 'phone', 'email', 'is_default', 'created_at')
    list_filter = ('is_default', 'created_at')
    search_fields = ('name', 'phone', 'email', 'fleet_owner__email')


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('trip_number', 'fleet_owner', 'customer', 'status', 'income_status', 'planned_departure_time')
    list_filter = ('status', 'income_status', 'created_at')
    search_fields = ('trip_number', 'customer__name', 'customer_name', 'fleet_owner__email')
