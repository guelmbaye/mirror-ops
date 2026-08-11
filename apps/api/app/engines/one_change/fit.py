"""Adequation contextuelle : le look convient-il au moment ?

C'est la question que le positionnement place AVANT le changement :

    MOMENT → CURRENT LOOK → CONTEXTUAL FIT → FIT / MISMATCH → ONE CHANGE

Le moteur ne demandait jusqu'ici que « quel est le meilleur levier ? ». Il
repond desormais d'abord a « ce look va-t-il ici ? », et ce n'est pas la meme
question : un look excellent dans l'absolu peut etre un contresens pour
l'occasion, et un look modeste peut convenir parfaitement.

Trois etats, dans le vocabulaire du produit :

    FIT           You're good to go.
    ALMOST_THERE  Ca convient, mais un element tire l'ensemble vers le bas.
    MISMATCH      L'ecart au moment est net.

`ALMOST_THERE` est l'etat de la demonstration de reference : « votre tenue
convient a l'occasion, mais les baskets font baisser le niveau de formalite ».
Il nomme donc l'element fautif et la raison — sans quoi ce n'est qu'un score.
"""

from __future__ import annotations

from app.engines.one_change.tables import (
    OCCASION_TARGET_FORMALITY,
    OCCASION_VECTORS,
    POTENTIAL_CEILING,
)
from app.engines.one_change.types import (
    DecisionContext,
    FitAssessment,
    FitState,
    clamp,
)
from app.models.enums import ELEMENT_LABEL, OutfitElement

#: Au-dessus : le look va. En dessous du second seuil : l'ecart est net.
FIT_THRESHOLD = 0.72
MISMATCH_THRESHOLD = 0.58

#: Un element est « en cause » quand il est nettement sous le reste de la tenue.
WEAK_ELEMENT_MARGIN = 0.10


def assess_fit(context: DecisionContext, action=None) -> FitAssessment:
    """Verdict d'adequation, reconcilie avec la decision.

    Le score mesure l'adequation du look au moment ; l'action dit ce qui vaut
    la peine d'etre fait. Les deux s'affichent l'un sous l'autre : ils ne
    peuvent pas se contredire. « You're good to go » suivi de « Change the
    jacket » detruit la credibilite du produit en une ligne.

    La regle est donc : FIT si et seulement si rien n'est a changer.
    """
    appearance = context.appearance
    occasion = context.moment.occasion
    weights = OCCASION_VECTORS[occasion]

    # Le score d'adequation est la projection du look sur ce que cette occasion
    # demande — pas une note de qualite absolue.
    score = sum(weights[dimension] * appearance.dimensions.get(dimension, 0.0) for dimension in weights)
    score = clamp(score)

    weakest, gap = _weakest_element(context)

    # Ne nommer un coupable que s'il se detache reellement. Quand toutes les
    # pieces sont a egalite — cas d'une tenue non decrite — designer « le bas »
    # serait une invention, et le produit s'interdit d'inventer ce qu'il n'a pas
    # observe.
    if gap < WEAK_ELEMENT_MARGIN:
        weakest = None

    from app.models.enums import ChangeAction

    nothing_to_do = action is None or action is ChangeAction.NO_CHANGE

    if nothing_to_do:
        # Rien a changer. Reste a savoir si c'est parce que le look convient,
        # ou parce qu'aucune intervention ne valait la peine malgre tout.
        state = FitState.FIT if score >= FIT_THRESHOLD else FitState.ALMOST_THERE
    elif score >= MISMATCH_THRESHOLD:
        state = FitState.ALMOST_THERE
    else:
        state = FitState.MISMATCH

    return FitAssessment(
        state=state,
        score=round(score * 100),
        headline=_headline(state, nothing_to_do),
        detail=_detail(state, context, weakest, nothing_to_do),
        weakest_element=str(weakest) if weakest else None,
    )


def _weakest_element(context: DecisionContext) -> tuple[OutfitElement | None, float]:
    """L'element le plus en retrait par rapport au reste de la tenue."""
    suitability = {
        element: value
        for element, value in context.appearance.element_suitability.items()
        if element in context.appearance.present_elements
    }
    if len(suitability) < 2:
        return None, 0.0

    weakest = min(suitability, key=lambda element: suitability[element])
    others = [value for element, value in suitability.items() if element is not weakest]
    average = sum(others) / len(others)
    return weakest, max(0.0, average - suitability[weakest])


def _headline(state: FitState, nothing_to_do: bool) -> str:
    if state is FitState.FIT:
        return "You're good to go."
    if state is FitState.ALMOST_THERE and nothing_to_do:
        # Le look n'est pas parfait, mais rien ne vaut la peine d'etre change :
        # le dire franchement plutot que de promettre « good to go ».
        return "Close enough."
    if state is FitState.ALMOST_THERE:
        return "Almost there."
    return "This doesn't fit the moment."


def _detail(
    state: FitState,
    context: DecisionContext,
    weakest: OutfitElement | None,
    nothing_to_do: bool = False,
) -> str:
    occasion = _with_article(str(context.moment.occasion).replace("_", " "))
    target = OCCASION_TARGET_FORMALITY.get(context.moment.occasion, 0.6)

    if state is FitState.FIT:
        return f"Your look already matches what {occasion} calls for."

    if nothing_to_do:
        return (
            f"It isn't perfect for {occasion}, but nothing here is worth changing "
            "right now."
        )

    if weakest is None:
        # Aucun element ne se detache : on le dit ainsi, sans designer personne.
        if state is FitState.ALMOST_THERE:
            return (
                f"Nothing is off, but the whole look sits a little below what "
                f"{occasion} calls for."
            )
        return f"As a whole, this look sits below what {occasion} calls for."

    label = ELEMENT_LABEL.get(weakest, str(weakest)).lower()
    # « the shoes reduce » mais « the jacket reduces » : une faute d'accord dans
    # la phrase centrale du produit couterait plus cher que sa correction.
    plural = weakest in (OutfitElement.SHOES, OutfitElement.ACCESSORIES)
    ceiling = POTENTIAL_CEILING.get(weakest, 0.85)
    if target >= 0.65:
        direction = "reduce" if plural else "reduces"
        direction += " the level of formality"
    else:
        direction = "make" if plural else "makes"
        direction += " the whole look feel stiffer than it needs to be"

    if state is FitState.ALMOST_THERE:
        return (
            f"Your outfit fits the occasion, but the {label} {direction}."
            if ceiling
            else f"The {label} is what holds this look back."
        )
    return f"For {occasion}, the {label} is the clearest mismatch."


def _with_article(occasion: str) -> str:
    """« an interview », « a wedding » : une faute d'article se remarque."""
    return f"{'an' if occasion[:1] in 'aeiou' else 'a'} {occasion}"
