import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BlogPost',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('slug', models.SlugField(max_length=200, unique=True)),
                ('title', models.CharField(max_length=300)),
                ('excerpt', models.TextField(blank=True)),
                ('body', models.TextField(help_text='Markdown content')),
                ('cover_url', models.URLField(blank=True, max_length=500)),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('PUBLISHED', 'Published'), ('SCHEDULED', 'Scheduled')], db_index=True, default='DRAFT', max_length=20)),
                ('seo_title', models.CharField(blank=True, max_length=300)),
                ('seo_description', models.CharField(blank=True, max_length=500)),
                ('published_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='blog_posts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'blog_posts',
                'ordering': ['-published_at', '-created_at'],
            },
        ),
    ]
