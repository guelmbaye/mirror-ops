"""Modeles internes stables exposes par l'adapter (Doc 05 §7 / §25).

"Le reste de MIRROR OPS ne doit jamais dependre du format proprietaire YouCam."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.db.base import utcnow


@dataclass(frozen=True, slots=True)
class SkinAnalysisResult:
    """Observations cosmetiques normalisees 0..1 (jamais un diagnostic)."""

    observations: dict[str, float]
    provider: str
    simulated: bool = False
    latency_ms: int = 0
    provider_task_id: str | None = None
    analyzed_at: datetime = field(default_factory=utcnow)

    @property
    def available(self) -> bool:
        return bool(self.observations)


@dataclass(frozen=True, slots=True)
class VTOGenerationResult:
    image_bytes: bytes
    mime_type: str
    provider: str
    simulated: bool = False
    latency_ms: int = 0
    provider_task_id: str | None = None


@dataclass(frozen=True, slots=True)
class GarmentRef:
    """Vetement transmis au VTO : id catalogue + octets de l'asset."""

    garment_id: str
    category: str
    name: str
    image_bytes: bytes
    mime_type: str = "image/png"
