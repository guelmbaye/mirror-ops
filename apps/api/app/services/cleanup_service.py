"""Nettoyage des donnees expirees (Doc 08 §29 : expires_at -> cleanup job)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models.enums import SessionStatus
from app.models.image_asset import ImageAsset
from app.models.session import UserSession
from app.services.storage import get_storage

logger = logging.getLogger("mirror_ops.cleanup")


async def cleanup_expired(db: AsyncSession) -> dict[str, int]:
    """Supprime les medias expires et marque les sessions expirees."""
    now = utcnow()
    storage = get_storage()

    expired_images = (
        await db.execute(select(ImageAsset).where(ImageAsset.expires_at < now))
    ).scalars().all()
    deleted_media = 0
    for asset in expired_images:
        deleted_media += await storage.delete_prefix(asset.storage_key)
        await db.delete(asset)

    expired_sessions = (
        await db.execute(
            select(UserSession).where(
                UserSession.expires_at < now, UserSession.status == str(SessionStatus.ACTIVE)
            )
        )
    ).scalars().all()
    for session in expired_sessions:
        session.status = str(SessionStatus.EXPIRED)
        deleted_media += await storage.delete_prefix(f"sessions/{session.id}")

    await db.flush()
    report = {
        "expired_images": len(expired_images),
        "expired_sessions": len(expired_sessions),
        "deleted_media": deleted_media,
    }
    logger.info("cleanup_completed", extra=report)
    return report
