from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0005_user_platform_admin_role'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingFleetOwnerSignup',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(db_index=True, max_length=254, unique=True)),
                ('phone_number', models.CharField(max_length=20)),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('password', models.CharField(max_length=128)),
                ('code_hash', models.CharField(blank=True, max_length=128)),
                ('code_expires_at', models.DateTimeField(blank=True, null=True)),
                ('code_sent_at', models.DateTimeField(blank=True, null=True)),
                ('code_attempts', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'pending_fleet_owner_signups',
            },
        ),
    ]
