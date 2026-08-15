"""Toute action declaree doit etre reellement evaluable.

`REMOVE_ACCESSORY` existait dans l'enumeration, dans les libelles, dans le
positionnement et dans ses propres tests — mais pas dans `CHANGE_ACTIONS`. Le
moteur ne l'a donc jamais evaluee, et rien ne l'a signale : une action absente
de la liste ne provoque aucune erreur, elle disparait simplement.

Un balayage exhaustif l'a revele (0 occurrence sur 43 200 decisions). La lecture
du code ne l'avait pas vu, et aucun test unitaire non plus, parce que chacun
verifiait l'action isolement.
"""

from __future__ import annotations

import pytest

from app.engines.appearance.estimator import ImageQuality, build_appearance_signals
from app.engines.one_change import (
    DecisionContext,
    MomentSpec,
    OutfitItem,
    SkinObservations,
    default_engine,
)
from app.engines.one_change.explanation import ELEMENT_NOUN
from app.engines.one_change.tables import (
    CAPABILITY,
    CHANGE_ACTIONS,
    CONTEXT_FIT,
    SIMPLICITY,
    TIME_FIT,
    VISIBILITY,
    VTO_FEASIBILITY,
)
from app.models.enums import (
    ACTION_ELEMENT,
    ACTION_LABEL,
    MATERIALISED_ELEMENT,
    ChangeAction,
    Goal,
    Occasion,
    OutfitElement,
    TimeAvailable,
)


def test_every_declared_action_is_actually_evaluated():
    """L'enumeration et l'espace de decision ne doivent pas diverger."""
    declared = {action for action in ChangeAction if action is not ChangeAction.NO_CHANGE}
    evaluated = set(CHANGE_ACTIONS)
    assert declared == evaluated, (
        f"declared but never evaluated: {[str(a) for a in declared - evaluated]}"
    )


@pytest.mark.parametrize("action", list(CHANGE_ACTIONS))
def test_every_evaluated_action_has_every_table_entry(action):
    """Une entree manquante fait planter le moteur, ou l'action disparait."""
    for name, table in (("CAPABILITY", CAPABILITY), ("VISIBILITY", VISIBILITY),
                        ("SIMPLICITY", SIMPLICITY), ("VTO_FEASIBILITY", VTO_FEASIBILITY),
                        ("ACTION_ELEMENT", ACTION_ELEMENT), ("ACTION_LABEL", ACTION_LABEL),
                        ("MATERIALISED_ELEMENT", MATERIALISED_ELEMENT),
                        ("ELEMENT_NOUN", ELEMENT_NOUN)):
        assert action in table, f"{name} has no entry for {action}"

    for occasion, levels in CONTEXT_FIT.items():
        assert action in levels, f"CONTEXT_FIT[{occasion}] has no entry for {action}"
    for time, levels in TIME_FIT.items():
        assert action in levels, f"TIME_FIT[{time}] has no entry for {action}"


def test_every_action_can_win_at_least_once():
    """Une action qui ne gagne jamais est du code mort qui se croit vivant.

    Ce test balaie un espace reduit mais representatif : si une action declaree
    n'y apparait pas une seule fois, elle est soit inaccessible, soit inutile —
    les deux meritent qu'on s'en apercoive.
    """
    winners: set[ChangeAction] = set()

    for occasion in Occasion:
        for goal in Goal:
            for time in (TimeAvailable.UNDER_5M, TimeAvailable.OVER_30M):
                for level in (0.15, 0.5, 0.9):
                    for odd in (None, *OutfitElement):
                        outfit = {}
                        for element in OutfitElement:
                            value = 0.05 if element is odd else level
                            outfit[element] = OutfitItem(
                                present=True, known=True, formality=value,
                                structure=value,
                                color_harmony=0.15 if element is odd else 0.85,
                                condition=0.9,
                            )
                        moment = MomentSpec(occasion, goal, time)
                        signals = build_appearance_signals(
                            moment, outfit, SkinObservations(available=False),
                            ImageQuality(score=0.9),
                        )
                        winners.add(default_engine.evaluate(DecisionContext(moment, signals)).action)

    never = set(CHANGE_ACTIONS) - winners
    assert not never, f"never chosen anywhere: {[str(a) for a in never]}"


def test_removing_an_accessory_needs_no_try_on():
    """On ne prouve pas une soustraction avec un catalogue de vetements."""
    assert VTO_FEASIBILITY[ChangeAction.REMOVE_ACCESSORY] == 0.0
    assert ACTION_LABEL[ChangeAction.REMOVE_ACCESSORY] == "Remove the accessory"
