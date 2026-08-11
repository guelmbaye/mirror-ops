from __future__ import annotations

from pydantic import Field

from app.schemas.common import APIModel, UtcDateTime


class VTOGenerateRequest(APIModel):
    session_id: str
    recommendation_id: str | None = Field(
        default=None, description="Par defaut : la derniere recommandation de la session."
    )
    garment_asset_id: str | None = Field(
        default=None, description="Par defaut : le vetement selectionne automatiquement."
    )


class VTOResponse(APIModel):
    id: str
    status: str
    action: str
    garment_id: str
    provider: str
    simulated: bool = Field(
        description="True si l'apercu a ete compose localement et NON genere par YouCam."
    )
    before_image_url: str | None = None
    result_image_url: str | None = None
    latency_ms: int | None = None
    created_at: UtcDateTime


class GarmentOut(APIModel):
    id: str
    category: str
    name: str
    description: str
    color: str
    attributes: dict[str, float]
    #: `true` tant que le visuel est un aplat genere, et non une photographie.
    #: Expose parce que la question « ce vetement est-il reel ? » revenait a
    #: chaque diagnostic : une trace doit y repondre seule.
    placeholder: bool = False


class GarmentListResponse(APIModel):
    garments: list[GarmentOut]


class UploadedGarmentResponse(APIModel):
    """Une piece fournie par l'utilisateur, utilisable comme `garment_asset_id`."""

    id: str
    width: int
    height: int
    size_bytes: int
