"""Adapter YouCam : normalisation, retries, erreurs, frontiere d'abstraction."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import get_settings
from app.integrations.youcam.client import YouCamClient
from app.integrations.youcam.exceptions import (
    YouCamAuthError,
    YouCamProviderError,
    YouCamRateLimitError,
    YouCamTimeoutError,
)
from app.integrations.youcam.mappers import (
    extract_result_urls,
    extract_status,
    extract_task_id,
    normalize_skin_payload,
)
from app.integrations.youcam.skin_ai import SkinAIService


# ------------------------------------------------------------------ mappers
def test_scores_are_health_scores_and_get_inverted_into_severity():
    """Chez YouCam, un score ELEVE = peau SAINE. Le moteur raisonne en severite.

    Sans cette inversion, une peau parfaite serait lue comme tres marquee — et
    le signal peau pousserait la decision dans le mauvais sens.
    """
    payload = {"result": {"hd_redness": {"score": 31}, "hd_oiliness": 64, "hd_texture": 42}}
    assert normalize_skin_payload(payload) == {"redness": 0.69, "oiliness": 0.36, "texture": 0.58}


def test_radiance_is_a_quality_and_stays_as_is():
    payload = {"data": [{"results": {"redness": 0.28}}, {"results": {"radiance": 0.71}}]}
    assert normalize_skin_payload(payload) == {"redness": 0.72, "radiance": 0.71}


def test_normalize_skin_ignores_unknown_metrics():
    payload = {"wrinkle": 88, "acne": 12, "redness": 40}
    assert normalize_skin_payload(payload) == {"redness": 0.60}


def test_v2_output_array_is_understood():
    """Forme documentee de l'API v2 : une liste d'objets typés."""
    payload = {
        "status": 200,
        "data": {
            "task_status": "success",
            "results": {
                "output": [
                    {"type": "hd_texture", "ui_score": 68, "raw_score": 57.33},
                    {"type": "hd_redness", "ui_score": 77, "raw_score": 72.0},
                ]
            },
        },
    }
    assert normalize_skin_payload(payload) == {"texture": 0.4267, "redness": 0.28}


def test_extract_task_id_and_status():
    assert extract_task_id({"result": {"task_id": "abc-123"}}) == "abc-123"
    assert extract_status({"result": {"status": "SUCCESS"}}) == "success"
    assert extract_status({}) == "unknown"


def test_extract_result_urls():
    payload = {"result": {"results": [{"data": [{"url": "https://cdn/x.jpg"}]}]}}
    assert extract_result_urls(payload) == ["https://cdn/x.jpg"]


# ------------------------------------------------------------------- client
def _client(handler) -> YouCamClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://provider.test")
    return YouCamClient(http_client=http)


async def test_client_retries_transient_errors_then_succeeds(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "YOUCAM_AUTH_MODE", "api_key", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_RETRY_BACKOFF_MS", 1, raising=False)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, text="temporarily unavailable")
        return httpx.Response(200, json={"result": {"task_id": "t-1"}})

    client = _client(handler)
    data = await client._request_json("POST", "/task", json={})
    assert data["result"]["task_id"] == "t-1"
    assert calls["n"] == 3


async def test_client_does_not_retry_rate_limit(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "YOUCAM_AUTH_MODE", "api_key", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_API_KEY", "test-key", raising=False)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, text="rate limited")

    with pytest.raises(YouCamRateLimitError):
        await _client(handler)._request_json("POST", "/task", json={})
    assert calls["n"] == 1


async def test_client_maps_auth_errors(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "YOUCAM_AUTH_MODE", "api_key", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_API_KEY", "bad", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    with pytest.raises(YouCamAuthError):
        await _client(handler)._request_json("GET", "/whatever")


async def test_client_maps_timeouts(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "YOUCAM_AUTH_MODE", "api_key", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_API_KEY", "k", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_MAX_RETRIES", 0, raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow")

    with pytest.raises(YouCamTimeoutError):
        await _client(handler)._request_json("GET", "/whatever")


async def test_missing_credentials_raise_auth_error(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "YOUCAM_AUTH_MODE", "client_credentials", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_CLIENT_ID", None, raising=False)
    monkeypatch.setattr(settings, "YOUCAM_CLIENT_SECRET", None, raising=False)

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return httpx.Response(200, json={})

    with pytest.raises(YouCamAuthError):
        await _client(handler)._request_json("GET", "/whatever")


async def test_live_skin_adapter_end_to_end_against_fake_provider(monkeypatch):
    """Protocole v2 complet : upload -> tache -> polling par chemin -> scores."""
    settings = get_settings()
    monkeypatch.setattr(settings, "YOUCAM_AUTH_MODE", "api_key", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_POLL_INTERVAL_MS", 1, raising=False)
    monkeypatch.setattr(settings, "YOUCAM_TASK_ID_IN_PATH", True, raising=False)
    monkeypatch.setattr(settings, "YOUCAM_SKIN_TASK_PATH", "/s2s/v2.0/task/skin-analysis", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_SKIN_FILE_PATH", "/s2s/v2.0/file/skin-analysis", raising=False)
    seen: dict[str, object] = {}
    polls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        # La cle API part en Bearer : v2 n'a pas d'endpoint d'authentification.
        if path.startswith("/s2s"):
            seen["auth"] = request.headers.get("authorization")

        if request.method == "POST" and path == "/s2s/v2.0/file/skin-analysis":
            return httpx.Response(
                200,
                json={
                    "status": 200,
                    "data": {
                        "files": [
                            {
                                "file_id": "f-1",
                                "requests": [
                                    {
                                        "method": "PUT",
                                        "url": "https://provider.test/upload/f-1",
                                        # v2 : en-tetes sous forme d'objet
                                        "headers": {"Content-Type": "image/jpeg"},
                                    }
                                ],
                            }
                        ]
                    },
                },
            )
        if request.method == "PUT":
            return httpx.Response(200)
        if request.method == "POST" and path == "/s2s/v2.0/task/skin-analysis":
            import json as _json

            seen["task_payload"] = _json.loads(request.content)
            return httpx.Response(200, json={"status": 200, "data": {"task_id": "t-9"}})
        if request.method == "GET" and path.startswith("/s2s/v2.0/task/skin-analysis/"):
            seen["poll_path"] = path
            polls["n"] += 1
            if polls["n"] < 2:
                return httpx.Response(200, json={"status": 200, "data": {"task_status": "running"}})
            return httpx.Response(
                200,
                json={
                    "status": 200,
                    "data": {
                        "task_status": "success",
                        "results": {
                            "output": [
                                {"type": "hd_redness", "raw_score": 31},
                                {"type": "hd_oiliness", "raw_score": 64},
                                {"type": "hd_texture", "raw_score": 42},
                            ]
                        },
                    },
                },
            )
        return httpx.Response(404)  # pragma: no cover

    service = SkinAIService(client=_client(handler))
    result = await service.analyze(b"fake-image-bytes", "image/jpeg")

    assert seen["auth"] == "Bearer test-key"
    assert seen["poll_path"] == "/s2s/v2.0/task/skin-analysis/t-9"
    assert seen["task_payload"]["src_file_id"] == "f-1"
    assert seen["task_payload"]["format"] == "json"

    assert result.simulated is False
    assert result.provider == "youcam_skin_ai"
    # Scores de sante inverses en severite.
    assert result.observations == {"redness": 0.69, "oiliness": 0.36, "texture": 0.58}
    assert result.provider_task_id == "t-9"


async def test_live_skin_adapter_refuses_to_invent_observations(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "YOUCAM_AUTH_MODE", "api_key", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_POLL_INTERVAL_MS", 1, raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path.endswith("/file/skin-analysis"):
            return httpx.Response(
                200,
                json={"data": {"files": [{"file_id": "f", "requests": [{"url": "https://provider.test/u"}]}]}},
            )
        if request.method == "PUT":
            return httpx.Response(200)
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"task_id": "t"}})
        return httpx.Response(200, json={"data": {"task_status": "success", "results": {"output": []}}})

    service = SkinAIService(client=_client(handler))
    with pytest.raises(YouCamProviderError):
        await service.analyze(b"fake", "image/jpeg")


async def test_vto_payload_uses_the_singular_ref_file_id(monkeypatch):
    """Trois iterations ont porte sur cette charge utile : on la verrouille.

    L'API refuse `ref_file_ids` (tableau) et exige `ref_file_id`. Le message
    d'erreur etait explicite : « ref_file_id is required but wasn't included ».
    """
    from app.integrations.youcam.apparel_vto import ApparelVTOService, garment_category_for
    from app.integrations.youcam.models import GarmentRef

    settings = get_settings()
    monkeypatch.setattr(settings, "YOUCAM_AUTH_MODE", "api_key", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_API_KEY", "k", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_POLL_INTERVAL_MS", 1, raising=False)
    monkeypatch.setattr(settings, "YOUCAM_VTO_FILE_PATH", "/s2s/v2.0/file/cloth", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_VTO_TASK_PATH", "/s2s/v2.0/task/cloth", raising=False)

    seen: dict[str, object] = {}
    uploads = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        path = request.url.path
        if request.method == "POST" and path == "/s2s/v2.0/file/cloth":
            uploads["n"] += 1
            return httpx.Response(
                200,
                json={
                    "data": {
                        "files": [
                            {
                                "file_id": f"file-{uploads['n']}",
                                "requests": [{"url": "https://provider.test/u", "headers": {}}],
                            }
                        ]
                    }
                },
            )
        if request.method == "PUT":
            return httpx.Response(200)
        if request.method == "POST" and path == "/s2s/v2.0/task/cloth":
            seen["payload"] = _json.loads(request.content)
            return httpx.Response(200, json={"data": {"task_id": "vt-1"}})
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "task_status": "success",
                        "results": [{"data": [{"url": "https://cdn/after.jpg"}]}],
                    }
                },
            )
        return httpx.Response(200, content=b"image-bytes")  # pragma: no cover

    service = ApparelVTOService(client=_client(handler))
    garment = GarmentRef(
        garment_id="jacket_01",
        category="jacket",
        name="Structured Neutral Jacket",
        image_bytes=b"png-bytes",
        mime_type="image/png",
    )
    await service.generate(b"look-bytes", garment)

    payload = seen["payload"]
    assert "ref_file_ids" not in payload
    assert payload["ref_file_id"] == "file-2"
    assert payload["src_file_id"] == "file-1"
    assert payload["garment_category"] == "upper_body"
    assert payload["change_shoes"] is False


def test_unknown_categories_fall_back_to_auto():
    """Mieux vaut laisser le provider deduire que lui imposer une valeur refusee."""
    from app.integrations.youcam.apparel_vto import garment_category_for

    assert garment_category_for("jacket") == "upper_body"
    assert garment_category_for("bottom") == "lower_body"
    assert garment_category_for("shoes") == "shoes"
    assert garment_category_for("accessories") == "auto"


async def test_an_empty_result_carries_the_payload(monkeypatch):
    """« No usable skin observation returned » etait un cul-de-sac.

    L'erreur ne portait ni code provider ni indice : la sonde affichait un
    tiret, et il devenait impossible de savoir si la tache avait echoue ou si
    elle avait renvoye une forme que nous ne savons pas lire.
    """
    from app.integrations.youcam.exceptions import YouCamProviderError
    from app.integrations.youcam.skin_ai import SkinAIService

    settings = get_settings()
    monkeypatch.setattr(settings, "YOUCAM_AUTH_MODE", "api_key", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_API_KEY", "k", raising=False)
    monkeypatch.setattr(settings, "YOUCAM_POLL_INTERVAL_MS", 1, raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path.endswith("/file/skin-analysis"):
            return httpx.Response(200, json={"data": {"files": [
                {"file_id": "f", "requests": [{"url": "https://p.test/u", "headers": {}}]}
            ]}})
        if request.method == "PUT":
            return httpx.Response(200)
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"task_id": "t"}})
        # Tache reussie, mais aucune metrique reconnue.
        return httpx.Response(200, json={
            "status": 200,
            "data": {"task_status": "success", "results": {"unexpected_shape": [1, 2, 3]}},
        })

    service = SkinAIService(client=_client(handler))
    with pytest.raises(YouCamProviderError) as caught:
        await service.analyze(b"bytes", "image/jpeg")

    error = caught.value
    assert error.provider_code == "empty_result"
    assert error.detail, "the payload must travel with the error"
    assert "unexpected_shape" in error.detail
