import os

from django.core.management.base import BaseCommand, CommandError

from oauth.models import User


class Command(BaseCommand):
    help = 'Create or update a PLATFORM_ADMIN user (email from PLATFORM_ADMIN_EMAIL env).'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Admin email (overrides PLATFORM_ADMIN_EMAIL)')
        parser.add_argument('--password', type=str, help='Password (overrides PLATFORM_ADMIN_PASSWORD)')
        parser.add_argument('--phone', type=str, default='+10000000001', help='Unique phone number')

    def handle(self, *args, **options):
        email = (options.get('email') or os.environ.get('PLATFORM_ADMIN_EMAIL', '')).strip().lower()
        password = options.get('password') or os.environ.get('PLATFORM_ADMIN_PASSWORD', '')
        if not email or not password:
            raise CommandError('Set --email/--password or PLATFORM_ADMIN_EMAIL and PLATFORM_ADMIN_PASSWORD.')

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'phone_number': options['phone'],
                'first_name': 'Platform',
                'last_name': 'Admin',
                'role': User.Role.PLATFORM_ADMIN,
                'is_verified': True,
                'is_staff': True,
                'is_active': True,
            },
        )
        user.role = User.Role.PLATFORM_ADMIN
        user.is_verified = True
        user.is_staff = True
        user.is_active = True
        user.set_password(password)
        user.save()
        verb = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{verb} platform admin: {email}'))
