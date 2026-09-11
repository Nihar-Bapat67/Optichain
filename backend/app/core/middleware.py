"""HTTP middleware: request correlation, access logging and security headers.

None of these change routing, status codes or response bodies — they only add
response headers and emit logs.
"""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.logging import get_logger, request_id_var

logger = get_logger("app.request")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, logs the outcome, and reports server timing."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Honour an upstream id when a proxy supplies one, so traces join up.
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming or uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - started) * 1000
            # exception() captures the traceback that was previously lost entirely.
            logger.exception(
                "%s %s failed after %.1fms",
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise
        finally:
            request_id_var.reset(token)

        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["Server-Timing"] = f"app;dur={elapsed_ms:.1f}"

        log = logger.warning if response.status_code >= 500 else logger.info
        log(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds the standard hardening headers (the Helmet equivalent).

    The API serves JSON only, so the policy can be maximally restrictive: no
    framing, no sniffing, no referrers, and a CSP that permits nothing.
    """

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        super().__init__(app)
        self.hsts = hsts

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
        )
        headers.setdefault("Cross-Origin-Resource-Policy", "same-site")

        # Interactive docs need to load their own JS/CSS, so exempt those paths.
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            )

        # Only meaningful over TLS; enabling it on plain HTTP dev servers can
        # lock a developer's browser out of localhost.
        if self.hsts:
            headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        return response
