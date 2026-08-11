"""Service de decision : branche le moteur ONE CHANGE sur les donnees persistees.

Le moteur reste pur ; ce service fait la traduction DB <-> domaine et
persiste la recommandation (Doc 07 §7).
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.engines.one_change import DecisionContext, EngineConfig, OneChangeEngine, ThresholdPolicy
from app.engines.one_change.engine import InsufficientDataError
from app.engines.one_change.types import DecisionOutcome
from app.models.analysis import AppearanceAnalysis
from app.models.enums import SessionState
from app.models.moment import Moment
from app.models.recommendation import Recommendation
from app.models.session import UserSession
from app.services import appearance_service, moment_service, session_service

logger = logging.getLogger("mirror_ops.decision")

#: Ce que l'utilisateur doit corriger, selon ce qui manque reellement.
#: Envoyer reprendre une photo parfaite parce que la TENUE n'est pas decrite
#: est une impasse : rien de ce qu'il fera devant l'objectif n'y changera rien.
#: Deux motifs, deux gestes. Chacun ouvre sur quelque chose que l'utilisateur
#: peut reellement faire — sinon ce n'est pas une erreur, c'est une impasse.
def _suggested_garment(action, moment) -> dict | None:
    """La piece retenue pour la preuve, nommee des la decision.

    Le produit ne propose pas de choisir — il annonce. « See it with the
    Structured Neutral Jacket » informe sans transformer l'ecran en catalogue.
    """
    from app.services import garment_service

    try:
        garment = garment_service.select_garment(action, moment)
    except AppError:
        return None  # NO_CHANGE, retrait : il n'y a rien a essayer
    return {"id": garment.id, "name": garment.name, "category": garment.category}


GATE_MESSAGES: dict[str, tuple[ErrorCode, str]] = {
    "no_outfit_declared": (
        ErrorCode.INVALID_REQUEST,
        "Tell us what you're wearing — we can't judge a look we know nothing about.",
    ),
    "image_unusable": (
        ErrorCode.INVALID_IMAGE,
        "We need a clearer view of your look before we can decide.",
    ),
}


def build_engine() -> OneChangeEngine:
    settings = get_settings()
    return OneChangeEngine(
        EngineConfig(
            threshold=ThresholdPolicy(
                min_recommendation_score=settings.ONE_CHANGE_THRESHOLD,
                no_change_margin=settings.ONE_CHANGE_NO_CHANGE_MARGIN,
                low_confidence_floor=settings.ONE_CHANGE_MIN_DATA_CONFIDENCE,
            ),
            tie_delta=settings.ONE_CHANGE_TIE_DELTA,
        )
    )


def build_context(moment: Moment, analysis: AppearanceAnalysis) -> DecisionContext:
    return DecisionContext(
        moment=moment_service.to_spec(moment),
        appearance=appearance_service.signals_from_analysis(analysis),
    )


async def evaluate_one_change(
    db: AsyncSession,
    session: UserSession,
    moment: Moment,
    analysis: AppearanceAnalysis,
) -> tuple[Recommendation, DecisionOutcome]:
    context = build_context(moment, analysis)
    engine = build_engine()

    try:
        outcome = engine.evaluate(context)
    except InsufficientDataError as exc:
        reason = str(exc)
        logger.info("decision_insufficient_data", extra={"reason": reason})
        code, message = GATE_MESSAGES.get(reason, GATE_MESSAGES["no_outfit_declared"])
        # En developpement, les chiffres accompagnent le refus : sans eux, un
        # blocage se diagnostique par essais successifs.
        details = None
        if get_settings().APP_ENV == "development":
            details = {
                "gate": reason,
                "declared_elements": sorted(str(e) for e in context.appearance.present_elements),
                "image_quality": round(context.appearance.image_quality, 3),
                "data_confidence": round(context.appearance.data_confidence, 3),
            }
        raise AppError(code, message, details=details)

    recommendation = Recommendation(
        session_id=session.id,
        moment_id=moment.id,
        analysis_id=analysis.id,
        action=str(outcome.action),
        label=outcome.label,
        score=outcome.score,
        confidence=str(outcome.confidence_level),
        confidence_value=outcome.confidence_value,
        is_addition=outcome.is_addition,
        suggested_garment=_suggested_garment(outcome.action, context.moment),
        fit=(
            {
                "state": str(outcome.fit.state),
                "score": outcome.fit.score,
                "headline": outcome.fit.headline,
                "detail": outcome.fit.detail,
                "weakest_element": outcome.fit.weakest_element,
            }
            if outcome.fit
            else None
        ),
        reason=outcome.explanation.reason,
        what=outcome.explanation.what,
        why=outcome.explanation.why,
        how=outcome.explanation.how,
        keep=outcome.keep,
        impact={
            "before": outcome.impact_before,
            "after": outcome.impact_after,
            "dominant_factors": outcome.explanation.dominant_factors,
        },
        candidates=[c.as_dict() for c in outcome.candidates],
    )
    db.add(recommendation)
    await db.flush()
    await session_service.advance_state(db, session, SessionState.DECISION_COMPLETED)

    logger.info(
        "one_change_persisted",
        extra={
            "session_id": session.id,
            "action": recommendation.action,
            "score": recommendation.score,
            "confidence": recommendation.confidence,
        },
    )
    return recommendation, outcome


async def get_recommendation(db: AsyncSession, recommendation_id: str) -> Recommendation:
    recommendation = (
        await db.execute(select(Recommendation).where(Recommendation.id == recommendation_id))
    ).scalar_one_or_none()
    if recommendation is None:
        raise AppError(ErrorCode.NOT_FOUND, "We couldn't find this recommendation.")
    return recommendation


async def get_latest_recommendation(db: AsyncSession, session_id: str) -> Recommendation:
    stmt = (
        select(Recommendation)
        .where(Recommendation.session_id == session_id)
        .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
    )
    recommendation = (await db.execute(stmt)).scalars().first()
    if recommendation is None:
        raise AppError(ErrorCode.INVALID_STATE, "Run the ONE CHANGE analysis first.")
    return recommendation
