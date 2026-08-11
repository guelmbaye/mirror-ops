"""Vetements fournis par l'utilisateur.

Le catalogue existe pour que le parcours ne s'arrete jamais : quand le moteur
decide « changez la veste », il faut bien une veste a essayer, et la demander a
l'utilisateur au milieu d'un parcours de 90 secondes le casserait.

Mais rien n'oblige a s'y limiter. Quelqu'un qui hesite devant une piece precise
— dans sa penderie, en boutique, dans un onglet — a une raison bien plus forte
de vouloir la voir sur lui. Ce module accepte donc n'importe quelle photo de
vetement, le temps d'une session.

L'image est normalisee comme celles du catalogue (fond blanc, RGB, JPEG, cote
long >= 1024 px), stockee avec les autres medias temporaires de la session, et
supprimee a expiration comme tout le reste.
"""

from __future__ import annotations

import io
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.security import hash_bytes
from app.db.base import in_minutes
from app.integrations.youcam.models import GarmentRef
from app.models.image_asset import ImageAsset
from app.models.session import UserSession
from app.services.image_validation import validate_image
from app.services.storage import get_storage, session_key

logger = logging.getLogger("mirror_ops.garments.upload")

KIND = "garment"
MIN_LONG_SIDE = 1024


def _normalize(image_bytes: bytes) -> tuple[bytes, int, int]:
    """Meme traitement que le catalogue : une variable de moins cote provider."""
    from PIL import Image

    with Image.open(io.BytesIO(image_bytes)) as opened:
        image = opened.convert("RGBA")
        canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
        canvas.alpha_composite(image)
        flat = canvas.convert("RGB")

        long_side = max(flat.size)
        if long_side < MIN_LONG_SIDE:
            scale = MIN_LONG_SIDE / long_side
            flat = flat.resize(
                (round(flat.width * scale), round(flat.height * scale)), Image.LANCZOS
            )

        buffer = io.BytesIO()
        flat.save(buffer, format="JPEG", quality=94)
        return buffer.getvalue(), flat.width, flat.height


async def store_uploaded_garment(
    db: AsyncSession, session: UserSession, raw: bytes, mime_type: str
) -> ImageAsset:
    """Valide, normalise et enregistre une photo de vetement pour la session."""
    validate_image(raw, mime_type)
    normalized, width, height = _normalize(raw)

    settings = get_settings()
    digest = hash_bytes(normalized)
    key = session_key(session.id, KIND, f"{digest[:16]}.jpg")
    await get_storage().put(key, normalized, "image/jpeg")

    asset = ImageAsset(
        session_id=session.id,
        kind=KIND,
        storage_key=key,
        mime_type="image/jpeg",
        size_bytes=len(normalized),
        width=width,
        height=height,
        content_hash=digest,
        expires_at=in_minutes(settings.MEDIA_TTL_MINUTES),
    )
    db.add(asset)
    await db.flush()
    logger.info("garment_uploaded", extra={"asset_id": asset.id, "bytes": len(normalized)})
    return asset


async def find_uploaded_garment(
    db: AsyncSession, session_id: str, asset_id: str
) -> ImageAsset | None:
    result = await db.execute(
        select(ImageAsset).where(
            ImageAsset.id == asset_id,
            ImageAsset.session_id == session_id,
            ImageAsset.kind == KIND,
        )
    )
    return result.scalar_one_or_none()


async def to_ref(asset: ImageAsset, category: str) -> GarmentRef:
    """Le vetement de l'utilisateur, sous la meme forme que ceux du catalogue.

    La categorie est celle qu'impose la decision en cours : l'utilisateur
    fournit une piece POUR ce changement, il n'en choisit pas un autre.
    """
    data = await get_storage().get(asset.storage_key)
    if data is None:
        raise AppError(ErrorCode.MEDIA_LINK_EXPIRED, "That piece is no longer available.")

    return GarmentRef(
        garment_id=asset.id,
        category=category,
        name="Your own piece",
        image_bytes=data,
        mime_type="image/jpeg",
    )
