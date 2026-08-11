"""Securite et confidentialite (Doc 05 §22, Doc 07 §22/§23, Doc 12 §23/§24)."""

from __future__ import annotations

import time

from app.core.config import get_settings
from app.core.logging import sanitize
from app.core.security import build_media_url, sign_media_key, verify_media_signature
from app.services.cleanup_service import cleanup_expired
from app.services.storage import get_storage


async def test_media_urls_are_signed_and_expire():
    key = "sessions/x/input/demo.jpg"
    signature, expires_at = sign_media_key(key, ttl_seconds=60)
    assert verify_media_signature(key, expires_at, signature) is True
    assert verify_media_signature(key, expires_at, "tampered") is False
    assert verify_media_signature("sessions/y/input/demo.jpg", expires_at, signature) is False
    assert verify_media_signature(key, int(time.time()) - 5, signature) is False


async def test_media_requires_valid_signature(client, flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    analysis = await flow.analyze(session_id)
    url = analysis["image_url"].replace("http://testserver", "")

    assert (await client.get(url)).status_code == 200

    tampered = url.split("&sig=")[0] + "&sig=" + "0" * 32
    response = await client.get(tampered)
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "MEDIA_LINK_EXPIRED"


async def test_media_path_traversal_is_blocked(client):
    url = build_media_url("../../etc/passwd").replace("http://testserver", "")
    response = await client.get(url)
    assert response.status_code in (400, 404)


async def test_logs_never_contain_secrets_or_images():
    cleaned = sanitize(
        {
            "youcam_api_key": "secret-value",
            "authorization": "Bearer abc",
            "image": b"\xff\xd8\xff\xe0binary",
            "nested": {"client_secret": "top-secret", "session_id": "s-1"},
            "latency_ms": 42,
        }
    )
    assert cleaned["youcam_api_key"] == "***"
    assert cleaned["authorization"] == "***"
    assert cleaned["image"] == "***"
    assert cleaned["nested"]["client_secret"] == "***"
    assert cleaned["nested"]["session_id"] == "s-1"
    assert cleaned["latency_ms"] == 42


async def test_api_never_returns_provider_credentials(client, flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    await flow.one_change(session_id)
    await flow.vto(session_id)

    body = (await client.get(f"/api/v1/sessions/{session_id}")).text.lower()
    settings = get_settings()
    assert "api_key" not in body
    assert "client_secret" not in body
    assert settings.MEDIA_SIGNING_SECRET not in body
    assert "scoring_weights" not in body
    assert "features" not in body  # les vecteurs de features restent internes


async def test_openapi_documents_the_error_contract(client):
    schema = (await client.get("/openapi.json")).json()
    assert "ErrorEnvelope" in schema["components"]["schemas"]
    assert "/api/v1/one-change/evaluate" in schema["paths"]


async def test_cleanup_removes_expired_media(db, flow):
    from sqlalchemy import select

    from app.db.base import utcnow
    from app.models.image_asset import ImageAsset

    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)

    asset = (
        await db.execute(select(ImageAsset).where(ImageAsset.session_id == session_id))
    ).scalars().first()
    assert asset is not None
    assert await get_storage().exists(asset.storage_key) is True

    asset.expires_at = utcnow().replace(year=utcnow().year - 1)
    await db.commit()

    report = await cleanup_expired(db)
    await db.commit()
    assert report["expired_images"] >= 1
    assert await get_storage().exists(asset.storage_key) is False
