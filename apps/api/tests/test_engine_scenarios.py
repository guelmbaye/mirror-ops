"""Scenarios obligatoires du moteur ONE CHANGE (Doc 04 §26, Doc 06 §26).

Ces tests s'executent SANS reseau, SANS YouCam, SANS base de donnees.
"""

from __future__ import annotations

import pytest

from app.engines.appearance.estimator import (
    ImageQuality,
    build_appearance_signals,
    default_outfit,
)
from app.engines.one_change import (
    DecisionContext,
    EngineConfig,
    InsufficientDataError,
    MomentSpec,
    OneChangeEngine,
    OutfitItem,
    SkinObservations,
    ThresholdPolicy,
    default_engine,
)
from app.models.enums import ChangeAction, Goal, Occasion, OutfitElement, TimeAvailable

SKIN = SkinObservations(
    texture=0.42, redness=0.31, oiliness=0.64, radiance=0.55, available=True, source="test"
)


def context(
    occasion=Occasion.PRESENTATION,
    goal=Goal.PROFESSIONAL,
    time=TimeAvailable.UNDER_5M,
    outfit=None,
    skin=SKIN,
    image_score=0.78,
) -> DecisionContext:
    moment = MomentSpec(occasion, goal, time)
    signals = build_appearance_signals(
        moment, outfit or default_outfit(), skin, ImageQuality(score=image_score)
    )
    return DecisionContext(moment, signals)


def uniform_outfit(**overrides) -> dict[OutfitElement, OutfitItem]:
    base = {
        element: OutfitItem(
            present=True, known=True, formality=0.80, structure=0.80,
            color_harmony=0.80, condition=0.85,
        )
        for element in OutfitElement
    }
    base.update(overrides)
    return base


def scores(outcome) -> dict[str, float]:
    return {str(c.action): c.score for c in outcome.candidates}


# --------------------------------------------------------------------------- #
# Scenario A — Presentation + Professional + <5 min -> changement structurant
# --------------------------------------------------------------------------- #
def test_scenario_a_presentation_professional_short_time_picks_jacket():
    outcome = default_engine.evaluate(context())
    assert outcome.action is ChangeAction.CHANGE_JACKET
    assert outcome.score >= 60
    assert outcome.requires_vto is True
    assert "jacket" not in outcome.keep


# --------------------------------------------------------------------------- #
# Scenario B — Date + Approachable -> changement contextuellement pertinent
# --------------------------------------------------------------------------- #
def test_scenario_b_date_approachable_picks_context_appropriate_change():
    outcome = default_engine.evaluate(
        context(Occasion.DATE, Goal.APPROACHABLE, TimeAvailable.FROM_5_TO_15M)
    )
    assert outcome.action in {
        ChangeAction.CHANGE_TOP,
        ChangeAction.CHANGE_COLOR,
        ChangeAction.CHANGE_ACCESSORY,
    }
    # Un blazer structure n'est pas la reponse par defaut d'un diner
    assert outcome.action is not ChangeAction.CHANGE_BOTTOM


# --------------------------------------------------------------------------- #
# Scenario C — Event + Elegant + 30+ min -> changement a fort impact
# --------------------------------------------------------------------------- #
def test_scenario_c_event_elegant_allows_high_impact_change():
    outcome = default_engine.evaluate(
        context(Occasion.EVENT, Goal.ELEGANT, TimeAvailable.OVER_30M)
    )
    assert outcome.action is not ChangeAction.NO_CHANGE
    assert outcome.winner.features.visual_impact >= 0.4


# --------------------------------------------------------------------------- #
# Scenario D — Look deja fort -> NO_CHANGE
# --------------------------------------------------------------------------- #
def test_scenario_d_strong_look_returns_no_change():
    strong = uniform_outfit(
        **{
            element: OutfitItem(
                present=True, known=True, formality=0.82, structure=0.88,
                color_harmony=0.86, condition=0.92,
            )
            for element in OutfitElement
        }
    )
    outcome = default_engine.evaluate(
        context(outfit=strong, time=TimeAvailable.FROM_15_TO_30M, image_score=0.9)
    )
    assert outcome.action is ChangeAction.NO_CHANGE
    assert outcome.requires_vto is False
    assert "Don't change it." == outcome.explanation.what


# --------------------------------------------------------------------------- #
# Scenario E — Donnees insuffisantes -> demander une meilleure photo
# --------------------------------------------------------------------------- #
def test_scenario_e_poor_data_requests_better_input():
    poor = context(image_score=0.05)
    with pytest.raises(InsufficientDataError):
        default_engine.evaluate(poor)


def test_no_outfit_element_raises():
    moment = MomentSpec(Occasion.PRESENTATION, Goal.PROFESSIONAL, TimeAvailable.UNDER_5M)
    outfit = {element: OutfitItem(present=False) for element in OutfitElement}
    signals = build_appearance_signals(moment, outfit, SKIN, ImageQuality(score=0.9))
    with pytest.raises(InsufficientDataError):
        default_engine.evaluate(DecisionContext(moment, signals))


# --------------------------------------------------------------------------- #
# Comportements transverses
# --------------------------------------------------------------------------- #
def test_weak_jacket_makes_jacket_candidate_rise():
    weak = uniform_outfit(
        **{
            OutfitElement.JACKET: OutfitItem(
                present=True, known=True, formality=0.25, structure=0.30,
                color_harmony=0.40, condition=0.60,
            )
        }
    )
    strong_jacket = uniform_outfit()
    weak_score = scores(default_engine.evaluate(context(outfit=weak)))["CHANGE_JACKET"]
    strong_score = scores(default_engine.evaluate(context(outfit=strong_jacket)))["CHANGE_JACKET"]
    assert weak_score > strong_score


def test_short_time_favours_low_effort_changes():
    long_time = scores(default_engine.evaluate(context(time=TimeAvailable.OVER_30M)))
    short_time = scores(default_engine.evaluate(context(time=TimeAvailable.UNDER_5M)))
    # Le haut (effort eleve) recule, l'accessoire (effort faible) progresse
    assert short_time["CHANGE_TOP"] < long_time["CHANGE_TOP"]
    assert short_time["CHANGE_ACCESSORY"] >= long_time["CHANGE_ACCESSORY"]


def test_bottom_is_filtered_when_time_is_very_short():
    short = scores(default_engine.evaluate(context(time=TimeAvailable.UNDER_5M)))
    assert "CHANGE_BOTTOM" not in short
    longer = scores(default_engine.evaluate(context(time=TimeAvailable.OVER_30M)))
    assert "CHANGE_BOTTOM" in longer


def test_a_missing_jacket_becomes_an_addition_not_a_change():
    """Une veste absente n'est pas une impasse : c'est peut-etre LE levier.

    Ce qui serait faux, c'est de dire « change the jacket » a quelqu'un qui n'en
    porte pas. Le libelle suit donc la realite.
    """
    outfit = default_outfit()
    outfit[OutfitElement.JACKET] = OutfitItem(present=False)
    outcome = default_engine.evaluate(context(outfit=outfit))

    assert "CHANGE_JACKET" in scores(outcome)
    if outcome.action is ChangeAction.CHANGE_JACKET:
        assert outcome.label == "Add a jacket"
        assert outcome.explanation.what == "Add a jacket."
        assert "change the jacket" not in outcome.explanation.why.lower()


def test_a_missing_bottom_is_still_removed():
    """On n'« ajoute » pas un bas : son absence signifie qu'on ne le voit pas."""
    outfit = default_outfit()
    outfit[OutfitElement.BOTTOM] = OutfitItem(present=False)
    outcome = default_engine.evaluate(context(outfit=outfit, time=TimeAvailable.OVER_30M))
    assert "CHANGE_BOTTOM" not in scores(outcome)


def test_a_present_jacket_is_still_a_change():
    outfit = default_outfit()
    outfit[OutfitElement.JACKET] = OutfitItem(present=True, known=True, formality=0.2)
    outcome = default_engine.evaluate(context(outfit=outfit))
    if outcome.action is ChangeAction.CHANGE_JACKET:
        # Le libelle porte desormais le SENS quand le niveau est en cause :
        # « for something sharper » / « for something easier ».
        assert outcome.label.startswith("Change the jacket")


def test_engine_is_deterministic():
    first = default_engine.evaluate(context())
    second = default_engine.evaluate(context())
    assert first.action == second.action
    assert first.score == second.score
    assert first.confidence_value == second.confidence_value


def test_engine_returns_exactly_one_action_with_a_reason():
    outcome = default_engine.evaluate(context())
    assert isinstance(outcome.action, ChangeAction)
    assert outcome.explanation.reason
    assert outcome.explanation.dominant_factors
    assert outcome.label


def test_threshold_can_force_no_change():
    strict = OneChangeEngine(
        EngineConfig(threshold=ThresholdPolicy(min_recommendation_score=99.0))
    )
    outcome = strict.evaluate(context())
    assert outcome.action is ChangeAction.NO_CHANGE


def test_explanation_matches_dominant_factors():
    outcome = default_engine.evaluate(context())
    contributions = outcome.winner.features.as_dict()
    top = outcome.explanation.dominant_factors[0]
    assert top in contributions


def test_impact_projection_improves_targeted_dimension():
    weak = uniform_outfit(
        **{
            OutfitElement.JACKET: OutfitItem(
                present=True, known=True, formality=0.25, structure=0.30,
                color_harmony=0.40, condition=0.60,
            )
        }
    )
    outcome = default_engine.evaluate(context(outfit=weak))
    assert outcome.action is ChangeAction.CHANGE_JACKET
    assert outcome.impact_after["professional_presence"] > outcome.impact_before["professional_presence"]


def test_skin_signal_never_hijacks_the_decision():
    """Une peau tres brillante ne doit pas transformer le produit en skin coach."""
    calm = context(skin=SkinObservations(redness=0.2, oiliness=0.2, texture=0.2, available=True))
    flagged = context(
        skin=SkinObservations(redness=0.95, oiliness=0.95, texture=0.95, available=True)
    )
    assert default_engine.evaluate(calm).action == default_engine.evaluate(flagged).action
