"""Application logging.

The codebase previously had no logging at all: model-load failures and CSV read
errors were swallowed silently, which made production issues invisible. This
module gives every component one consistent logger to write to.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

# Populated per request by RequestContextMiddleware so log lines can be
# correlated back to the request that produced them.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Injects the current request id into every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | req=%(request_id)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def configure_logging(level: str = "INFO") -> None:
    """Install a single stdout handler on the root logger.

    Safe to call more than once; repeated calls are ignored so that reload
    workers do not stack duplicate handlers.
    """
    global _configured
    if _configured:
        return

    resolved = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(resolved)

    # uvicorn installs its own handlers; let them propagate to ours instead so
    # access and application logs share one format.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Module-level logger, namespaced under the app."""
    return logging.getLogger(name)
