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


async def _load_source_image(
    db: AsyncSession, session_id: str, analysis: AppearanceAnalysis
) -> tuple[ImageAsset, bytes]:
    """La photo preparee, ET l'asset qui la sert comme etat « avant ».

    Le comparateur superposait la photo D'ORIGINE au rendu produit a partir de
    la photo PREPAREE. Sur un cliche etire, complete sur les cotes avant envoi,
    les deux cadrages differaient : le « avant » paraissait zoome, et la
    difference affichee incluait un recadrage. Une preuve visuelle doit comparer
    deux images qui ne different que par le vetement.
    """
    asset = (
        await db.execute(select(ImageAsset).where(ImageAsset.id == analysis.image_id))
    ).scalar_one_or_none()
    if asset is None:
        raise AppError(ErrorCode.INVALID_STATE, "Your photo is no longer available. Retake it.")

    original = await get_storage().get(asset.storage_key)
    prepared = _bounded(original)
    if prepared is original:
        return asset, prepared

    return await _store_prepared(db, session_id, asset, prepared), prepared


async def _store_prepared(
    db: AsyncSession, session_id: str, source: ImageAsset, data: bytes
) -> ImageAsset:
    """Enregistre la photo preparee, pour qu'elle serve d'etat « avant »."""
    import io

    from PIL import Image

    from app.core.security import hash_bytes
    from app.db.base import in_minutes
    from app.services.storage import session_key

    digest = hash_bytes(data)
    key = session_key(session_id, "input", f"{digest[:16]}.jpg")
    await get_storage().put(key, data, "image/jpeg")

    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size

    prepared = ImageAsset(
        session_id=session_id,
        kind=source.kind,
        storage_key=key,
        mime_type="image/jpeg",
        size_bytes=len(data),
        width=width,
        height=height,
        content_hash=digest,
        expires_at=source.expires_at or in_minutes(get_settings().MEDIA_TTL_MINUTES),
    )
    db.add(prepared)
    await db.flush()
    logger.info(
        "source_prepared_stored",
        extra={"from": source.id, "to": prepared.id, "size": f"{width}x{height}"},
    )
    return prepared


#: Cote long maximal envoye au provider. Les photos de telephone montent a
#: 4000 px et plus ; au-dela, on paie du transfert sans rien gagner, et
#: certaines limites provider se declenchent silencieusement.
MAX_SOURCE_LONG_SIDE = 2048

#: Au-dela de ce rapport hauteur/largeur, la photo est completee sur les cotes.
#:
#: Une photo recadree en bande — 1306x4080, soit 1:3.12, deux fois plus etiree
#: qu'un portrait de telephone — a produit `error_editing_failed` alors que le
#: vetement de reference etait irreprochable. Le modele d'essayage attend une
#: personne dans un cadre de photo, pas dans une colonne.
MAX_SOURCE_ASPECT = 2.1

#: Rapport vise apres completion : celui d'un portrait de telephone.
TARGET_SOURCE_ASPECT = 16 / 9


def _bounded(image_bytes: bytes) -> bytes:
    """Prepare la photo source : taille bornee, et cadre de proportions saines.

    On ne recadre JAMAIS : sur un plan en pied, retirer de la hauteur coupe les
    chaussures — c'est-a-dire une piece que le produit peut recommander. On
    complete donc sur les cotes, ce qui preserve la personne entiere.
    """
    import io

    from PIL import Image

    try:
        with Image.open(io.BytesIO(image_bytes)) as opened:
            image = opened.convert("RGB")
            changed = False

            if image.height / image.width > MAX_SOURCE_ASPECT:
                target_width = round(image.height / TARGET_SOURCE_ASPECT)
                canvas = Image.new("RGB", (target_width, image.height), _edge_colour(image))
                canvas.paste(image, ((target_width - image.width) // 2, 0))
                logger.info(
                    "source_letterboxed",
                    extra={
                        "from": f"{image.width}x{image.height}",
                        "to": f"{target_width}x{image.height}",
                    },
                )
                image, changed = canvas, True

            if max(image.size) > MAX_SOURCE_LONG_SIDE:
                scale = MAX_SOURCE_LONG_SIDE / max(image.size)
                image = image.resize(
                    (round(image.width * scale), round(image.height * scale)), Image.LANCZOS
                )
                changed = True

            if not changed:
                return image_bytes

            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=93)
            return buffer.getvalue()
    except Exception:  # pragma: no cover - on n'echoue jamais sur une optimisation
        return image_bytes


def _edge_colour(image) -> tuple[int, int, int]:
    """Teinte moyenne des bords, pour que la completion ne se voie pas."""
    from PIL import Image

    strip = image.resize((3, 3), Image.BILINEAR)
    corners = [strip.getpixel(p) for p in ((0, 0), (2, 0), (0, 2), (2, 2))]
    return tuple(sum(channel) // len(corners) for channel in zip(*corners))


def _fallback_garment(exc, uploaded, action, moment, attempted: set[str]):
    """La piece suivante, si et seulement si le refus la justifie.

    Une seule alternative : au-dela, on brulerait des unites a chercher une
    aiguille. Deux echecs d'affilee signalent la photo ou la pose, pas le
    vetement.
    """
    if uploaded is not None:
        # La piece de l'utilisateur : il l'a choisie, on ne la remplace pas.
        return None
    if getattr(exc, "provider_code", None) != "error_editing_failed":
        return None
    if len(attempted) >= 2:
        return None
    return garment_service.next_best_garment(action, moment, exclude=attempted)


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

    asset, source_bytes = await _load_source_image(db, session.id, analysis)

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
    async def _render():
        """Essaie la piece choisie, puis au plus une alternative.

        Une piece de catalogue qui passe tous nos controles peut quand meme
        faire echouer le rendu — mesure en direct : `jacket_01` echoue la ou
        `jacket_02` reussit, sur la meme photo. Nous ne savons pas dire
        lesquelles a l'avance, donc le produit doit survivre a la rencontre.

        La DECISION ne change pas : meme action, meme categorie. Seule la piece
        qui sert de preuve differe — la semantique de « Try another », appliquee
        une fois, automatiquement.

        Ecrit en boucle et non en `try/except` imbriques : une exception levee
        DANS un `except` echappe aux autres gestionnaires du meme `try`, et la
        seconde tentative remontait alors sans etre traduite.
        """
        nonlocal garment_ref, garment_label, garment_key
        attempted: set[str] = set()

        while True:
            attempted.add(garment_key)
            try:
                return await provider.generate(
                    source_bytes, garment_ref, source_mime=asset.mime_type
                )
            except YouCamError as failure:
                alternative = _fallback_garment(
                    failure, uploaded, action, moment_spec, attempted
                )
                if alternative is None:
                    raise
                logger.info(
                    "vto_fallback_garment",
                    extra={
                        "failed": garment_key,
                        "trying": alternative.id,
                        "reason": getattr(failure, "provider_code", None),
                    },
                )
                garment_ref = garment_service.to_ref(alternative)
                garment_label, garment_key = alternative.name, alternative.id
                context["garment_id"] = public["garment_id"] = alternative.id

    try:
        generated = await _render()

        # La piece a peut-etre change en cours de route : le resultat doit
        # nommer celle qui a REELLEMENT servi, sinon « Try another » proposerait
        # de remplacer un vetement qui n'a jamais ete utilise.
        result.garment_id = garment_key
        result.meta = {**(result.meta or {}), "garment_name": garment_label}
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
