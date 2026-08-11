"""Score normalise 0-100 (Doc 06 §9 / Doc 04 §12)."""

from __future__ import annotations

from app.engines.one_change.features import compute_features, projected_dimensions
from app.engines.one_change.tables import SCORE_WEIGHTS, SIMPLICITY
from app.engines.one_change.types import (
    CandidateFeatures,
    DecisionContext,
    ScoredCandidate,
)
from app.models.enums import ChangeAction


def raw_score(features: CandidateFeatures) -> float:
    values = features.as_dict()
    return sum(SCORE_WEIGHTS[name] * values[name] for name in SCORE_WEIGHTS)


def score_candidate(context: DecisionContext, action: ChangeAction) -> ScoredCandidate:
    features = compute_features(context, action)
    return ScoredCandidate(
        action=action,
        score=round(raw_score(features) * 100.0, 2),
        features=features,
        simplicity=SIMPLICITY[action],
        projected_dimensions=projected_dimensions(context, action),
    )


def score_all(context: DecisionContext, actions: list[ChangeAction]) -> list[ScoredCandidate]:
    return [score_candidate(context, action) for action in actions]


def contribution_breakdown(features: CandidateFeatures) -> dict[str, float]:
    """Contribution ponderee de chaque feature -> sert a expliquer la decision."""
    values = features.as_dict()
    return {name: round(SCORE_WEIGHTS[name] * values[name], 4) for name in SCORE_WEIGHTS}
