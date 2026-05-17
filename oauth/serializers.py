# serializers.py
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.contrib.auth import authenticate
from .models import (
    User, Company, DriverProfile, FleetOwnerProfile, 
    KYCDocument
)
import pyotp
import random
import string


class PasswordGenerationMixin:
    """Mixin to handle password and OTP generation"""
    
    @staticmethod
    def generate_random_password(length=12):
        """Generate a secure random password"""
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        return get_random_string(length, characters)
    
    @staticmethod
    def generate_otp_secret():
        """Generate OTP secret for 2FA"""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_otp(secret):
        """Generate OTP from secret"""
        totp = pyotp.TOTP(secret, interval=300)  # 5 minutes validity
        return totp.now()
    
    @staticmethod
    def verify_otp(secret, otp):
        """Verify OTP against secret"""
        totp = pyotp.TOTP(secret, interval=300)
        return totp.verify(otp)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer with role and company claims."""
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['email'] = user.email
        token['role'] = user.role
        token['is_verified'] = user.is_verified
        token['full_name'] = user.full_name
        
        if user.company:
            token['company_id'] = str(user.company.id)
            token['company_name'] = user.company.name
        
        return token
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add extra response data
        data['user'] = UserSerializer(self.user, context={'request': self.context.get('request')}).data
        data['role'] = self.user.role
        data['is_verified'] = self.user.is_verified
        
        # Determine redirect URL based on role and company status
        if self.user.is_fleet_owner:
            if self.user.company:
                data['redirect_url'] = '/fleet-owner/dashboard'
                data['company'] = CompanySerializer(self.user.company, context={'request': self.context.get('request')}).data
            else:
                data['redirect_url'] = '/fleet-owner/dashboard'
                data['requires_company'] = False
                data['next_step'] = 'register_company'
        else:
            data['redirect_url'] = '/driver/dashboard'
        
        # Check if driver needs to verify
        if self.user.is_driver and not self.user.is_verified:
            data['requires_password_change'] = True
            data['requires_verification'] = True
        
        return data


# ============================================================================
# FLEET OWNER ACCOUNT REGISTRATION (Step 1)
# ============================================================================

class FleetOwnerRegistrationSerializer(serializers.ModelSerializer, PasswordGenerationMixin):
    """
    Step 1: Register fleet owner account (without company).
    After registration, fleet owner must create a company.
    """
    
    password = serializers.CharField(
        write_only=True, 
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        write_only=True, 
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = [
            'email', 'phone_number', 'first_name', 'last_name',
            'password', 'confirm_password'
        ]
    
    def validate_email(self, value):
        """Validate and normalize email"""
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()
    
    def validate_phone_number(self, value):
        """Validate phone number"""
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return value
    
    def validate(self, data):
        """Validate passwords match"""
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        return data
    
    def create(self, validated_data):
        """Create fleet owner account without company"""
        validated_data.pop('confirm_password')
        
        # Set role and verification status
        validated_data['role'] = User.Role.FLEET_OWNER
        validated_data['is_active'] = True
        validated_data['is_verified'] = True  # Fleet owners are auto-verified
        
        # Create user WITHOUT company
        user = User.objects.create_user(**validated_data)
        
        return user


# ============================================================================
# COMPANY REGISTRATION (Step 2 - After Fleet Owner Account)
# ============================================================================

class CompanyRegistrationSerializer(serializers.ModelSerializer):
    """
    Step 2: Fleet owner creates their company after account registration.
    """
    
    class Meta:
        model = Company
        fields = [
            'name', 'registration_number', 'address',
            'contact_email', 'contact_phone', 'logo'
        ]
        extra_kwargs = {
            'registration_number': {'required': False},
            'address': {'required': False},
            'contact_email': {'required': False},
            'contact_phone': {'required': False},
            'logo': {'required': False},
        }
    
    def validate_name(self, value):
        """Validate company name on create (updates may keep the same name)."""
        request = self.context.get('request')
        if request and request.user and not self.instance:
            if Company.objects.filter(owner=request.user).exists():
                raise serializers.ValidationError("You have already registered a company.")
        return value

    def update(self, instance, validated_data):
        request = self.context.get('request')
        user = request.user
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if user.company_id != instance.id:
            user.company = instance
            user.save(update_fields=['company'])
        fleet_owner_profile = user.fleet_owner_profile
        if 'name' in validated_data:
            fleet_owner_profile.company_name = validated_data['name']
        if 'registration_number' in validated_data:
            fleet_owner_profile.business_registration_number = validated_data.get('registration_number') or ''
        if 'address' in validated_data:
            fleet_owner_profile.business_address = validated_data.get('address') or ''
        if 'contact_phone' in validated_data:
            fleet_owner_profile.business_phone = validated_data.get('contact_phone') or ''
        fleet_owner_profile.save()
        return instance

    def create(self, validated_data):
        """Create company and link to fleet owner"""
        request = self.context.get('request')
        user = request.user
        
        # Create company with owner
        company = Company.objects.create(
            owner=user,
            **validated_data
        )
        
        # Link user to company
        user.company = company
        user.save(update_fields=['company'])
        
        # Update fleet owner profile with company details
        fleet_owner_profile = user.fleet_owner_profile
        fleet_owner_profile.company_name = validated_data.get('name')
        fleet_owner_profile.business_registration_number = validated_data.get('registration_number', '')
        fleet_owner_profile.business_address = validated_data.get('address', '')
        fleet_owner_profile.business_phone = validated_data.get('contact_phone', '')
        fleet_owner_profile.save()
        
        return company


class CompanyUpdateSerializer(serializers.ModelSerializer):
    """Update company details."""
    
    class Meta:
        model = Company
        fields = [
            'name', 'registration_number', 'address',
            'contact_email', 'contact_phone', 'logo'
        ]


# ============================================================================
# DRIVER ONBOARDING (Step 3 - After Company Creation)
# ============================================================================

class DriverOnboardingSerializer(serializers.ModelSerializer, PasswordGenerationMixin):
    """
    Step 3: Fleet owner onboards drivers under their company.
    Generates random password and OTP for account verification.
    Temporary password is valid for 24 hours.
    """
    
    # Driver profile fields
    date_of_birth = serializers.DateField(required=False)
    address = serializers.CharField(required=False, allow_blank=True)
    drivers_license_number = serializers.CharField(required=False, allow_blank=True)
    license_type = serializers.ChoiceField(
        choices=DriverProfile.LicenseType.choices,
        required=False
    )
    license_expiry_date = serializers.DateField(required=False)
    employment_status = serializers.ChoiceField(
        choices=DriverProfile.EmploymentStatus.choices,
        required=False
    )
    payment_rate = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2,
        required=False
    )
    payment_type = serializers.ChoiceField(
        choices=[
            ('PER_TRIP', 'Per Trip'),
            ('PER_KM', 'Per Kilometer'),
            ('PER_HOUR', 'Per Hour'),
            ('FIXED', 'Fixed Salary'),
        ],
        required=False
    )
    
    class Meta:
        model = User
        fields = [
            'email', 'phone_number', 'first_name', 'last_name',
            'date_of_birth', 'address',
            'drivers_license_number', 'license_type', 
            'license_expiry_date', 'employment_status',
            'payment_rate', 'payment_type'
        ]
    
    def validate_email(self, value):
        """Validate email"""
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()
    
    def validate_phone_number(self, value):
        """Validate phone number"""
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return value
    
    def create(self, validated_data):
        """Create driver account with generated credentials"""
        request = self.context.get('request')
        fleet_owner = request.user
        
        # Extract driver profile fields
        profile_fields = {}
        profile_field_names = [
            'date_of_birth', 'address', 'drivers_license_number',
            'license_type', 'license_expiry_date', 'employment_status',
            'payment_rate', 'payment_type'
        ]
        
        for field in profile_field_names:
            if field in validated_data:
                profile_fields[field] = validated_data.pop(field)
        
        # Generate random password
        password = self.generate_random_password()
        
        # Generate OTP secret and current OTP
        otp_secret = self.generate_otp_secret()
        otp = self.generate_otp(otp_secret)
        
        # Create user linked to fleet owner's company
        user = User.objects.create_user(
            email=validated_data['email'],
            phone_number=validated_data['phone_number'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=password,  # This becomes the temporary password
            role=User.Role.DRIVER,
            company=fleet_owner.company,
            is_active=False,  # Must verify via OTP or temp login
            is_verified=False,
            invited_by=fleet_owner,
            invitation_accepted=False
        )
        
        # Update driver profile with OTP and temp password info
        driver_profile = user.driver_profile
        for field, value in profile_fields.items():
            if value is not None:
                setattr(driver_profile, field, value)
        driver_profile.date_hired = timezone.now().date()
        driver_profile.otp_secret = otp_secret
        driver_profile.otp_generated_at = timezone.now()
        driver_profile.otp_attempts = 0
        # Set temporary password expiry to 24 hours from now
        driver_profile.temp_password_expires_at = timezone.now() + timezone.timedelta(hours=24)
        driver_profile.password_changed = False
        driver_profile.save()
        
        # Store credentials for email sending
        user._generated_password = password
        user._generated_otp = otp
        user._otp_secret = otp_secret
        
        return user
    
    def to_representation(self, instance):
        """Add generated credentials to response"""
        data = super().to_representation(instance)
        
        if hasattr(instance, '_generated_password'):
            data['generated_password'] = instance._generated_password
            data['generated_otp'] = instance._generated_otp
            data['otp_validity_minutes'] = 5
            data['temp_password_valid_hours'] = 24
        
        return data


# ============================================================================
# RESEND OTP
# ============================================================================

class ResendOTPSerializer(serializers.Serializer):
    """Serializer for resending OTP to a driver."""
    
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        """Validate email exists and is a pending driver"""
        try:
            user = User.objects.get(
                email=value.lower(), 
                role=User.Role.DRIVER,
                is_verified=False,
                is_active=False
            )
            self.user = user
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "No pending driver account found with this email. "
                "The account may already be verified or does not exist."
            )
        return value.lower()
    
    def save(self):
        """Generate new OTP and update driver profile"""
        user = self.user
        driver_profile = user.driver_profile
        
        # Generate new OTP
        otp_secret = pyotp.random_base32()
        otp = pyotp.TOTP(otp_secret, interval=300).now()
        
        # Store new OTP secret
        driver_profile.otp_secret = otp_secret
        driver_profile.otp_generated_at = timezone.now()
        driver_profile.otp_attempts = 0
        driver_profile.save()
        
        # Store credentials for email sending
        user._generated_otp = otp
        user._otp_secret = otp_secret
        
        return user


# ============================================================================
# DRIVER OTP VERIFICATION (Updated with dual flow)
# ============================================================================

class DriverOTPVerificationSerializer(serializers.Serializer):
    """
    Serializer for driver verification/login.
    Supports two flows:
    
    Flow 1 - OTP + New Password (first-time setup):
    {
        "email": "driver@example.com",
        "otp": "123456",
        "new_password": "MyNewPass123",
        "confirm_password": "MyNewPass123"
    }
    
    Flow 2 - Temporary Password Login (within 24hrs):
    {
        "email": "driver@example.com",
        "password": "temp_password_from_email",
        "is_temporary_login": true
    }
    """
    
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=False, max_length=6, allow_blank=True)
    password = serializers.CharField(
        required=False,
        style={'input_type': 'password'},
        write_only=True
    )
    new_password = serializers.CharField(
        required=False,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        required=False,
        style={'input_type': 'password'}
    )
    is_temporary_login = serializers.BooleanField(default=False)
    
    def validate_email(self, value):
        """Validate email exists and is a driver"""
        try:
            user = User.objects.get(
                email=value.lower(), 
                role=User.Role.DRIVER
            )
            self.user = user
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "No driver account found with this email."
            )
        return value.lower()
    
    def validate(self, data):
        """Validate based on verification method"""
        user = self.user
        
        # Case 1: OTP Verification (first-time setup)
        if data.get('otp'):
            return self._validate_otp_verification(data, user)
        
        # Case 2: Temporary password login
        elif data.get('is_temporary_login') and data.get('password'):
            return self._validate_temporary_login(data, user)
        
        # Case 3: Invalid combination
        else:
            raise serializers.ValidationError(
                "Please provide either an OTP with a new password, "
                "or use temporary login with your temporary password. "
                "Set 'is_temporary_login': true for temporary password login."
            )
    
    def _validate_otp_verification(self, data, user):
        """Validate OTP verification flow"""
        if not data.get('new_password') or not data.get('confirm_password'):
            raise serializers.ValidationError({
                "new_password": "New password is required for OTP verification."
            })
        
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        
        # Check if user is already verified
        if user.is_verified:
            raise serializers.ValidationError(
                "Account is already verified. Please use the login endpoint instead."
            )
        
        driver_profile = user.driver_profile
        otp_secret = getattr(driver_profile, 'otp_secret', None)
        
        if not otp_secret:
            raise serializers.ValidationError({
                "otp": "No OTP found. Please request a new OTP."
            })
        
        # Check OTP attempts
        if driver_profile.otp_attempts >= 5:
            raise serializers.ValidationError({
                "otp": "Too many failed OTP attempts. Please request a new OTP."
            })
        
        # Verify OTP
        totp = pyotp.TOTP(otp_secret, interval=300)
        if not totp.verify(data['otp']):
            driver_profile.otp_attempts += 1
            driver_profile.save(update_fields=['otp_attempts'])
            remaining = 5 - driver_profile.otp_attempts
            raise serializers.ValidationError({
                "otp": f"Invalid or expired OTP. {remaining} attempts remaining."
            })
        
        # Check if OTP is expired (10 minutes from generation)
        if driver_profile.otp_generated_at:
            otp_age = timezone.now() - driver_profile.otp_generated_at
            if otp_age.total_seconds() > 600:  # 10 minutes
                raise serializers.ValidationError({
                    "otp": "OTP has expired. Please request a new one."
                })
        
        return data
    
    def _validate_temporary_login(self, data, user):
        """Validate temporary password login"""
        # Check if user is already verified
        if user.is_verified:
            raise serializers.ValidationError(
                "Account is already verified. Please use the login endpoint instead."
            )
        
        # Check if temporary password is still valid (24 hours)
        driver_profile = user.driver_profile
        if driver_profile.temp_password_expires_at:
            if timezone.now() > driver_profile.temp_password_expires_at:
                raise serializers.ValidationError(
                    "Temporary password has expired (valid for 24 hours only). "
                    "Please use OTP verification instead."
                )
        else:
            raise serializers.ValidationError(
                "No temporary password found. Please use OTP verification instead."
            )
        
        # Verify temporary password
        if not user.check_password(data['password']):
            raise serializers.ValidationError({
                "password": "Invalid temporary password. Please check your email and try again."
            })
        
        return data
    
    def save(self):
        """Verify account and/or set new password"""
        user = self.user
        driver_profile = user.driver_profile
        
        # Case 1: OTP Verification - Set new password
        if self.validated_data.get('otp'):
            user.is_active = True
            user.is_verified = True
            user.invitation_accepted = True
            user.set_password(self.validated_data['new_password'])
            user.save()
            
            # Clear OTP data and temp password
            driver_profile.otp_secret = None
            driver_profile.otp_attempts = 0
            driver_profile.temp_password_expires_at = None
            driver_profile.password_changed = True
            driver_profile.save()
        
        # Case 2: Temporary login - Mark as verified, keep temp password
        elif self.validated_data.get('is_temporary_login'):
            user.is_active = True
            user.is_verified = True
            user.invitation_accepted = True
            user.save()
            
            # Clear OTP but keep temp password expiry
            driver_profile.otp_secret = None
            driver_profile.otp_attempts = 0
            # password_changed remains False
            driver_profile.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        refresh['email'] = user.email
        refresh['role'] = user.role
        refresh['is_verified'] = user.is_verified
        refresh['full_name'] = user.full_name
        
        if user.company:
            refresh['company_id'] = str(user.company.id)
            refresh['company_name'] = user.company.name
        
        user._tokens = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        
        return user


# ============================================================================
# AUTHENTICATION
# ============================================================================

class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        style={'input_type': 'password'},
        write_only=True
    )
    
    def validate(self, data):
        """Validate credentials"""
        email = data.get('email', '').lower()
        password = data.get('password', '')
        
        if email and password:
            user = authenticate(
                request=self.context.get('request'), 
                email=email, 
                password=password
            )
            
            if not user:
                raise serializers.ValidationError(
                    "Invalid email or password.",
                    code='authentication_failed'
                )
            
            if not user.is_active:
                raise serializers.ValidationError(
                    "Account is not active. Please verify your account first.",
                    code='account_inactive'
                )
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            refresh['email'] = user.email
            refresh['role'] = user.role
            refresh['is_verified'] = user.is_verified
            refresh['full_name'] = user.full_name
            
            if user.company:
                refresh['company_id'] = str(user.company.id)
                refresh['company_name'] = user.company.name
            
            self.user = user
            self._tokens = {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        else:
            raise serializers.ValidationError(
                "Must include 'email' and 'password'.",
                code='missing_fields'
            )
        
        return data


# ============================================================================
# USER/PROFILE SERIALIZERS
# ============================================================================

class UserSerializer(serializers.ModelSerializer):
    """Base user serializer"""
    
    avatar_url = serializers.SerializerMethodField()
    full_name = serializers.ReadOnlyField()
    company_id = serializers.CharField(source='company.id', read_only=True, default=None)
    company_name = serializers.CharField(source='company.name', read_only=True, default=None)
    has_company = serializers.SerializerMethodField()
    driver_profile_id = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone_number', 'first_name', 'last_name',
            'full_name', 'role', 'avatar', 'avatar_url', 'is_verified',
            'is_active', 'date_joined', 'last_login',
            'company_id', 'company_name', 'has_company', 'driver_profile_id',
        ]
        read_only_fields = [
            'id', 'email', 'role', 'is_verified', 'is_active',
            'date_joined', 'last_login', 'company_id', 'company_name'
        ]
    
    def get_avatar_url(self, obj):
        return obj.get_avatar_url(self.context.get('request'))
    
    def get_has_company(self, obj):
        if obj.company_id:
            return True
        if obj.role == obj.Role.FLEET_OWNER:
            return Company.objects.filter(owner=obj).exists()
        return False

    def get_driver_profile_id(self, obj):
        if obj.role != obj.Role.DRIVER:
            return None
        profile = getattr(obj, 'driver_profile', None)
        return str(profile.id) if profile else None


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile"""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'avatar']
    
    def validate_avatar(self, value):
        if value:
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("Avatar file size cannot exceed 5MB.")
            allowed_types = ['image/jpeg', 'image/png', 'image/webp']
            if hasattr(value, 'content_type') and value.content_type not in allowed_types:
                raise serializers.ValidationError("Unsupported file type. Allowed: JPG, PNG, WebP")
        return value
    
    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exclude(id=self.instance.id).exists():
            raise serializers.ValidationError("This phone number is already in use.")
        return value


class DriverProfileSerializer(serializers.ModelSerializer):
    """Serializer for driver profile"""
    
    user = UserSerializer(read_only=True)
    is_license_expired = serializers.BooleanField(read_only=True)
    completion_rate = serializers.FloatField(read_only=True)
    
    class Meta:
        model = DriverProfile
        fields = [
            'user', 'date_of_birth', 'address',
            'emergency_contact_name', 'emergency_contact_phone',
            'drivers_license_number', 'license_type',
            'license_expiry_date', 'license_issuing_country',
            'employment_status', 'date_hired', 'employee_id',
            'payment_rate', 'payment_type',
            'bank_account_number', 'bank_name',
            'max_daily_hours', 'max_weekly_hours',
            'total_trips', 'completed_trips',
            'on_time_percentage', 'average_rating',
            'is_active', 'is_available',
            'is_license_expired', 'completion_rate'
        ]
        read_only_fields = [
            'user', 'total_trips', 'completed_trips',
            'on_time_percentage', 'average_rating',
            'is_license_expired', 'completion_rate'
        ]


class DriverProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating driver profile"""
    
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    phone_number = serializers.CharField(source='user.phone_number', required=False)
    avatar = serializers.ImageField(source='user.avatar', required=False)
    
    class Meta:
        model = DriverProfile
        fields = [
            'first_name', 'last_name', 'phone_number', 'avatar',
            'date_of_birth', 'address',
            'emergency_contact_name', 'emergency_contact_phone',
            'bank_account_number', 'bank_name'
        ]
    
    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        user = instance.user
        for field, value in user_data.items():
            setattr(user, field, value)
        user.save()
        
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        
        return instance


class FleetOwnerProfileSerializer(serializers.ModelSerializer):
    """Serializer for fleet owner profile"""
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = FleetOwnerProfile
        fields = [
            'user', 'company_name', 'business_registration_number',
            'tax_id', 'business_address', 'business_phone', 'website',
            'preferred_currency', 'timezone', 'notification_preferences',
            'total_vehicles', 'active_drivers'
        ]
        read_only_fields = ['user', 'total_vehicles', 'active_drivers']


# ============================================================================
# KYC DOCUMENTS
# ============================================================================

class KYCDocumentSerializer(serializers.ModelSerializer):
    """Serializer for KYC documents"""
    
    driver_name = serializers.CharField(source='driver.user.full_name', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.full_name', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = KYCDocument
        fields = [
            'id', 'driver', 'driver_name', 'document_type',
            'document_number', 'issuing_country', 'issuing_authority',
            'front_image', 'back_image', 'issue_date', 'expiry_date',
            'verification_status', 'verified_by', 'verified_by_name',
            'verification_date', 'rejection_reason',
            'uploaded_at', 'updated_at', 'is_expired'
        ]
        read_only_fields = [
            'id', 'driver_name', 'verification_status',
            'verified_by', 'verified_by_name', 'verification_date',
            'uploaded_at', 'updated_at', 'is_expired'
        ]
    
    def validate_front_image(self, value):
        if value and value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 10MB.")
        return value
    
    def validate_back_image(self, value):
        if value and value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 10MB.")
        return value


class KYCDocumentVerificationSerializer(serializers.Serializer):
    """Serializer for KYC document verification"""
    
    verification_status = serializers.ChoiceField(choices=['VERIFIED', 'REJECTED'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        if data['verification_status'] == 'REJECTED' and not data.get('rejection_reason'):
            raise serializers.ValidationError({
                "rejection_reason": "Rejection reason is required when rejecting."
            })
        return data


class CompanySerializer(serializers.ModelSerializer):
    """Serializer for company"""
    
    owner = UserSerializer(read_only=True)
    total_drivers = serializers.SerializerMethodField()
    total_vehicles = serializers.SerializerMethodField()
    
    class Meta:
        model = Company
        fields = [
            'id', 'name', 'logo', 'registration_number',
            'address', 'contact_email', 'contact_phone',
            'is_active', 'subscription_plan', 'owner',
            'total_drivers', 'total_vehicles',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']
    
    def get_total_drivers(self, obj):
        return obj.users.filter(role=User.Role.DRIVER).count()
    
    def get_total_vehicles(self, obj):
        return obj.vehicles.count() if hasattr(obj, 'vehicles') else 0


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change"""
    
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    confirm_password = serializers.CharField(required=True)
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "New passwords do not match."})
        return data
    
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        
        # Mark password as changed for drivers
        if user.is_driver:
            driver_profile = user.driver_profile
            driver_profile.password_changed = True
            driver_profile.temp_password_expires_at = None
            driver_profile.save(update_fields=['password_changed', 'temp_password_expires_at'])
        
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        try:
            user = User.objects.get(email=value.lower())
            self.user = user
        except User.DoesNotExist:
            pass
        return value.lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    confirm_password = serializers.CharField(required=True)
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return data


class TokenRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)
    
    def validate(self, data):
        try:
            refresh = RefreshToken(data['refresh'])
            data['access'] = str(refresh.access_token)
            data['refresh'] = str(refresh)
        except Exception:
            raise serializers.ValidationError({"refresh": "Invalid or expired refresh token."})
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)
    
    def validate(self, data):
        try:
            token = RefreshToken(data['refresh'])
            token.blacklist()
        except Exception:
            raise serializers.ValidationError({"refresh": "Invalid or expired refresh token."})
        return data