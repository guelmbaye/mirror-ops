from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Moment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Le "moment qui compte" : occasion + objectif + temps disponible."""

    __tablename__ = "moments"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occasion: Mapped[str] = mapped_column(String(24), nullable=False)
    goal: Mapped[str] = mapped_column(String(24), nullable=False)
    time_available: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(String(280), nullable=True)

    session = relationship("UserSession", back_populates="moments")
