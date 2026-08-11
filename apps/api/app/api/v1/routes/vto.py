"""Apparel Virtual Try-On : la preuve visuelle de ONE CHANGE."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import DbSession, IdempotencyKey
from app.core.errors import AppError, ErrorCode
from app.models.enums import SessionState
from app.schemas.vto import (
    GarmentListResponse,
    GarmentOut,
    UploadedGarmentResponse,
    VTOGenerateRequest,
    VTOResponse,
)
from app.services import (
    appearance_service,
    decision_service,
    garment_service,
    idempotency,
    moment_service,
    session_service,
    vto_service,
)
from app.services import uploaded_garment
from app.services.garment_audit import placeholder_ids
from app.services.result_builder import vto_response

router = APIRouter(tags=["vto"])


@router.post(
    "/vto/generate",
    response_model=VTOResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Visualiser le changement recommande",
)
async def generate(
    payload: VTOGenerateRequest, db: DbSession, idempotency_key: IdempotencyKey = None
) -> VTOResponse:
    session = await session_service.get_active_session(db, payload.session_id)
    session_service.require_state(session, SessionState.DECISION_COMPLETED, "previewing the change")

    recommendation = (
        await decision_service.get_recommendation(db, payload.recommendation_id)
        if payload.recommendation_id
        else await decision_service.get_latest_recommendation(db, session.id)
    )
    if recommendation.session_id != session.id:
        raise AppError(ErrorCode.INVALID_REQUEST, "This recommendation belongs to another session.")

    scope = "vto.generate"
    key = idempotency_key or f"{recommendation.id}:{payload.garment_asset_id or 'auto'}"
    cached = await idempotency.get_cached_response(db, scope, key)
    if cached:
        return VTOResponse.model_validate(cached)

    analysis = await appearance_service.get_analysis(db, recommendation.analysis_id)
    moment = await moment_service.get_moment(db, recommendation.moment_id)

    result, _url, _simulated = await vto_service.generate_vto(
        db, session, recommendation, analysis, moment, garment_id=payload.garment_asset_id
    )
    response = await vto_response(db, result)
    await idempotency.store_response(db, scope, key, response.model_dump(mode="json"))
    return response


@router.get("/vto/{vto_id}", response_model=VTOResponse, summary="Recuperer un apercu")
async def get_vto(vto_id: str, db: DbSession) -> VTOResponse:
    result = await vto_service.get_vto(db, vto_id)
    return await vto_response(db, result)


@router.get("/garments", response_model=GarmentListResponse, summary="Catalogue de demonstration")
async def list_garments(category: str | None = None) -> GarmentListResponse:
    garments = garment_service.list_garments(category)
    # Chaque vetement dit s'il est une vraie photo ou un aplat genere : sans
    # cela, diagnostiquer un echec d'essayage demande une inspection manuelle
    # des fichiers.
    fake = set(placeholder_ids(garments))
    return GarmentListResponse(
        garments=[
            GarmentOut(**g.as_dict(), placeholder=g.id in fake) for g in garments
        ]
    )


@router.post(
    "/garments/upload",
    response_model=UploadedGarmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Essayer sa propre piece",
)
async def upload_garment(
    db: DbSession,
    session_id: str = Form(...),
    image: UploadFile = File(...),
) -> UploadedGarmentResponse:
    """Accepte une photo de vetement pour la duree de la session.

    Le catalogue existe pour que le parcours ne s'arrete jamais. Mais quelqu'un
    qui hesite devant une piece precise a une bien meilleure raison de vouloir
    la voir sur lui : l'identifiant renvoye ici s'utilise tel quel comme
    `garment_asset_id` sur `POST /vto/generate`.
    """
    session = await session_service.get_active_session(db, session_id)
    raw = await image.read()
    asset = await uploaded_garment.store_uploaded_garment(
        db, session, raw, image.content_type or "image/jpeg"
    )
    await db.commit()

    return UploadedGarmentResponse(
        id=asset.id,
        width=asset.width,
        height=asset.height,
        size_bytes=asset.size_bytes,
    )
