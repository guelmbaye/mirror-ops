"""Contrat d'erreur et etats d'echec (Doc 03 §16, Doc 08 §19/§20)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.config import get_settings
from app.integrations.youcam import (
    YouCamProviderError,
    YouCamRateLimitError,
    YouCamTimeoutError,
    set_providers,
)
from app.integrations.youcam.models import SkinAnalysisResult
from tests.conftest import make_image


def assert_error_shape(payload: dict, code: str) -> None:
    assert set(payload) == {"error"}
    error = payload["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["retryable"], bool)
    # Jamais de fuite technique dans le message utilisateur
    lowered = error["message"].lower()
    for forbidden in ("traceback", "youcam", "sqlalchemy", "500 internal", "http"):
        assert forbidden not in lowered


async def test_unknown_session_returns_not_found(client):
    response = await client.get("/api/v1/sessions/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert_error_shape(response.json(), "NOT_FOUND")


async def test_invalid_moment_payload_is_rejected(client, flow):
    session_id = await flow.session()
    response = await client.post(
        "/api/v1/moments",
        json={"session_id": session_id, "occasion": "brunch", "goal": "professional", "time_available": "<5m"},
    )
    assert response.status_code == 422
    assert_error_shape(response.json(), "INVALID_REQUEST")


async def test_corrupted_image_is_rejected(client, flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    response = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("look.jpg", b"this-is-not-an-image", "image/jpeg")},
    )
    assert response.status_code == 422
    assert_error_shape(response.json(), "INVALID_IMAGE")


async def test_tiny_image_asks_for_a_retake(client, flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    tiny = make_image(width=120, height=160, noisy=False)
    response = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("look.jpg", tiny, "image/jpeg")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_IMAGE"
    assert response.json()["error"]["retryable"] is True


async def test_unsupported_format_is_rejected(client, flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    buffer = io.BytesIO()
    Image.new("RGB", (600, 800), (120, 120, 120)).save(buffer, format="BMP")
    response = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("look.bmp", buffer.getvalue(), "image/bmp")},
    )
    assert response.status_code == 422
    assert_error_shape(response.json(), "IMAGE_UNSUPPORTED")


async def test_oversized_image_is_rejected(client, flow, monkeypatch):
    session_id = await flow.session()
    await flow.moment(session_id)
    settings = get_settings()
    monkeypatch.setattr(settings, "MAX_IMAGE_BYTES", 1024, raising=False)
    response = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("look.jpg", make_image(), "image/jpeg")},
    )
    assert response.status_code == 413
    assert_error_shape(response.json(), "IMAGE_TOO_LARGE")


class _FailingSkinProvider:
    provider_name = "test_failing"
    requires_face_crop = False

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def analyze(self, image_bytes, mime_type="image/jpeg", *, file_name="look.jpg"):
        raise self._error


class _FailingVTOProvider:
    provider_name = "test_failing"

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def generate(self, source_image, garment, *, source_mime="image/jpeg"):
        raise self._error


@pytest.mark.parametrize(
    "error",
    [YouCamTimeoutError("timeout"), YouCamProviderError("boom")],
)
async def test_skin_failure_degrades_instead_of_breaking_the_journey(client, flow, error):
    """Skin AI *informe* la decision, il ne la prend pas.

    Son indisponibilite ne doit donc pas interrompre le parcours : on continue
    sans signal peau, en le declarant, et la confiance de decision baisse d'elle
    -meme. Une version anterieure renvoyait 502 et bloquait tout — un provider
    tiers pouvait a lui seul faire echouer une demonstration.
    """
    session_id = await flow.session()
    await flow.moment(session_id)
    set_providers(skin=_FailingSkinProvider(error))

    response = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("look.jpg", make_image(), "image/jpeg")},
    )
    assert response.status_code == 201
    body = response.json()

    # Rien n'est invente...
    assert body["skin"]["redness"] is None
    assert body["skin_source"] == "unavailable"
    # ...et le produit le sait.
    assert body["data_confidence"] < 1.0

    # Le parcours va jusqu'a la decision.
    recommendation = await flow.one_change(session_id)
    assert recommendation["action"]


async def test_rate_limit_still_surfaces_to_the_user(client, flow):
    """Un rate limit n'est pas une degradation : reessayer plus tard a du sens."""
    session_id = await flow.session()
    await flow.moment(session_id)
    set_providers(skin=_FailingSkinProvider(YouCamRateLimitError("slow down")))
    response = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("look.jpg", make_image(), "image/jpeg")},
    )
    assert response.status_code == 429
    assert_error_shape(response.json(), "RATE_LIMITED")


async def test_vto_failure_is_explained_gracefully(client, flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    await flow.one_change(session_id)

    set_providers(vto=_FailingVTOProvider(YouCamTimeoutError("slow")))
    response = await flow.vto(session_id)
    assert response.status_code == 504
    assert_error_shape(response.json(), "VTO_TIMEOUT")


async def test_analysis_never_fabricated_when_provider_returns_nothing(client, flow):
    """Doc 02 §16 : "Le MVP ne doit pas produire une fausse analyse"."""

    class _EmptyProvider:
        provider_name = "test_empty"

        async def analyze(self, image_bytes, mime_type="image/jpeg", *, file_name="look.jpg"):
            return SkinAnalysisResult(observations={}, provider="test_empty", simulated=True)

    session_id = await flow.session()
    await flow.moment(session_id)
    set_providers(skin=_EmptyProvider())
    response = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("look.jpg", make_image(), "image/jpeg")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["skin"]["redness"] is None  # aucune valeur inventee
    assert body["data_confidence"] < 1.0


async def test_malformed_outfit_json_is_rejected(client, flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    response = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id, "outfit": "{not-json"},
        files={"image": ("look.jpg", make_image(), "image/jpeg")},
    )
    assert response.status_code == 400
    assert_error_shape(response.json(), "INVALID_REQUEST")
