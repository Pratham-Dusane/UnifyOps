"""
UnifyOps - Middleware (FR-0.4.3, FR-0.5.1)

- RequestIDMiddleware: Generates/propagates X-Request-ID on every request.
- LoggingMiddleware: Logs method, path, status_code, latency_ms per request.
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Assigns a unique X-Request-ID to every request.
    If the client sends one, it is preserved; otherwise a new UUID is generated.
    The ID is propagated to the response headers and bound to structlog context
    so every downstream log entry carries it automatically.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Bind request_id into structlog context vars for all downstream logs
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Store on request state for access in route handlers
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every request with structured fields:
    severity, request_id, service_name, method, path, status_code, latency_ms.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        logger = structlog.get_logger(service_name="unifyops-api")
        start_time = time.perf_counter()

        response = await call_next(request)

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.info(
            "request_completed",
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            latency_ms=latency_ms,
        )

        return response
