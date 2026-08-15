"""Types partages du contrat public."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer


def _iso_z(value: datetime) -> str:
    return value.replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


UtcDateTime = Annotated[datetime, PlainSerializer(_iso_z, return_type=str)]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ErrorBody(APIModel):
    code: str
    message: str
    retryable: bool
    request_id: str | None = None
    details: dict | None = None


class ErrorEnvelope(APIModel):
    """Contrat d'erreur unique de l'API (Doc 08 §19)."""

    error: ErrorBody


class HealthResponse(APIModel):
    status: str = "ok"
    version: str
    environment: str


class DependencyHealthResponse(APIModel):
    api: str
    database: str
    storage: str
    youcam: str
    youcam_mode: str
    garments: str = "ok"
    face_detection: str = "ok"
