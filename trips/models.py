# trips/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
import uuid
import os
from decimal import Decimal


def trip_image_upload_path(instance, filename):
    """Generate upload path for trip-related images (odometer photos, delivery proofs, etc.)"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"trips/{instance.trip.id}/images/{filename}"


class Trip(models.Model):
    """Main Trip model for journey tracking (GPS-free)"""
    
    class TripStatus(models.TextChoices):
        PLANNED = 'PLANNED', 'Planned'
        ONGOING = 'ONGOING', 'Ongoing'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        FLAGGED = 'FLAGGED', 'Flagged'  
        DELAYED = 'DELAYED', 'Delayed'
    
    class RevenueModel(models.TextChoices):
        FIXED_RATE = 'FIXED_RATE', 'Fixed Rate'
        PER_KM = 'PER_KM', 'Per Kilometer'
        PER_DELIVERY = 'PER_DELIVERY', 'Per Delivery'
        CONTRACT = 'CONTRACT', 'Contract Based'
        HOURLY = 'HOURLY', 'Hourly Rate'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Company Ownership
    company = models.ForeignKey(
        'oauth.Company',
        on_delete=models.CASCADE,
        related_name='trips',
        help_text="Company that owns this trip"
    )
    
    # Vehicle Assignment (Required - each trip must have a vehicle)
    vehicle = models.ForeignKey(
        'vehicles.Vehicle',
        on_delete=models.PROTECT,  # Prevent vehicle deletion if trips exist
        related_name='trips',
        help_text="Vehicle assigned to this trip"
    )
    
    # Driver Assignment
    driver = models.ForeignKey(
        'oauth.DriverProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trips',
        help_text="Driver assigned to this trip"
    )
    
    # Trip Identification
    trip_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique trip reference number"
    )
    
    # Trip Route Information
    pickup_location = models.CharField(
        max_length=500,
        help_text="Starting point / pickup location"
    )

    destination = models.CharField(
        max_length=500,
        help_text="Final destination"
    )

    waypoints = models.JSONField(
        null=True,
        blank=True,
        help_text="List of stops/waypoints along the route"
    )
    
    # Trip Planning
    planned_departure_time = models.DateTimeField(
        help_text="Scheduled departure time"
    )

    planned_arrival_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Estimated arrival time"
    )
    
    # Actual Trip Data (GPS-Free - entered by driver)
    actual_departure_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Actual departure time"
    )

    actual_arrival_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Actual arrival time"
    )

    start_odometer = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Odometer reading at start of trip"
    )

    end_odometer = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Odometer reading at end of trip"
    )
    
    # Odometer Verification
    start_odometer_photo = models.ImageField(
        upload_to=trip_image_upload_path,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        null=True,
        blank=True,
        help_text="Photo of odometer at trip start"
    )

    end_odometer_photo = models.ImageField(
        upload_to=trip_image_upload_path,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        null=True,
        blank=True,
        help_text="Photo of odometer at trip end"
    )
    
    # Cargo/Delivery Information
    cargo_description = models.TextField(
        null=True,
        blank=True,
        help_text="Description of cargo being transported"
    )

    cargo_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cargo weight in tons"
    )

    number_of_stops = models.PositiveIntegerField(
        default=1,
        help_text="Number of delivery stops"
    )

    deliveries_completed = models.PositiveIntegerField(
        default=0,
        help_text="Number of successful deliveries"
    )
    
    # Revenue & Financials
    revenue_model = models.CharField(
        max_length=20,
        choices=RevenueModel.choices,
        default=RevenueModel.FIXED_RATE
    )

    revenue_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total revenue for this trip"
    )

    rate_per_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Rate per kilometer (if PER_KM model)"
    )
    
    # Expense Tracking
    fuel_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Fuel cost for this trip"
    )

    toll_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Toll charges"
    )
    other_expenses = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Other miscellaneous expenses"
    )
    
    # Trip Status & Tracking
    status = models.CharField(
        max_length=20,
        choices=TripStatus.choices,
        default=TripStatus.PLANNED
    )

    is_flagged = models.BooleanField(
        default=False,
        help_text="Flagged for review (unusual data, fraud detection)"
    )

    flag_reason = models.TextField(
        null=True,
        blank=True,
        help_text="Reason for flagging the trip"
    )

    is_approved = models.BooleanField(
        default=False,
        help_text="Approved by fleet manager (for flagged trips)"
    )

    approved_by = models.ForeignKey(
        'oauth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_trips'
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Customer Information (Optional)
    customer_name = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Customer/client name"
    )

    customer_contact = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Customer contact number"
    )

    customer_reference = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Customer PO/reference number"
    )
    
    # Trip Notes
    driver_notes = models.TextField(
        null=True,
        blank=True,
        help_text="Notes from the driver about the trip"
    )

    manager_notes = models.TextField(
        null=True,
        blank=True,
        help_text="Notes from the fleet manager"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'oauth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_trips'
    )
    
    class Meta:
        db_table = 'trips'
        ordering = ['-created_at']
        verbose_name = 'Trip'
        verbose_name_plural = 'Trips'
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['vehicle', 'status']),
            models.Index(fields=['driver', 'status']),
            models.Index(fields=['trip_number']),
            models.Index(fields=['planned_departure_time']),
            models.Index(fields=['status', 'is_flagged']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Trip {self.trip_number} - {self.vehicle.registration_number} ({self.status})"
    
    def save(self, *args, **kwargs):
        """Auto-generate trip number and perform validations"""
        if not self.trip_number:
            self.trip_number = self._generate_trip_number()
        
        # Validate odometer readings
        if self.start_odometer and self.end_odometer:
            if self.end_odometer < self.start_odometer:
                raise ValueError("End odometer cannot be less than start odometer")
        
        # Auto-calculate distance if both odometer readings exist
        # Auto-flag trips with unusual data
        if self.start_odometer and self.end_odometer:
            distance = self.end_odometer - self.start_odometer
            # Flag if distance seems too short or too long
            if distance < 1:
                self.is_flagged = True
                self.flag_reason = "Suspicious odometer reading: distance too short"
            elif distance > 2000:  
                self.is_flagged = True
                self.flag_reason = "Unusually long trip distance"
        
        # Flag if trip duration exceeds 16 hours
        if self.actual_departure_time and self.actual_arrival_time:
            duration = self.actual_arrival_time - self.actual_departure_time
            if duration.total_seconds() / 3600 > 16:
                self.is_flagged = True
                self.flag_reason = "Trip exceeded 16-hour limit"
        
        super().save(*args, **kwargs)
    
    def _generate_trip_number(self):
        """Generate a unique trip number: TRIP-YYYYMMDD-XXXX"""
        date_part = timezone.now().strftime('%Y%m%d')
        last_trip = Trip.objects.filter(
            trip_number__startswith=f'TRIP-{date_part}'
        ).order_by('-trip_number').first()
        
        if last_trip:
            last_number = int(last_trip.trip_number.split('-')[-1])
            new_number = str(last_number + 1).zfill(4)
        else:
            new_number = '0001'
        
        return f'TRIP-{date_part}-{new_number}'
    
    @property
    def distance_km(self):
        """Calculate trip distance in kilometers"""
        if self.start_odometer and self.end_odometer:
            return self.end_odometer - self.start_odometer
        return None
    
    @property
    def duration_hours(self):
        """Calculate trip duration in hours"""
        if self.actual_departure_time and self.actual_arrival_time:
            duration = self.actual_arrival_time - self.actual_departure_time
            return round(duration.total_seconds() / 3600, 2)
        return None
    
    @property
    def total_expenses(self):
        """Calculate total trip expenses"""
        return self.fuel_cost + self.toll_cost + self.other_expenses
    
    @property
    def profit(self):
        """Calculate trip profit"""
        return self.revenue_amount - self.total_expenses
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.revenue_amount > 0:
            return round((self.profit / self.revenue_amount) * 100, 2)
        return None
    
    @property
    def revenue_per_km(self):
        """Calculate revenue per kilometer"""
        distance = self.distance_km
        if distance and distance > 0:
            return round(self.revenue_amount / distance, 2)
        return None
    
    @property
    def cost_per_km(self):
        """Calculate cost per kilometer"""
        distance = self.distance_km
        if distance and distance > 0:
            return round(self.total_expenses / distance, 2)
        return None
    
    def start_trip(self, odometer, photo=None):
        """Mark trip as ongoing"""
        self.status = self.TripStatus.ONGOING
        self.actual_departure_time = timezone.now()
        self.start_odometer = odometer
        if photo:
            self.start_odometer_photo = photo
        self.save()
    
    def complete_trip(self, odometer, photo=None, notes=None):
        """Mark trip as completed"""
        self.status = self.TripStatus.COMPLETED
        self.actual_arrival_time = timezone.now()
        self.end_odometer = odometer
        if photo:
            self.end_odometer_photo = photo
        if notes:
            self.driver_notes = notes
        
        # Update vehicle odometer
        self.vehicle.current_odometer = odometer
        self.vehicle.save(update_fields=['current_odometer'])
        
        # Update driver stats
        if self.driver:
            self.driver.total_trips += 1
            self.driver.completed_trips += 1
            if self.driver.total_trips > 0:
                self.driver.completion_rate
            self.driver.save(update_fields=['total_trips', 'completed_trips'])
        
        self.save()
    
    def cancel_trip(self, reason=None):
        """Cancel a trip"""
        self.status = self.TripStatus.CANCELLED
        if reason:
            self.manager_notes = reason
        self.save()
    
    def approve_trip(self, approved_by):
        """Approve a flagged trip"""
        self.is_approved = True
        self.approved_by = approved_by
        self.approved_at = timezone.now()
        self.is_flagged = False
        self.status = self.TripStatus.COMPLETED
        self.save()

# More than 2000km in a single trip
class TripStop(models.Model):
    """Individual stop/delivery point within a trip"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='stops'
    )
    
    # Stop Details
    stop_number = models.PositiveIntegerField(
        help_text="Order of this stop in the trip"
    )
    location = models.CharField(
        max_length=500,
        help_text="Stop location/address"
    )
    contact_person = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )
    contact_phone = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )
    
    # Stop Status
    is_completed = models.BooleanField(default=False)
    arrival_time = models.DateTimeField(null=True, blank=True)
    departure_time = models.DateTimeField(null=True, blank=True)
    odometer_reading = models.PositiveIntegerField(null=True, blank=True)
    
    # Delivery Details
    items_delivered = models.TextField(
        null=True,
        blank=True,
        help_text="Description of items delivered at this stop"
    )

    delivery_proof_photo = models.ImageField(
        upload_to=f'trips/{uuid.uuid4()}/delivery_proofs/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        null=True,
        blank=True,
        help_text="Photo proof of delivery"
    )
    
    recipient_signature = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Name of person who received delivery"
    )
    
    # Notes
    notes = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = 'trip_stops'
        ordering = ['trip', 'stop_number']
        unique_together = ['trip', 'stop_number']
    
    def __str__(self):
        return f"Stop {self.stop_number} - {self.trip.trip_number}"


class TripExpense(models.Model):
    """Detailed expense tracking for trips"""
    
    class ExpenseType(models.TextChoices):
        FUEL = 'FUEL', 'Fuel'
        TOLL = 'TOLL', 'Toll'
        PARKING = 'PARKING', 'Parking'
        LOADING = 'LOADING', 'Loading/Unloading'
        MEALS = 'MEALS', 'Meals & Refreshments'
        ACCOMMODATION = 'ACCOMMODATION', 'Accommodation'
        REPAIRS = 'REPAIRS', 'Emergency Repairs'
        OTHER = 'OTHER', 'Other'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='detailed_expenses'
    )
    expense_type = models.CharField(
        max_length=20,
        choices=ExpenseType.choices
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    description = models.CharField(
        max_length=500,
        help_text="Description of the expense"
    )
    expense_date = models.DateTimeField(default=timezone.now)
    location = models.CharField(
        max_length=300,
        null=True,
        blank=True,
        help_text="Where the expense occurred"
    )
    
    # Receipt
    receipt = models.ImageField(
        upload_to=f'trips/{uuid.uuid4()}/expense_receipts/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'pdf'])],
        null=True,
        blank=True,
        help_text="Receipt photo/scan"
    )
    
    # Verification
    is_verified = models.BooleanField(
        default=False,
        help_text="Verified by fleet manager"
    )
    verified_by = models.ForeignKey(
        'oauth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_trip_expenses'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'oauth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_trip_expenses'
    )
    
    class Meta:
        db_table = 'trip_expenses'
        ordering = ['-expense_date']
        indexes = [
            models.Index(fields=['trip', 'expense_type']),
            models.Index(fields=['is_verified']),
        ]
    
    def __str__(self):
        return f"{self.expense_type} - {self.trip.trip_number} ({self.amount})"