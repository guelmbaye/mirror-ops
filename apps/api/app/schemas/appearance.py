from __future__ import annotations

import json
from typing import Any

from pydantic import Field, field_validator

from app.engines.one_change.types import OutfitItem
from app.models.enums import OutfitElement
from app.schemas.common import APIModel, UtcDateTime


class OutfitItemIn(APIModel):
    """Description optionnelle d'une piece de la tenue.

    Tous les champs numeriques sont facultatifs. S'ils sont absents, MIRROR OPS
    utilise un a priori neutre ET abaisse sa confiance de decision : le produit
    ne pretend jamais avoir mesure ce qu'il n'a pas mesure.
    """

    present: bool = True
    formality: float | None = Field(default=None, ge=0.0, le=1.0)
    structure: float | None = Field(default=None, ge=0.0, le=1.0)
    color_harmony: float | None = Field(default=None, ge=0.0, le=1.0)
    condition: float | None = Field(default=None, ge=0.0, le=1.0)
    descriptor: str | None = Field(default=None, max_length=120)

    def to_domain(self) -> OutfitItem:
        provided = [self.formality, self.structure, self.color_harmony, self.condition]
        known = any(value is not None for value in provided)
        return OutfitItem(
            present=self.present,
            known=known,
            formality=0.55 if self.formality is None else self.formality,
            structure=0.55 if self.structure is None else self.structure,
            color_harmony=0.55 if self.color_harmony is None else self.color_harmony,
            condition=0.70 if self.condition is None else self.condition,
            descriptor=self.descriptor,
        )


class OutfitIn(APIModel):
    jacket: OutfitItemIn | None = None
    top: OutfitItemIn | None = None
    bottom: OutfitItemIn | None = None
    shoes: OutfitItemIn | None = None
    accessories: OutfitItemIn | None = None

    def to_domain(self) -> dict[OutfitElement, OutfitItem]:
        mapping = {
            OutfitElement.JACKET: self.jacket,
            OutfitElement.TOP: self.top,
            OutfitElement.BOTTOM: self.bottom,
            OutfitElement.SHOES: self.shoes,
            OutfitElement.ACCESSORIES: self.accessories,
        }
        return {
            element: (item or OutfitItemIn()).to_domain()
            for element, item in mapping.items()
            if item is None or item.present
        }

    @classmethod
    def parse_form_value(cls, raw: str | None) -> "OutfitIn":
        if not raw:
            return cls()
        try:
            payload: Any = json.loads(raw)
        except json.JSONDecodeError:
            from app.core.errors import AppError, ErrorCode

            raise AppError(ErrorCode.INVALID_REQUEST, "The outfit description is malformed.")
        return cls.model_validate(payload)


class SkinObservationsOut(APIModel):
    texture: float | None = None
    redness: float | None = None
    oiliness: float | None = None
    radiance: float | None = None


class ImageQualityOut(APIModel):
    score: float
    brightness: float | None = None
    sharpness: float | None = None
    resolution_score: float | None = None
    full_look_visible: bool = True


class AppearanceAnalysisResponse(APIModel):
    analysis_id: str
    status: str = "completed"
    appearance: dict[str, float]
    skin: SkinObservationsOut
    skin_source: str
    skin_simulated: bool = Field(
        description="True si les observations proviennent d'une heuristique locale, pas de YouCam."
    )
    element_suitability: dict[str, float]
    image_quality: ImageQualityOut
    data_confidence: float
    image_url: str | None = None
    created_at: UtcDateTime

    @field_validator("appearance", "element_suitability", mode="before")
    @classmethod
    def _floats(cls, value: dict) -> dict:
        return {k: float(v) for k, v in (value or {}).items()}
