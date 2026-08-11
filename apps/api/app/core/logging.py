"""Logging structure + middleware de contexte de requete (Doc 07 §24).

Regle de securite (Doc 05 §22) : on ne logue jamais d'image brute,
ni de cle API, ni de credentials provider.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings

_SENSITIVE_KEYS = {
    "authorization", "api_key", "youcam_api_key", "client_secret",
    "secret", "token", "password", "image", "image_bytes", "id_token",
}

_RESERVED = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "module", "msecs", "message", "msg", "name",
    "pathname", "process", "processName", "relativeCreated", "stack_info",
    "thread", "threadName", "taskName",
}


def sanitize(payload: dict[str, Any]) -> dict[str, Any]:
    """Retire les valeurs sensibles avant journalisation."""
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in _SENSITIVE_KEYS:
            clean[key] = "***"
        elif isinstance(value, (bytes, bytearray, memoryview)):
            clean[key] = f"<{len(value)} bytes>"
        elif isinstance(value, dict):
            clean[key] = sanitize(value)
        else:
            clean[key] = value
    return clean


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = {k: v for k, v in record.__dict__.items() if k not in _RESERVED and not k.startswith("_")}
        base.update(sanitize(extra))
        if record.exc_info:
            base["exception"] = self.formatException(record.exc_info)
        return json.dumps(base, default=str)


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if settings.LOG_JSON
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s :: %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.LOG_LEVEL.upper())
    logging.getLogger("uvicorn.access").handlers = [handler]


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attache un request_id, mesure la latence, journalise proprement."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logging.getLogger("mirror_ops.request").exception(
                "request_failed",
                extra={"request_id": request_id, "path": request.url.path, "method": request.method},
            )
            raise
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logging.getLogger("mirror_ops.request").info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        return response
