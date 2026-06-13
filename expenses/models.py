import uuid

from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


def expense_receipt_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    return f'expenses/{instance.fleet_owner_id}/{uuid.uuid4()}.{ext}'


class Expense(models.Model):
    """Unified expense ledger for fleet, trip, vehicle, and platform costs."""

    class Scope(models.TextChoices):
        FLEET = 'FLEET', 'Fleet'
        VEHICLE = 'VEHICLE', 'Vehicle'
        TRIP = 'TRIP', 'Trip'
        PLATFORM = 'PLATFORM', 'Platform'

    class Category(models.TextChoices):
        FUEL = 'FUEL', 'Fuel'
        MAINTENANCE = 'MAINTENANCE', 'Maintenance'
        INSURANCE = 'INSURANCE', 'Insurance'
        REGISTRATION = 'REGISTRATION', 'Registration'
        TOLL = 'TOLL', 'Toll'
        PARKING = 'PARKING', 'Parking'
        DRIVER_WAGES = 'DRIVER_WAGES', 'Driver wages'
        HOSTING = 'HOSTING', 'Hosting'
        MARKETING = 'MARKETING', 'Marketing'
        OPERATIONS = 'OPERATIONS', 'Operations'
        SOFTWARE = 'SOFTWARE', 'Software'
        OTHER = 'OTHER', 'Other'

    class Status(models.TextChoices):
        PAID = 'PAID', 'Paid'
        PENDING = 'PENDING', 'Pending'
        OVERDUE = 'OVERDUE', 'Overdue'

    class DriverPaymentMode(models.TextChoices):
        MONTHLY_FIXED = 'MONTHLY_FIXED', 'Paid Monthly'
        WEEKLY_TRIPS = 'WEEKLY_TRIPS', 'Weekly Payment'
        FIXED_DAILY = 'FIXED_DAILY', 'Fixed Pay Daily'
        PER_TRIP = 'PER_TRIP', 'Per Trip'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fleet_owner = models.ForeignKey(
        'oauth.User',
        on_delete=models.CASCADE,
        related_name='expenses',
        null=True,
        blank=True,
        help_text='Fleet owner for fleet/vehicle/trip expenses. Empty for platform-only costs.',
    )
    vehicle = models.ForeignKey(
        'vehicles.Vehicle',
        on_delete=models.SET_NULL,
        related_name='expenses',
        null=True,
        blank=True,
    )
    trip = models.ForeignKey(
        'trips.Trip',
        on_delete=models.SET_NULL,
        related_name='expenses',
        null=True,
        blank=True,
    )
    scope = models.CharField(max_length=20, choices=Scope.choices, db_index=True)
    category = models.CharField(max_length=32, choices=Category.choices, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PAID, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    driver_payment_mode = models.CharField(
        max_length=20,
        choices=DriverPaymentMode.choices,
        null=True,
        blank=True,
        help_text='Optional payment mode for driver wage expenses.',
    )
    description = models.CharField(max_length=500)
    vendor = models.CharField(max_length=200, blank=True)
    expense_date = models.DateField(default=timezone.localdate, db_index=True)
    odometer_reading = models.PositiveIntegerField(null=True, blank=True)
    receipt = models.FileField(
        upload_to=expense_receipt_upload_path,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'pdf'])],
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'oauth.User',
        on_delete=models.SET_NULL,
        related_name='expenses_created',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'expenses'
        ordering = ['-expense_date', '-created_at']
        indexes = [
            models.Index(fields=['fleet_owner', 'expense_date']),
            models.Index(fields=['fleet_owner', 'vehicle']),
            models.Index(fields=['fleet_owner', 'trip']),
            models.Index(fields=['scope', 'category']),
            models.Index(fields=['status']),
        ]

    def clean(self):
        if self.trip and not self.vehicle:
            self.vehicle = self.trip.vehicle
        if self.vehicle and not self.fleet_owner:
            self.fleet_owner = self.vehicle.fleet_owner
        if self.trip and not self.fleet_owner:
            self.fleet_owner = self.trip.fleet_owner

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.category} - {self.amount}'
