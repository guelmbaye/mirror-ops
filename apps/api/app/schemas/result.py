"""Reponse agregee : tout l'ecran final en une seule requete (Doc 08 §31)."""

from __future__ import annotations

from app.schemas.appearance import AppearanceAnalysisResponse
from app.schemas.common import APIModel
from app.schemas.decision import RecommendationOut
from app.schemas.moment import MomentResponse
from app.schemas.session import SessionSummary
from app.schemas.vto import VTOResponse


class SessionDetailResponse(APIModel):
    session: SessionSummary
    moment: MomentResponse | None = None
    analysis: AppearanceAnalysisResponse | None = None
    recommendation: RecommendationOut | None = None
    vto: VTOResponse | None = None
