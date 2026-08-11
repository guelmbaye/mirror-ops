"""Creation du Moment (Doc 02 FR-01) : occasion + goal + temps disponible."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.engines.one_change.types import MomentSpec
from app.models.enums import Goal, Occasion, SessionState, TimeAvailable
from app.models.moment import Moment
from app.models.session import UserSession
from app.services import session_service

logger = logging.getLogger("mirror_ops.moment")


async def create_moment(
    db: AsyncSession,
    session: UserSession,
    *,
    occasion: Occasion,
    goal: Goal,
    time_available: TimeAvailable,
    note: str | None = None,
) -> Moment:
    # Une session porte UN moment. Revenir en arriere pour corriger l'occasion
    # doit modifier ce moment, pas en creer un second : deux moments crees dans
    # la meme seconde laissaient le depart se jouer sur un UUID aleatoire, et
    # la correction de l'utilisateur etait ignoree une fois sur deux.
    existing = await find_moment(db, session.id)
    if existing is not None:
        existing.occasion = str(occasion)
        existing.goal = str(goal)
        existing.time_available = str(time_available)
        existing.note = note
        await db.flush()
        logger.info(
            "moment_updated",
            extra={"session_id": session.id, "occasion": str(occasion), "goal": str(goal)},
        )
        return existing

    moment = Moment(
        session_id=session.id,
        occasion=str(occasion),
        goal=str(goal),
        time_available=str(time_available),
        note=note,
    )
    db.add(moment)
    await db.flush()
    await session_service.advance_state(db, session, SessionState.MOMENT_CREATED)
    logger.info(
        "moment_created",
        extra={"session_id": session.id, "occasion": str(occasion), "goal": str(goal)},
    )
    return moment


async def find_moment(db: AsyncSession, session_id: str) -> Moment | None:
    """Le moment de la session, s'il existe."""
    stmt = select(Moment).where(Moment.session_id == session_id).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_latest_moment(db: AsyncSession, session_id: str) -> Moment:
    stmt = (
        select(Moment)
        .where(Moment.session_id == session_id)
        .order_by(Moment.created_at.desc(), Moment.id.desc())
    )
    moment = (await db.execute(stmt)).scalars().first()
    if moment is None:
        raise AppError(ErrorCode.INVALID_STATE, "Tell us about the moment first.")
    return moment


async def get_moment(db: AsyncSession, moment_id: str) -> Moment:
    moment = (
        await db.execute(select(Moment).where(Moment.id == moment_id))
    ).scalar_one_or_none()
    if moment is None:
        raise AppError(ErrorCode.NOT_FOUND, "We couldn't find this moment.")
    return moment


def to_spec(moment: Moment) -> MomentSpec:
    return MomentSpec(
        occasion=Occasion(moment.occasion),
        goal=Goal(moment.goal),
        time_available=TimeAvailable(moment.time_available),
    )
