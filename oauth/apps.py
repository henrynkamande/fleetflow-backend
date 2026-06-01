import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class OauthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'oauth'

    def ready(self) -> None:
        from oauth.email_conf import describe_email_backend

        logger.info('Outbound email: %s', describe_email_backend())
