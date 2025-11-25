from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..logging_utils import bind_request_context, clear_context

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(
        0.05,
        0.1,
        0.25,
        0.5,
        1,
        2.5,
        5,
        10,
        float("inf"),
    ),
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Capture request metadata, log structured events, and expose Prometheus metrics."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = logging.getLogger("app.http")

    async def dispatch(self, request: Request, call_next):
        clear_context()
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        bind_request_context(request_id)
        start = time.perf_counter()
        path_template = getattr(request.scope.get("route"), "path", request.url.path)
        try:
            response = await call_next(request)
            duration = time.perf_counter() - start
            self._record_metrics(request.method, path_template, response.status_code, duration)
            self.logger.info(
                "HTTP request completed",
                extra={
                    "method": request.method,
                    "path": path_template,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
            )
            return response
        except Exception:
            duration = time.perf_counter() - start
            self._record_metrics(request.method, path_template, 500, duration)
            self.logger.exception(
                "HTTP request failed",
                extra={
                    "method": request.method,
                    "path": path_template,
                    "duration_ms": round(duration * 1000, 2),
                },
            )
            raise
        finally:
            clear_context()

    @staticmethod
    def _record_metrics(method: str, path: str, status_code: int, duration: float) -> None:
        REQUEST_COUNT.labels(method=method, path=path, status_code=str(status_code)).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(duration)

