"""Adapter YouCam Apparel Virtual Try-On (Doc 05 §10 a §14).

    ApparelVTOService.generate(source_image, garment) -> VTOGenerationResult

Regle produit majeure (Doc 05 §12) : le VTO n'est appele QUE pour le gagnant
ONE CHANGE. Jamais pour les candidats perdants.
"""

from __future__ import annotations

import logging
import time

from app.core.config import get_settings
from app.integrations.youcam.client import YouCamClient, get_youcam_client
from app.integrations.youcam.exceptions import YouCamProviderError
from app.integrations.youcam.mappers import extract_result_urls
from app.integrations.youcam.models import GarmentRef, VTOGenerationResult
from app.integrations.youcam.skin_ai import _read_upload_slot

logger = logging.getLogger("mirror_ops.youcam.vto")

#: Nos categories de catalogue vers celles attendues par l'API Clothes.
#: Tout ce qui n'a pas d'equivalent clair passe en `auto` : mieux vaut laisser
#: le provider deduire que lui imposer une valeur qu'il refusera.
GARMENT_CATEGORY_MAP: dict[str, str] = {
    "jacket": "upper_body",
    "top": "upper_body",
    "bottom": "lower_body",
    "shoes": "shoes",
}


def garment_category_for(category: str) -> str:
    return GARMENT_CATEGORY_MAP.get(category, "auto")


class ApparelVTOService:
    provider_name = "youcam_apparel_vto"

    def __init__(self, client: YouCamClient | None = None) -> None:
        self._client = client or get_youcam_client()
        self._settings = get_settings()

    async def generate(
        self,
        source_image: bytes,
        garment: GarmentRef,
        *,
        source_mime: str = "image/jpeg",
    ) -> VTOGenerationResult:
        started = time.perf_counter()
        settings = self._settings

        source_id = await self._upload(source_image, source_mime, "current-look.jpg")
        garment_id = await self._upload(garment.image_bytes, garment.mime_type, "garment.png")

        # Charge utile v2 : structure plate, comme skin-analysis.
        # `auto` laisse YouCam deduire la categorie : une source d'erreur en
        # moins pour les pieces dont la correspondance n'est pas evidente.
        task_id = await self._client.create_task(
            settings.YOUCAM_VTO_TASK_PATH,
            # `ref_file_id` au SINGULIER : l'API accepte soit la paire
            # (src_file_url, ref_file_url), soit la paire (src_file_id,
            # ref_file_id). Un tableau `ref_file_ids` est rejete — c'est
            # exactement ce que disait le 400 : « ref_file_id is required ».
            {
                "src_file_id": source_id,
                "ref_file_id": garment_id,
                "garment_category": garment_category_for(garment.category),
                "change_shoes": garment.category == "shoes",
            },
        )
        result = await self._client.poll_task(settings.YOUCAM_VTO_TASK_PATH, task_id)

        urls = extract_result_urls(result)
        if not urls:
            raise YouCamProviderError("Provider returned no VTO image")
        image_bytes = await self._client.download_bytes(urls[0])

        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info("vto_completed", extra={"latency_ms": latency_ms, "garment_id": garment.garment_id})

        return VTOGenerationResult(
            image_bytes=image_bytes,
            mime_type="image/jpeg",
            provider=self.provider_name,
            simulated=False,
            latency_ms=latency_ms,
            provider_task_id=task_id,
        )

    async def _upload(self, data: bytes, mime_type: str, file_name: str) -> str:
        slot = await self._client.request_upload_slot(
            self._settings.YOUCAM_VTO_FILE_PATH,
            file_name=file_name,
            content_type=mime_type,
            size=len(data),
        )
        file_id, upload_url, headers = _read_upload_slot(slot)
        await self._client.upload_bytes(upload_url, data, mime_type, headers)
        return file_id
