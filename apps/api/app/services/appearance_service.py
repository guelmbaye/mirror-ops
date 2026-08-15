"""Orchestration de l'analyse d'apparence (Doc 02 FR-03/FR-04, Doc 05 §5).

    image -> validation -> stockage temporaire -> Skin AI -> normalisation
          -> estimateur d'apparence -> AppearanceAnalysis persistee

Le cache court evite de repayer une analyse pour la meme image (Doc 05 §20).
"""

from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.security import hash_bytes
from app.db.base import in_minutes
from app.engines.appearance.estimator import build_appearance_signals
from app.engines.one_change.types import (
    AppearanceSignals,
    MomentSpec,
    OutfitItem,
    SkinObservations,
)
from app.integrations.youcam import (
    YouCamError,
    diagnostics,
    YouCamInvalidImageError,
    YouCamQuotaExhaustedError,
    YouCamRateLimitError,
    YouCamTimeoutError,
    get_skin_provider,
)
from app.models.analysis import AppearanceAnalysis
from app.models.enums import OutfitElement, SessionState
from app.models.image_asset import ImageAsset
from app.models.session import UserSession
from app.services import session_service
from app.services.face_crop import FALLBACK_FACE_RATIO, crop_face_for_skin
from app.services.framing import estimate_framing
from app.services.image_validation import ValidatedImage, validate_image
from app.services.storage import get_storage, session_key

logger = logging.getLogger("mirror_ops.appearance")


def _tighter_crop(exc, image, provider):
    """Le recadrage de repli, si et seulement si le refus le justifie."""
    if getattr(exc, "provider_code", None) != "error_src_face_too_small":
        return None
    if not (settings.SKIN_FACE_CROP_ENABLED and getattr(provider, "requires_face_crop", False)):
        return None
    return crop_face_for_skin(image.data, target=FALLBACK_FACE_RATIO)


def _debug_details(info: dict[str, str]) -> dict[str, str] | None:
    """En developpement uniquement : la cause remonte jusqu'a l'appelant.

    En production, le contrat d'erreur reste opaque — aucun detail provider ne
    doit fuiter vers un utilisateur final.
    """
    return info if get_settings().APP_ENV == "development" else None

#: Cache memoire court : hash(image) + type d'analyse -> observations.
_skin_cache: dict[str, tuple[float, dict, str, bool]] = {}


async def store_input_image(
    db: AsyncSession, session: UserSession, image: ValidatedImage
) -> ImageAsset:
    settings = get_settings()
    extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[image.mime_type]
    content_hash = hash_bytes(image.data)
    key = session_key(session.id, "input", f"{content_hash[:16]}.{extension}")
    await get_storage().put(key, image.data, image.mime_type)

    asset = ImageAsset(
        session_id=session.id,
        kind="input",
        storage_key=key,
        mime_type=image.mime_type,
        size_bytes=image.size_bytes,
        width=image.width,
        height=image.height,
        content_hash=content_hash,
        expires_at=in_minutes(settings.MEDIA_TTL_MINUTES),
    )
    db.add(asset)
    await db.flush()
    return asset


async def run_skin_analysis(image: ValidatedImage) -> tuple[SkinObservations, str, bool, int]:
    """Appelle le provider Skin AI, avec cache court et erreurs traduites."""
    settings = get_settings()
    cache_key = f"{hash_bytes(image.data)}:skin"
    cached = _skin_cache.get(cache_key)
    now = time.time()
    if cached and now - cached[0] < settings.YOUCAM_CACHE_TTL_SECONDS:
        _, observations, provider, simulated = cached
        return _to_observations(observations, provider, simulated), provider, simulated, 0

    provider = get_skin_provider()
    started = time.perf_counter()

    # Skin AI exige un visage occupant > 60 % de la largeur ; la photo de tenue
    # ne le permet pas. On lui envoie donc un cadrage du visage, extrait de la
    # meme prise de vue. L'original reste intact pour le VTO et l'affichage.
    payload, payload_mime = image.data, image.mime_type
    if settings.SKIN_FACE_CROP_ENABLED and getattr(provider, "requires_face_crop", False):
        crop = crop_face_for_skin(image.data)
        if crop is not None:
            payload, payload_mime = crop.image_bytes, crop.mime_type
            logger.info(
                "skin_face_cropped",
                extra={"face_ratio": crop.face_ratio, "width": crop.width, "height": crop.height},
            )
        else:
            # Aucun visage exploitable : inutile de consommer une unite pour un
            # rejet certain. On poursuit sans signal peau.
            logger.info("skin_skipped_no_face")
            return _to_observations({}, "unavailable_no_face", False), "unavailable_no_face", False, 0

    try:
        result = await provider.analyze(payload, payload_mime)
    except YouCamInvalidImageError as exc:
        # « Visage trop petit » malgre le recadrage : le provider mesure
        # autrement que nous, ou son detecteur trouve un visage plus petit.
        # Une seconde tentative, plus serree, coute une unite — et seulement
        # quand la premiere a echoue pour cette raison precise.
        retry = _tighter_crop(exc, image, provider)
        if retry is None:
            raise
        logger.info("skin_retry_tighter_crop", extra={"face_ratio": retry.face_ratio})
        try:
            result = await provider.analyze(retry.image_bytes, retry.mime_type)
        except YouCamError as second:
            info = diagnostics(second, provider.provider_name)
            logger.warning("skin_provider_degraded", extra={**info, "attempt": "tighter"})
            return _to_observations({}, "unavailable", False), "unavailable", False, 0
    except YouCamRateLimitError:
        raise AppError(ErrorCode.RATE_LIMITED)
    except (YouCamInvalidImageError, YouCamQuotaExhaustedError, YouCamTimeoutError, YouCamError) as exc:
        # Skin AI INFORME la decision, il ne la prend pas : son indisponibilite
        # ne doit pas interrompre le parcours. On continue sans signal peau, en
        # le declarant — la confiance de decision baisse d'elle-meme.
        info = diagnostics(exc, provider.provider_name)
        logger.warning("skin_provider_degraded", extra=info)
        return _to_observations({}, "unavailable", False), "unavailable", False, 0

    latency_ms = int((time.perf_counter() - started) * 1000)
    _skin_cache[cache_key] = (now, result.observations, result.provider, result.simulated)
    return (
        _to_observations(result.observations, result.provider, result.simulated),
        result.provider,
        result.simulated,
        latency_ms,
    )


def _to_observations(raw: dict, provider: str, simulated: bool) -> SkinObservations:
    return SkinObservations(
        texture=raw.get("texture"),
        redness=raw.get("redness"),
        oiliness=raw.get("oiliness"),
        radiance=raw.get("radiance"),
        available=bool(raw),
        source=provider + ("_simulated" if simulated else ""),
    )


async def analyze_appearance(
    db: AsyncSession,
    session: UserSession,
    moment_spec: MomentSpec,
    raw_image: bytes,
    declared_mime: str | None,
    outfit: dict[OutfitElement, OutfitItem],
) -> tuple[AppearanceAnalysis, AppearanceSignals, bool]:
    image = validate_image(raw_image, declared_mime)
    asset = await store_input_image(db, session, image)

    skin, provider_name, simulated, latency_ms = await run_skin_analysis(image)
    # Ce que la photo montre borne ce que le produit peut PROUVER.
    estimate = estimate_framing(image.data)
    signals = build_appearance_signals(
        moment_spec, outfit, skin, image.quality, visible_elements=set(estimate.visible)
    )

    analysis = AppearanceAnalysis(
        session_id=session.id,
        image_id=asset.id,
        skin=skin.as_dict(),
        skin_source=skin.source,
        appearance=signals.dimensions,
        element_suitability={str(k): round(v, 4) for k, v in signals.element_suitability.items()},
        outfit={
            str(element): {
                "present": item.present,
                "known": item.known,
                "formality": item.formality,
                "structure": item.structure,
                "color_harmony": item.color_harmony,
                "condition": item.condition,
                "descriptor": item.descriptor,
            }
            for element, item in outfit.items()
        },
        image_quality=image.quality.as_dict(),
        framing=estimate.as_dict(),
        data_confidence=signals.data_confidence,
    )
    db.add(analysis)
    await db.flush()
    await session_service.advance_state(db, session, SessionState.ANALYSIS_COMPLETED)

    logger.info(
        "appearance_analyzed",
        extra={
            "session_id": session.id,
            "provider": provider_name,
            "simulated": simulated,
            "skin_latency_ms": latency_ms,
            "data_confidence": signals.data_confidence,
        },
    )
    return analysis, signals, simulated


async def get_analysis(db: AsyncSession, analysis_id: str) -> AppearanceAnalysis:
    analysis = (
        await db.execute(select(AppearanceAnalysis).where(AppearanceAnalysis.id == analysis_id))
    ).scalar_one_or_none()
    if analysis is None:
        raise AppError(ErrorCode.NOT_FOUND, "We couldn't find this analysis.")
    return analysis


async def get_latest_analysis(db: AsyncSession, session_id: str) -> AppearanceAnalysis:
    stmt = (
        select(AppearanceAnalysis)
        .where(AppearanceAnalysis.session_id == session_id)
        .order_by(AppearanceAnalysis.created_at.desc(), AppearanceAnalysis.id.desc())
    )
    analysis = (await db.execute(stmt)).scalars().first()
    if analysis is None:
        raise AppError(ErrorCode.INVALID_STATE, "Show us your current look first.")
    return analysis


def signals_from_analysis(analysis: AppearanceAnalysis) -> AppearanceSignals:
    """Reconstruit les signaux depuis la base (evite de re-appeler le provider)."""
    suitability = {OutfitElement(k): float(v) for k, v in (analysis.element_suitability or {}).items()}
    outfit = analysis.outfit or {}
    known = {
        OutfitElement(k): bool(v.get("known", False))
        for k, v in outfit.items()
        if v.get("present", True)
    }
    present = {OutfitElement(k) for k, v in outfit.items() if v.get("present", True)}
    skin_raw = analysis.skin or {}
    return AppearanceSignals(
        dimensions={k: float(v) for k, v in (analysis.appearance or {}).items()},
        element_suitability=suitability,
        element_known=known,
        present_elements=present,
        data_confidence=float(analysis.data_confidence),
        image_quality=float((analysis.image_quality or {}).get("score", 0.7) or 0.7),
        skin=SkinObservations(
            texture=skin_raw.get("texture"),
            redness=skin_raw.get("redness"),
            oiliness=skin_raw.get("oiliness"),
            radiance=skin_raw.get("radiance"),
            available=bool(skin_raw),
            source=analysis.skin_source,
        ),
        # Ces deux champs traversent la base, comme le reste.
        #
        # Ils avaient ete ajoutes au domaine sans etre restaures ici : la
        # decision les recevait vides. `element_formality` sert a dire dans
        # quel SENS changer — le libelle retombait donc sur « Change the
        # jacket », sans direction. `visible_elements` borne la decision a ce
        # que la photo montre — la restriction de cadrage etait donc inerte.
        #
        # Un champ ajoute a un objet de domaine doit etre suivi jusqu'au bout
        # de son chemin, y compris la ou l'objet est RECONSTRUIT.
        element_formality={
            OutfitElement(key): float(value["formality"])
            for key, value in outfit.items()
            if value.get("present", True) and value.get("formality") is not None
        },
        visible_elements=(
            {OutfitElement(e) for e in (analysis.framing or {}).get("visible_elements", [])}
            or None
        ),
    )


def clear_skin_cache() -> None:
    _skin_cache.clear()
