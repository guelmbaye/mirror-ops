"""Generation et filtrage des candidats (Doc 06 §7).

Espace de decision ferme et volontairement petit : plus fiable, plus testable
(Doc 04 §4 : "Le moteur ne doit pas generer de nouvelles categories dynamiquement").
"""

from __future__ import annotations

from dataclasses import dataclass

from app.engines.one_change.tables import CHANGE_ACTIONS, TIME_INFEASIBLE
from app.engines.one_change.types import DecisionContext
from app.models.enums import ADDABLE_ELEMENTS, ACTION_ELEMENT, ChangeAction, OutfitElement


@dataclass(frozen=True, slots=True)
class FilteredCandidate:
    action: ChangeAction
    reason: str


def generate_candidates(context: DecisionContext) -> tuple[list[ChangeAction], list[FilteredCandidate]]:
    """Retourne (candidats retenus, candidats ecartes + motif)."""
    kept: list[ChangeAction] = []
    dropped: list[FilteredCandidate] = []
    appearance = context.appearance
    infeasible = TIME_INFEASIBLE.get(context.moment.time_available, set())

    for action in CHANGE_ACTIONS:
        element: OutfitElement | None = ACTION_ELEMENT[action]

        if element is not None and element not in appearance.present_elements:
            # Une veste absente n'est pas une impasse : c'est peut-etre
            # l'intervention a plus forte valeur. On la garde comme AJOUT.
            if element not in ADDABLE_ELEMENTS:
                dropped.append(FilteredCandidate(action, "element_not_present"))
                continue

        if action in infeasible:
            dropped.append(FilteredCandidate(action, "not_feasible_in_available_time"))
            continue

        if action is ChangeAction.CHANGE_COLOR and len(appearance.present_elements) < 2:
            dropped.append(FilteredCandidate(action, "not_enough_elements_for_color_work"))
            continue

        kept.append(action)

    # NO_CHANGE est toujours un candidat legitime (Doc 06 §16).
    kept.append(ChangeAction.NO_CHANGE)
    return kept, dropped
