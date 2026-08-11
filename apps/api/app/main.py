"""Point d'entree de l'API MIRROR OPS.

    YouCam perceives and visualizes. MIRROR OPS decides.

Architecture : monolithe modulaire (Doc 07). Un seul deployable.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.integrations.youcam import INSTALL_HINT, crypto_available
from app.services.garment_audit import placeholder_ids
from app.services.garment_service import list_garments
from app.core.errors import register_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.rate_limit import RateLimitMiddleware
from app.db.session import dispose_engine, init_models
from app.integrations.youcam.client import close_youcam_client
from app.schemas.common import ErrorEnvelope

logger = logging.getLogger("mirror_ops")

DESCRIPTION = """
**MIRROR OPS** — Contextual Appearance Decision Engine. One moment. One change.

Parcours : `Moment -> Analyze -> ONE CHANGE -> See -> Decide`.

- `POST /sessions` demarre un parcours anonyme
- `POST /moments` decrit le moment qui compte
- `POST /appearance/analyze` lit le look actuel (YouCam Skin AI)
- `POST /one-change/evaluate` selectionne **une seule** intervention
- `POST /vto/generate` prouve visuellement la recommandation (YouCam Apparel VTO)

L'API expose des **decisions**, pas des details d'implementation.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    logger.info(
        "startup",
        extra={"env": settings.APP_ENV, "youcam_mode": settings.YOUCAM_MODE},
    )
    # Une configuration YouCam incoherente doit se voir au demarrage, et non se
    # decouvrir en plein parcours sous la forme d'un 502.
    if settings.is_live_youcam:
        if not settings.has_youcam_credentials:
            logger.error(
                "youcam_live_without_credentials",
                extra={
                    "youcam_mode": settings.YOUCAM_MODE,
                    "auth_mode": settings.YOUCAM_AUTH_MODE,
                    "hint": "Set YOUCAM_CLIENT_ID, YOUCAM_CLIENT_SECRET and YOUCAM_SECRET_KEY "
                    "in apps/api/.env",
                },
            )
        if settings.YOUCAM_AUTH_MODE == "client_credentials" and not crypto_available():
            logger.error("youcam_missing_dependency", extra={"hint": INSTALL_HINT})

        placeholders = placeholder_ids(list_garments())
        if placeholders:
            logger.error(
                "garment_catalog_is_placeholder",
                extra={
                    "count": len(placeholders),
                    "ids": placeholders[:5],
                    "hint": "The shipped garment images are flat placeholders. A real try-on "
                    "will fail with error_editing_failed. Replace the PNG files in "
                    "app/assets/garments/ with real garment photographs, same file names.",
                },
            )
    else:
        logger.warning(
            "youcam_mock_mode_active",
            extra={
                "youcam_mode": settings.YOUCAM_MODE,
                "note": "previews are composed locally and flagged simulated",
            },
        )
    await init_models()
    yield
    await close_youcam_client()
    await dispose_engine()
    logger.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        responses={
            400: {"model": ErrorEnvelope},
            409: {"model": ErrorEnvelope},
            422: {"model": ErrorEnvelope},
            500: {"model": ErrorEnvelope},
        },
    )

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["health"], summary="Liveness (alias racine)")
    async def root_health() -> dict[str, str]:
        return {"status": "ok", "version": settings.APP_VERSION}

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "product": "MIRROR OPS",
            "tagline": "Don't change everything. Change one thing.",
            "docs": "/docs",
            "api": settings.API_V1_PREFIX,
        }

    return app


app = create_app()
