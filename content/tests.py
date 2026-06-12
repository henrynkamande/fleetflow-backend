from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from content.models import BlogPost
from oauth.models import User


class BlogPublicAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.published = BlogPost.objects.create(
            slug='hello-fleet',
            title='Hello Fleet',
            excerpt='Short intro',
            body='## Hello\n\nMarkdown **works**.',
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        BlogPost.objects.create(
            slug='draft-only',
            title='Draft',
            excerpt='Hidden',
            body='secret',
            status=BlogPost.Status.DRAFT,
        )

    def test_list_published_posts(self):
        res = self.client.get('/content/api/posts/', {'status': 'published', 'limit': 10})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 1)
        self.assertEqual(len(res.data['results']), 1)
        self.assertEqual(res.data['results'][0]['slug'], 'hello-fleet')
        self.assertNotIn('body', res.data['results'][0])

    def test_detail_includes_markdown_body(self):
        res = self.client.get('/content/api/posts/hello-fleet/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('body', res.data)
        self.assertIn('Markdown', res.data['body'])

    def test_draft_not_public(self):
        res = self.client.get('/content/api/posts/draft-only/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


class BlogAdminAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='admin@platform.test',
            password='pass12345',
            phone_number='+15550000099',
            first_name='Plat',
            last_name='Admin',
            role=User.Role.PLATFORM_ADMIN,
            is_verified=True,
        )
        self.owner = User.objects.create_user(
            email='owner@fleet.test',
            password='pass12345',
            phone_number='+15550000098',
            first_name='Fleet',
            last_name='Owner',
            role=User.Role.FLEET_OWNER,
            is_verified=True,
        )

    def test_admin_requires_platform_role(self):
        self.client.force_authenticate(self.owner)
        res = self.client.get('/content/api/admin/posts/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_list_for_platform_admin(self):
        BlogPost.objects.create(slug='a', title='A', body='x', status=BlogPost.Status.DRAFT)
        self.client.force_authenticate(self.admin)
        res = self.client.get('/content/api/admin/posts/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res.data['count'], 1)

    def test_admin_create_post(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post(
            '/content/api/admin/posts/',
            {
                'title': 'New Article',
                'slug': 'new-article-test',
                'body': '## Hello',
                'excerpt': 'Intro',
                'cover_url': '',
                'status': BlogPost.Status.DRAFT,
                'seo_title': 'New Article',
                'seo_description': 'Intro',
            },
            format='json',
            HTTP_HOST='127.0.0.1',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['slug'], 'new-article-test')

    def test_admin_upload_blog_cover(self):
        self.client.force_authenticate(self.admin)
        image = SimpleUploadedFile(
            'cover.png',
            b'\x89PNG\r\n\x1a\n' + b'\x00' * 64,
            content_type='image/png',
        )
        res = self.client.post(
            '/content/api/admin/uploads/cover/',
            {'cover': image},
            format='multipart',
            HTTP_HOST='127.0.0.1',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('cover_url', res.data)
        self.assertIn('/media/blog_covers/', res.data['cover_url'])

    def test_upload_cover_rejects_non_admin(self):
        self.client.force_authenticate(self.owner)
        image = SimpleUploadedFile('cover.png', b'x', content_type='image/png')
        res = self.client.post(
            '/content/api/admin/uploads/cover/',
            {'cover': image},
            format='multipart',
            HTTP_HOST='127.0.0.1',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_publish_draft_appears_on_public_api(self):
        draft = BlogPost.objects.create(
            slug='draft-to-live',
            title='Draft To Live',
            body='## Hi',
            status=BlogPost.Status.DRAFT,
        )
        self.assertIsNone(draft.published_at)
        self.client.force_authenticate(self.admin)
        res = self.client.patch(
            f'/content/api/admin/posts/{draft.id}/',
            {'status': BlogPost.Status.PUBLISHED},
            format='json',
            HTTP_HOST='127.0.0.1',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        draft.refresh_from_db()
        self.assertIsNotNone(draft.published_at)

        pub = self.client.get('/content/api/posts/', {'status': 'published', 'limit': 50})
        self.assertEqual(pub.status_code, status.HTTP_200_OK)
        slugs = [p['slug'] for p in pub.data['results']]
        self.assertIn('draft-to-live', slugs)
