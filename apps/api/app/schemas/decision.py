from __future__ import annotations

from pydantic import Field

from app.schemas.common import APIModel


class OneChangeEvaluateRequest(APIModel):
    session_id: str
    moment_id: str | None = Field(
        default=None, description="Par defaut : le dernier moment de la session."
    )
    analysis_id: str | None = Field(
        default=None, description="Par defaut : la derniere analyse de la session."
    )


class ImpactOut(APIModel):
    before: dict[str, int]
    after: dict[str, int]
    dominant_factors: list[str] = []


class FitOut(APIModel):
    """Le look convient-il au moment ? C'est la premiere reponse du produit.

    Elle precede le changement : « FIT THE MOMENT » avant « ONE CHANGE ».
    """

    state: str
    score: int
    headline: str
    detail: str
    weakest_element: str | None = None


class SuggestedGarmentOut(APIModel):
    """La piece que la preuve visuelle utilisera, si elle est demandee."""

    id: str
    name: str
    category: str


class RecommendationOut(APIModel):
    """Objet central du produit (Doc 04 §17 / Doc 08 §8)."""

    id: str
    action: str
    label: str
    score: float
    confidence: str
    reason: str
    what: str
    why: str
    how: str
    keep: list[str]
    impact: ImpactOut
    requires_vto: bool
    #: `true` quand la piece etait absente : l'interface doit ecrire « Add »
    #: plutot que « Change », partout ou elle nomme l'intervention.
    is_addition: bool = False
    fit: FitOut | None = None
    suggested_garment: SuggestedGarmentOut | None = None


class OneChangeResponse(APIModel):
    recommendation: RecommendationOut
