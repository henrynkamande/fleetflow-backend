from django.urls import path

from content import views

urlpatterns = [
    path('posts/', views.public_posts, name='content-public-posts'),
    path('posts/<slug:slug>/', views.public_post_detail, name='content-public-post-detail'),
    path('admin/posts/', views.admin_posts, name='content-admin-posts'),
    path('admin/posts/<uuid:post_id>/', views.admin_post_detail, name='content-admin-post-detail'),
    path(
        'admin/uploads/cover/',
        views.admin_upload_blog_cover,
        name='content-admin-upload-blog-cover',
    ),
]
