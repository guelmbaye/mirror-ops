from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, in_minutes
from app.core.config import get_settings
from app.models.enums import SessionState, SessionStatus


def _default_expiry() -> datetime:
    return in_minutes(get_settings().SESSION_TTL_MINUTES)


class UserSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Parcours anonyme (Doc 07 §13 : aucun compte utilisateur au MVP)."""

    __tablename__ = "sessions"

    status: Mapped[str] = mapped_column(String(24), default=SessionStatus.ACTIVE, nullable=False)
    state: Mapped[str] = mapped_column(
        String(32), default=SessionState.SESSION_CREATED, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, default=_default_expiry, nullable=False)

    moments = relationship("Moment", back_populates="session", cascade="all, delete-orphan", lazy="selectin")
    analyses = relationship("AppearanceAnalysis", back_populates="session", cascade="all, delete-orphan", lazy="selectin")
    recommendations = relationship("Recommendation", back_populates="session", cascade="all, delete-orphan", lazy="selectin")
    vto_results = relationship("VTOResult", back_populates="session", cascade="all, delete-orphan", lazy="selectin")
    images = relationship("ImageAsset", back_populates="session", cascade="all, delete-orphan", lazy="selectin")
