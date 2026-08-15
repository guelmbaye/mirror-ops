"""Health checks (Doc 08 §18)."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import get_settings
from app.integrations.youcam import crypto_available
from app.services.face_crop import opencv_status
from app.services.garment_audit import placeholder_ids
from app.services.garment_service import list_garments
from app.schemas.common import DependencyHealthResponse, HealthResponse
from app.services.storage import get_storage

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness")
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok", version=settings.APP_VERSION, environment=settings.APP_ENV
    )


@router.get(
    "/health/dependencies",
    response_model=DependencyHealthResponse,
    summary="Etat des dependances",
)
async def dependencies(db: DbSession) -> DependencyHealthResponse:
    settings = get_settings()

    try:
        await db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001
        database = "unavailable"

    try:
        await get_storage().exists("healthcheck")
        storage = "ok"
    except Exception:  # noqa: BLE001
        storage = "unavailable"

    # Un catalogue de substitution est exploitable par la composition locale,
    # jamais par un vrai try-on : la tache echoue alors en `error_editing_failed`.
    # Sans detection de visage : aucun signal peau, et le cadrage retombe sur
    # « inconnu ». Le produit fonctionne, mais l'integration Skin AI est morte.
    face_ready, face_reason = opencv_status()
    face_state = "ok" if face_ready else "unavailable"

    missing_real = placeholder_ids(list_garments())
    garments_state = "placeholder" if missing_real else "ok"

    if settings.is_live_youcam:
        if settings.YOUCAM_AUTH_MODE == "client_credentials" and not crypto_available():
            # La dependance de chiffrement manque : l'authentification echouera.
            # Le dire ici evite de le decouvrir au premier appel d'analyse.
            youcam = "missing_dependency"
        elif settings.has_youcam_credentials:
            youcam = "configured"
        else:
            youcam = "missing_credentials"
    else:
        youcam = "mock_mode"

    return DependencyHealthResponse(
        api="ok",
        database=database,
        storage=storage,
        youcam=youcam,
        garments=garments_state,
        face_detection=face_state,
        youcam_mode=settings.YOUCAM_MODE,
    )
