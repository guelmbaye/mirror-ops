"""Service Apparel VTO (Doc 05 §10-§14, Doc 09 Phase 9).

Regles produit appliquees ici :
- un seul VTO, uniquement pour le gagnant ONE CHANGE (economie d'unites) ;
- NO_CHANGE -> aucun appel VTO ;
- toute erreur provider est traduite en message utilisateur ;
- si le resultat est simule, l'API le dit explicitement.
"""

from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.photo_guidance import guidance_for
from app.core.errors import AppError, ErrorCode
from app.core.security import build_media_url, hash_bytes
from app.db.base import in_minutes
from app.integrations.youcam import (
    YouCamError,
    YouCamInvalidImageError,
    YouCamQuotaExhaustedError,
    YouCamRateLimitError,
    YouCamTimeoutError,
    diagnostics,
    get_vto_provider,
)
from app.models.analysis import AppearanceAnalysis
from app.models.enums import ChangeAction, SessionState, VTOStatus
from app.models.image_asset import ImageAsset
from app.models.moment import Moment
from app.models.recommendation import Recommendation
from app.models.session import UserSession
from app.models.vto import VTOResult
from app.services import garment_service, uploaded_garment, moment_service, session_service
from app.services.storage import get_storage, session_key

logger = logging.getLogger("mirror_ops.vto")


async def _load_source_image(db: AsyncSession, analysis: AppearanceAnalysis) -> tuple[ImageAsset, bytes]:
    asset = (
        await db.execute(select(ImageAsset).where(ImageAsset.id == analysis.image_id))
    ).scalar_one_or_none()
    if asset is None:
        raise AppError(ErrorCode.INVALID_STATE, "Your photo is no longer available. Retake it.")
    data = await get_storage().get(asset.storage_key)
    return asset, _bounded(data)


#: Cote long maximal envoye au provider. Les photos de telephone montent a
#: 4000 px et plus ; au-dela, on paie du transfert sans rien gagner, et
#: certaines limites provider se declenchent silencieusement.
MAX_SOURCE_LONG_SIDE = 2048


def _bounded(image_bytes: bytes) -> bytes:
    """Reduit la photo source si elle depasse, sans jamais l'agrandir."""
    import io

    from PIL import Image

    try:
        with Image.open(io.BytesIO(image_bytes)) as opened:
            if max(opened.size) <= MAX_SOURCE_LONG_SIDE:
                return image_bytes
            image = opened.convert("RGB")
            scale = MAX_SOURCE_LONG_SIDE / max(image.size)
            image = image.resize(
                (round(image.width * scale), round(image.height * scale)), Image.LANCZOS
            )
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=93)
            return buffer.getvalue()
    except Exception:  # pragma: no cover - on n'echoue jamais sur une optimisation
        return image_bytes


async def generate_vto(
    db: AsyncSession,
    session: UserSession,
    recommendation: Recommendation,
    analysis: AppearanceAnalysis,
    moment: Moment,
    *,
    garment_id: str | None = None,
) -> tuple[VTOResult, str, bool]:
    """Retourne (resultat persistant, URL temporaire signee, simule ?)."""
    settings = get_settings()

    action = ChangeAction(recommendation.action)
    if action is ChangeAction.NO_CHANGE:
        raise AppError(
            ErrorCode.VTO_NOT_APPLICABLE,
            "Your current look already fits this moment — there is nothing to preview.",
        )

    moment_spec = moment_service.to_spec(moment)
    expected_category = garment_service.category_for_action(action)

    # Un identifiant peut designer une piece du catalogue OU une photo que
    # l'utilisateur vient de televerser. Sa piece prime : personne ne connait
    # mieux que lui ce qu'il envisage de porter.
    uploaded = (
        await uploaded_garment.find_uploaded_garment(db, session.id, garment_id)
        if garment_id
        else None
    )

    if uploaded is not None:
        garment_ref = await uploaded_garment.to_ref(uploaded, expected_category or "auto")
        garment_label, garment_key, garment_category = (
            "Your own piece",
            uploaded.id,
            expected_category or "auto",
        )
    else:
        garment = (
            garment_service.get_garment(garment_id)
            if garment_id
            else garment_service.select_garment(action, moment_spec)
        )
        if expected_category and garment.category != expected_category:
            raise AppError(
                ErrorCode.INVALID_REQUEST,
                "This garment doesn't match the recommended change.",
            )
        garment_ref = garment_service.to_ref(garment)
        garment_label, garment_key, garment_category = (
            garment.name,
            garment.id,
            garment.category,
        )

    asset, source_bytes = await _load_source_image(db, analysis)

    result = VTOResult(
        session_id=session.id,
        recommendation_id=recommendation.id,
        action=str(action),
        garment_id=garment_key,
        status=str(VTOStatus.PROCESSING),
        source_image_id=asset.id,
        meta={"garment_name": garment_label, "garment_category": garment_category},
    )
    db.add(result)
    await db.flush()
    await session_service.advance_state(db, session, SessionState.VTO_PROCESSING)

    provider = get_vto_provider()
    started = time.perf_counter()

    # Sans ces champs, un echec ne dit pas SI le catalogue ou la piece de
    # l'utilisateur est en cause — et le diagnostic repart de zero a chaque fois.
    # `garment_id` et `garment_source` decrivent les donnees de l'utilisateur,
    # pas les entrailles du provider : ils sont exposes en toutes circonstances.
    public = {
        "garment_id": garment_key,
        "garment_source": "uploaded" if uploaded is not None else "catalog",
    }
    context = {
        "garment_id": garment_key,
        "garment_source": "uploaded" if uploaded is not None else "catalog",
        "garment_category": garment_category,
        "garment_bytes": len(garment_ref.image_bytes),
        "source_bytes": len(source_bytes),
        "action": str(action),
    }
    try:
        generated = await provider.generate(
            source_bytes, garment_ref, source_mime=asset.mime_type
        )
    except YouCamInvalidImageError as exc:
        info = {**diagnostics(exc, provider.provider_name), **context}
        logger.warning("vto_image_rejected", extra=info)
        await _fail(db, result, ErrorCode.INVALID_IMAGE, "Image rejected for try-on")
        raise AppError(
            ErrorCode.INVALID_IMAGE,
            # Le provider nomme la cause : on la traduit en consigne plutot que
            # de renvoyer un message generique.
            guidance_for(exc.provider_code),
            details=info if get_settings().APP_ENV == "development" else public,
        )
    except YouCamTimeoutError as exc:
        info = {**diagnostics(exc, provider.provider_name), **context}
        logger.warning("vto_timeout", extra=info)
        await _fail(db, result, ErrorCode.VTO_TIMEOUT, "Provider timeout")
        raise AppError(
            ErrorCode.VTO_TIMEOUT,
            "The visual preview took too long. Try again.",
            details=info if get_settings().APP_ENV == "development" else public,
        )
    except YouCamRateLimitError:
        await _fail(db, result, ErrorCode.RATE_LIMITED, "Provider rate limit")
        raise AppError(ErrorCode.RATE_LIMITED)
    except YouCamQuotaExhaustedError as exc:
        info = {**diagnostics(exc, provider.provider_name), **context}
        logger.warning("vto_quota", extra=info)
        await _fail(db, result, ErrorCode.PROVIDER_UNAVAILABLE, "Provider quota exhausted")
        raise AppError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "The preview service is unavailable.",
            details=info if get_settings().APP_ENV == "development" else public,
        )
    except YouCamError as exc:
        info = {**diagnostics(exc, provider.provider_name), **context}
        logger.warning("vto_provider_failed", extra=info)
        await _fail(db, result, ErrorCode.VTO_FAILED, "Provider error")
        raise AppError(
            ErrorCode.VTO_FAILED,
            guidance_for(exc.provider_code, "We couldn't complete the visual preview."),
            details=info if get_settings().APP_ENV == "development" else public,
        )

    latency_ms = int((time.perf_counter() - started) * 1000)
    content_hash = hash_bytes(generated.image_bytes)
    extension = "jpg" if generated.mime_type == "image/jpeg" else "png"
    key = session_key(session.id, "vto", f"{content_hash[:16]}.{extension}")
    await get_storage().put(key, generated.image_bytes, generated.mime_type)

    result_asset = ImageAsset(
        session_id=session.id,
        kind="vto",
        storage_key=key,
        mime_type=generated.mime_type,
        size_bytes=len(generated.image_bytes),
        width=asset.width,
        height=asset.height,
        content_hash=content_hash,
        expires_at=in_minutes(settings.MEDIA_TTL_MINUTES),
    )
    db.add(result_asset)
    await db.flush()

    result.status = str(VTOStatus.COMPLETED)
    result.provider = generated.provider
    result.provider_task_id = generated.provider_task_id
    result.result_image_id = result_asset.id
    result.latency_ms = latency_ms
    result.meta = {**result.meta, "simulated": generated.simulated}
    await db.flush()
    await session_service.advance_state(db, session, SessionState.VTO_COMPLETED)

    logger.info(
        "vto_generated",
        extra={
            "session_id": session.id,
            "action": result.action,
            "provider": generated.provider,
            "simulated": generated.simulated,
            "latency_ms": latency_ms,
        },
    )
    return result, build_media_url(key), generated.simulated


async def _fail(db: AsyncSession, result: VTOResult, code: ErrorCode, message: str) -> None:
    result.status = str(VTOStatus.FAILED)
    result.error_code = str(code)
    result.error_message = message
    await db.flush()


async def get_vto(db: AsyncSession, vto_id: str) -> VTOResult:
    result = (
        await db.execute(select(VTOResult).where(VTOResult.id == vto_id))
    ).scalar_one_or_none()
    if result is None:
        raise AppError(ErrorCode.NOT_FOUND, "We couldn't find this preview.")
    return result


async def get_latest_vto(db: AsyncSession, session_id: str) -> VTOResult | None:
    stmt = (
        select(VTOResult)
        .where(VTOResult.session_id == session_id)
        .order_by(VTOResult.created_at.desc(), VTOResult.id.desc())
    )
    return (await db.execute(stmt)).scalars().first()


async def result_image_url(db: AsyncSession, result: VTOResult) -> str | None:
    if not result.result_image_id:
        return None
    asset = (
        await db.execute(select(ImageAsset).where(ImageAsset.id == result.result_image_id))
    ).scalar_one_or_none()
    return build_media_url(asset.storage_key) if asset else None


async def source_image_url(db: AsyncSession, image_id: str | None) -> str | None:
    if not image_id:
        return None
    asset = (
        await db.execute(select(ImageAsset).where(ImageAsset.id == image_id))
    ).scalar_one_or_none()
    return build_media_url(asset.storage_key) if asset else None
