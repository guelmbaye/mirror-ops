"""Creation du moment (occasion + objectif + temps)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.schemas.moment import MomentCreateRequest, MomentResponse
from app.services import moment_service, session_service

router = APIRouter(prefix="/moments", tags=["moment"])


@router.post(
    "",
    response_model=MomentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Decrire le moment qui compte",
)
async def create_moment(payload: MomentCreateRequest, db: DbSession) -> MomentResponse:
    session = await session_service.get_active_session(db, payload.session_id)
    moment = await moment_service.create_moment(
        db,
        session,
        occasion=payload.occasion,
        goal=payload.goal,
        time_available=payload.time_available,
        note=payload.note,
    )
    return MomentResponse.model_validate(moment)
