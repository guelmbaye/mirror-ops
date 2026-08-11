from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import VTOStatus


class VTOResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Trace d'une generation Apparel VTO (metadonnees uniquement)."""

    __tablename__ = "vto_results"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recommendation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    garment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=VTOStatus.QUEUED, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), default="youcam", nullable=False)
    provider_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_image_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    result_image_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    session = relationship("UserSession", back_populates="vto_results")
