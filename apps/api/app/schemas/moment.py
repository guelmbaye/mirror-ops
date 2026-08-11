from __future__ import annotations

from pydantic import Field

from app.models.enums import Goal, Occasion, TimeAvailable
from app.schemas.common import APIModel


class MomentCreateRequest(APIModel):
    session_id: str
    occasion: Occasion
    goal: Goal
    time_available: TimeAvailable = Field(
        description="Temps disponible pour agir : <5m, 5_15m, 15_30m, 30m_plus"
    )
    note: str | None = Field(default=None, max_length=280)


class MomentResponse(APIModel):
    id: str
    session_id: str
    occasion: str
    goal: str
    time_available: str
    note: str | None = None
