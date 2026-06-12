from django.utils import timezone
from rest_framework import serializers

from content.models import BlogPost


class BlogPostPublicSerializer(serializers.ModelSerializer):
    cover_url = serializers.SerializerMethodField()

    def get_cover_url(self, obj: BlogPost) -> str:
        raw = (obj.cover_url or '').strip()
        if not raw:
            return ''
        if raw.startswith(('http://', 'https://')):
            return raw
        request = self.context.get('request')
        path = raw if raw.startswith('/') else f'/{raw}'
        if not path.startswith('/media/'):
            path = f'/media/{path.lstrip("/")}'
        if request:
            return request.build_absolute_uri(path)
        return path

    class Meta:
        model = BlogPost
        fields = [
            'id',
            'slug',
            'title',
            'excerpt',
            'cover_url',
            'published_at',
            'seo_title',
            'seo_description',
        ]


class BlogPostDetailPublicSerializer(BlogPostPublicSerializer):
    class Meta(BlogPostPublicSerializer.Meta):
        fields = BlogPostPublicSerializer.Meta.fields + ['body']


class BlogPostAdminSerializer(serializers.ModelSerializer):
    cover_url = serializers.URLField(required=False, allow_blank=True, max_length=500)

    def _apply_publish_timestamp(self, instance):
        if instance.status == BlogPost.Status.PUBLISHED and not instance.published_at:
            instance.published_at = timezone.now()

    def create(self, validated_data):
        instance = BlogPost(**validated_data)
        self._apply_publish_timestamp(instance)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        self._apply_publish_timestamp(instance)
        instance.save()
        return instance

    class Meta:
        model = BlogPost
        fields = [
            'id',
            'slug',
            'title',
            'excerpt',
            'body',
            'cover_url',
            'status',
            'seo_title',
            'seo_description',
            'published_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
