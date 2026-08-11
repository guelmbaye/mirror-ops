"""Confiance de decision (Doc 06 §13/§14).

Distinction essentielle :
- Decision Score      -> qualite relative de l'intervention ;
- Decision Confidence -> confiance du moteur dans sa selection.

Jamais presentee comme une probabilite calibree scientifiquement.
"""

from __future__ import annotations

from app.engines.one_change.types import DecisionContext, ScoredCandidate, clamp
from app.models.enums import ConfidenceLevel, OutfitElement


def candidate_separation(winner: ScoredCandidate, runner_up: ScoredCandidate | None) -> float:
    if runner_up is None:
        return 0.85
    # Distance ABSOLUE au concurrent le plus proche : un quasi ex aequo reste
    # un quasi ex aequo, meme lorsque le departage a retenu le moindre effort.
    delta = abs(winner.score - runner_up.score)
    return clamp(0.45 + delta / 20.0)  # 0 pt -> 0.45 ; >= 11 pts -> 1.0


def context_completeness(context: DecisionContext) -> float:
    elements = list(OutfitElement)
    known = sum(1 for e in elements if context.appearance.element_known.get(e, False))
    presence_ratio = len(context.appearance.present_elements) / len(elements)
    known_ratio = known / len(elements)
    skin_bonus = 0.1 if context.appearance.skin.available else 0.0
    return clamp(0.45 + 0.25 * presence_ratio + 0.25 * known_ratio + skin_bonus)


def compute_confidence(
    context: DecisionContext,
    winner: ScoredCandidate,
    runner_up: ScoredCandidate | None,
) -> tuple[float, ConfidenceLevel]:
    data_quality = clamp(0.35 + 0.65 * context.appearance.data_confidence)
    separation = candidate_separation(winner, runner_up)
    completeness = context_completeness(context)
    value = clamp(data_quality * separation * completeness)
    return round(value, 4), to_level(value)


def to_level(value: float) -> ConfidenceLevel:
    if value >= 0.62:
        return ConfidenceLevel.HIGH
    if value >= 0.40:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW
