import logging
import os
import uuid

from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from content.models import BlogPost
from content.serializers import (
    BlogPostAdminSerializer,
    BlogPostDetailPublicSerializer,
    BlogPostPublicSerializer,
)
from platform_api.permissions import IsPlatformAdmin

logger = logging.getLogger(__name__)

_BLOG_COVER_MAX_BYTES = 5 * 1024 * 1024
_BLOG_COVER_ALLOWED_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
}
_BLOG_COVER_ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


def _published_queryset():
    now = timezone.now()
    return BlogPost.objects.filter(
        status=BlogPost.Status.PUBLISHED,
        published_at__isnull=False,
        published_at__lte=now,
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def public_posts(request):
    status_param = (request.query_params.get('status') or 'published').lower()
    if status_param != 'published':
        return Response({'count': 0, 'results': []})
    qs = _published_queryset().order_by('-published_at')
    limit = min(50, max(1, int(request.query_params.get('limit', 10))))
    page = max(1, int(request.query_params.get('page', 1)))
    paginator = Paginator(qs, limit)
    page_obj = paginator.get_page(page)
    data = BlogPostPublicSerializer(
        page_obj.object_list,
        many=True,
        context={'request': request},
    ).data
    return Response({'count': paginator.count, 'results': data})


@api_view(['GET'])
@permission_classes([AllowAny])
def public_post_detail(request, slug):
    post = get_object_or_404(_published_queryset(), slug=slug)
    return Response(
        BlogPostDetailPublicSerializer(post, context={'request': request}).data,
    )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def admin_posts(request):
    if request.method == 'GET':
        qs = BlogPost.objects.all().order_by('-updated_at')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = min(100, max(1, int(request.query_params.get('page_size', 25))))
        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page)
        return Response(
            {
                'count': paginator.count,
                'results': BlogPostAdminSerializer(page_obj.object_list, many=True).data,
            }
        )

    serializer = BlogPostAdminSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        author = request.user if getattr(request.user, 'is_authenticated', False) else None
        post = serializer.save(author=author)
    except DatabaseError:
        logger.exception('Blog post create failed (database)')
        return Response(
            {'detail': 'Could not save the post. Please try again.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception as exc:
        logger.exception('Blog post create failed')
        return Response(
            {'detail': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return Response(BlogPostAdminSerializer(post).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def admin_post_detail(request, post_id):
    post = get_object_or_404(BlogPost, pk=post_id)
    if request.method == 'GET':
        return Response(BlogPostAdminSerializer(post).data)
    if request.method == 'PATCH':
        serializer = BlogPostAdminSerializer(post, data=request.data, partial=True)
        if serializer.is_valid():
            post = serializer.save()
            return Response(BlogPostAdminSerializer(post).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    post.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def admin_upload_blog_cover(request):
    """Store a blog cover image and return its public URL for `cover_url`."""
    uploaded = request.FILES.get('cover')
    if not uploaded:
        return Response(
            {'detail': 'Missing file field "cover".'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if uploaded.size > _BLOG_COVER_MAX_BYTES:
        return Response(
            {'detail': 'Cover image must be 5 MB or smaller.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    content_type = (getattr(uploaded, 'content_type', '') or '').lower()
    if content_type and content_type not in _BLOG_COVER_ALLOWED_TYPES:
        return Response(
            {'detail': 'Cover must be a JPEG, PNG, WebP, or GIF image.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ext = os.path.splitext(uploaded.name or '')[1].lower()
    if ext not in _BLOG_COVER_ALLOWED_EXT:
        return Response(
            {'detail': 'Cover must use a .jpg, .jpeg, .png, .webp, or .gif file.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    rel_path = f'blog_covers/{uuid.uuid4().hex}{ext}'
    saved_path = default_storage.save(rel_path, uploaded)
    media_url = default_storage.url(saved_path)
    cover_url = request.build_absolute_uri(media_url)

    return Response({'cover_url': cover_url}, status=status.HTTP_201_CREATED)
