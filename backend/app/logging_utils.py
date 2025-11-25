from __future__ import annotations

import contextvars
import json
import logging
import logging.config
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import yaml
from prometheus_client import Counter, REGISTRY

from .core.config import Settings

_DEFAULT_CONTEXT = "-"
_REQUEST_ID = contextvars.ContextVar("request_id", default=_DEFAULT_CONTEXT)
_USER_ID = contextvars.ContextVar("user_id", default=_DEFAULT_CONTEXT)
_DOCUMENT_ID = contextvars.ContextVar("document_id", default=_DEFAULT_CONTEXT)
_TASK_ID = contextvars.ContextVar("task_id", default=_DEFAULT_CONTEXT)

def _register_error_counter() -> Counter:
    try:
        return Counter(
            "log_errors_total",
            "Total log statements at error level or above",
            ["module", "level"],
            registry=REGISTRY,
        )
    except ValueError:
        existing = getattr(REGISTRY, "_names_to_collectors", {}).get("log_errors_total")
        if existing:
            return existing  # type: ignore[return-value]
        raise


LOG_ERROR_COUNTER = _register_error_counter()


def bind_request_context(request_id: Optional[str] = None) -> None:
    if request_id:
        _REQUEST_ID.set(request_id)


def bind_user_context(user_id: Optional[str]) -> None:
    if user_id:
        _USER_ID.set(user_id)


def bind_document_context(document_id: Optional[str]) -> None:
    if document_id:
        _DOCUMENT_ID.set(document_id)


def bind_task_context(task_id: Optional[str]) -> None:
    if task_id:
        _TASK_ID.set(task_id)


def clear_context() -> None:
    _REQUEST_ID.set(_DEFAULT_CONTEXT)
    _USER_ID.set(_DEFAULT_CONTEXT)
    _DOCUMENT_ID.set(_DEFAULT_CONTEXT)
    _TASK_ID.set(_DEFAULT_CONTEXT)


def current_context() -> Dict[str, str]:
    return {
        "request_id": _REQUEST_ID.get(),
        "user_id": _USER_ID.get(),
        "document_id": _DOCUMENT_ID.get(),
        "task_id": _TASK_ID.get(),
    }


class ContextFilter(logging.Filter):
    """Inject contextvars into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        record.request_id = _REQUEST_ID.get()
        record.user_id = _USER_ID.get()
        record.document_id = _DOCUMENT_ID.get()
        record.task_id = _TASK_ID.get()
        record.error_code = getattr(record, "error_code", "")
        return True


class PIIRedactingFilter(logging.Filter):
    """Filter that removes common PII tokens such as emails or API keys."""

    _PATTERNS: Iterable[re.Pattern[str]] = (
        re.compile(r"sk-[a-zA-Z0-9]{10,}", re.IGNORECASE),
        re.compile(r"bearer [a-z0-9\._\-]{10,}", re.IGNORECASE),
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    )
    _REPLACEMENT = "[REDACTED]"

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        record.msg = self._scrub(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(self._scrub(arg) for arg in record.args)
        return True

    def _scrub(self, value: Any) -> Any:
        if isinstance(value, str):
            redacted = value
            for pattern in self._PATTERNS:
                redacted = pattern.sub(self._REPLACEMENT, redacted)
            return redacted
        if isinstance(value, dict):
            return {k: self._scrub(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._scrub(item) for item in value]
        return value


class PrometheusErrorHandler(logging.Handler):
    """A logging handler that increments a Prometheus counter on errors."""

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            LOG_ERROR_COUNTER.labels(module=record.name, level=record.levelname).inc()
        except Exception:  # pragma: no cover - never raise from logging
            pass


def setup_logging(settings: Settings) -> None:
    """Load logging.yaml and configure handlers per environment."""

    config_path = settings.log_config_path or Path(__file__).with_name("logging.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"Logging configuration not found at {config_path}")

    with config_path.open("r", encoding="utf-8") as fp:
        config: Dict[str, Any] = yaml.safe_load(fp)

    log_dir = settings.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = config.get("handlers", {}).get("file")
    if file_handler:
        file_handler["filename"] = str(log_dir / "backend.log")

    env = settings.environment.lower()

    app_handlers: list[str]
    if env == "development":
        app_handlers = ["console", "error_metrics"]
        config["root"]["handlers"] = ["console"]
    else:
        app_handlers = ["json", "error_metrics"]
        if settings.enable_file_logging:
            app_handlers.append("file")
        config["root"]["handlers"] = ["json"]

    config.setdefault("loggers", {})
    config["loggers"]["app"] = {
        "handlers": app_handlers,
        "level": settings.log_level.upper(),
        "propagate": False,
    }

    for handler_name in ("console", "json"):
        handler = config.get("handlers", {}).get(handler_name)
        if handler:
            handler["level"] = settings.log_level.upper()

    if not settings.enable_json_logs and "json" in config["handlers"]:
        # fallback to console handler only
        app_handlers = ["console", "error_metrics"]
        config["root"]["handlers"] = ["console"]
        config["loggers"]["app"]["handlers"] = app_handlers

    logging.config.dictConfig(config)


def serialize_log_record(record: logging.LogRecord) -> str:
    payload = {
        "timestamp": record.created,
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
        "context": current_context(),
    }
    return json.dumps(payload, ensure_ascii=False)


__all__ = [
    "bind_request_context",
    "bind_user_context",
    "bind_document_context",
    "bind_task_context",
    "clear_context",
    "ContextFilter",
    "PIIRedactingFilter",
    "PrometheusErrorHandler",
    "setup_logging",
    "current_context",
]

