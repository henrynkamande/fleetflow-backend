# views.py
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
import logging

from .models import User, DriverProfile, FleetOwnerProfile, KYCDocument, Company
from .serializers import (
    FleetOwnerRegistrationSerializer,
    CompanyRegistrationSerializer,
    CompanyUpdateSerializer,
    DriverOnboardingSerializer,
    ResendOTPSerializer,
    DriverOTPVerificationSerializer,
    UserLoginSerializer,
    UserSerializer,
    UserUpdateSerializer,
    DriverProfileSerializer,
    DriverProfileUpdateSerializer,
    FleetOwnerProfileSerializer,
    KYCDocumentSerializer,
    KYCDocumentVerificationSerializer,
    PasswordChangeSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    TokenRefreshSerializer,
    LogoutSerializer,
    CustomTokenObtainPairSerializer,
    CompanySerializer,
)

logger = logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def send_welcome_email(user):
    """Send welcome email to fleet owner."""
    subject = 'Welcome to Fleet Flow!'
    message = f"""
    Hi {user.first_name},
    
    Welcome to Fleet Flow! Your fleet owner account has been created successfully.
    
    Next step: Register your company to start managing your fleet.
    
    Best regards,
    Fleet Flow Team
    """
    
    try:
        send_mail(
            subject, message, settings.DEFAULT_FROM_EMAIL,
            [user.email], fail_silently=True,
        )
        logger.info(f"Welcome email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
        return False


def send_company_registration_email(user, company):
    """Send company registration confirmation email."""
    subject = 'Company Registered - Fleet Flow'
    message = f"""
    Hi {user.first_name},
    
    Your company "{company.name}" has been registered successfully on Fleet Flow.
    
    You can now:
    - Onboard drivers to your company
    - Add vehicles to your fleet
    - Start managing your operations
    
    Best regards,
    Fleet Flow Team
    """
    
    try:
        send_mail(
            subject, message, settings.DEFAULT_FROM_EMAIL,
            [user.email], fail_silently=True,
        )
        logger.info(f"Company registration email sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send company registration email: {str(e)}")
        return False


def send_onboarding_email(driver, password=None, otp=None):
    """Send onboarding email with credentials and OTP."""
    company_name = driver.company.name if driver.company else "Fleet Flow"
    invited_by_name = driver.invited_by.full_name if driver.invited_by else "Fleet Flow"
    
    subject = f'Welcome to {company_name} - Verify Your Account'
    
    message = f"""
    Hi {driver.first_name},
    
    You have been added to {company_name} on Fleet Flow by {invited_by_name}.
    """
    
    # Add OTP option if provided
    if otp:
        message += f"""
    OPTION 1 - Verify with OTP (Recommended):
    Your OTP for account verification: {otp}
    This OTP is valid for 5 minutes.
    You will be prompted to set your own password after verification.
    """
    
    # Add temporary password option if provided
    if password:
        message += f"""
    OPTION 2 - Login with Temporary Password:
    Email: {driver.email}
    Temporary Password: {password}
    This password is valid for 24 hours only.
    You must change your password within 24 hours.
    """
    
    message += """
    Please verify your account immediately using either option above.
    
    Best regards,
    Fleet Flow Team
    """
    
    try:
        send_mail(
            subject, message, settings.DEFAULT_FROM_EMAIL,
            [driver.email], fail_silently=True,
        )
        logger.info(f"Onboarding email sent to {driver.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send onboarding email to {driver.email}: {str(e)}")
        return False


def send_otp_resend_email(driver, otp):
    """Send OTP resend email."""
    company_name = driver.company.name if driver.company else "Fleet Flow"
    
    subject = f'{company_name} - New OTP for Account Verification'
    message = f"""
    Hi {driver.first_name},
    
    You requested a new OTP for your Fleet Flow account.
    
    Your new OTP: {otp}
    This OTP is valid for 5 minutes.
    
    Your temporary password is still valid for login if you prefer.
    
    Best regards,
    Fleet Flow Team
    """
    
    try:
        send_mail(
            subject, message, settings.DEFAULT_FROM_EMAIL,
            [driver.email], fail_silently=True,
        )
        logger.info(f"OTP resend email sent to {driver.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP resend email: {str(e)}")
        return False


def send_verification_confirmation(user):
    """Send verification confirmation email."""
    subject = 'Account Verified - Fleet Flow'
    message = f"""
    Hi {user.first_name},
    
    Your Fleet Flow account has been verified successfully.
    You can now login and start using the app.
    
    Best regards,
    Fleet Flow Team
    """
    
    try:
        send_mail(
            subject, message, settings.DEFAULT_FROM_EMAIL,
            [user.email], fail_silently=True,
        )
        logger.info(f"Verification confirmation sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification confirmation to {user.email}: {str(e)}")
        return False


def get_tokens_for_user(user):
    """Generate JWT tokens for a user with custom claims."""
    refresh = RefreshToken.for_user(user)
    
    # Add custom claims
    refresh['email'] = user.email
    refresh['role'] = user.role
    refresh['is_verified'] = user.is_verified
    refresh['full_name'] = user.full_name
    
    if user.company:
        refresh['company_id'] = str(user.company.id)
        refresh['company_name'] = user.company.name
    
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def register_fleet_owner(request):
    """
    Step 1: Register a fleet owner account.
    After registration, fleet owner must register a company.
    """
    serializer = FleetOwnerRegistrationSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.save()
        
        # Generate JWT tokens
        tokens = get_tokens_for_user(user)
        
        # Send welcome email
        send_welcome_email(user)
        
        logger.info(f"New fleet owner registered: {user.email}")
        
        return Response({
            'message': 'Registration successful. Please register your company to continue.',
            'user': UserSerializer(user, context={'request': request}).data,
            'tokens': tokens,
            'next_step': 'register_company',
            'requires_company': True
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """Login user and return JWT tokens."""
    serializer = UserLoginSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        user = serializer.user
        tokens = serializer._tokens
        
        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        logger.info(f"User logged in: {user.email}")
        
        response_data = {
            'tokens': tokens,
            'user': UserSerializer(user, context={'request': request}).data,
        }
        
        # Determine redirect and next steps based on role and company status
        if user.is_fleet_owner:
            if not user.company:
                response_data['redirect_url'] = '/fleet-owner/register-company'
                response_data['requires_company'] = True
                response_data['next_step'] = 'register_company'
            else:
                response_data['redirect_url'] = '/fleet-owner/dashboard'
                response_data['company'] = CompanySerializer(
                    user.company, context={'request': request}
                ).data
        elif user.is_driver:
            if not user.is_verified:
                response_data['redirect_url'] = '/driver/verify'
                response_data['requires_verification'] = True
                response_data['message'] = 'Please verify your account to continue.'
            else:
                response_data['redirect_url'] = '/driver/dashboard'
                # Check if temp password needs changing
                driver_profile = user.driver_profile
                if not driver_profile.password_changed and not driver_profile.is_temp_password_expired:
                    response_data['requires_password_change'] = True
                    response_data['temp_password_hours_remaining'] = driver_profile.temp_password_hours_remaining
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    """Refresh JWT access token."""
    serializer = TokenRefreshSerializer(data=request.data)
    
    if serializer.is_valid():
        return Response({
            'tokens': serializer.validated_data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """Logout user by blacklisting refresh token."""
    serializer = LogoutSerializer(data=request.data)
    
    if serializer.is_valid():
        logger.info(f"User logged out: {request.user.email}")
        return Response({
            'message': 'Successfully logged out'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# OTP MANAGEMENT ENDPOINTS
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def resend_driver_otp(request):
    """
    Resend OTP to a driver who hasn't verified their account yet.
    The temporary password remains valid for 24 hours.
    """
    serializer = ResendOTPSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.save()
        
        # Send OTP resend email
        send_otp_resend_email(user, user._generated_otp)
        
        logger.info(f"OTP resent to driver: {user.email}")
        
        response_data = {
            'message': 'OTP sent successfully. Valid for 5 minutes.',
            'email': user.email,
            'otp_validity_minutes': 5,
        }
        
        # Only include dev OTP in DEBUG mode
        if settings.DEBUG:
            response_data['dev_otp'] = user._generated_otp
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_driver_otp(request):
    """
    Verify driver via OTP or temporary password.
    
    Flow 1 - OTP Verification (first-time):
    {
        "email": "driver@example.com",
        "otp": "123456",
        "new_password": "MyNewPass123",
        "confirm_password": "MyNewPass123"
    }
    
    Flow 2 - Temporary Password Login:
    {
        "email": "driver@example.com",
        "password": "temp_password_from_email",
        "is_temporary_login": true
    }
    """
    serializer = DriverOTPVerificationSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.save()
        
        # Get generated tokens
        tokens = getattr(user, '_tokens', None)
        
        # Send confirmation email
        send_verification_confirmation(user)
        
        logger.info(f"Driver verified: {user.email}")
        
        response_data = {
            'message': 'Account verified successfully.',
            'user': UserSerializer(user, context={'request': request}).data,
        }
        
        # Add password change requirement if using temp password
        if serializer.validated_data.get('is_temporary_login'):
            response_data['requires_password_change'] = True
            response_data['message'] = (
                'Account verified. You are now logged in with your temporary password. '
                'Please change your password within 24 hours.'
            )
            driver_profile = user.driver_profile
            response_data['temp_password_hours_remaining'] = driver_profile.temp_password_hours_remaining
        
        if tokens:
            response_data['tokens'] = tokens
            response_data['message'] = response_data.get(
                'message', 
                'Account verified successfully. You are now logged in.'
            )
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_temp_password_status(request):
    """Check if the logged-in driver needs to change their temporary password."""
    user = request.user
    
    if not user.is_driver:
        return Response({
            'error': 'This endpoint is for drivers only.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    driver_profile = user.driver_profile
    
    needs_password_change = False
    hours_remaining = None
    temp_password_expired = False
    
    if not driver_profile.password_changed and driver_profile.temp_password_expires_at:
        if timezone.now() < driver_profile.temp_password_expires_at:
            needs_password_change = True
            hours_remaining = (
                driver_profile.temp_password_expires_at - timezone.now()
            ).total_seconds() / 3600
        else:
            needs_password_change = True
            temp_password_expired = True
            hours_remaining = 0
    
    return Response({
        'needs_password_change': needs_password_change,
        'hours_remaining': round(hours_remaining, 1) if hours_remaining else None,
        'temp_password_expired': temp_password_expired,
        'password_changed': driver_profile.password_changed,
    }, status=status.HTTP_200_OK)


# ============================================================================
# COMPANY REGISTRATION & MANAGEMENT (Step 2)
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_company(request):
    """
    Step 2: Fleet owner registers their company after account creation.
    Only fleet owners without a company can register one.
    """
    user = request.user
    
    # Check if user is a fleet owner
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can register a company.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if user already has a company
    if user.company:
        return Response({
            'error': 'You have already registered a company.',
            'company': CompanySerializer(user.company, context={'request': request}).data
        }, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = CompanyRegistrationSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        company = serializer.save()
        
        # Send confirmation email
        send_company_registration_email(user, company)
        
        # Generate fresh tokens with company info
        tokens = get_tokens_for_user(user)
        
        logger.info(f"Company registered by {user.email}: {company.name}")
        
        return Response({
            'message': 'Company registered successfully. You can now onboard drivers.',
            'company': CompanySerializer(company, context={'request': request}).data,
            'tokens': tokens,
            'next_step': 'onboard_drivers'
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def view_company(request):
    """View current user's company details."""
    user = request.user
    
    if not user.company:
        if user.is_fleet_owner:
            return Response({
                'error': 'No company found. Please register your company first.',
                'requires_company': True,
                'next_step': 'register_company'
            }, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({
                'error': 'No company found.'
            }, status=status.HTTP_404_NOT_FOUND)
    
    # Fleet owners see their own company, drivers see their assigned company
    if user.is_fleet_owner:
        company = get_object_or_404(Company, owner=user)
    else:
        company = user.company
    
    serializer = CompanySerializer(company, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_company(request):
    """Update company details (fleet owner only)."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can update company details.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if not user.company:
        return Response({
            'error': 'No company found. Please register your company first.',
            'requires_company': True
        }, status=status.HTTP_404_NOT_FOUND)
    
    company = user.company
    serializer = CompanyUpdateSerializer(
        company,
        data=request.data,
        partial=request.method == 'PATCH',
        context={'request': request}
    )
    
    if serializer.is_valid():
        serializer.save()
        logger.info(f"Company updated by {user.email}: {company.name}")
        return Response({
            'message': 'Company updated successfully.',
            'company': CompanySerializer(company, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_company_status(request):
    """Check if the logged-in fleet owner has registered a company."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'This endpoint is for fleet owners only.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if user.company:
        return Response({
            'has_company': True,
            'company': CompanySerializer(user.company, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    
    return Response({
        'has_company': False,
        'message': 'Please register your company to continue.',
        'requires_company': True,
        'next_step': 'register_company'
    }, status=status.HTTP_200_OK)


# ============================================================================
# DRIVER ONBOARDING (Step 3)
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboard_driver(request):
    """
    Step 3: Fleet owner onboards a new driver under their company.
    Requires fleet owner to have a registered company first.
    """
    user = request.user
    
    # Check if user is a fleet owner
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can onboard drivers.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if not user.is_verified:
        return Response({
            'error': 'Your account must be verified to onboard drivers.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check if fleet owner has a company
    if not user.company:
        return Response({
            'error': 'You must register a company before onboarding drivers.',
            'requires_company': True,
            'next_step': 'register_company'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = DriverOnboardingSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        driver = serializer.save()
        
        # Send onboarding email with both OTP and temp password
        send_onboarding_email(
            driver,
            driver._generated_password,
            driver._generated_otp
        )
        
        # Update fleet owner's active driver count
        fleet_owner_profile = user.fleet_owner_profile
        fleet_owner_profile.active_drivers = User.objects.filter(
            company=user.company,
            role=User.Role.DRIVER,
            is_active=True
        ).count()
        fleet_owner_profile.save(update_fields=['active_drivers'])
        
        logger.info(
            f"Driver onboarded by {user.email}: {driver.email} "
            f"for company {user.company.name}"
        )
        
        response_data = {
            'message': 'Driver onboarded successfully. Verification email sent.',
            'driver': UserSerializer(driver, context={'request': request}).data,
            'company': CompanySerializer(user.company, context={'request': request}).data,
        }
        
        # Only include dev credentials in DEBUG mode
        if settings.DEBUG:
            response_data['dev_credentials'] = {
                'password': driver._generated_password,
                'otp': driver._generated_otp
            }
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# PROFILE ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def view_profile(request):
    """View current user's profile."""
    user = request.user
    serializer = UserSerializer(user, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """Update current user's profile."""
    user = request.user
    serializer = UserUpdateSerializer(
        user,
        data=request.data,
        partial=request.method == 'PATCH',
        context={'request': request}
    )
    
    if serializer.is_valid():
        serializer.save()
        logger.info(f"Profile updated: {user.email}")
        return Response({
            'message': 'Profile updated successfully.',
            'user': serializer.data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def view_extended_profile(request):
    """Get user's extended profile based on role."""
    user = request.user
    
    if user.is_driver:
        serializer = DriverProfileSerializer(
            user.driver_profile,
            context={'request': request}
        )
    elif user.is_fleet_owner:
        serializer = FleetOwnerProfileSerializer(
            user.fleet_owner_profile,
            context={'request': request}
        )
    else:
        return Response({
            'error': 'Profile not found for this user role.'
        }, status=status.HTTP_404_NOT_FOUND)
    
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_extended_profile(request):
    """Update user's extended profile."""
    user = request.user
    
    if user.is_driver:
        serializer = DriverProfileUpdateSerializer(
            user.driver_profile,
            data=request.data,
            partial=request.method == 'PATCH',
            context={'request': request}
        )
    elif user.is_fleet_owner:
        return Response({
            'error': 'Fleet owner profile update not implemented yet.'
        }, status=status.HTTP_501_NOT_IMPLEMENTED)
    else:
        return Response({
            'error': 'Invalid user role.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if serializer.is_valid():
        serializer.save()
        logger.info(f"Extended profile updated: {user.email}")
        return Response({
            'message': 'Profile updated successfully.',
            'profile': serializer.data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# PASSWORD MANAGEMENT ENDPOINTS
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change user password."""
    serializer = PasswordChangeSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        serializer.save()
        logger.info(f"Password changed for user: {request.user.email}")
        return Response({
            'message': 'Password changed successfully. Please login again.'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    """Request password reset."""
    serializer = PasswordResetRequestSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    if hasattr(serializer, 'user'):
        logger.info(f"Password reset requested for: {serializer.user.email}")
        # Implement password reset email logic here
    
    # Always return success to prevent email enumeration
    return Response({
        'message': 'If the email exists, a password reset link has been sent.'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """Reset password with token."""
    serializer = PasswordResetConfirmSerializer(data=request.data)
    
    if serializer.is_valid():
        # Implement password reset logic here
        return Response({
            'message': 'Password has been reset successfully.'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# USER MANAGEMENT ENDPOINTS (Fleet Owner Only)
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_company_users(request):
    """List all users in the fleet owner's company."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can view company users.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if not user.company:
        return Response({
            'error': 'No company found. Please register your company first.',
            'requires_company': True
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get filters from query params
    role_filter = request.query_params.get('role', None)
    is_active_filter = request.query_params.get('is_active', None)
    
    users = User.objects.filter(company=user.company).select_related('company')
    
    if role_filter:
        users = users.filter(role=role_filter)
    if is_active_filter is not None:
        is_active = is_active_filter.lower() == 'true'
        users = users.filter(is_active=is_active)
    
    serializer = UserSerializer(users, many=True, context={'request': request})
    
    return Response({
        'count': users.count(),
        'users': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_detail(request, user_id):
    """Get a specific user's details (fleet owner only)."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can view user details.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    target_user = get_object_or_404(
        User.objects.filter(company__owner=user),
        id=user_id
    )
    
    serializer = UserSerializer(target_user, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deactivate_user(request, user_id):
    """Deactivate a user (fleet owner only)."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can deactivate users.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    target_user = get_object_or_404(
        User.objects.filter(company__owner=user),
        id=user_id
    )
    
    if target_user == user:
        return Response({
            'error': 'You cannot deactivate your own account.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if target_user.is_fleet_owner:
        return Response({
            'error': 'Cannot deactivate another fleet owner.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    target_user.is_active = False
    target_user.save()
    
    logger.info(f"User deactivated by {user.email}: {target_user.email}")
    
    return Response({
        'message': f'User {target_user.full_name} has been deactivated.',
        'user': UserSerializer(target_user, context={'request': request}).data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activate_user(request, user_id):
    """Activate a user (fleet owner only)."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can activate users.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    target_user = get_object_or_404(
        User.objects.filter(company__owner=user),
        id=user_id
    )
    
    target_user.is_active = True
    target_user.save()
    
    logger.info(f"User activated by {user.email}: {target_user.email}")
    
    return Response({
        'message': f'User {target_user.full_name} has been activated.',
        'user': UserSerializer(target_user, context={'request': request}).data
    }, status=status.HTTP_200_OK)


# ============================================================================
# KYC DOCUMENT ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_kyc_documents(request):
    """List KYC documents based on user role."""
    user = request.user
    
    if user.is_fleet_owner:
        documents = KYCDocument.objects.filter(
            driver__user__company__owner=user
        ).select_related('driver__user', 'verified_by')
    elif user.is_driver:
        documents = KYCDocument.objects.filter(
            driver=user.driver_profile
        ).select_related('driver__user', 'verified_by')
    else:
        return Response({
            'error': 'Unauthorized.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Apply filters from query params
    doc_type = request.query_params.get('document_type', None)
    verification_status = request.query_params.get('verification_status', None)
    
    if doc_type:
        documents = documents.filter(document_type=doc_type)
    if verification_status:
        documents = documents.filter(verification_status=verification_status)
    
    serializer = KYCDocumentSerializer(
        documents,
        many=True,
        context={'request': request}
    )
    
    return Response({
        'count': documents.count(),
        'documents': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_kyc_document(request):
    """Upload a new KYC document."""
    user = request.user
    
    if not user.is_verified:
        return Response({
            'error': 'Your account must be verified to upload documents.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = KYCDocumentSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        # Set driver based on user role
        if user.is_driver:
            serializer.save(driver=user.driver_profile)
        elif user.is_fleet_owner:
            driver_id = request.data.get('driver')
            if not driver_id:
                return Response({
                    'error': 'Driver ID is required.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                driver_profile = DriverProfile.objects.get(pk=driver_id)
                if driver_profile.user.company and driver_profile.user.company.owner == user:
                    serializer.save(driver=driver_profile)
                else:
                    return Response({
                        'error': 'Driver does not belong to your company.'
                    }, status=status.HTTP_403_FORBIDDEN)
            except DriverProfile.DoesNotExist:
                return Response({
                    'error': 'Invalid driver ID.'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({
                'error': 'Invalid user role.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"KYC document uploaded by {user.email}")
        
        return Response({
            'message': 'Document uploaded successfully.',
            'document': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_kyc_document(request, document_id):
    """Get a specific KYC document."""
    user = request.user
    
    if user.is_fleet_owner:
        document = get_object_or_404(
            KYCDocument.objects.filter(driver__user__company__owner=user),
            id=document_id
        )
    elif user.is_driver:
        document = get_object_or_404(
            KYCDocument.objects.filter(driver=user.driver_profile),
            id=document_id
        )
    else:
        return Response({
            'error': 'Unauthorized.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = KYCDocumentSerializer(document, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_kyc_document(request, document_id):
    """Update a KYC document."""
    user = request.user
    
    if user.is_driver:
        document = get_object_or_404(
            KYCDocument.objects.filter(driver=user.driver_profile),
            id=document_id
        )
    elif user.is_fleet_owner:
        document = get_object_or_404(
            KYCDocument.objects.filter(driver__user__company__owner=user),
            id=document_id
        )
    else:
        return Response({
            'error': 'Unauthorized.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = KYCDocumentSerializer(
        document,
        data=request.data,
        partial=request.method == 'PATCH',
        context={'request': request}
    )
    
    if serializer.is_valid():
        serializer.save()
        logger.info(f"KYC document updated by {user.email}: {document_id}")
        return Response({
            'message': 'Document updated successfully.',
            'document': serializer.data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_kyc_document(request, document_id):
    """Delete a KYC document."""
    user = request.user
    
    if user.is_driver:
        document = get_object_or_404(
            KYCDocument.objects.filter(driver=user.driver_profile),
            id=document_id
        )
    elif user.is_fleet_owner:
        document = get_object_or_404(
            KYCDocument.objects.filter(driver__user__company__owner=user),
            id=document_id
        )
    else:
        return Response({
            'error': 'Unauthorized.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    document.delete()
    logger.info(f"KYC document deleted by {user.email}: {document_id}")
    
    return Response({
        'message': 'Document deleted successfully.'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_kyc_document(request, document_id):
    """Verify or reject a KYC document (fleet owner only)."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can verify documents.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    document = get_object_or_404(
        KYCDocument.objects.filter(driver__user__company__owner=user),
        id=document_id
    )
    
    serializer = KYCDocumentVerificationSerializer(data=request.data)
    
    if serializer.is_valid():
        verification_status = serializer.validated_data['verification_status']
        
        if verification_status == 'VERIFIED':
            document.mark_as_verified(user)
            message = 'Document verified successfully.'
        else:
            document.mark_as_rejected(
                user,
                serializer.validated_data.get('rejection_reason', 'No reason provided.')
            )
            message = 'Document rejected.'
        
        logger.info(f"KYC document {document_id} {verification_status} by {user.email}")
        
        return Response({
            'message': message,
            'document': KYCDocumentSerializer(document, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pending_kyc_documents(request):
    """Get all pending KYC documents (fleet owner only)."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can view pending documents.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    pending_docs = KYCDocument.objects.filter(
        driver__user__company__owner=user,
        verification_status=KYCDocument.VerificationStatus.PENDING
    ).select_related('driver__user')
    
    serializer = KYCDocumentSerializer(
        pending_docs,
        many=True,
        context={'request': request}
    )
    
    return Response({
        'count': pending_docs.count(),
        'documents': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_expired_kyc_documents(request):
    """Get all expired KYC documents (fleet owner only)."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can view expired documents.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    today = timezone.now().date()
    expired_docs = KYCDocument.objects.filter(
        driver__user__company__owner=user,
        expiry_date__lt=today
    ).select_related('driver__user')
    
    serializer = KYCDocumentSerializer(
        expired_docs,
        many=True,
        context={'request': request}
    )
    
    return Response({
        'count': expired_docs.count(),
        'documents': serializer.data
    }, status=status.HTTP_200_OK)


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fleet_owner_dashboard(request):
    """Get fleet owner dashboard summary."""
    user = request.user
    
    if not user.is_fleet_owner:
        return Response({
            'error': 'Only fleet owners can access this dashboard.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if not user.company:
        return Response({
            'error': 'Please register your company first.',
            'requires_company': True
        }, status=status.HTTP_400_BAD_REQUEST)
    
    company = user.company
    
    # Get counts
    total_drivers = User.objects.filter(
        company=company,
        role=User.Role.DRIVER
    ).count()
    
    active_drivers = User.objects.filter(
        company=company,
        role=User.Role.DRIVER,
        is_active=True,
        is_verified=True
    ).count()
    
    pending_kyc = KYCDocument.objects.filter(
        driver__user__company__owner=user,
        verification_status=KYCDocument.VerificationStatus.PENDING
    ).count()
    
    expired_docs = KYCDocument.objects.filter(
        driver__user__company__owner=user,
        expiry_date__lt=timezone.now().date()
    ).count()
    
    return Response({
        'company': CompanySerializer(company, context={'request': request}).data,
        'stats': {
            'total_drivers': total_drivers,
            'active_drivers': active_drivers,
            'pending_kyc_documents': pending_kyc,
            'expired_documents': expired_docs,
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def driver_dashboard(request):
    """Get driver dashboard summary."""
    user = request.user
    
    if not user.is_driver:
        return Response({
            'error': 'Only drivers can access this dashboard.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    driver_profile = user.driver_profile
    pending_kyc = KYCDocument.objects.filter(
        driver=driver_profile,
        verification_status=KYCDocument.VerificationStatus.PENDING
    ).count()
    
    return Response({
        'user': UserSerializer(user, context={'request': request}).data,
        'profile': DriverProfileSerializer(driver_profile, context={'request': request}).data,
        'stats': {
            'total_trips': driver_profile.total_trips,
            'completed_trips': driver_profile.completed_trips,
            'completion_rate': driver_profile.completion_rate,
            'on_time_percentage': float(driver_profile.on_time_percentage),
            'average_rating': float(driver_profile.average_rating),
            'pending_kyc_documents': pending_kyc,
        }
    }, status=status.HTTP_200_OK)


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT token obtain pair view."""
    serializer_class = CustomTokenObtainPairSerializer