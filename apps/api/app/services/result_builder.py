"""Assemblage des reponses publiques (Doc 08 §27 : internal vs public data).

Le frontend ne voit jamais : reponse brute YouCam, vecteurs de features,
poids de scoring, identifiants de requete provider.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import build_media_url
from app.models.analysis import AppearanceAnalysis
from app.models.enums import ChangeAction
from app.models.moment import Moment
from app.models.recommendation import Recommendation
from app.models.session import UserSession
from app.models.vto import VTOResult
from app.schemas.appearance import (
    AppearanceAnalysisResponse,
    ImageQualityOut,
    SkinObservationsOut,
)
from app.schemas.decision import ImpactOut, RecommendationOut
from app.schemas.moment import MomentResponse
from app.schemas.result import SessionDetailResponse
from app.schemas.session import SessionSummary
from app.schemas.vto import VTOResponse
from app.services import appearance_service, decision_service, moment_service, vto_service
from app.services.storage import get_storage


async def analysis_response(
    db: AsyncSession, analysis: AppearanceAnalysis, *, simulated: bool | None = None
) -> AppearanceAnalysisResponse:
    image_url = await vto_service.source_image_url(db, analysis.image_id)
    is_simulated = (
        simulated if simulated is not None else analysis.skin_source.endswith("_simulated")
    )
    return AppearanceAnalysisResponse(
        analysis_id=analysis.id,
        appearance=analysis.appearance or {},
        skin=SkinObservationsOut(**(analysis.skin or {})),
        skin_source=analysis.skin_source,
        skin_simulated=is_simulated,
        element_suitability=analysis.element_suitability or {},
        image_quality=ImageQualityOut(**(analysis.image_quality or {"score": 0.0})),
        data_confidence=analysis.data_confidence,
        image_url=image_url,
        created_at=analysis.created_at,
    )


def recommendation_response(recommendation: Recommendation) -> RecommendationOut:
    impact = recommendation.impact or {}
    return RecommendationOut(
        id=recommendation.id,
        action=recommendation.action,
        label=recommendation.label,
        score=recommendation.score,
        confidence=recommendation.confidence,
        reason=recommendation.reason,
        what=recommendation.what,
        why=recommendation.why,
        how=recommendation.how,
        keep=recommendation.keep or [],
        impact=ImpactOut(
            before=impact.get("before", {}),
            after=impact.get("after", {}),
            dominant_factors=impact.get("dominant_factors", []),
        ),
        requires_vto=recommendation.action
        not in (str(ChangeAction.NO_CHANGE), str(ChangeAction.REMOVE_ACCESSORY)),
        is_addition=bool(recommendation.is_addition),
        fit=recommendation.fit,
        suggested_garment=recommendation.suggested_garment,
    )


async def vto_response(db: AsyncSession, result: VTOResult) -> VTOResponse:
    return VTOResponse(
        id=result.id,
        status=result.status,
        action=result.action,
        garment_id=result.garment_id,
        provider=result.provider,
        simulated=bool((result.meta or {}).get("simulated", False)),
        before_image_url=await vto_service.source_image_url(db, result.source_image_id),
        result_image_url=await vto_service.result_image_url(db, result),
        latency_ms=result.latency_ms,
        created_at=result.created_at,
    )


def moment_response(moment: Moment) -> MomentResponse:
    return MomentResponse.model_validate(moment)


async def build_session_detail(db: AsyncSession, session: UserSession) -> SessionDetailResponse:
    moment = analysis = recommendation = vto = None

    try:
        moment_model = await moment_service.get_latest_moment(db, session.id)
        moment = moment_response(moment_model)
    except Exception:  # noqa: BLE001 - etape non encore atteinte
        moment = None

    try:
        analysis_model = await appearance_service.get_latest_analysis(db, session.id)
        analysis = await analysis_response(db, analysis_model)
    except Exception:  # noqa: BLE001
        analysis = None

    try:
        recommendation_model = await decision_service.get_latest_recommendation(db, session.id)
        recommendation = recommendation_response(recommendation_model)
    except Exception:  # noqa: BLE001
        recommendation = None

    vto_model = await vto_service.get_latest_vto(db, session.id)
    if vto_model is not None:
        vto = await vto_response(db, vto_model)

    return SessionDetailResponse(
        session=SessionSummary.model_validate(session),
        moment=moment,
        analysis=analysis,
        recommendation=recommendation,
        vto=vto,
    )


def media_url(storage_key: str) -> str:
    get_storage()  # garantit l'initialisation du backend de stockage
    return build_media_url(storage_key)
