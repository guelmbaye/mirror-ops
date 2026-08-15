"""Capture + analyse d'apparence (Skin AI + contexte)."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import DbSession, IdempotencyKey
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.security import hash_bytes
from app.models.enums import SessionState
from app.schemas.appearance import AppearanceAnalysisResponse, OutfitIn
from app.services import appearance_service, idempotency, moment_service, session_service
from app.services.result_builder import analysis_response

router = APIRouter(prefix="/appearance", tags=["appearance"])


@router.post(
    "/analyze",
    response_model=AppearanceAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyser le look actuel (YouCam Skin AI + contexte d'apparence)",
)
async def analyze(
    db: DbSession,
    idempotency_key: IdempotencyKey = None,
    session_id: str = Form(...),
    image: UploadFile = File(...),
    outfit: str | None = Form(default=None, description="JSON optionnel decrivant la tenue"),
    moment_id: str | None = Form(default=None),
) -> AppearanceAnalysisResponse:
    settings = get_settings()
    session = await session_service.get_active_session(db, session_id)
    session_service.require_state(session, SessionState.MOMENT_CREATED, "analysing your look")

    moment = (
        await moment_service.get_moment(db, moment_id)
        if moment_id
        else await moment_service.get_latest_moment(db, session.id)
    )
    if moment.session_id != session.id:
        raise AppError(ErrorCode.INVALID_REQUEST, "This moment belongs to another session.")

    raw = await image.read()
    if len(raw) > settings.MAX_IMAGE_BYTES:
        raise AppError(ErrorCode.IMAGE_TOO_LARGE)

    scope = "appearance.analyze"
    # La cle doit couvrir TOUT ce dont le resultat depend.
    #
    # Photo et tenue ne suffisent pas : l'analyse evalue l'adequation de chaque
    # piece AU MOMENT (`item_suitability(item, moment)`). Sans le moment dans la
    # cle, revenir en arriere pour choisir une autre occasion renvoyait
    # l'analyse precedente — figee sur l'occasion initiale — et la decision
    # repetait la meme recommandation quel que soit le nouveau moment.
    #
    # C'est la deuxieme fois que cette regle est enfreinte dans ce fichier. Elle
    # merite d'etre enoncee : une memoisation doit etre indexee sur la totalite
    # de ses entrees, sinon elle transforme une correction en illusion.
    moment_key = f"{moment.occasion}:{moment.goal}:{moment.time_available}"
    key = idempotency_key or (
        f"{session.id}:{hash_bytes(raw)[:32]}"
        f":{hash_bytes((outfit or '').encode())[:16]}"
        f":{hash_bytes(moment_key.encode())[:12]}"
    )
    cached = await idempotency.get_cached_response(db, scope, key)
    if cached:
        return AppearanceAnalysisResponse.model_validate(cached)

    outfit_input = OutfitIn.parse_form_value(outfit)
    analysis, _signals, simulated = await appearance_service.analyze_appearance(
        db,
        session,
        moment_service.to_spec(moment),
        raw,
        image.content_type,
        outfit_input.to_domain(),
    )

    response = await analysis_response(db, analysis, simulated=simulated)
    await idempotency.store_response(db, scope, key, response.model_dump(mode="json"))
    return response
