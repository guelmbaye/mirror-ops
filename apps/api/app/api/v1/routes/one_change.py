"""Endpoint signature : ONE CHANGE."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.core.errors import AppError, ErrorCode
from app.models.enums import SessionState
from app.schemas.decision import OneChangeEvaluateRequest, OneChangeResponse
from app.services import appearance_service, decision_service, moment_service, session_service
from app.services.result_builder import recommendation_response

router = APIRouter(prefix="/one-change", tags=["one-change"])


@router.post(
    "/evaluate",
    response_model=OneChangeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Selectionner LE changement le plus utile",
)
async def evaluate(payload: OneChangeEvaluateRequest, db: DbSession) -> OneChangeResponse:
    session = await session_service.get_active_session(db, payload.session_id)
    session_service.require_state(session, SessionState.ANALYSIS_COMPLETED, "deciding")

    moment = (
        await moment_service.get_moment(db, payload.moment_id)
        if payload.moment_id
        else await moment_service.get_latest_moment(db, session.id)
    )
    analysis = (
        await appearance_service.get_analysis(db, payload.analysis_id)
        if payload.analysis_id
        else await appearance_service.get_latest_analysis(db, session.id)
    )
    if moment.session_id != session.id or analysis.session_id != session.id:
        raise AppError(ErrorCode.INVALID_REQUEST, "These items belong to another session.")

    recommendation, _outcome = await decision_service.evaluate_one_change(
        db, session, moment, analysis
    )
    return OneChangeResponse(recommendation=recommendation_response(recommendation))
