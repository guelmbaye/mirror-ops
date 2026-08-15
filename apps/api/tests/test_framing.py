"""Le produit ne decide que sur ce qu'il peut prouver.

MIRROR OPS promet trois choses : decider, expliquer, PROUVER. Recommander
« replace the shoes » sur un cliche qui s'arrete au ventre produit un
before/after ou rien ne bouge : la promesse se casse en silence, au moment ou
elle compte le plus.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.engines.appearance.estimator import (
    ImageQuality,
    build_appearance_signals,
    default_outfit,
)
from app.engines.one_change import (
    DecisionContext,
    MomentSpec,
    OutfitItem,
    SkinObservations,
    default_engine,
)
from app.models.enums import ChangeAction, Goal, MATERIALISED_ELEMENT, Occasion, OutfitElement, TimeAvailable
from app.services.framing import (
    FACE_RATIO_THRESHOLDS,
    VISIBLE_ELEMENTS,
    Framing,
    estimate_framing,
)


def dressed(level: float = 0.85):
    return {
        element: OutfitItem(present=True, known=True, formality=level, structure=level,
                            color_harmony=0.55, condition=0.70)
        for element in OutfitElement
    }


def decide(visible, occasion=Occasion.INTERVIEW, goal=Goal.PROFESSIONAL):
    moment = MomentSpec(occasion, goal, TimeAvailable.FROM_15_TO_30M)
    signals = build_appearance_signals(
        moment, dressed(), SkinObservations(available=False), ImageQuality(score=0.85),
        visible_elements=visible,
    )
    return default_engine.evaluate(DecisionContext(moment, signals))


# ---------------------------------------------------------------- le cadrage
def test_the_visibility_ladder_only_ever_grows():
    """Un cadrage plus large ne peut pas montrer MOINS de choses."""
    order = [Framing.HEAD, Framing.CHEST, Framing.WAIST, Framing.KNEE, Framing.FULL]
    for tighter, wider in zip(order, order[1:]):
        assert VISIBLE_ELEMENTS[tighter] <= VISIBLE_ELEMENTS[wider]
    assert VISIBLE_ELEMENTS[Framing.FULL] == frozenset(OutfitElement)


def test_an_unreadable_photo_restricts_nothing():
    """Sans visage detecte, mieux vaut ne rien affirmer qu'ecarter a tort."""
    assert VISIBLE_ELEMENTS[Framing.UNKNOWN] == frozenset(OutfitElement)

    buffer = io.BytesIO()
    Image.new("RGB", (900, 1200), (130, 120, 115)).save(buffer, format="JPEG")
    estimate = estimate_framing(buffer.getvalue())
    assert estimate.framing is Framing.UNKNOWN
    assert estimate.visible == frozenset(OutfitElement)


def test_thresholds_are_ordered():
    ratios = [ratio for ratio, _ in FACE_RATIO_THRESHOLDS]
    assert ratios == sorted(ratios, reverse=True)


# ------------------------------------------------------------- la decision
def test_a_piece_out_of_frame_is_never_recommended():
    """Le cas signale : chaussures cochees, photo coupee au ventre."""
    upper = {OutfitElement.TOP, OutfitElement.JACKET, OutfitElement.ACCESSORIES}
    outcome = decide(upper)

    touched = MATERIALISED_ELEMENT[outcome.action]
    assert touched is None or touched in upper


@pytest.mark.parametrize("framing", [Framing.HEAD, Framing.CHEST, Framing.KNEE, Framing.FULL])
def test_the_decision_stays_within_what_the_photo_shows(framing):
    visible = set(VISIBLE_ELEMENTS[framing])
    for occasion, goal in [(Occasion.INTERVIEW, Goal.PROFESSIONAL),
                           (Occasion.WEDDING, Goal.ELEGANT),
                           (Occasion.TRAVEL, Goal.APPROACHABLE)]:
        outcome = decide(visible, occasion, goal)
        touched = MATERIALISED_ELEMENT[outcome.action]
        assert touched is None or touched in visible, (
            f"{framing}: recommends {outcome.action}, photo shows {sorted(map(str, visible))}"
        )


def test_the_engine_still_decides_on_a_tight_shot():
    """Restreindre ne doit pas paralyser : une decision reste possible."""
    outcome = decide({OutfitElement.TOP, OutfitElement.JACKET, OutfitElement.ACCESSORIES})
    assert outcome.action in set(ChangeAction)
    assert outcome.fit is not None


def test_no_restriction_when_visibility_is_unknown():
    """`None` signifie « on ne sait pas » : le moteur garde tous ses leviers."""
    moment = MomentSpec(Occasion.INTERVIEW, Goal.PROFESSIONAL, TimeAvailable.OVER_30M)
    signals = build_appearance_signals(
        moment, dressed(0.25), SkinObservations(available=False), ImageQuality(score=0.85)
    )
    assert signals.visible_elements is None
    assert default_engine.evaluate(DecisionContext(moment, signals)).action
