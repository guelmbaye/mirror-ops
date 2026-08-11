"""Primitives de securite : URLs media signees + comparaison constante.

Doc 07 §22 : "temporary objects / private bucket / signed URLs".
Les images ne sont jamais servies via une URL publique permanente.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import quote

from app.core.config import get_settings


def _signature(key: str, expires_at: int, secret: str) -> str:
    payload = f"{key}:{expires_at}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()[:32]


def sign_media_key(key: str, ttl_seconds: int | None = None) -> tuple[str, int]:
    """Retourne (signature, expires_at_epoch) pour une cle de stockage."""
    settings = get_settings()
    ttl = ttl_seconds if ttl_seconds is not None else settings.MEDIA_TTL_MINUTES * 60
    expires_at = int(time.time()) + ttl
    return _signature(key, expires_at, settings.MEDIA_SIGNING_SECRET), expires_at


def build_media_url(key: str, ttl_seconds: int | None = None) -> str:
    settings = get_settings()
    signature, expires_at = sign_media_key(key, ttl_seconds)
    base = settings.PUBLIC_BASE_URL.rstrip("/") + settings.API_V1_PREFIX
    return f"{base}/media/{quote(key)}?exp={expires_at}&sig={signature}"


def verify_media_signature(key: str, expires_at: int, signature: str) -> bool:
    settings = get_settings()
    if expires_at < int(time.time()):
        return False
    expected = _signature(key, expires_at, settings.MEDIA_SIGNING_SECRET)
    return hmac.compare_digest(expected, signature)


def hash_bytes(data: bytes) -> str:
    """Empreinte stable d'une image (cache YouCam, idempotency)."""
    return hashlib.sha256(data).hexdigest()
