"""Interpretation du contexte (Doc 06 §5) : donnees brutes -> signaux decisionnels."""

from __future__ import annotations

from app.engines.one_change.tables import (
    GOAL_VECTORS,
    OCCASION_TARGET_FORMALITY,
    OCCASION_VECTORS,
)
from app.engines.one_change.types import DIMENSIONS, MomentSpec, clamp
from app.models.enums import TimeAvailable


def goal_vector(moment: MomentSpec) -> dict[str, float]:
    return GOAL_VECTORS[moment.goal]


def occasion_vector(moment: MomentSpec) -> dict[str, float]:
    return OCCASION_VECTORS[moment.occasion]


def blended_priority_vector(moment: MomentSpec, goal_weight: float = 0.6) -> dict[str, float]:
    """Objectif utilisateur (dominant) + exigences de l'occasion."""
    goal = goal_vector(moment)
    occasion = occasion_vector(moment)
    blended = {
        d: goal_weight * goal.get(d, 0.0) + (1.0 - goal_weight) * occasion.get(d, 0.0)
        for d in DIMENSIONS
    }
    total = sum(blended.values()) or 1.0
    return {d: v / total for d, v in blended.items()}


def target_formality(moment: MomentSpec) -> float:
    return OCCASION_TARGET_FORMALITY[moment.occasion]


def weighted_fit(dimensions: dict[str, float], vector: dict[str, float]) -> float:
    """Adequation ponderee de l'etat courant a un vecteur de priorites (0..1)."""
    total = sum(vector.values()) or 1.0
    return clamp(sum(dimensions.get(d, 0.0) * vector.get(d, 0.0) for d in DIMENSIONS) / total)


def intervention_tolerance(moment: MomentSpec) -> float:
    """Tolerance a l'intervention selon le temps disponible (Doc 06 §5)."""
    return {
        TimeAvailable.UNDER_5M: 0.35,
        TimeAvailable.FROM_5_TO_15M: 0.65,
        TimeAvailable.FROM_15_TO_30M: 0.85,
        TimeAvailable.OVER_30M: 1.00,
    }[moment.time_available]
