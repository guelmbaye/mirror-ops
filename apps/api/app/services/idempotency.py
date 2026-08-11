"""Idempotency des operations couteuses (Doc 08 §22).

But : "Eviter double click -> double YouCam call -> unites consommees deux fois."
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import in_minutes, utcnow
from app.models.idempotency import IdempotencyRecord


async def get_cached_response(db: AsyncSession, scope: str, key: str | None) -> dict | None:
    if not key:
        return None
    stmt = select(IdempotencyRecord).where(
        IdempotencyRecord.scope == scope, IdempotencyRecord.key == key
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        return None
    if record.expires_at < utcnow():
        await db.delete(record)
        await db.flush()
        return None
    return record.response


async def store_response(
    db: AsyncSession, scope: str, key: str | None, response: dict, ttl_minutes: int = 60
) -> None:
    if not key:
        return
    existing = await get_cached_response(db, scope, key)
    if existing is not None:
        return
    db.add(
        IdempotencyRecord(
            scope=scope, key=key, response=response, expires_at=in_minutes(ttl_minutes)
        )
    )
    await db.flush()
