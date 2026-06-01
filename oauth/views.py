# views.py
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status, serializers
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
import logging

from .models import User, DriverProfile, FleetOwnerProfile, KYCDocument, Company, EmailAuthCode
from . import auth_codes, pending_signup
from .email_utils import deliver_auth_email, schedule_auth_email
from fleetflow.pagination import paginate_queryset

from .fleet_workspace import ensure_fleet_owner_company, resolve_user_company, company_members_queryset
from .serializers import (
    FleetOwnerRegistrationSerializer,
    CompanyRegistrationSerializer,
    CompanyUpdateSerializer,
    DriverOnboardingSerializer,
    DriverCreateSerializer,
    serialize_user_for_api,
    ResendOTPSerializer,
    DriverOTPVerificationSerializer,
    FleetOwnerLoginSerializer,
    UserSerializer,
    UserUpdateSerializer,
    DriverProfileSerializer,
    DriverProfileUpdateSerializer,
    FleetOwnerProfileSerializer,
    KYCDocumentSerializer,
    KYCDocumentVerificationSerializer,
    PasswordChangeSerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
    PasswordResetConfirmSerializer,
    SignupVerifyOTPSerializer,
    SignupResendOTPSerializer,
    TokenRefreshSerializer,
    LogoutSerializer,
    CustomTokenObtainPairSerializer,
    CompanySerializer,
)

logger = logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _format_transactional_email(recipient_name, intro, detail_lines=None, action_lines=None, security_note=None):
    """Build a consistent plain-text transactional email body."""
    details = "\n".join(detail_lines or [])
    actions = "\n".join(action_lines or [])

    sections = [
        f"Hello {recipient_name},",
        "",
        intro.strip(),
    ]

    if details:
        sections.extend(["", details])

    if actions:
        sections.extend(["", "What to do next:", actions])

    if security_note:
        sections.extend(["", security_note.strip()])

    sections.extend(
        [
            "",
            "Regards,",
            "Fleet Flow Support Team",
        ]
    )
    return "\n".join(sections).strip()


def send_welcome_email(user):
    """Send welcome email to fleet owner."""
    subject = "Welcome to Fleet Flow"
    message = _format_transactional_email(
        recipient_name=user.first_name,
        intro="Your fleet owner account has been created successfully.",
        action_lines=[
            "- Sign in to your dashboard.",
            "- Complete your company profile to begin managing operations.",
        ],
        security_note="If you did not create this account, please contact support immediately.",
    )
    return deliver_auth_email(subject, message, user.email)


def send_company_registration_email(user, company):
    """Send company registration confirmation email."""
    subject = "Company Registration Confirmed"
    message = _format_transactional_email(
        recipient_name=user.first_name,
        intro=f'Your company "{company.name}" is now registered on Fleet Flow.',
        action_lines=[
            "- Invite and onboard your drivers.",
            "- Add your vehicles and documentation.",
            "- Start tracking operations from your dashboard.",
        ],
    )
    return deliver_auth_email(subject, message, user.email)


def send_onboarding_email(driver, password=None, otp=None):
    """Send onboarding email with credentials and OTP."""
    company_name = driver.company.name if driver.company else "Fleet Flow"
    invited_by_name = driver.invited_by.full_name if driver.invited_by else "Fleet Flow"

    subject = f"Welcome to {company_name} - Verify Your Account"

    details = [f"You were added to {company_name} by {invited_by_name}."]
    actions = []

    if otp:
        details.extend(
            [
                "",
                "Verification code:",
                f"- OTP: {otp}",
                "- Expires in 5 minutes.",
            ]
        )
        actions.append("- Use the OTP first (recommended) to verify your account.")

    if password:
        details.extend(
            [
                "",
                "Temporary sign-in details:",
                f"- Email: {driver.email}",
                f"- Temporary password: {password}",
                "- Temporary password expires in 24 hours.",
            ]
        )
        actions.append("- If you use the temporary password, change it immediately after login.")

    actions.append("- Complete verification as soon as possible to activate full account access.")

    message = _format_transactional_email(
        recipient_name=driver.first_name,
        intro="Your Fleet Flow driver account is ready.",
        detail_lines=details,
        action_lines=actions,
        security_note="If this invitation is unexpected, please contact your fleet administrator.",
    )
    return deliver_auth_email(subject, message, driver.email)


def send_otp_resend_email(driver, otp):
    """Send OTP resend email."""
    company_name = driver.company.name if driver.company else "Fleet Flow"

    subject = f"{company_name} - New Verification Code"
    message = _format_transactional_email(
        recipient_name=driver.first_name,
        intro="You requested a new verification code for your account.",
        detail_lines=[
            f"- OTP: {otp}",
            "- Expires in 5 minutes.",
            "- Your temporary password remains valid if it has not expired.",
        ],
        action_lines=["- Enter this OTP in the verification screen to continue."],
        security_note="If you did not request this code, please secure your account immediately.",
    )
    return deliver_auth_email(subject, message, driver.email)


def send_signup_otp_email(user, otp):
    return send_signup_otp_email_to(
        recipient_email=user.email,
        first_name=user.first_name,
        otp=otp,
    )


def _signup_otp_email_content(*, first_name: str, otp: str) -> tuple[str, str]:
    brand = getattr(settings, 'APP_BRAND_NAME', 'FleetVault')
    subject = f"{brand} - Verify Your Email Address"
    message = _format_transactional_email(
        recipient_name=first_name,
        intro="Thank you for registering. Please verify your email to continue.",
        detail_lines=[
            f"- Verification code: {otp}",
            "- Expires in 30 minutes.",
        ],
        action_lines=["- Enter this code in the verification prompt to activate your account."],
        security_note="If you did not create this account, you can safely ignore this email.",
    )
    return subject, message


def send_signup_otp_email_to(*, recipient_email: str, first_name: str, otp: str) -> bool:
    subject, message = _signup_otp_email_content(first_name=first_name, otp=otp)
    return deliver_auth_email(subject, message, recipient_email)


def schedule_signup_otp_email_to(*, recipient_email: str, first_name: str, otp: str) -> None:
    subject, message = _signup_otp_email_content(first_name=first_name, otp=otp)
    schedule_auth_email(subject, message, recipient_email)


def send_password_reset_code_email(user, code):
    brand = getattr(settings, 'APP_BRAND_NAME', 'FleetVault')
    subject = f"{brand} - Password Reset Code"
    message = _format_transactional_email(
        recipient_name=user.first_name,
        intro="We received a request to reset your password.",
        detail_lines=[
            f"- Password reset code: {code}",
            "- Expires in 30 minutes.",
        ],
        action_lines=["- Enter this code in the password reset flow to set a new password."],
        security_note="If you did not request a password reset, no action is required.",
    )
    return deliver_auth_email(subject, message, user.email)


def send_verification_confirmation(user):
    """Send verification confirmation email."""
    subject = "Account Verified Successfully"
    message = _format_transactional_email(
        recipient_name=user.first_name,
        intro="Your Fleet Flow account has been verified successfully.",
        action_lines=["- Sign in to continue setting up and managing your fleet operations."],
    )
    return deliver_auth_email(subject, message, user.email)


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
    After registration, fleet owner may register a company (optional).
    """
    serializer = FleetOwnerRegistrationSerializer(data=request.data)
    
    if serializer.is_valid():
        pending = serializer.save()
        otp = pending_signup.issue_code(pending)
        schedule_signup_otp_email_to(
            recipient_email=pending.email,
            first_name=pending.first_name,
            otp=otp,
        )

        logger.info('Fleet owner signup pending OTP: %s', pending.email)

        return Response(
            {
                'message': 'Enter the verification code sent to your email to finish creating your account.',
                'email': pending.email,
                'requires_verification': True,
                'email_sent': True,
                'otp_expires_minutes': pending_signup.CODE_EXPIRY_SECONDS // 60,
                'resend_cooldown_seconds': pending_signup.RESEND_COOLDOWN_SECONDS,
            },
            status=status.HTTP_201_CREATED,
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """Login user and return JWT tokens."""
    serializer = FleetOwnerLoginSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if not serializer.is_valid():
        email_hint = (request.data.get('email') or '')[:80]
        logger.warning('Login failed for %s: %s', email_hint, serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = serializer.user
    tokens = serializer._tokens

    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    logger.info(f"User logged in: {user.email}")

    response_data = {
        'tokens': tokens,
        'user': UserSerializer(user, context={'request': request}).data,
    }

    if user.is_fleet_owner:
        from billing.access import company_has_platform_access, company_requires_checkout
        from oauth.fleet_workspace import ensure_fleet_owner_company

        company = resolve_user_company(user) or ensure_fleet_owner_company(user)
        response_data['redirect_url'] = '/fleet-owner/dashboard'
        if not user.company and company and not company.registration_number:
            response_data['requires_company'] = False
            response_data['next_step'] = 'register_company'
        if company:
            response_data['company'] = CompanySerializer(
                company, context={'request': request}
            ).data
        if company:
            response_data['billing_status'] = company.billing_status
            response_data['requires_billing_checkout'] = company_requires_checkout(company)
            response_data['has_billing_access'] = company_has_platform_access(company)
    elif user.is_driver:
        if not user.is_verified:
            response_data['redirect_url'] = '/driver/verify'
            response_data['requires_verification'] = True
            response_data['message'] = 'Please verify your account to continue.'
        else:
            response_data['redirect_url'] = '/driver/dashboard'
            driver_profile = user.driver_profile
            if not driver_profile.password_changed and not driver_profile.is_temp_password_expired:
                response_data['requires_password_change'] = True
                response_data['temp_password_hours_remaining'] = driver_profile.temp_password_hours_remaining

    return Response(response_data, status=status.HTTP_200_OK)


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
def verify_signup_otp(request):
    """Verify fleet owner signup OTP; activate account (login separately)."""
    serializer = SignupVerifyOTPSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        send_welcome_email(user)
        send_verification_confirmation(user)
        logger.info(f'Fleet owner email verified: {user.email}')
        return Response({
            'message': 'Email verified successfully. You can now sign in.',
            'email': user.email,
        }, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_signup_otp(request):
    serializer = SignupResendOTPSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        schedule_signup_otp_email_to(
            recipient_email=serializer._recipient_email,
            first_name=serializer._first_name,
            otp=serializer._issued_otp,
        )
        return Response(
            {
                'message': 'A new verification code has been sent.',
                'email': serializer._recipient_email,
                'email_sent': True,
                'otp_expires_minutes': pending_signup.CODE_EXPIRY_SECONDS // 60,
                'resend_cooldown_seconds': pending_signup.RESEND_COOLDOWN_SECONDS,
            },
            status=status.HTTP_200_OK,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
    
    if user.company:
        serializer = CompanyRegistrationSerializer(
            user.company,
            data=request.data,
            partial=True,
            context={'request': request},
        )
    else:
        serializer = CompanyRegistrationSerializer(
            data=request.data,
            context={'request': request},
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

    if user.is_fleet_owner:
        company = resolve_user_company(user) or ensure_fleet_owner_company(user)
    else:
        company = resolve_user_company(user)

    if not company:
        return Response(
            {'error': 'No company found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

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
    
    company = resolve_user_company(user) or ensure_fleet_owner_company(user)
    if not company:
        return Response({
            'error': 'No company found. Please register your company first.',
            'requires_company': True
        }, status=status.HTTP_404_NOT_FOUND)

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
        'message': 'Company registration is optional. Add your business details anytime.',
        'requires_company': False,
        'next_step': 'register_company',
    }, status=status.HTTP_200_OK)


# ============================================================================
# DRIVER MANAGEMENT (fleet owner)
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_driver(request):
    """Add a driver to the fleet (no platform invitation)."""
    user = request.user

    if not user.is_fleet_owner:
        return Response(
            {'error': 'Only fleet owners can add drivers.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Informal fleets: auto-create a workspace company; no separate registration step.
    company = ensure_fleet_owner_company(user)
    if not company:
        return Response(
            {'error': 'Could not set up your fleet workspace. Try again or contact support.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = DriverCreateSerializer(
        data=request.data,
        context={'request': request, 'company': company},
    )

    if serializer.is_valid():
        try:
            driver_user = serializer.save()
        except serializers.ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            return Response(
                {
                    'non_field_errors': [
                        'Could not save this driver because of a duplicate phone or license number.'
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            fleet_owner_profile, _ = FleetOwnerProfile.objects.get_or_create(user=user)
            fleet_owner_profile.active_drivers = User.objects.filter(
                company=company,
                role=User.Role.DRIVER,
                is_active=True,
            ).count()
            fleet_owner_profile.save(update_fields=['active_drivers'])
        except Exception:
            logger.exception('Failed to update fleet owner active_drivers after driver create')

        logger.info(
            f"Driver added by {user.email}: {driver_user.get_full_name()} "
            f"for company {company.name}"
        )

        return Response(
            {
                'message': 'Driver added successfully.',
                'driver': serialize_user_for_api(driver_user, request),
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# DRIVER ONBOARDING (Step 3 — driver app invites)
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
    
    from oauth.fleet_workspace import ensure_fleet_owner_company

    company = ensure_fleet_owner_company(user)
    if not company:
        return Response({'error': 'Unable to create fleet workspace.'}, status=status.HTTP_400_BAD_REQUEST)

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
        user.refresh_from_db()
        logger.info(f"Profile updated: {user.email}")
        return Response({
            'message': 'Profile updated successfully.',
            'user': UserSerializer(user, context={'request': request}).data
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
    """Request password reset code by email."""
    serializer = PasswordResetRequestSerializer(data=request.data)
    if not serializer.is_valid():
        status_code = status.HTTP_400_BAD_REQUEST
        if 'cooldown_seconds' in serializer.errors:
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
        return Response(serializer.errors, status=status_code)

    user = serializer.save()
    if user:
        send_password_reset_code_email(user, user._issued_reset_code)
        logger.info(f'Password reset code sent for: {user.email}')

    payload = {
        'message': 'If the email exists, a reset code has been sent.',
        'resend_cooldown_seconds': auth_codes.RESEND_COOLDOWN_SECONDS,
        'code_expires_minutes': auth_codes.CODE_EXPIRY_SECONDS // 60,
    }
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_reset_code(request):
    """Validate reset code before showing the new-password form."""
    serializer = PasswordResetVerifySerializer(data=request.data)
    if serializer.is_valid():
        return Response({
            'message': 'Code verified. You can set a new password.',
            'email': serializer.validated_data['email'],
            'verified': True,
        }, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """Reset password using email + code."""
    serializer = PasswordResetConfirmSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({
            'message': 'Password has been reset successfully. You can now sign in.',
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
    
    company = ensure_fleet_owner_company(user)
    if not company:
        return Response({'count': 0, 'users': []}, status=status.HTTP_200_OK)

    # Get filters from query params
    role_filter = request.query_params.get('role', None)
    is_active_filter = request.query_params.get('is_active', None)
    
    users = company_members_queryset(user, company).select_related('company')
    
    if role_filter:
        users = users.filter(role=role_filter)
    if is_active_filter is not None:
        is_active = is_active_filter.lower() == 'true'
        users = users.filter(is_active=is_active)

    users = users.order_by('-date_joined')
    page_obj, meta = paginate_queryset(request, users)
    serializer = UserSerializer(page_obj.object_list, many=True, context={'request': request})

    return Response({
        **meta,
        'users': serializer.data,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_company_drivers(request):
    """List drivers in the fleet owner's company (for trip/vehicle assignment)."""
    user = request.user

    if not user.is_fleet_owner:
        return Response(
            {'error': 'Only fleet owners can list company drivers.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    company = ensure_fleet_owner_company(user)
    if not company:
        return Response({'count': 0, 'drivers': []}, status=status.HTTP_200_OK)

    is_active_filter = request.query_params.get('is_active', None)
    drivers = company_members_queryset(user, company).filter(
        role=User.Role.DRIVER,
    ).select_related('company', 'driver_profile')
    if is_active_filter is not None:
        is_active = is_active_filter.lower() == 'true'
        drivers = drivers.filter(is_active=is_active)

    drivers = drivers.order_by('-date_joined')
    page_obj, meta = paginate_queryset(request, drivers)
    serializer = UserSerializer(page_obj.object_list, many=True, context={'request': request})
    return Response({**meta, 'drivers': serializer.data}, status=status.HTTP_200_OK)


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

    documents = documents.order_by('-uploaded_at')
    page_obj, meta = paginate_queryset(request, documents)
    serializer = KYCDocumentSerializer(
        page_obj.object_list,
        many=True,
        context={'request': request},
    )

    return Response({
        **meta,
        'documents': serializer.data,
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
            'company': None,
            'stats': {
                'total_drivers': 0,
                'active_drivers': 0,
                'pending_kyc_documents': 0,
                'expired_documents': 0,
            },
        }, status=status.HTTP_200_OK)

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