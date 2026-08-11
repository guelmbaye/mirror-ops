"""Un echec de tache doit dire ce qu'il faut corriger.

Incident a l'origine de ce module : une tache VTO terminee en `error` remontait
« Provider task failed (error) » avec un `detail` vide. L'API nommait pourtant
la cause — pose non detectee, plusieurs personnes, cadrage inadapte — et cette
information n'atteignait ni les logs ni l'utilisateur.
"""

from __future__ import annotations

import httpx
import pytest

from app.core.config import get_settings
from app.integrations.youcam.client import YouCamClient
from app.integrations.youcam.exceptions import (
    YouCamInvalidImageError,
    YouCamProviderError,
    diagnostics,
)
from app.integrations.youcam.mappers import extract_task_error
from app.services.photo_guidance import DEFAULT_PHOTO_GUIDANCE, guidance_for


def _client(handler) -> YouCamClient:
    transport = httpx.MockTransport(handler)
    return YouCamClient(http_client=httpx.AsyncClient(transport=transport, base_url="https://p.test"))


def test_error_code_and_message_are_extracted():
    payload = {
        "status": 200,
        "data": {"task_status": "error", "error_code": "error_pose", "error": "Failed to detect pose"},
    }
    assert extract_task_error(payload) == ("error_pose", "Failed to detect pose")


def test_extraction_survives_an_empty_failure():
    assert extract_task_error({"data": {"task_status": "error"}}) == (None, None)


async def _run_failing_task(monkeypatch, payload):
    settings = get_settings()
    monkeypatch.setattr(settings, "YOUCAM_AUTH_MODE", "api_key", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_API_KEY", "k", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_POLL_INTERVAL_MS", 1, raising=False)
    monkeypatch.setattr(settings, "YOUCAM_TASK_ID_IN_PATH", True, raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return await _client(handler).poll_task("/s2s/v2.0/task/cloth", "t-1")


async def test_a_photo_problem_is_not_reported_as_a_service_failure(monkeypatch):
    payload = {
        "status": 200,
        "data": {"task_status": "error", "error_code": "error_pose", "error": "Failed to detect pose"},
    }
    with pytest.raises(YouCamInvalidImageError) as caught:
        await _run_failing_task(monkeypatch, payload)

    error = caught.value
    assert error.provider_code == "error_pose"
    assert "error_pose" in (error.detail or "")
    # Et la cause atteint bien les logs.
    assert diagnostics(error, "youcam_apparel_vto")["provider_code"] == "error_pose"


async def test_an_internal_provider_failure_stays_a_provider_error(monkeypatch):
    payload = {
        "status": 200,
        "data": {"task_status": "error", "error_code": "unknown_internal_error"},
    }
    with pytest.raises(YouCamProviderError) as caught:
        await _run_failing_task(monkeypatch, payload)
    assert caught.value.provider_code == "unknown_internal_error"


async def test_the_detail_is_never_empty_when_the_provider_said_something(monkeypatch):
    """Le symptome exact de l'incident : `detail` vide."""
    payload = {"status": 200, "data": {"task_status": "error", "error_code": "error_multiple_people"}}
    with pytest.raises(YouCamInvalidImageError) as caught:
        await _run_failing_task(monkeypatch, payload)
    assert caught.value.detail


def test_each_code_maps_to_an_actionable_sentence():
    assert "one person" in guidance_for("error_multiple_people")
    assert "full body" in guidance_for("error_pose")
    assert "brighter" in guidance_for("error_lighting_dark")
    # Un code inconnu ne doit pas produire une phrase vide.
    assert guidance_for("something_new") == DEFAULT_PHOTO_GUIDANCE
    assert guidance_for(None) == DEFAULT_PHOTO_GUIDANCE


def test_guidance_speaks_to_someone_getting_ready():
    """Aucun jargon d'integrateur dans ce qui s'affiche."""
    from app.services.photo_guidance import PHOTO_GUIDANCE

    for code, sentence in PHOTO_GUIDANCE.items():
        lowered = sentence.lower()
        for jargon in ("error", "api", "provider", "task", "http", "youcam", "_"):
            assert jargon not in lowered, f"{code} expose du jargon : {sentence}"
        assert sentence.endswith(".")


def test_a_code_sent_as_a_message_is_still_recognised():
    """Cas reel : le provider renvoie le code dans `error`, pas `error_code`.

    Le symptome etait un `provider_code` vide alors que `detail` contenait
    « error_editing_failed » — l'information etait la, mal rangee.
    """
    payload = {"status": 200, "data": {"task_status": "error", "error": "error_editing_failed"}}
    assert extract_task_error(payload) == ("error_editing_failed", None)


def test_a_real_sentence_is_not_mistaken_for_a_code():
    payload = {"status": 200, "data": {"task_status": "error", "error": "Failed to detect pose"}}
    code, message = extract_task_error(payload)
    assert code is None
    assert message == "Failed to detect pose"


def test_an_editing_failure_points_at_the_garment():
    assert "another piece" in guidance_for("error_editing_failed")
