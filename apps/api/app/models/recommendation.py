from __future__ import annotations

from sqlalchemy import Boolean, JSON, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Recommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Sortie du moteur ONE CHANGE (Doc 04 §17)."""

    __tablename__ = "recommendations"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    moment_id: Mapped[str] = mapped_column(String(36), ForeignKey("moments.id", ondelete="CASCADE"))
    analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("appearance_analyses.id", ondelete="CASCADE")
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[str] = mapped_column(String(12), nullable=False)
    confidence_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    #: La piece visee etait absente : c'est un ajout, pas un remplacement.
    is_addition: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: Verdict d'adequation contextuelle : FIT / ALMOST_THERE / MISMATCH.
    fit: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    #: La piece que le moteur utilisera pour la preuve visuelle.
    #: Exposee AVANT l'essayage : le bouton peut alors dire ce qu'il montrera,
    #: sans pour autant offrir un catalogue a parcourir.
    suggested_garment: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    what: Mapped[str] = mapped_column(String(120), nullable=False)
    why: Mapped[str] = mapped_column(Text, nullable=False)
    how: Mapped[str] = mapped_column(Text, nullable=False)
    keep: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    impact: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    candidates: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # interne / debug

    session = relationship("UserSession", back_populates="recommendations")
