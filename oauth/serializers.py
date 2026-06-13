# serializers.py
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import check_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.contrib.auth import authenticate
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from .models import (
    User, DriverProfile, FleetOwnerProfile,
    EmailAuthCode, PendingFleetOwnerSignup,
)
from . import pending_signup
from . import auth_codes
from .phone_utils import normalize_phone_number, phone_number_lookup_variants
import pyotp
import random
import string
import uuid


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
    """Custom JWT token serializer with role and fleet-owner claims."""
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['email'] = user.email
        token['role'] = user.role
        token['is_verified'] = user.is_verified
        token['full_name'] = user.full_name
        
        if user.fleet_owner_id:
            token['fleet_owner_id'] = str(user.fleet_owner_id)
        
        return token
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add extra response data
        data['user'] = UserSerializer(self.user, context={'request': self.context.get('request')}).data
        data['role'] = self.user.role
        data['is_verified'] = self.user.is_verified
        
        # Determine redirect URL based on role.
        if self.user.is_platform_admin:
            data['redirect_url'] = '/dashboard'
        elif self.user.is_fleet_owner:
            data['redirect_url'] = '/fleet-owner/dashboard'
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

class FleetOwnerRegistrationSerializer(serializers.ModelSerializer):
    """
    Step 1: Collect signup data; User is created only after email OTP verification.
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )
    preferred_currency = serializers.CharField(max_length=3, default='USD')

    class Meta:
        model = PendingFleetOwnerSignup
        fields = [
            'email', 'phone_number', 'first_name', 'last_name',
            'preferred_currency', 'password', 'confirm_password',
        ]

    def validate_email(self, value):
        email = value.lower()
        if User.objects.filter(email=email, is_verified=True).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return email

    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value, is_verified=True).exists():
            raise serializers.ValidationError('A user with this phone number already exists.')
        return value

    def validate_preferred_currency(self, value):
        currency = value.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise serializers.ValidationError('Currency must be a valid 3-letter ISO currency code.')
        return currency

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        from django.contrib.auth.hashers import make_password

        validated_data.pop('confirm_password')
        email = validated_data['email'].lower()
        plain_password = validated_data.pop('password')

        User.objects.filter(
            email=email,
            role=User.Role.FLEET_OWNER,
            is_verified=False,
        ).delete()

        pending, _created = PendingFleetOwnerSignup.objects.update_or_create(
            email=email,
            defaults={
                'phone_number': validated_data['phone_number'],
                'first_name': validated_data['first_name'],
                'last_name': validated_data['last_name'],
                'preferred_currency': validated_data.get('preferred_currency', 'USD'),
                'password': make_password(plain_password),
            },
        )
        return pending


# ============================================================================
# COMPANY REGISTRATION (Step 2 - After Fleet Owner Account)
# ============================================================================

class CompanyRegistrationSerializer(serializers.Serializer):
    """Compatibility serializer: stores fleet business details on FleetOwnerProfile."""

    name = serializers.CharField(max_length=200)
    registration_number = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(required=False, allow_blank=True)
    logo = serializers.ImageField(required=False)

    def save(self, **kwargs):
        user = self.context['request'].user
        profile, _ = FleetOwnerProfile.objects.get_or_create(user=user)
        data = self.validated_data
        profile.company_name = data.get('name', profile.company_name)
        profile.business_registration_number = data.get('registration_number', '') or ''
        profile.business_address = data.get('address', '') or ''
        profile.business_phone = data.get('contact_phone', '') or ''
        profile.save()
        user._profile_company_payload = {
            'id': str(user.id),
            'name': profile.company_name,
            'registration_number': profile.business_registration_number,
            'address': profile.business_address,
            'contact_email': data.get('contact_email') or user.email,
            'contact_phone': profile.business_phone,
            'owner': str(user.id),
        }
        return user


class CompanyUpdateSerializer(CompanyRegistrationSerializer):
    name = serializers.CharField(max_length=200, required=False)


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
        choices=DriverProfile.PaymentType.choices,
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
        
        # Create user linked to fleet owner.
        user = User.objects.create_user(
            email=validated_data['email'],
            phone_number=validated_data['phone_number'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=password,  # This becomes the temporary password
            role=User.Role.DRIVER,
            fleet_owner=fleet_owner,
            is_active=False,  # Must verify via OTP or temp login
            is_verified=False,
            invited_by=fleet_owner,
            invitation_accepted=False
        )
        
        # Update driver profile with OTP and temp password info
        driver_profile = user.driver_profile
        driver_profile.fleet_owner = fleet_owner
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


def _placeholder_driver_email(fleet_owner_id, phone_number: str) -> str:
    """Internal-only email when fleet owner adds a driver without an address."""
    digits = ''.join(c for c in phone_number if c.isdigit()) or uuid.uuid4().hex[:10]
    candidate = f'driver.{fleet_owner_id}.{digits}@fleetvault.internal'
    n = 0
    while User.objects.filter(email=candidate).exists():
        n += 1
        candidate = f'driver.{fleet_owner_id}.{digits}.{n}@fleetvault.internal'
    return candidate


class DriverCreateSerializer(serializers.Serializer):
    """
    Fleet owner adds a driver to the fleet (no invite / no driver-app login).
    Mirrors adding a vehicle: record-only for owner operations.
    """

    phone_number = serializers.CharField(max_length=20)
    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50)
    email = serializers.EmailField(required=False, allow_blank=True)
    drivers_license_number = serializers.CharField(
        required=False, allow_blank=True, max_length=50
    )
    employment_status = serializers.ChoiceField(
        choices=DriverProfile.EmploymentStatus.choices,
        required=False,
    )
    payment_rate = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    payment_type = serializers.ChoiceField(choices=DriverProfile.PaymentType.choices, required=False)

    def validate_phone_number(self, value):
        request = self.context.get('request')
        fleet_owner = request.user if request else None
        normalized = normalize_phone_number(value)
        variants = phone_number_lookup_variants(value)
        existing = User.objects.filter(phone_number__in=variants).first()
        if not existing:
            return normalized

        if existing.role == User.Role.DRIVER and existing.fleet_owner_id is None:
            self._claim_existing_user = existing
            return normalized

        if (
            existing.role == User.Role.DRIVER
            and fleet_owner is not None
            and existing.fleet_owner_id == fleet_owner.id
        ):
            raise serializers.ValidationError('This driver is already in your fleet.')

        raise serializers.ValidationError('A user with this phone number already exists.')

    def validate_email(self, value):
        if not value or not str(value).strip():
            return ''
        normalized = value.lower().strip()
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return normalized

    def validate_drivers_license_number(self, value):
        if not value or not str(value).strip():
            return None
        license_number = value.strip()
        request = self.context.get('request')
        fleet_owner = request.user if request else None
        qs = DriverProfile.objects.filter(drivers_license_number=license_number)
        claim_user = getattr(self, '_claim_existing_user', None)
        if claim_user:
            qs = qs.exclude(user_id=claim_user.id)
        if not qs.exists():
            return license_number
        if fleet_owner and qs.filter(fleet_owner=fleet_owner).exists():
            raise serializers.ValidationError(
                'A driver with this license number already exists in your fleet.'
            )
        raise serializers.ValidationError(
            'A driver with this license number is already registered. Use a different number.'
        )

    @transaction.atomic
    def create(self, validated_data):
        request = self.context['request']
        fleet_owner = request.user

        claim_user = getattr(self, '_claim_existing_user', None)
        if claim_user:
            user = claim_user
            user.fleet_owner = fleet_owner
            user.first_name = validated_data['first_name']
            user.last_name = validated_data['last_name']
            user.phone_number = validated_data['phone_number']
            user.is_active = True
            user.is_verified = True
            user.invited_by = fleet_owner
            user.invitation_accepted = True
            user.save(
                update_fields=[
                    'fleet_owner',
                    'first_name',
                    'last_name',
                    'phone_number',
                    'is_active',
                    'is_verified',
                    'invited_by',
                    'invitation_accepted',
                ]
            )
        else:
            email = validated_data.get('email') or ''
            if not email:
                email = _placeholder_driver_email(fleet_owner.id, validated_data['phone_number'])

            user = User(
                email=email,
                phone_number=validated_data['phone_number'],
                first_name=validated_data['first_name'],
                last_name=validated_data['last_name'],
                role=User.Role.DRIVER,
                fleet_owner=fleet_owner,
                is_active=True,
                is_verified=True,
                invited_by=fleet_owner,
                invitation_accepted=True,
            )
            user.set_unusable_password()
            user.save()

        profile = user.driver_profile
        profile.fleet_owner = fleet_owner
        license_number = validated_data.get('drivers_license_number')
        if license_number:
            profile.drivers_license_number = license_number
        employment_status = validated_data.get('employment_status')
        if employment_status:
            profile.employment_status = employment_status
        if 'payment_rate' in validated_data:
            profile.payment_rate = validated_data['payment_rate']
        if 'payment_type' in validated_data:
            profile.payment_type = validated_data['payment_type']
        profile.date_hired = timezone.now().date()
        profile.save()
        DriverProfile.objects.get_or_create(user=user)

        return user


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
        
        if user.fleet_owner_id:
            refresh['fleet_owner_id'] = str(user.fleet_owner_id)
        
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
                username=email,
                password=password,
            )

            # Fallback when backends return None (e.g. Mongo/email edge cases).
            if user is None:
                try:
                    candidate = User.objects.get(email=email)
                except User.DoesNotExist:
                    candidate = None
                if candidate and candidate.check_password(password):
                    user = candidate

            if not user:
                raise serializers.ValidationError(
                    "Invalid email or password.",
                    code='authentication_failed',
                )

            if not user.is_active:
                raise serializers.ValidationError(
                    "Account is not active. Please verify your email with the OTP we sent.",
                    code='account_inactive'
                )

            if (
                user.is_fleet_owner
                and not user.is_platform_admin
                and not user.is_verified
            ):
                raise serializers.ValidationError(
                    "Please verify your email before signing in.",
                    code='email_not_verified',
                )

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            refresh['email'] = user.email
            refresh['role'] = user.role
            refresh['is_verified'] = user.is_verified
            refresh['full_name'] = user.full_name
            
            if user.fleet_owner_id:
                refresh['fleet_owner_id'] = str(user.fleet_owner_id)
            
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


class FleetOwnerLoginSerializer(UserLoginSerializer):
    """Fleet owner / driver sign-in at /users/api/auth/login/ — not platform admins."""

    def validate(self, data):
        super().validate(data)
        if self.user.is_platform_admin:
            raise serializers.ValidationError(
                'Platform administrators must use the platform sign-in page.',
                code='wrong_portal',
            )
        return data


# ============================================================================
# USER/PROFILE SERIALIZERS
# ============================================================================

def serialize_user_for_api(user: User, request=None) -> dict:
    """Build a JSON-safe user dict."""
    fleet_owner_id = user.id if user.is_fleet_owner else user.fleet_owner_id
    business_name = None
    preferred_currency = 'USD'
    owner = user if user.is_fleet_owner else getattr(user, 'fleet_owner', None)
    if owner:
        try:
            profile = owner.fleet_owner_profile
            business_name = profile.company_name
            preferred_currency = profile.preferred_currency
        except (ObjectDoesNotExist, AttributeError, FleetOwnerProfile.DoesNotExist):
            business_name = owner.get_full_name()

    avatar_value = None
    if user.avatar and str(user.avatar).strip():
        try:
            avatar_value = user.avatar.name
        except (ValueError, AttributeError):
            avatar_value = str(user.avatar)

    driver_profile_id = None
    if user.role == User.Role.DRIVER:
        try:
            driver_profile_id = str(user.driver_profile.id)
        except (ObjectDoesNotExist, AttributeError, DriverProfile.DoesNotExist):
            # DriverProfile PK is the user id; assignment APIs still need a stable id.
            driver_profile_id = str(user.pk)

    return {
        'id': str(user.pk),
        'email': user.email,
        'phone_number': user.phone_number,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'full_name': user.get_full_name(),
        'role': user.role,
        'avatar': avatar_value,
        'avatar_url': user.get_avatar_url(request),
        'is_verified': user.is_verified,
        'is_active': user.is_active,
        'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        'last_login': user.last_login.isoformat() if user.last_login else None,
        'fleet_owner_id': str(fleet_owner_id) if fleet_owner_id else None,
        'company_id': str(fleet_owner_id) if fleet_owner_id else None,
        'company_name': business_name,
        'preferred_currency': preferred_currency,
        'has_company': bool(fleet_owner_id),
        'driver_profile_id': driver_profile_id,
    }


class UserSerializer(serializers.ModelSerializer):
    """Base user serializer"""
    
    avatar = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    full_name = serializers.ReadOnlyField()
    company_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    preferred_currency = serializers.SerializerMethodField()
    has_company = serializers.SerializerMethodField()
    driver_profile_id = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone_number', 'first_name', 'last_name',
            'full_name', 'role', 'avatar', 'avatar_url', 'is_verified',
            'is_active', 'date_joined', 'last_login',
            'company_id', 'company_name', 'preferred_currency', 'has_company', 'driver_profile_id',
        ]
        read_only_fields = [
            'id', 'email', 'role', 'is_verified', 'is_active',
            'date_joined', 'last_login', 'company_id', 'company_name',
            'preferred_currency',
        ]

    def to_representation(self, instance):
        return serialize_user_for_api(instance, self.context.get('request'))
    
    def get_avatar(self, obj):
        if not obj.avatar or not str(obj.avatar).strip():
            return None
        try:
            return obj.avatar.name
        except (ValueError, AttributeError):
            return None

    def get_avatar_url(self, obj):
        return obj.get_avatar_url(self.context.get('request'))
    
    def get_company_id(self, obj):
        owner_id = obj.id if obj.is_fleet_owner else obj.fleet_owner_id
        return str(owner_id) if owner_id else None

    def get_company_name(self, obj):
        owner = obj if obj.is_fleet_owner else getattr(obj, 'fleet_owner', None)
        if not owner:
            return None
        try:
            return owner.fleet_owner_profile.company_name or owner.get_full_name()
        except (ObjectDoesNotExist, AttributeError, FleetOwnerProfile.DoesNotExist):
            return owner.get_full_name()

    def get_preferred_currency(self, obj):
        owner = obj if obj.is_fleet_owner else getattr(obj, 'fleet_owner', None)
        if not owner:
            return 'USD'
        try:
            return owner.fleet_owner_profile.preferred_currency
        except (ObjectDoesNotExist, AttributeError, FleetOwnerProfile.DoesNotExist):
            return 'USD'

    def get_has_company(self, obj):
        return bool(obj.is_fleet_owner or obj.fleet_owner_id)

    def get_driver_profile_id(self, obj):
        if obj.role != obj.Role.DRIVER:
            return None
        try:
            return str(obj.driver_profile.id)
        except (ObjectDoesNotExist, AttributeError, DriverProfile.DoesNotExist):
            return str(obj.pk)


class UserListSerializer(serializers.Serializer):
    """Compact user row for owner/admin list pages."""

    def to_representation(self, user):
        owner = user if user.is_fleet_owner else getattr(user, 'fleet_owner', None)
        company_name = None
        preferred_currency = 'USD'
        if owner:
            try:
                profile = owner.fleet_owner_profile
                company_name = profile.company_name or owner.get_full_name()
                preferred_currency = profile.preferred_currency
            except (ObjectDoesNotExist, AttributeError, FleetOwnerProfile.DoesNotExist):
                company_name = owner.get_full_name()
        driver_profile_id = None
        if user.role == User.Role.DRIVER:
            try:
                driver_profile_id = str(user.driver_profile.id)
            except (ObjectDoesNotExist, AttributeError, DriverProfile.DoesNotExist):
                driver_profile_id = str(user.pk)

        return {
            'id': str(user.pk),
            'email': user.email,
            'phone_number': user.phone_number,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.get_full_name(),
            'role': user.role,
            'avatar': None,
            'avatar_url': None,
            'is_verified': user.is_verified,
            'is_active': user.is_active,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'company_id': str(owner.id) if owner else None,
            'company_name': company_name,
            'preferred_currency': preferred_currency,
            'has_company': bool(owner),
            'driver_profile_id': driver_profile_id,
        }


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile"""

    preferred_currency = serializers.CharField(required=False, max_length=3)
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'avatar', 'preferred_currency']
    
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

    def validate_preferred_currency(self, value):
        currency = value.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise serializers.ValidationError("Currency must be a valid 3-letter ISO currency code.")
        return currency

    def update(self, instance, validated_data):
        preferred_currency = validated_data.pop('preferred_currency', None)
        user = super().update(instance, validated_data)

        if preferred_currency is not None:
            if not user.is_fleet_owner:
                raise serializers.ValidationError({
                    'preferred_currency': 'Only fleet owners can update account currency.',
                })
            FleetOwnerProfile.objects.update_or_create(
                user=user,
                defaults={'preferred_currency': preferred_currency},
            )

        return user


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
            'payment_rate', 'payment_type',
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


class CompanySerializer(serializers.Serializer):
    """Compatibility shape backed by FleetOwnerProfile, not a companies table."""

    def to_representation(self, owner):
        if hasattr(owner, '_profile_company_payload'):
            return owner._profile_company_payload
        profile, _ = FleetOwnerProfile.objects.get_or_create(user=owner)
        return {
            'id': str(owner.id),
            'name': profile.company_name or owner.get_full_name(),
            'logo': None,
            'registration_number': profile.business_registration_number,
            'address': profile.business_address,
            'contact_email': owner.email,
            'contact_phone': profile.business_phone or owner.phone_number,
            'is_active': owner.is_active,
            'subscription_plan': owner.subscription_plan,
            'owner': UserSerializer(owner).data,
            'billing_status': owner.billing_status,
            'trial_ends_at': owner.trial_ends_at,
            'billing_quantity': owner.billing_quantity,
            'total_drivers': owner.driver_profiles.count(),
            'total_vehicles': owner.vehicles.count(),
            'created_at': owner.date_joined,
            'updated_at': owner.updated_at,
        }


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


class SignupVerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)

    def validate_email(self, value):
        email = value.lower()
        try:
            self.pending = PendingFleetOwnerSignup.objects.get(email=email)
            self.legacy_user = None
            return email
        except PendingFleetOwnerSignup.DoesNotExist:
            pass
        try:
            self.legacy_user = User.objects.get(
                email=email,
                role=User.Role.FLEET_OWNER,
                is_verified=False,
            )
            self.pending = None
            return email
        except User.DoesNotExist:
            raise serializers.ValidationError(
                'No pending signup found for this email. It may already be verified.',
            )

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('OTP must be a 6-digit number.')
        return value

    def validate(self, data):
        if self.pending is not None:
            ok, err = pending_signup.verify_code(self.pending, data['otp'])
        else:
            ok, err = auth_codes.verify_code(
                self.legacy_user,
                EmailAuthCode.Purpose.SIGNUP_VERIFY,
                data['otp'],
            )
        if not ok:
            raise serializers.ValidationError({'otp': err})
        return data

    def save(self):
        if self.pending is not None:
            pending = self.pending
            user = User(
                email=pending.email,
                phone_number=pending.phone_number,
                first_name=pending.first_name,
                last_name=pending.last_name,
                role=User.Role.FLEET_OWNER,
                is_active=True,
                is_verified=True,
            )
            user.password = pending.password
            user.save()
            FleetOwnerProfile.objects.update_or_create(
                user=user,
                defaults={'preferred_currency': pending.preferred_currency},
            )
            pending.delete()
            return user

        user = self.legacy_user
        user.is_active = True
        user.is_verified = True
        user.save(update_fields=['is_active', 'is_verified'])
        auth_codes.clear_code(user, EmailAuthCode.Purpose.SIGNUP_VERIFY)
        return user


class SignupResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        email = value.lower()
        try:
            self.pending = PendingFleetOwnerSignup.objects.get(email=email)
            self.legacy_user = None
            return email
        except PendingFleetOwnerSignup.DoesNotExist:
            pass
        try:
            self.legacy_user = User.objects.get(
                email=email,
                role=User.Role.FLEET_OWNER,
                is_verified=False,
            )
            self.pending = None
            return email
        except User.DoesNotExist:
            raise serializers.ValidationError('No pending signup found for this email.')

    def validate(self, data):
        if self.pending is not None:
            if not pending_signup.can_resend(self.pending):
                remaining = pending_signup.resend_cooldown_remaining(self.pending)
                raise serializers.ValidationError({
                    'non_field_errors': [
                        f'Please wait {remaining} seconds before requesting another OTP.',
                    ],
                    'cooldown_seconds': remaining,
                })
        elif not auth_codes.can_resend(self.legacy_user, EmailAuthCode.Purpose.SIGNUP_VERIFY):
            remaining = auth_codes.resend_cooldown_remaining(
                self.legacy_user, EmailAuthCode.Purpose.SIGNUP_VERIFY,
            )
            raise serializers.ValidationError({
                'non_field_errors': [
                    f'Please wait {remaining} seconds before requesting another OTP.',
                ],
                'cooldown_seconds': remaining,
            })
        return data

    def save(self):
        if self.pending is not None:
            plain = pending_signup.issue_code(self.pending)
            self._issued_otp = plain
            self._recipient_email = self.pending.email
            self._first_name = self.pending.first_name
            return self.pending
        plain = auth_codes.issue_code(self.legacy_user, EmailAuthCode.Purpose.SIGNUP_VERIFY)
        self._issued_otp = plain
        self._recipient_email = self.legacy_user.email
        self._first_name = self.legacy_user.first_name
        return self.legacy_user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        email = value.lower()
        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            self.user = None
            return email

        if not auth_codes.can_resend(user, EmailAuthCode.Purpose.PASSWORD_RESET):
            remaining = auth_codes.resend_cooldown_remaining(
                user, EmailAuthCode.Purpose.PASSWORD_RESET
            )
            raise serializers.ValidationError({
                'non_field_errors': [
                    f'Please wait {remaining} seconds before requesting another code.',
                ],
                'cooldown_seconds': remaining,
            })
        self.user = user
        return email

    def save(self):
        user = getattr(self, 'user', None)
        if not user:
            return None
        plain = auth_codes.issue_code(user, EmailAuthCode.Purpose.PASSWORD_RESET)
        user._issued_reset_code = plain
        return user


class PasswordResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(required=True, min_length=6, max_length=6)

    def validate(self, data):
        email = data['email'].lower()
        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError({'email': 'Invalid email or code.'})

        if not data['code'].isdigit():
            raise serializers.ValidationError({'code': 'Code must be a 6-digit number.'})

        ok, err = auth_codes.verify_code(
            user,
            EmailAuthCode.Purpose.PASSWORD_RESET,
            data['code'],
        )
        if not ok:
            raise serializers.ValidationError({'code': err})

        self.user = user
        data['email'] = email
        return data


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(required=True, min_length=6, max_length=6)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    confirm_password = serializers.CharField(required=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})

        email = data['email'].lower()
        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError({'code': 'Invalid email or code.'})

        if not data['code'].isdigit():
            raise serializers.ValidationError({'code': 'Code must be a 6-digit number.'})

        ok, err = auth_codes.verify_code(
            user,
            EmailAuthCode.Purpose.PASSWORD_RESET,
            data['code'],
        )
        if not ok:
            raise serializers.ValidationError({'code': err})

        if check_password(data['new_password'], user.password):
            raise serializers.ValidationError({
                'new_password': 'New password cannot be the same as your current password.',
            })

        self.user = user
        data['email'] = email
        return data

    def save(self):
        user = self.user
        user.set_password(self.validated_data['new_password'])
        user.save()
        auth_codes.clear_code(user, EmailAuthCode.Purpose.PASSWORD_RESET)
        if user.is_driver:
            driver_profile = user.driver_profile
            driver_profile.password_changed = True
            driver_profile.temp_password_expires_at = None
            driver_profile.save(update_fields=['password_changed', 'temp_password_expires_at'])
        return user


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