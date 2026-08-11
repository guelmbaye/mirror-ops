"""Contrat d'erreur unique (Doc 08 §19 / §20).

Toutes les erreurs de l'API sortent sous la forme :

    {"error": {"code": "...", "message": "...", "retryable": true|false}}

Aucun detail brut du provider (YouCam) n'est jamais expose (Doc 05 §17).
"""

from __future__ import annotations

import logging
from enum import StrEnum

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("mirror_ops.errors")


class ErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_IMAGE = "INVALID_IMAGE"
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"
    IMAGE_UNSUPPORTED = "IMAGE_UNSUPPORTED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    DECISION_FAILED = "DECISION_FAILED"
    VTO_FAILED = "VTO_FAILED"
    VTO_TIMEOUT = "VTO_TIMEOUT"
    VTO_NOT_APPLICABLE = "VTO_NOT_APPLICABLE"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    NOT_FOUND = "NOT_FOUND"
    INVALID_STATE = "INVALID_STATE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    MEDIA_LINK_EXPIRED = "MEDIA_LINK_EXPIRED"


#: code -> (status HTTP, message par defaut orientee utilisateur, retryable)
ERROR_SPEC: dict[ErrorCode, tuple[int, str, bool]] = {
    ErrorCode.INVALID_REQUEST: (400, "This request is missing something we need.", False),
    ErrorCode.INVALID_IMAGE: (422, "We couldn't use this image. Try taking another photo.", True),
    ErrorCode.IMAGE_TOO_LARGE: (413, "This photo is too large.", True),
    ErrorCode.IMAGE_UNSUPPORTED: (422, "This image format isn't supported.", True),
    ErrorCode.ANALYSIS_FAILED: (502, "We couldn't read your look right now.", True),
    ErrorCode.DECISION_FAILED: (500, "We couldn't complete the analysis.", True),
    ErrorCode.VTO_FAILED: (502, "We couldn't complete the visual preview.", True),
    ErrorCode.VTO_TIMEOUT: (504, "The visual preview took too long.", True),
    ErrorCode.VTO_NOT_APPLICABLE: (409, "There is no change to visualize.", False),
    ErrorCode.SESSION_EXPIRED: (409, "This session has expired. Start again.", False),
    ErrorCode.NOT_FOUND: (404, "We couldn't find that.", False),
    ErrorCode.INVALID_STATE: (409, "This step isn't available yet.", False),
    ErrorCode.PROVIDER_UNAVAILABLE: (502, "A required service is unavailable.", True),
    ErrorCode.RATE_LIMITED: (429, "Too many requests. Try again in a moment.", True),
    ErrorCode.INTERNAL_ERROR: (500, "Something went wrong on our side.", True),
    ErrorCode.MEDIA_LINK_EXPIRED: (410, "This link has expired.", False),
}


class AppError(Exception):
    """Erreur applicative portant un code du contrat public."""

    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        *,
        status_code: int | None = None,
        retryable: bool | None = None,
        details: dict | None = None,
    ) -> None:
        spec_status, spec_message, spec_retryable = ERROR_SPEC[code]
        self.code = code
        self.message = message or spec_message
        self.status_code = status_code or spec_status
        self.retryable = spec_retryable if retryable is None else retryable
        self.details = details or {}
        super().__init__(f"{code}: {self.message}")

    def to_payload(self) -> dict:
        payload: dict = {
            "error": {
                "code": str(self.code),
                "message": self.message,
                "retryable": self.retryable,
            }
        }
        if self.details:
            payload["error"]["details"] = self.details
        return payload


def _response(err: AppError, request: Request) -> JSONResponse:
    payload = err.to_payload()
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        payload["error"]["request_id"] = request_id
    return JSONResponse(status_code=err.status_code, content=jsonable_encoder(payload))


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:  # noqa: D401
        logger.warning("app_error", extra={"error_code": str(exc.code), "path": request.url.path})
        return _response(exc, request)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in e.get("loc", [])), "issue": e.get("msg", "")}
            for e in exc.errors()[:10]
        ]
        err = AppError(ErrorCode.INVALID_REQUEST, details={"fields": details})
        err.status_code = 422
        return _response(err, request)

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = ErrorCode.NOT_FOUND if exc.status_code == 404 else ErrorCode.INVALID_REQUEST
        if exc.status_code == 429:
            code = ErrorCode.RATE_LIMITED
        elif exc.status_code >= 500:
            code = ErrorCode.INTERNAL_ERROR
        err = AppError(code, str(exc.detail) if exc.detail else None, status_code=exc.status_code)
        return _response(err, request)

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", extra={"path": request.url.path})
        return _response(AppError(ErrorCode.INTERNAL_ERROR), request)
