"""Sessions anonymes + vue agregee du parcours."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.schemas.result import SessionDetailResponse
from app.schemas.session import SessionCreateResponse, SessionSummary
from app.services import session_service
from app.services.result_builder import build_session_detail

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Demarrer un parcours MIRROR OPS",
)
async def create_session(db: DbSession) -> SessionCreateResponse:
    session = await session_service.create_session(db)
    return SessionCreateResponse.model_validate(session)


@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    summary="Recuperer tout l'etat du parcours en une requete",
)
async def get_session(session_id: str, db: DbSession) -> SessionDetailResponse:
    session = await session_service.get_session(db, session_id)
    return await build_session_detail(db, session)


@router.get(
    "/{session_id}/summary",
    response_model=SessionSummary,
    summary="Etat court de la session",
)
async def get_session_summary(session_id: str, db: DbSession) -> SessionSummary:
    session = await session_service.get_session(db, session_id)
    return SessionSummary.model_validate(session)
