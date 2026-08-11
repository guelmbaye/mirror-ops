"""Calcul des features par candidat (Doc 06 §8). Toutes normalisees 0..1."""

from __future__ import annotations

from app.engines.one_change.contexts import (
    blended_priority_vector,
    goal_vector,
    occasion_vector,
    weighted_fit,
)
from app.engines.one_change.tables import (
    CAPABILITY,
    CONTEXT_FIT,
    NO_CHANGE_SHARPNESS,
    POTENTIAL_CEILING,
    TIME_FIT,
    VISIBILITY,
    VTO_FEASIBILITY,
)
from app.engines.one_change.types import (
    DIMENSIONS,
    CandidateFeatures,
    DecisionContext,
    clamp,
)
from app.models.enums import ACTION_ELEMENT, ChangeAction, OutfitElement


def element_gap(context: DecisionContext, element: OutfitElement) -> float:
    """Marge de progression realiste sur une piece (0..1)."""
    current = context.appearance.element_suitability.get(element, 0.55)
    ceiling = POTENTIAL_CEILING[element]
    return clamp(ceiling - current)


def best_available_gap(context: DecisionContext) -> float:
    gaps = [element_gap(context, e) for e in context.appearance.present_elements]
    return max(gaps) if gaps else 0.0


def color_gap(context: DecisionContext) -> float:
    """Le travail couleur agit sur la coherence globale, pas sur une piece."""
    coherence = context.appearance.dimensions.get("visual_coherence", 0.55)
    return clamp(0.90 - coherence)


def element_data_confidence(context: DecisionContext, element: OutfitElement | None) -> float:
    base = context.appearance.data_confidence
    if element is None:
        return base
    known = context.appearance.element_known.get(element, False)
    return clamp(base * (1.0 if known else 0.82))


def compute_features(context: DecisionContext, action: ChangeAction) -> CandidateFeatures:
    if action is ChangeAction.NO_CHANGE:
        return _no_change_features(context)

    moment = context.moment
    element = ACTION_ELEMENT[action]
    capability = CAPABILITY[action]
    goal = goal_vector(moment)

    goal_alignment = clamp(sum(goal.get(d, 0.0) * capability.get(d, 0.0) for d in DIMENSIONS))
    context_fit = CONTEXT_FIT[moment.occasion][action]
    gap = color_gap(context) if element is None else element_gap(context, element)
    visual_impact = clamp(VISIBILITY[action] * (0.5 + 0.5 * gap))
    time_fit = TIME_FIT[moment.time_available][action]
    data_confidence = element_data_confidence(context, element)
    vto_feasibility = VTO_FEASIBILITY[action]

    return CandidateFeatures(
        goal_alignment=goal_alignment,
        context_fit=context_fit,
        visual_impact=visual_impact,
        current_gap=gap,
        time_fit=time_fit,
        data_confidence=data_confidence,
        vto_feasibility=vto_feasibility,
    )


def _no_change_features(context: DecisionContext) -> CandidateFeatures:
    """NO_CHANGE marque des points quand la tenue actuelle est deja alignee.

    Doc 06 §16 : "NO_CHANGE est un veritable candidat", pas un fallback technique.
    """
    dims = context.appearance.dimensions
    current_goal_fit = weighted_fit(dims, goal_vector(context.moment))
    current_context_fit = weighted_fit(dims, occasion_vector(context.moment))
    remaining_gap = best_available_gap(context)

    # Durcissement convexe : "ne rien changer" doit se meriter.
    sharp_goal = clamp(current_goal_fit ** NO_CHANGE_SHARPNESS)
    sharp_context = clamp(current_context_fit ** NO_CHANGE_SHARPNESS)

    return CandidateFeatures(
        goal_alignment=sharp_goal,
        context_fit=sharp_context,
        visual_impact=sharp_goal,
        current_gap=clamp(1.0 - remaining_gap),
        time_fit=1.0,
        data_confidence=context.appearance.data_confidence,
        vto_feasibility=1.0,
    )


def projected_dimensions(context: DecisionContext, action: ChangeAction) -> dict[str, float]:
    """Projection de l'etat d'apparence apres le changement (heuristique explicable)."""
    current = context.appearance.dimensions
    if action is ChangeAction.NO_CHANGE:
        return dict(current)

    element = ACTION_ELEMENT[action]
    gap = color_gap(context) if element is None else element_gap(context, element)
    capability = CAPABILITY[action]
    priority = blended_priority_vector(context.moment)

    projected: dict[str, float] = {}
    for dimension in DIMENSIONS:
        headroom = 1.0 - current.get(dimension, 0.0)
        lift = capability.get(dimension, 0.0) * gap * (0.55 + 0.45 * priority.get(dimension, 0.0))
        projected[dimension] = clamp(current.get(dimension, 0.0) + lift * headroom * 1.6)
    return projected
