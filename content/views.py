from django.core.paginator import Paginator
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
    data = BlogPostPublicSerializer(page_obj.object_list, many=True).data
    return Response({'count': paginator.count, 'results': data})


@api_view(['GET'])
@permission_classes([AllowAny])
def public_post_detail(request, slug):
    post = get_object_or_404(_published_queryset(), slug=slug)
    return Response(BlogPostDetailPublicSerializer(post).data)


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
    if serializer.is_valid():
        post = serializer.save(author=request.user)
        return Response(BlogPostAdminSerializer(post).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
