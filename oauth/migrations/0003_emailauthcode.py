# Generated manually for EmailAuthCode model

import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('oauth', '0002_driverprofile_otp_attempts_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailAuthCode',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('purpose', models.CharField(choices=[('SIGNUP_VERIFY', 'Signup verification'), ('PASSWORD_RESET', 'Password reset')], db_index=True, max_length=32)),
                ('code_hash', models.CharField(max_length=128)),
                ('expires_at', models.DateTimeField()),
                ('sent_at', models.DateTimeField()),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_auth_codes', to='oauth.user')),
            ],
            options={
                'db_table': 'email_auth_codes',
            },
        ),
        migrations.AddConstraint(
            model_name='emailauthcode',
            constraint=models.UniqueConstraint(fields=('user', 'purpose'), name='unique_user_email_auth_code_purpose'),
        ),
    ]
