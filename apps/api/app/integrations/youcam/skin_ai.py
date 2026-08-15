"""Adapter YouCam Skin AI (Doc 05 §6/§7/§8).

Interface interne consommee par le reste du produit :

    SkinAIService.analyze(image_bytes, mime) -> SkinAnalysisResult

Rien d'autre dans MIRROR OPS ne connait le format YouCam.
"""

from __future__ import annotations

import logging
import time

from app.core.config import get_settings
from app.integrations.youcam.client import YouCamClient, get_youcam_client
from app.integrations.youcam.exceptions import YouCamProviderError
from app.integrations.youcam.mappers import extract_result_urls, normalize_skin_payload
from app.integrations.youcam.models import SkinAnalysisResult

logger = logging.getLogger("mirror_ops.youcam.skin")


class SkinAIService:
    """Implementation live : appelle reellement l'API YouCam Skin AI."""

    provider_name = "youcam_skin_ai"
    requires_face_crop = True

    def __init__(self, client: YouCamClient | None = None) -> None:
        self._client = client or get_youcam_client()
        self._settings = get_settings()

    async def analyze(
        self, image_bytes: bytes, mime_type: str = "image/jpeg", *, file_name: str = "look.jpg"
    ) -> SkinAnalysisResult:
        started = time.perf_counter()
        settings = self._settings

        slot = await self._client.request_upload_slot(
            settings.YOUCAM_SKIN_FILE_PATH,
            file_name=file_name,
            content_type=mime_type,
            size=len(image_bytes),
        )
        file_id, upload_url, upload_headers = _read_upload_slot(slot)
        await self._client.upload_bytes(upload_url, image_bytes, mime_type, upload_headers)

        # Charge utile v2 : structure plate. Le format `json` renvoie les scores
        # directement dans la reponse, sans archive a telecharger.
        task_id = await self._client.create_task(
            settings.YOUCAM_SKIN_TASK_PATH,
            {
                "src_file_id": file_id,
                "dst_actions": settings.skin_action_list,
                "format": settings.YOUCAM_SKIN_RESULT_FORMAT,
            },
        )
        result = await self._client.poll_task(settings.YOUCAM_SKIN_TASK_PATH, task_id)

        observations = normalize_skin_payload(result)
        if not observations:
            # Certains comptes renvoient un lien vers une archive de resultats.
            for url in extract_result_urls(result)[:1]:
                payload = await self._client.download_bytes(url)
                observations = normalize_skin_payload(_maybe_json(payload))

        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "skin_ai_completed",
            extra={"latency_ms": latency_ms, "observations": list(observations)},
        )
        if not observations:
            # La tache a abouti, mais rien d'exploitable n'en est ressorti.
            # Sans la charge utile, cette erreur est un cul-de-sac : elle ne
            # porte ni code provider, ni indice sur ce qui a ete renvoye.
            import json as _json

            try:
                snippet = _json.dumps(result)[:400]
            except (TypeError, ValueError):  # pragma: no cover
                snippet = str(result)[:400]
            raise YouCamProviderError(
                "No usable skin observation returned",
                detail=snippet,
                provider_code="empty_result",
            )

        return SkinAnalysisResult(
            observations=observations,
            provider=self.provider_name,
            simulated=False,
            latency_ms=latency_ms,
            provider_task_id=task_id,
        )


def _read_upload_slot(slot: dict) -> tuple[str, str, dict]:
    # v2 encapsule dans `data`, v1 dans `result`.
    result = slot.get("data") or slot.get("result") or slot
    files = result.get("files") or result.get("file") or []
    if isinstance(files, dict):
        files = [files]
    if not files:
        raise YouCamProviderError("Provider did not return an upload slot")
    entry = files[0]
    file_id = entry.get("file_id") or entry.get("id")
    requests = entry.get("requests") or []
    if requests:
        upload_url = requests[0].get("url")
        raw_headers = requests[0].get("headers", {})
        if isinstance(raw_headers, dict):
            # v2 : {"Content-Type": "image/jpg", "Content-Length": 50000}
            headers = {str(k): str(v) for k, v in raw_headers.items()}
        else:
            # v1 : [{"name": ..., "value": ...}]
            headers = {h["name"]: str(h["value"]) for h in raw_headers if "name" in h}
    else:
        upload_url = entry.get("url") or entry.get("upload_url")
        headers = {}
    if not (file_id and upload_url):
        raise YouCamProviderError("Incomplete upload slot from provider")
    return str(file_id), str(upload_url), headers


def _maybe_json(payload: bytes):
    import json

    try:
        return json.loads(payload.decode("utf-8"))
    except Exception:  # noqa: BLE001 - archive binaire ou format inattendu
        return {}
