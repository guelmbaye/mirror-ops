"""Seuils de decision (Doc 04 §14 / §15)."""

from __future__ import annotations

from dataclasses import dataclass

from app.engines.one_change.types import ScoredCandidate
from app.models.enums import ChangeAction


@dataclass(frozen=True, slots=True)
class ThresholdPolicy:
    min_recommendation_score: float = 60.0
    no_change_margin: float = 2.0
    #: En deca, la photo est inexploitable : on demande a la reprendre.
    min_image_quality: float = 0.35
    #: Conserve pour la calibration et les diagnostics : en dessous, la
    #: decision est rendue avec `confidence: low`. Ce n'est PAS un motif de
    #: refus — voir OneChangeEngine._validate.
    low_confidence_floor: float = 0.20


def apply_thresholds(
    ranked: list[ScoredCandidate],
    policy: ThresholdPolicy,
) -> tuple[ScoredCandidate, str]:
    """Retourne (gagnant, motif de la selection).

    Regles :
    - un changement doit depasser le score minimal ;
    - un changement doit battre NO_CHANGE d'une marge minimale, sinon on ne
      recommande rien (Doc 02 §13 : ne pas inventer un changement pour utiliser VTO).
    """
    no_change = next((c for c in ranked if c.action is ChangeAction.NO_CHANGE), None)
    changes = [c for c in ranked if c.action is not ChangeAction.NO_CHANGE]

    if not changes:
        assert no_change is not None
        return no_change, "no_candidate_change_available"

    best_change = changes[0]

    if best_change.score < policy.min_recommendation_score:
        if no_change is not None:
            return no_change, "best_change_below_threshold"
        return best_change, "below_threshold_but_no_alternative"

    if no_change is not None and best_change.score < no_change.score + policy.no_change_margin:
        return no_change, "current_look_already_fits"

    return best_change, "highest_impact_change"
