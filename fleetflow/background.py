"""Small background task runner for non-critical follow-up work.

This keeps request handlers from waiting on external services or expensive
aggregate updates. It is intentionally lightweight; replace with Celery/RQ when
durable retries become a product requirement.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from django.db import connection, transaction

logger = logging.getLogger(__name__)


def run_after_commit(name: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    def _start() -> None:
        def _run() -> None:
            try:
                func(*args, **kwargs)
            except Exception:
                logger.exception('Background task failed: %s', name)
            finally:
                connection.close()

        threading.Thread(target=_run, name=f'bg-{name[:40]}', daemon=True).start()

    transaction.on_commit(_start)
