from __future__ import annotations

from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AppearanceAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Contexte d'apparence normalise (jamais la reponse brute du provider)."""

    __tablename__ = "appearance_analyses"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("image_assets.id", ondelete="CASCADE"), nullable=False
    )
    skin: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    skin_source: Mapped[str] = mapped_column(String(32), default="youcam_skin_ai", nullable=False)
    appearance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    element_suitability: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    outfit: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    image_quality: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    #: Ce que la photo montre : cadrage estime et elements prouvables.
    framing: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    session = relationship("UserSession", back_populates="analyses")
