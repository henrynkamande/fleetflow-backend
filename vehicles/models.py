# vehicles/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
import uuid
import os


def vehicle_image_upload_path(instance, filename):
    """Generate upload path for vehicle images"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"vehicles/{instance.id}/images/{filename}"


def vehicle_document_upload_path(instance, filename):
    """Generate upload path for vehicle documents"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"vehicles/{instance.vehicle.id}/documents/{filename}"


class Vehicle(models.Model):
    """Vehicle model for fleet management"""
    
    class VehicleType(models.TextChoices):
        TRUCK = 'TRUCK', 'Truck'
        VAN = 'VAN', 'Van'
        PICKUP = 'PICKUP', 'Pickup'
        BUS = 'BUS', 'Bus'
        MINIBUS = 'MINIBUS', 'Minibus'
        CAR = 'CAR', 'Car'
        MOTORCYCLE = 'MOTORCYCLE', 'Motorcycle'
        TRAILER = 'TRAILER', 'Trailer'
        OTHER = 'OTHER', 'Other'
    
    class VehicleStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'
        UNDER_MAINTENANCE = 'UNDER_MAINTENANCE', 'Under Maintenance'
        OUT_OF_SERVICE = 'OUT_OF_SERVICE', 'Out of Service'
    
    class FuelType(models.TextChoices):
        PETROL = 'PETROL', 'Petrol'
        DIESEL = 'DIESEL', 'Diesel'
        ELECTRIC = 'ELECTRIC', 'Electric'
        HYBRID = 'HYBRID', 'Hybrid'
        CNG = 'CNG', 'CNG'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Fleet ownership
    fleet_owner = models.ForeignKey(
        'oauth.User',
        on_delete=models.CASCADE,
        related_name='vehicles',
        help_text="Fleet owner that owns this vehicle"
    )
    
    # Assigned Driver
    assigned_driver = models.ForeignKey(
        'oauth.DriverProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_vehicles',
        help_text="Currently assigned driver"
    )
    
    # Basic Vehicle Information
    registration_number = models.CharField(
        max_length=50, 
        help_text="Vehicle license plate/registration number"
    )
    make = models.CharField(
        max_length=100,
        help_text="Vehicle manufacturer (e.g., Toyota, Isuzu)"
    )
    model = models.CharField(
        max_length=100,
        help_text="Vehicle model (e.g., Hilux, NPR)"
    )
    year = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Year of manufacture"
    )
    color = models.CharField(
        max_length=50, 
        null=True, 
        blank=True
    )
    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices,
        default=VehicleType.TRUCK
    )
    
    # Vehicle Identification
    vin = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        help_text="Vehicle Identification Number (VIN/Chassis Number)"
    )
    engine_number = models.CharField(
        max_length=100, 
        null=True, 
        blank=True
    )
    
    # Specifications
    load_capacity = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Load capacity in tons"
    )
    seating_capacity = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Number of passengers (for buses/vans)"
    )
    fuel_type = models.CharField(
        max_length=20,
        choices=FuelType.choices,
        default=FuelType.DIESEL
    )
    fuel_tank_capacity = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Fuel tank capacity in liters"
    )
    
    # Insurance & Registration
    insurance_provider = models.CharField(
        max_length=200, 
        null=True, 
        blank=True
    )
    insurance_policy_number = models.CharField(
        max_length=100, 
        null=True, 
        blank=True
    )
    insurance_expiry_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Insurance policy expiry date"
    )
    registration_expiry_date = models.DateField(
        null=True, 
        blank=True,
        help_text="Vehicle registration expiry date"
    )
    
    # Service & Maintenance
    last_service_date = models.DateField(
        null=True, 
        blank=True
    )
    last_service_odometer = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Odometer reading at last service"
    )
    next_service_date = models.DateField(
        null=True, 
        blank=True
    )
    next_service_odometer = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Odometer reading for next service"
    )
    service_interval_km = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Service interval in kilometers"
    )
    
    # Current Status
    status = models.CharField(
        max_length=20,
        choices=VehicleStatus.choices,
        default=VehicleStatus.ACTIVE
    )
    current_odometer = models.PositiveIntegerField(
        default=0,
        help_text="Current odometer reading"
    )
    
    # Financial Tracking
    purchase_date = models.DateField(
        null=True, 
        blank=True
    )
    purchase_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    current_value = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    # Vehicle Image
    image = models.ImageField(
        upload_to=vehicle_image_upload_path,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])],
        null=True,
        blank=True,
        help_text="Vehicle photo"
    )
    
    # Additional Info
    notes = models.TextField(
        null=True, 
        blank=True,
        help_text="Additional notes about the vehicle"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the vehicle is active in the system"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'oauth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_vehicles'
    )
    
    class Meta:
        db_table = 'vehicles'
        ordering = ['-created_at']
        verbose_name = 'Vehicle'
        verbose_name_plural = 'Vehicles'
        constraints = [
            models.UniqueConstraint(
                fields=['fleet_owner', 'registration_number'],
                name='unique_vehicle_registration_per_fleet_owner',
            ),
        ]
        indexes = [
            models.Index(fields=['fleet_owner', 'status']),
            models.Index(fields=['fleet_owner', '-created_at']),
            models.Index(fields=['fleet_owner', 'vehicle_type']),
            models.Index(fields=['fleet_owner', 'assigned_driver']),
            models.Index(fields=['fleet_owner', 'is_active']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['registration_number']),
            models.Index(fields=['assigned_driver']),
            models.Index(fields=['vehicle_type']),
        ]
    
    def __str__(self):
        return f"{self.make} {self.model} - {self.registration_number}"
    
    @property
    def is_insurance_expired(self):
        """Check if insurance has expired"""
        if self.insurance_expiry_date:
            return self.insurance_expiry_date < timezone.now().date()
        return False
    
    @property
    def is_registration_expired(self):
        """Check if registration has expired"""
        if self.registration_expiry_date:
            return self.registration_expiry_date < timezone.now().date()
        return False
    
    @property
    def is_service_due(self):
        """Check if service is due by date or odometer"""
        if self.next_service_date:
            if self.next_service_date <= timezone.now().date():
                return True
        if self.next_service_odometer and self.current_odometer:
            if self.current_odometer >= self.next_service_odometer:
                return True
        return False
    
    @property
    def age_years(self):
        """Calculate vehicle age in years"""
        if self.year:
            return timezone.now().year - self.year
        return None
    
    @property
    def assigned_driver_name(self):
        """Get assigned driver's full name"""
        if self.assigned_driver:
            return self.assigned_driver.user.full_name
        return None

