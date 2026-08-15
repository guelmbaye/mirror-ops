"""Score normalise 0-100 (Doc 06 §9 / Doc 04 §12)."""

from __future__ import annotations

from app.engines.one_change.features import compute_features, projected_dimensions
from app.engines.one_change.tables import (
    ANOMALY_BONUS,
    ANOMALY_MARGIN,
    SCORE_WEIGHTS,
    SIMPLICITY,
)
from app.engines.one_change.types import (
    CandidateFeatures,
    DecisionContext,
    ScoredCandidate,
    clamp,
)
from app.models.enums import MATERIALISED_ELEMENT, ChangeAction


def raw_score(features: CandidateFeatures) -> float:
    values = features.as_dict()
    return sum(SCORE_WEIGHTS[name] * values[name] for name in SCORE_WEIGHTS)


def anomaly_lift(context: DecisionContext, action: ChangeAction) -> float:
    """Prime au levier qui corrige la piece qui detonne.

    Le produit corrige un ecart, il ne redessine pas une tenue. Quand un
    element est nettement en retrait de ses voisins, le reparer EST la
    reponse — meme si un autre levier offrirait un gain moyen superieur.

    Sur une tenue homogene, aucun element ne se detache et cette prime vaut
    zero : les scenarios de reference restent inchanges.
    """
    element = MATERIALISED_ELEMENT[action]
    if element is None:
        return 0.0

    suitability = {
        candidate: value
        for candidate, value in context.appearance.element_suitability.items()
        if candidate in context.appearance.present_elements
    }
    if len(suitability) < 2 or element not in suitability:
        return 0.0

    peers = [value for candidate, value in suitability.items() if candidate is not element]
    shortfall = (sum(peers) / len(peers)) - suitability[element]
    if shortfall < ANOMALY_MARGIN:
        return 0.0

    # Proportionnelle a l'ecart, plafonnee : un ecart enorme ne doit pas
    # ecraser le reste du raisonnement.
    return ANOMALY_BONUS * clamp(shortfall / 0.35)


def score_candidate(context: DecisionContext, action: ChangeAction) -> ScoredCandidate:
    features = compute_features(context, action)
    lift = anomaly_lift(context, action)
    return ScoredCandidate(
        action=action,
        score=round((raw_score(features) + lift) * 100.0, 2),
        features=features,
        simplicity=SIMPLICITY[action],
        projected_dimensions=projected_dimensions(context, action),
        repairs_anomaly=lift > 0.0,
    )


def score_all(context: DecisionContext, actions: list[ChangeAction]) -> list[ScoredCandidate]:
    return [score_candidate(context, action) for action in actions]


def contribution_breakdown(features: CandidateFeatures) -> dict[str, float]:
    """Contribution ponderee de chaque feature -> sert a expliquer la decision."""
    values = features.as_dict()
    return {name: round(SCORE_WEIGHTS[name] * values[name], 4) for name in SCORE_WEIGHTS}
