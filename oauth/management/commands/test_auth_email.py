from django.core.management.base import BaseCommand, CommandError

from oauth.email_conf import describe_email_backend, delivery_is_real_inbox
from oauth.email_utils import deliver_auth_email


class Command(BaseCommand):
    help = 'Send a test transactional email (validates SendGrid/SMTP on this host).'

    def add_arguments(self, parser):
        parser.add_argument('recipient', type=str, help='Inbox to receive the test message')

    def handle(self, *args, **options):
        recipient = options['recipient'].strip()
        if not recipient or '@' not in recipient:
            raise CommandError('Provide a valid recipient email address.')

        self.stdout.write(f'Backend: {describe_email_backend()}')
        if not delivery_is_real_inbox():
            self.stdout.write(
                self.style.WARNING(
                    'This environment uses the console backend — check runserver/logs, not an inbox.'
                )
            )

        ok = deliver_auth_email(
            subject='FleetVault email test',
            message=(
                'If you received this message, outbound email from the API is working.\n'
                'You can delete this message.'
            ),
            recipient=recipient,
        )
        if ok:
            self.stdout.write(self.style.SUCCESS(f'Test email accepted for delivery to {recipient}.'))
            if delivery_is_real_inbox():
                self.stdout.write('Check inbox and spam; SendGrid Activity shows delivery status.')
        else:
            raise CommandError(
                'Send failed. See application logs (Auth email failed). '
                'Verify SENDGRID_API_KEY and DEFAULT_FROM_EMAIL (verified sender in SendGrid).'
            )
