from __future__ import annotations

from app.schemas.common import APIModel, UtcDateTime


class SessionCreateResponse(APIModel):
    id: str
    status: str
    state: str
    expires_at: UtcDateTime


class SessionSummary(APIModel):
    id: str
    status: str
    state: str
    created_at: UtcDateTime
    expires_at: UtcDateTime
