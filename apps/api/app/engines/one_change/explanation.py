"""Moteur d'explication deterministe (Doc 04 §18, Doc 06 §17/§18).

Contrainte forte : l'explication doit refleter le calcul reel.
"Ne jamais generer une justification generique independante du calcul."
Aucun LLM requis.
"""

from __future__ import annotations

from app.engines.one_change.scorer import contribution_breakdown
from app.engines.one_change.tables import CHANGE_ACTIONS, OCCASION_TARGET_FORMALITY
from app.engines.one_change.types import DecisionContext, Explanation, ScoredCandidate
from app.models.enums import (
    ACTION_ELEMENT,
    OutfitElement,
    ELEMENT_LABEL,
    MATERIALISED_ELEMENT,
    ACTION_LABEL,
    ACTION_LABEL_ADD,
    ChangeAction,
    Goal,
)

GOAL_PHRASE: dict[Goal, str] = {
    Goal.PROFESSIONAL: "professional presence",
    Goal.CONFIDENT: "visual confidence",
    Goal.APPROACHABLE: "approachability",
    Goal.ELEGANT: "elegance",
    Goal.EXPRESSIVE: "personal expression",
}

FACTOR_PHRASE: dict[str, str] = {
    "goal_alignment": "it is the lever most aligned with your goal",
    "context_fit": "it fits what this occasion calls for",
    "visual_impact": "it is the change people will actually notice",
    "current_gap": "it is where your look has the most room to improve",
    "time_fit": "it is realistic in the time you have",
    "data_confidence": "it is the element we can read most reliably",
    "vto_feasibility": "it can be shown to you before you commit",
}

ELEMENT_NOUN: dict[ChangeAction, str] = {
    ChangeAction.CHANGE_JACKET: "jacket",
    ChangeAction.CHANGE_TOP: "top",
    ChangeAction.CHANGE_BOTTOM: "bottom",
    ChangeAction.CHANGE_SHOES: "shoes",
    ChangeAction.CHANGE_ACCESSORY: "accessory",
    ChangeAction.CHANGE_COLOR: "colour balance",
    # « Removing the accessory offers the highest expected improvement… »
    ChangeAction.REMOVE_ACCESSORY: "accessory you're wearing",
}

#: Completude : une action evaluee sans nom fait planter l'explication.
_MISSING_NOUNS = [a for a in CHANGE_ACTIONS if a not in ELEMENT_NOUN]
if _MISSING_NOUNS:  # pragma: no cover - defaut de configuration
    raise RuntimeError(f"ELEMENT_NOUN is missing: {[str(a) for a in _MISSING_NOUNS]}")


def dominant_factors(winner: ScoredCandidate, limit: int = 2) -> list[str]:
    """Les features qui ont reellement porte le score du gagnant."""
    contributions = contribution_breakdown(winner.features)
    ranked = sorted(contributions.items(), key=lambda kv: (-kv[1], kv[0]))
    return [name for name, _ in ranked[:limit]]


def keep_list(context: DecisionContext, action: ChangeAction) -> list[str]:
    # On retire l'element reellement touche, pas seulement celui que l'action
    # nomme : sinon « Keep · Top » cohabite avec un apercu qui change le haut.
    element = MATERIALISED_ELEMENT[action]
    kept = [str(e) for e in sorted(context.appearance.present_elements, key=lambda e: str(e))]
    if element is not None:
        kept = [e for e in kept if e != str(element)]
    return kept


#: Ecart minimal a la cible pour parler de sens. En deca, « changez » suffit :
#: le probleme n'est pas le niveau, c'est la piece elle-meme.
DIRECTION_MARGIN = 0.12


def _direction(context: DecisionContext, action: ChangeAction) -> str | None:
    """Dans quel SENS changer la piece.

    « Change the jacket » disait exactement la meme chose a quelqu'un
    sous-habille pour un entretien et a quelqu'un sur-habille pour un voyage.
    Deux situations opposees, une seule phrase : l'utilisateur ne pouvait pas
    savoir s'il fallait monter ou descendre en formalite, et trois reglages
    differents rendaient un ecran identique.
    """
    element = MATERIALISED_ELEMENT[action]
    if element is None or element not in context.appearance.present_elements:
        return None

    target = OCCASION_TARGET_FORMALITY.get(context.moment.occasion)
    current = context.appearance.element_formality.get(element)
    if target is None or current is None:
        return None

    noun = ELEMENT_LABEL.get(element, str(element))
    plural = element in (OutfitElement.SHOES, OutfitElement.ACCESSORIES)
    verb = "are" if plural else "is"

    if current < target - DIRECTION_MARGIN:
        return (
            f"The {noun} {verb} more casual than this moment calls for. "
            "Keep the rest exactly as it is."
        )
    if current > target + DIRECTION_MARGIN:
        return (
            f"The {noun} {verb} dressier than this moment calls for. "
            "Keep the rest exactly as it is."
        )
    return None


def is_addition(context: DecisionContext, action: ChangeAction) -> bool:
    """La piece visee manque-t-elle ? Alors on l'ajoute, on ne la change pas."""
    element = ACTION_ELEMENT[action]
    return element is not None and element not in context.appearance.present_elements


def formality_shift(context: DecisionContext, action: ChangeAction) -> str | None:
    """`sharper`, `easier`, ou None quand le niveau n'est pas en cause."""
    element = MATERIALISED_ELEMENT[action]
    if element is None or element not in context.appearance.present_elements:
        return None

    target = OCCASION_TARGET_FORMALITY.get(context.moment.occasion)
    current = context.appearance.element_formality.get(element)
    if target is None or current is None:
        return None

    if current < target - DIRECTION_MARGIN:
        return "sharper"
    if current > target + DIRECTION_MARGIN:
        return "easier"
    return None


def label_for(context: DecisionContext, action: ChangeAction) -> str:
    """« Change the jacket » ou « Add a jacket », selon ce que la personne porte.

    Dire « change the jacket » a quelqu'un qui n'en porte pas est faux, et le
    produit perd sa credibilite dans la seconde qui suit.
    """
    if is_addition(context, action):
        return ACTION_LABEL_ADD.get(action, ACTION_LABEL[action])

    base = ACTION_LABEL[action]

    # Le SENS appartient au titre, pas a une ligne secondaire.
    #
    # « Change the jacket » disait exactement la meme chose a quelqu'un
    # sous-habille pour un entretien et a quelqu'un sur-habille pour un voyage.
    # Trois reglages d'habillement differents rendaient un titre identique, et
    # le produit paraissait insensible a ce qu'on lui disait.
    shift = formality_shift(context, action)
    if shift and action is not ChangeAction.CHANGE_COLOR:
        return f"{base} for something {shift}"
    return base


def build_explanation(
    context: DecisionContext,
    winner: ScoredCandidate,
    selection_reason: str,
) -> Explanation:
    goal_phrase = GOAL_PHRASE[context.moment.goal]

    if winner.action is ChangeAction.NO_CHANGE:
        return _no_change_explanation(context, goal_phrase, selection_reason)

    noun = ELEMENT_NOUN[winner.action]
    factors = dominant_factors(winner)
    primary = FACTOR_PHRASE[factors[0]]
    secondary = FACTOR_PHRASE[factors[1]] if len(factors) > 1 else None

    what = label_for(context, winner.action) + "."
    why = (
        f"Among the changes available to you right now, the {noun} offers the highest "
        f"expected improvement for {goal_phrase} — {primary}"
        + (f", and {secondary}." if secondary else ".")
    )
    how = _direction(context, winner.action) or "Keep the rest of your look exactly as it is."
    reason = (
        f"{label_for(context, winner.action)} because it offers the highest expected improvement "
        f"for {goal_phrase} while keeping the rest of your look unchanged."
    )
    return Explanation(what=what, why=why, how=how, reason=reason, dominant_factors=factors)


def _no_change_explanation(
    context: DecisionContext, goal_phrase: str, selection_reason: str
) -> Explanation:
    occasion = str(context.moment.occasion)
    if selection_reason == "best_change_below_threshold":
        why = (
            "No available change scored high enough to be worth the effort right now. "
            f"Your look already carries enough {goal_phrase} for this {occasion}."
        )
    else:
        why = (
            f"Your current look already matches this {occasion}, and no single change "
            f"would add enough {goal_phrase} to justify it."
        )
    return Explanation(
        what="Don't change it.",
        why=why,
        how="Leave your look as it is and go.",
        reason="Your current look already fits the selected moment.",
        dominant_factors=["current_gap", "context_fit"],
    )
