from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from oauth.serializers import UserSerializer
from oauth.views import get_tokens_for_user
from platform_api.serializers_auth import (
    PlatformAdminLoginSerializer,
    PlatformAdminRegistrationSerializer,
)


@api_view(['POST'])
@permission_classes([AllowAny])
def platform_register(request):
    serializer = PlatformAdminRegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = serializer.save()
    tokens = get_tokens_for_user(user)
    return Response(
        {
            'message': 'Platform administrator account created.',
            'tokens': tokens,
            'user': UserSerializer(user, context={'request': request}).data,
            'redirect_url': '/dashboard',
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def platform_login(request):
    serializer = PlatformAdminLoginSerializer(
        data=request.data,
        context={'request': request},
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = serializer.user
    tokens = serializer._tokens
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    return Response(
        {
            'tokens': tokens,
            'user': UserSerializer(user, context={'request': request}).data,
            'redirect_url': '/dashboard',
        },
        status=status.HTTP_200_OK,
    )
