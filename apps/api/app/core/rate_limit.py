"""Rate limiting minimal en memoire (Doc 12 §23 : "Basic rate limiting").

Suffisant pour le MVP hackathon : pas de dependance Redis (Doc 07 §17).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode

_EXEMPT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        if not settings.RATE_LIMIT_ENABLED or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        identity = request.client.host if request.client else "anonymous"
        now = time.monotonic()
        window = self._hits[identity]
        while window and now - window[0] > 60.0:
            window.popleft()
        if len(window) >= settings.RATE_LIMIT_PER_MINUTE:
            err = AppError(ErrorCode.RATE_LIMITED)
            return JSONResponse(status_code=err.status_code, content=err.to_payload())
        window.append(now)
        return await call_next(request)
