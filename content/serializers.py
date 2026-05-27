from rest_framework import serializers

from content.models import BlogPost


class BlogPostPublicSerializer(serializers.ModelSerializer):
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
