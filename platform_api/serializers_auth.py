from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from oauth.models import User
from oauth.serializers import UserLoginSerializer


class PlatformAdminRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'email',
            'phone_number',
            'first_name',
            'last_name',
            'password',
            'confirm_password',
        ]

    def validate_email(self, value):
        email = value.lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return email

    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError('A user with this phone number already exists.')
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        return User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            phone_number=validated_data['phone_number'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            role=User.Role.PLATFORM_ADMIN,
            is_active=True,
            is_verified=True,
            is_staff=True,
        )


class PlatformAdminLoginSerializer(UserLoginSerializer):
    """Super admin sign-in at /platform/api/auth/login/."""

    def validate(self, data):
        super().validate(data)
        if not self.user.is_platform_admin:
            raise serializers.ValidationError(
                'This sign-in is for platform administrators only. '
                'Fleet owners should use the main app sign-in.',
                code='wrong_portal',
            )
        if not self.user.is_active:
            raise serializers.ValidationError(
                'Platform admin account is disabled.',
                code='account_inactive',
            )
        return data
