from django.core.management.base import BaseCommand, CommandError

from oauth.models import User


class Command(BaseCommand):
    help = 'Check whether an email/password would pass login (no HTTP).'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--password', required=True)

    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        password = options['password']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f'No user with email={email!r}')

        self.stdout.write(f'Found user id={user.id} role={user.role}')
        self.stdout.write(f'  is_active={user.is_active} is_verified={user.is_verified} is_staff={user.is_staff}')

        if not user.check_password(password):
            raise CommandError('Password does NOT match (check_password=False).')

        if not user.is_active:
            raise CommandError('Password matches but is_active=False.')

        if user.is_fleet_owner and not user.is_platform_admin and not user.is_verified:
            raise CommandError('Password matches but fleet owner email is not verified (OTP).')

        self.stdout.write(self.style.SUCCESS('Credentials OK — login API should accept this pair.'))
