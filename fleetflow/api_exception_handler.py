"""
DRF exception handler — must exist (see REST_FRAMEWORK['EXCEPTION_HANDLER'] in settings).
"""
from __future__ import annotations

import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response
    logger.exception('Unhandled API exception', exc_info=exc)
    detail = str(exc) if settings.DEBUG else 'Internal server error.'
    return Response({'detail': detail}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
