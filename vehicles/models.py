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
    
    # Company Ownership
    company = models.ForeignKey(
        'oauth.Company',
        on_delete=models.CASCADE,
        related_name='vehicles',
        help_text="Company that owns this vehicle"
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
        unique=True, 
        db_index=True,
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
        unique=True, 
        null=True, 
        blank=True,
        db_index=True,
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
        indexes = [
            models.Index(fields=['company', 'status']),
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


class VehicleDocument(models.Model):
    """Documents related to a vehicle (insurance, registration, etc.)"""
    
    class DocumentType(models.TextChoices):
        INSURANCE = 'INSURANCE', 'Insurance Certificate'
        REGISTRATION = 'REGISTRATION', 'Registration Certificate'
        INSPECTION = 'INSPECTION', 'Inspection Report'
        SERVICE_RECORD = 'SERVICE_RECORD', 'Service Record'
        PURCHASE_INVOICE = 'PURCHASE_INVOICE', 'Purchase Invoice'
        OTHER = 'OTHER', 'Other'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.CharField(
        max_length=30,
        choices=DocumentType.choices,
        default=DocumentType.OTHER
    )
    title = models.CharField(max_length=200)
    document_number = models.CharField(max_length=100, null=True, blank=True)
    file = models.FileField(
        upload_to=vehicle_document_upload_path,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'pdf'])],
        help_text="Upload document (PDF, JPG, PNG)"
    )
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    
    # Metadata
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        'oauth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_vehicle_documents'
    )
    
    class Meta:
        db_table = 'vehicle_documents'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['vehicle', 'document_type']),
            models.Index(fields=['expiry_date']),
        ]
    
    def __str__(self):
        return f"{self.document_type} - {self.vehicle.registration_number}"
    
    @property
    def is_expired(self):
        """Check if document has expired"""
        if self.expiry_date:
            return self.expiry_date < timezone.now().date()
        return False


class VehicleServiceRecord(models.Model):
    """Service and maintenance records for vehicles"""
    
    class ServiceType(models.TextChoices):
        ROUTINE = 'ROUTINE', 'Routine Service'
        REPAIR = 'REPAIR', 'Repair'
        INSPECTION = 'INSPECTION', 'Inspection'
        TIRE_CHANGE = 'TIRE_CHANGE', 'Tire Change'
        OIL_CHANGE = 'OIL_CHANGE', 'Oil Change'
        BRAKE_SERVICE = 'BRAKE_SERVICE', 'Brake Service'
        ENGINE_WORK = 'ENGINE_WORK', 'Engine Work'
        BODY_WORK = 'BODY_WORK', 'Body Work'
        OTHER = 'OTHER', 'Other'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='service_records'
    )
    service_type = models.CharField(
        max_length=30,
        choices=ServiceType.choices,
        default=ServiceType.ROUTINE
    )
    service_date = models.DateField()
    odometer_reading = models.PositiveIntegerField(
        help_text="Odometer reading at time of service"
    )
    service_provider = models.CharField(
        max_length=200,
        help_text="Garage or service center name"
    )
    description = models.TextField(
        help_text="Description of service performed"
    )
    cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Total cost of service"
    )
    parts_replaced = models.TextField(
        null=True, 
        blank=True,
        help_text="List of parts replaced"
    )
    next_service_date = models.DateField(
        null=True, 
        blank=True
    )
    next_service_odometer = models.PositiveIntegerField(
        null=True, 
        blank=True
    )
    
    # Receipt/Invoice
    receipt = models.FileField(
        upload_to=f'vehicles/{uuid.uuid4()}/service_receipts/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'pdf'])],
        null=True,
        blank=True,
        help_text="Upload service receipt/invoice"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'oauth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_service_records'
    )
    
    class Meta:
        db_table = 'vehicle_service_records'
        ordering = ['-service_date']
        indexes = [
            models.Index(fields=['vehicle', 'service_date']),
            models.Index(fields=['service_type']),
        ]
    
    def __str__(self):
        return f"{self.service_type} - {self.vehicle.registration_number} ({self.service_date})"


class VehicleExpense(models.Model):
    """Expenses related to vehicles (fuel, maintenance, etc.)"""
    
    class ExpenseType(models.TextChoices):
        FUEL = 'FUEL', 'Fuel'
        MAINTENANCE = 'MAINTENANCE', 'Maintenance'
        INSURANCE = 'INSURANCE', 'Insurance'
        REGISTRATION = 'REGISTRATION', 'Registration'
        TOLL = 'TOLL', 'Toll'
        PARKING = 'PARKING', 'Parking'
        FINES = 'FINES', 'Fines/Penalties'
        OTHER = 'OTHER', 'Other'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='expenses'
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
        help_text="Brief description of the expense"
    )
    expense_date = models.DateField(default=timezone.now)
    odometer_reading = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Odometer reading at time of expense"
    )
    
    # Receipt
    receipt = models.FileField(
        upload_to=f'vehicles/{uuid.uuid4()}/expense_receipts/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'pdf'])],
        null=True,
        blank=True,
        help_text="Upload receipt"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'oauth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_vehicle_expenses'
    )
    
    class Meta:
        db_table = 'vehicle_expenses'
        ordering = ['-expense_date']
        indexes = [
            models.Index(fields=['vehicle', 'expense_type']),
            models.Index(fields=['expense_date']),
        ]
    
    def __str__(self):
        return f"{self.expense_type} - {self.vehicle.registration_number} ({self.amount})"


class FuelLog(models.Model):
    """Fuel consumption tracking"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='fuel_logs'
    )
    fill_date = models.DateField(default=timezone.now)
    odometer_reading = models.PositiveIntegerField(
        help_text="Odometer reading at time of fill"
    )
    liters = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        help_text="Liters of fuel added"
    )
    price_per_liter = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        help_text="Price per liter"
    )
    total_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Total cost of fuel"
    )
    fuel_station = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Name of fuel station"
    )
    is_full_tank = models.BooleanField(
        default=True,
        help_text="Was the tank filled to full?"
    )
    
    # Calculated fields (can be computed by property)
    notes = models.TextField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'oauth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_fuel_logs'
    )
    
    class Meta:
        db_table = 'fuel_logs'
        ordering = ['-fill_date']
        indexes = [
            models.Index(fields=['vehicle', 'fill_date']),
        ]
    
    def __str__(self):
        return f"Fuel - {self.vehicle.registration_number} ({self.fill_date})"
    
    @property
    def cost_per_km(self):
        """Calculate fuel cost per km based on previous fill"""
        previous_log = FuelLog.objects.filter(
            vehicle=self.vehicle,
            fill_date__lt=self.fill_date
        ).order_by('-fill_date').first()
        
        if previous_log and self.odometer_reading > previous_log.odometer_reading:
            distance = self.odometer_reading - previous_log.odometer_reading
            if distance > 0:
                return self.total_cost / distance
        return None