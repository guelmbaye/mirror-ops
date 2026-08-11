"""Fabrique de providers visuels + protocoles internes (Doc 05 §16).

Le moteur ONE CHANGE et les services ne dependent QUE de ces deux protocoles.
Passer de `mock` a `live` ne change aucune ligne de code metier.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.core.config import get_settings
from app.integrations.youcam.apparel_vto import ApparelVTOService
from app.integrations.youcam.mock import LocalCompositeVTOService, LocalSkinHeuristicService
from app.integrations.youcam.models import GarmentRef, SkinAnalysisResult, VTOGenerationResult


@runtime_checkable
class SkinProvider(Protocol):
    provider_name: str
    #: Le provider exige-t-il un gros plan du visage ? C'est une contrainte de
    #: YouCam Skin AI (visage > 60 % de la largeur), pas du produit : l'analyse
    #: locale, elle, travaille sur l'image telle quelle.
    requires_face_crop: bool

    async def analyze(
        self, image_bytes: bytes, mime_type: str = "image/jpeg", *, file_name: str = "look.jpg"
    ) -> SkinAnalysisResult: ...


@runtime_checkable
class VTOProvider(Protocol):
    provider_name: str

    async def generate(
        self, source_image: bytes, garment: GarmentRef, *, source_mime: str = "image/jpeg"
    ) -> VTOGenerationResult: ...


_skin_provider: SkinProvider | None = None
_vto_provider: VTOProvider | None = None


def get_skin_provider() -> SkinProvider:
    global _skin_provider
    if _skin_provider is None:
        if get_settings().is_live_youcam:
            from app.integrations.youcam.skin_ai import SkinAIService

            _skin_provider = SkinAIService()
        else:
            _skin_provider = LocalSkinHeuristicService()
    return _skin_provider


def get_vto_provider() -> VTOProvider:
    global _vto_provider
    if _vto_provider is None:
        _vto_provider = (
            ApparelVTOService() if get_settings().is_live_youcam else LocalCompositeVTOService()
        )
    return _vto_provider


def reset_providers() -> None:
    """Utilise par les tests et par le rechargement de configuration."""
    global _skin_provider, _vto_provider
    _skin_provider = None
    _vto_provider = None


def set_providers(
    skin: SkinProvider | None = None, vto: VTOProvider | None = None
) -> None:  # pragma: no cover - utilitaire de test
    global _skin_provider, _vto_provider
    if skin is not None:
        _skin_provider = skin
    if vto is not None:
        _vto_provider = vto
