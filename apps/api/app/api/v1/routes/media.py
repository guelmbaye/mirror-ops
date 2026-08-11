"""Service de medias temporaires signes (Doc 07 §22)."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response

from app.core.errors import AppError, ErrorCode
from app.core.security import verify_media_signature
from app.services.storage import get_storage

router = APIRouter(tags=["media"])

_MIME_BY_EXTENSION = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


@router.get("/media/{key:path}", summary="Lire un media temporaire signe")
async def get_media(
    key: str,
    exp: int = Query(..., description="Expiration (epoch seconds)"),
    sig: str = Query(..., description="Signature HMAC"),
) -> Response:
    if not verify_media_signature(key, exp, sig):
        raise AppError(ErrorCode.MEDIA_LINK_EXPIRED, "This preview link is no longer valid.")
    data = await get_storage().get(key)
    extension = key.rsplit(".", 1)[-1].lower()
    return Response(
        content=data,
        media_type=_MIME_BY_EXTENSION.get(extension, "application/octet-stream"),
        headers={"Cache-Control": "private, max-age=300", "X-Robots-Tag": "noindex"},
    )
