from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import uuid
import os


def user_avatar_upload_path(instance, filename):
    """Generate upload path for user avatars"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"avatars/{instance.id}/{filename}"


class UserManager(BaseUserManager):
    """Custom user manager for Fleet Flow"""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model for Fleet Flow"""
    
    class Role(models.TextChoices):
        FLEET_OWNER = 'FLEET_OWNER', 'Fleet Owner'
        DRIVER = 'DRIVER', 'Driver'
        PLATFORM_ADMIN = 'PLATFORM_ADMIN', 'Platform Admin'

    class BillingStatus(models.TextChoices):
        NOT_STARTED = 'NOT_STARTED', 'Not started'
        TRIALING = 'TRIALING', 'Trialing'
        ACTIVE = 'ACTIVE', 'Active'
        PAST_DUE = 'PAST_DUE', 'Past due'
        CANCELED = 'CANCELED', 'Canceled'
        INCOMPLETE = 'INCOMPLETE', 'Incomplete'
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    phone_number = models.CharField(max_length=20, unique=True, db_index=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    role = models.CharField(max_length=20, choices=Role.choices, db_index=True)
    
    # Avatar
    avatar = models.ImageField(
        upload_to=user_avatar_upload_path,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])],
        null=True,
        blank=True,
        help_text="User profile picture. Accepted formats: JPG, JPEG, PNG, WebP"
    )
    
    # Account Status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    
    # Timestamps
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Invitation System
    invited_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='invited_users'
    )
    invitation_accepted = models.BooleanField(default=False)

    # Fleet ownership boundary. Drivers are managed by a fleet owner; fleet owners own themselves.
    fleet_owner = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='managed_users',
        null=True,
        blank=True,
    )

    # Billing lives on the fleet-owner account; no separate company table is needed.
    subscription_plan = models.CharField(max_length=50, default='free')
    billing_status = models.CharField(
        max_length=20,
        choices=BillingStatus.choices,
        default=BillingStatus.NOT_STARTED,
        db_index=True,
    )
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    billing_quantity = models.PositiveIntegerField(default=0, help_text='Last synced billable vehicle count')
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'phone_number', 'role']
    
    class Meta:
        db_table = 'users'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email', 'role']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['fleet_owner', 'role']),
            models.Index(fields=['billing_status']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_full_name(self):
        return self.full_name
    
    def get_short_name(self):
        return self.first_name
    
    @property
    def is_fleet_owner(self):
        return self.role == self.Role.FLEET_OWNER
    
    @property
    def is_driver(self):
        return self.role == self.Role.DRIVER

    @property
    def is_platform_admin(self):
        return self.role == self.Role.PLATFORM_ADMIN
    
    @property
    def avatar_url(self):
        """Get the avatar URL or return None"""
        if self.avatar:
            return self.avatar.url
        return None
    
    def get_avatar_url(self, request=None):
        """Get absolute avatar URL (useful for APIs)"""
        if self.avatar:
            if request:
                return request.build_absolute_uri(self.avatar.url)
            return self.avatar.url
        return None
    
    def delete_avatar(self):
        """Delete avatar file and set field to None"""
        if self.avatar:
            if os.path.isfile(self.avatar.path):
                os.remove(self.avatar.path)
            self.avatar = None
            self.save()


class DriverProfile(models.Model):
    """Extended profile for drivers"""
    
    class LicenseType(models.TextChoices):
        CLASS_A = 'CLASS_A', 'Class A'
        CLASS_B = 'CLASS_B', 'Class B'
        CLASS_C = 'CLASS_C', 'Class C'
        CLASS_D = 'CLASS_D', 'Class D'
        CLASS_E = 'CLASS_E', 'Class E'
    
    class EmploymentStatus(models.TextChoices):
        FULL_TIME = 'FULL_TIME', 'Full Time'
        PART_TIME = 'PART_TIME', 'Part Time'
        CONTRACT = 'CONTRACT', 'Contract'
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='driver_profile',
        primary_key=True
    )
    fleet_owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='driver_profiles',
        null=True,
        blank=True,
        limit_choices_to={'role': User.Role.FLEET_OWNER},
    )
    
    # Personal Information
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=100, null=True, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, null=True, blank=True)
    
    # License Information
    drivers_license_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    license_type = models.CharField(
        max_length=10, 
        choices=LicenseType.choices, 
        null=True, 
        blank=True
    )
    license_expiry_date = models.DateField(null=True, blank=True)
    license_issuing_country = models.CharField(max_length=100, null=True, blank=True)
    
    # Employment Details
    employment_status = models.CharField(
        max_length=20,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.FULL_TIME
    )
    date_hired = models.DateField(null=True, blank=True)
    employee_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    
    # Payment Details
    payment_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_type = models.CharField(
        max_length=20,
        choices=[
            ('PER_TRIP', 'Per Trip'),
            ('PER_KM', 'Per Kilometer'),
            ('PER_HOUR', 'Per Hour'),
            ('FIXED', 'Fixed Salary'),
        ],
        default='PER_TRIP'
    )
    bank_account_number = models.CharField(max_length=50, null=True, blank=True)
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    
    # Work Limits
    max_daily_hours = models.DecimalField(max_digits=4, decimal_places=1, default=12.0)
    max_weekly_hours = models.DecimalField(max_digits=5, decimal_places=1, default=60.0)
    
    # Performance Metrics
    total_trips = models.PositiveIntegerField(default=0)
    completed_trips = models.PositiveIntegerField(default=0)
    on_time_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    
    # ========================================================================
    # OTP & TEMPORARY PASSWORD FIELDS
    # ========================================================================
    
    # OTP related fields
    otp_secret = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        help_text="Secret key for OTP generation"
    )
    otp_generated_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Timestamp when the last OTP was generated"
    )
    otp_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of failed OTP verification attempts"
    )
    
    # Temporary password fields
    temp_password_expires_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Expiry timestamp for temporary password (24 hours from onboarding)"
    )
    password_changed = models.BooleanField(
        default=False,
        help_text="Whether the driver has changed their temporary password"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'driver_profiles'
        indexes = [
            models.Index(fields=['fleet_owner', 'is_active']),
            models.Index(fields=['otp_secret']),
            models.Index(fields=['temp_password_expires_at']),
        ]
    
    def __str__(self):
        return f"Driver Profile - {self.user.full_name}"
    
    @property
    def is_license_expired(self):
        if self.license_expiry_date:
            return self.license_expiry_date < timezone.now().date()
        return False
    
    @property
    def completion_rate(self):
        if self.total_trips > 0:
            return (self.completed_trips / self.total_trips) * 100
        return 0
    
    @property
    def is_temp_password_expired(self):
        """Check if temporary password has expired"""
        if self.temp_password_expires_at:
            return timezone.now() > self.temp_password_expires_at
        return True
    
    @property
    def temp_password_hours_remaining(self):
        """Get hours remaining for temporary password"""
        if self.temp_password_expires_at and not self.is_temp_password_expired:
            delta = self.temp_password_expires_at - timezone.now()
            return round(delta.total_seconds() / 3600, 1)
        return 0
    
    @property
    def otp_is_expired(self):
        """Check if OTP has expired (10 minutes validity)"""
        if self.otp_generated_at:
            otp_age = timezone.now() - self.otp_generated_at
            return otp_age.total_seconds() > 600  # 10 minutes
        return True
    
    @property
    def otp_attempts_remaining(self):
        """Get remaining OTP attempts"""
        return max(0, 5 - self.otp_attempts)
    
    @property
    def is_otp_locked(self):
        """Check if OTP is locked due to too many attempts"""
        return self.otp_attempts >= 5


class FleetOwnerProfile(models.Model):
    """Extended profile for fleet owners"""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='fleet_owner_profile',
        primary_key=True
    )
    
    # Company Details
    company_name = models.CharField(max_length=200, null=True, blank=True)
    business_registration_number = models.CharField(max_length=100, null=True, blank=True)
    tax_id = models.CharField(max_length=50, null=True, blank=True)
    
    # Contact Information
    business_address = models.TextField(null=True, blank=True)
    business_phone = models.CharField(max_length=20, null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    
    # Preferences
    preferred_currency = models.CharField(max_length=3, default='USD')
    timezone = models.CharField(max_length=50, default='UTC')
    notification_preferences = models.JSONField(default=dict)
    
    # Fleet Stats
    total_vehicles = models.PositiveIntegerField(default=0)
    active_drivers = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'fleet_owner_profiles'
    
    def __str__(self):
        return f"Fleet Owner Profile - {self.user.full_name}"


class PendingFleetOwnerSignup(models.Model):
    """
    Fleet owner signup before email verification.
    No User row exists until OTP is confirmed.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    phone_number = models.CharField(max_length=20)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    password = models.CharField(max_length=128)
    code_hash = models.CharField(max_length=128, blank=True)
    code_expires_at = models.DateTimeField(null=True, blank=True)
    code_sent_at = models.DateTimeField(null=True, blank=True)
    code_attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pending_fleet_owner_signups'

    @property
    def is_code_expired(self):
        if not self.code_expires_at:
            return True
        return timezone.now() > self.code_expires_at

    def __str__(self):
        return f'Pending signup {self.email}'


class EmailAuthCode(models.Model):
    """Hashed email OTP / reset codes per user and purpose."""

    class Purpose(models.TextChoices):
        SIGNUP_VERIFY = 'SIGNUP_VERIFY', 'Signup verification'
        PASSWORD_RESET = 'PASSWORD_RESET', 'Password reset'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_auth_codes',
    )
    purpose = models.CharField(max_length=32, choices=Purpose.choices, db_index=True)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    sent_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'email_auth_codes'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'purpose'],
                name='unique_user_email_auth_code_purpose',
            ),
        ]

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f'{self.purpose} code for {self.user.email}'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create profile when user is created"""
    if created:
        if instance.role == User.Role.DRIVER:
            DriverProfile.objects.get_or_create(
                user=instance,
                defaults={'fleet_owner': instance.fleet_owner or instance.invited_by},
            )
        elif instance.role == User.Role.FLEET_OWNER:
            FleetOwnerProfile.objects.get_or_create(user=instance)


@receiver(pre_save, sender=User)
def delete_old_avatar_on_change(sender, instance, **kwargs):
    """Delete old avatar file when user updates avatar"""
    if not instance.pk:
        return  # New instance, no old file to delete
    
    try:
        old_user = User.objects.get(pk=instance.pk)
    except User.DoesNotExist:
        return
    
    # Check if avatar has changed
    if old_user.avatar and old_user.avatar != instance.avatar:
        if os.path.isfile(old_user.avatar.path):
            os.remove(old_user.avatar.path)