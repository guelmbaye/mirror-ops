"""Cycle de vie de la session anonyme + machine a etats (Doc 08 §21).

Aucun compte, aucun mot de passe, aucun OAuth (Doc 07 §13).
Les transitions impossibles sont rejetees avec 409 INVALID_STATE.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.db.base import utcnow
from app.models.enums import STATE_ORDER, SessionState, SessionStatus
from app.models.session import UserSession

logger = logging.getLogger("mirror_ops.session")


async def create_session(db: AsyncSession) -> UserSession:
    session = UserSession()
    db.add(session)
    await db.flush()
    logger.info("session_created", extra={"session_id": session.id})
    return session


async def get_session(db: AsyncSession, session_id: str) -> UserSession:
    session = (
        await db.execute(select(UserSession).where(UserSession.id == session_id))
    ).scalar_one_or_none()
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND, "We couldn't find this session.")
    return session


async def get_active_session(db: AsyncSession, session_id: str) -> UserSession:
    session = await get_session(db, session_id)
    if session.expires_at < utcnow():
        if session.status != SessionStatus.EXPIRED:
            session.status = SessionStatus.EXPIRED
            await db.flush()
        raise AppError(ErrorCode.SESSION_EXPIRED)
    if session.status in (SessionStatus.EXPIRED, SessionStatus.FAILED):
        raise AppError(ErrorCode.SESSION_EXPIRED)
    return session


def require_state(session: UserSession, minimum: SessionState, step: str) -> None:
    """Empeche par exemple un VTO avant que ONE CHANGE n'ait decide."""
    current = STATE_ORDER[SessionState(session.state)]
    if current < STATE_ORDER[minimum]:
        raise AppError(
            ErrorCode.INVALID_STATE,
            f"You need to complete the previous step before {step}.",
            details={"current_state": session.state, "required_state": str(minimum)},
        )


async def advance_state(db: AsyncSession, session: UserSession, target: SessionState) -> UserSession:
    """N'avance jamais en arriere : l'etat est monotone."""
    if STATE_ORDER[target] > STATE_ORDER[SessionState(session.state)]:
        session.state = str(target)
    if target is SessionState.SESSION_COMPLETED:
        session.status = str(SessionStatus.COMPLETED)
    await db.flush()
    return session


async def mark_failed(db: AsyncSession, session: UserSession) -> None:
    session.status = str(SessionStatus.FAILED)
    await db.flush()
