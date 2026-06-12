import logging
import time

from django.conf import settings

logger = logging.getLogger('fleetflow.request_timing')


class RequestTimingMiddleware:
    """Log API request durations so slow endpoints are visible in normal logs."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.slow_ms = int(getattr(settings, 'REQUEST_TIMING_SLOW_MS', 750))

    def __call__(self, request):
        started = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - started) * 1000

        log = logger.warning if elapsed_ms >= self.slow_ms else logger.info
        log(
            'request_timing method=%s path=%s status=%s duration_ms=%.1f',
            request.method,
            request.path,
            getattr(response, 'status_code', '-'),
            elapsed_ms,
        )
        response['X-Response-Time-ms'] = f'{elapsed_ms:.1f}'
        return response
