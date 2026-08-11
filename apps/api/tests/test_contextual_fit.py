"""Adequation contextuelle — le coeur du positionnement « Contextual ».

« MIRROR OPS ne demande pas si le look est objectivement bon. Il demande s'il
est approprie au moment. » Ces tests verifient que le moteur pose bien cette
question-la, et qu'aucune occasion ne le fait tomber.
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
    MomentSpec,
    OutfitItem,
    SkinObservations,
    default_engine,
)
from app.engines.one_change.fit import FIT_THRESHOLD, assess_fit
from app.engines.one_change.tables import (
    CAPABILITY,
    CONTEXT_FIT,
    OCCASION_TARGET_FORMALITY,
    OCCASION_VECTORS,
    SIMPLICITY,
    VISIBILITY,
    VTO_FEASIBILITY,
)
from app.models.enums import ChangeAction, Goal, Occasion, OutfitElement, TimeAvailable


def context(occasion, goal, outfit=None, quality=0.88, time=TimeAvailable.FROM_15_TO_30M):
    moment = MomentSpec(occasion, goal, time)
    signals = build_appearance_signals(
        moment, outfit or default_outfit(), SkinObservations(available=False), ImageQuality(score=quality)
    )
    return DecisionContext(moment, signals)


def fit_of(ctx, action=ChangeAction.CHANGE_JACKET):
    """Le verdict tel qu'il s'affiche AVEC une action : les deux se lisent ensemble."""
    return assess_fit(ctx, action)


def outfit_with(weak_element=None, level=0.20):
    items = {
        element: OutfitItem(
            present=True, known=True, formality=0.86, structure=0.88,
            color_harmony=0.86, condition=0.92,
        )
        for element in OutfitElement
    }
    if weak_element is not None:
        items[weak_element] = OutfitItem(
            present=True, known=True, formality=level, structure=level + 0.10,
            color_harmony=0.55, condition=0.80,
        )
    return items


# ------------------------------------------------------- toutes les occasions
@pytest.mark.parametrize("occasion", list(Occasion))
def test_every_occasion_produces_a_decision(occasion):
    """L'enumeration a deja ete etendue sans les tables : le moteur plantait."""
    outcome = default_engine.evaluate(context(occasion, Goal.PROFESSIONAL))
    assert outcome.action in set(ChangeAction)
    assert outcome.fit is not None


@pytest.mark.parametrize("occasion", list(Occasion))
def test_every_occasion_is_covered_by_every_table(occasion):
    assert occasion in OCCASION_VECTORS
    assert occasion in OCCASION_TARGET_FORMALITY
    assert occasion in CONTEXT_FIT
    assert pytest.approx(sum(OCCASION_VECTORS[occasion].values()), abs=1e-6) == 1.0


@pytest.mark.parametrize("action", [a for a in ChangeAction if a is not ChangeAction.NO_CHANGE])
def test_every_action_is_scorable(action):
    assert action in CAPABILITY
    assert action in VISIBILITY
    assert action in SIMPLICITY
    assert action in VTO_FEASIBILITY


# --------------------------------------------------------------- le verdict
def test_a_strong_look_fits_and_needs_nothing():
    outcome = default_engine.evaluate(
        context(Occasion.PRESENTATION, Goal.PROFESSIONAL, outfit_with(), 0.92)
    )
    assert outcome.fit.state == "FIT"
    assert outcome.fit.headline == "You're good to go."
    assert outcome.action is ChangeAction.NO_CHANGE


def test_the_golden_demo_scenario():
    """« Votre tenue convient, mais les baskets font baisser la formalite. »"""
    assessment = fit_of(
        context(Occasion.PRESENTATION, Goal.PROFESSIONAL, outfit_with(OutfitElement.SHOES), 0.92)
    )
    assert assessment.state == "ALMOST_THERE"
    assert assessment.headline == "Almost there."
    assert "shoes" in assessment.detail
    assert "formality" in assessment.detail
    assert assessment.weakest_element == "shoes"


def test_the_same_outfit_is_judged_differently_by_the_occasion():
    """Le meme look, deux moments : c'est toute la these du produit."""
    casual = outfit_with(OutfitElement.SHOES, level=0.15)
    interview = fit_of(context(Occasion.INTERVIEW, Goal.PROFESSIONAL, casual, 0.9))
    travel = fit_of(context(Occasion.TRAVEL, Goal.APPROACHABLE, casual, 0.9))
    assert travel.score != interview.score


def test_the_verdict_names_what_holds_the_look_back():
    for element in (OutfitElement.JACKET, OutfitElement.SHOES, OutfitElement.TOP):
        assessment = assess_fit(
            context(Occasion.BUSINESS, Goal.PROFESSIONAL, outfit_with(element), 0.9)
        )
        assert assessment.weakest_element == str(element)


def test_the_sentence_agrees_in_number():
    """« the shoes reduce » mais « the jacket reduces »."""
    plural = fit_of(context(Occasion.BUSINESS, Goal.PROFESSIONAL, outfit_with(OutfitElement.SHOES), 0.9))
    singular = fit_of(context(Occasion.BUSINESS, Goal.PROFESSIONAL, outfit_with(OutfitElement.JACKET), 0.9))
    assert "shoes reduce " in plural.detail
    assert "jacket reduces " in singular.detail


def test_the_score_is_a_percentage():
    assessment = fit_of(context(Occasion.DINNER, Goal.ELEGANT))
    assert 0 <= assessment.score <= 100


def test_fit_and_no_change_never_contradict_each_other():
    """Un ecran ne peut pas annoncer « good to go » puis exiger un changement."""
    for occasion in Occasion:
        for quality in (0.55, 0.75, 0.95):
            outcome = default_engine.evaluate(
                context(occasion, Goal.PROFESSIONAL, outfit_with(), quality)
            )
            if outcome.action is ChangeAction.NO_CHANGE:
                assert outcome.fit.state == "FIT"


# ---------------------------------------------------------------- retirer
def test_removing_an_accessory_is_a_real_option():
    """« Remove the accessory » figure explicitement dans le positionnement."""
    assert ChangeAction.REMOVE_ACCESSORY in CAPABILITY
    assert VTO_FEASIBILITY[ChangeAction.REMOVE_ACCESSORY] == 0.0


def test_removal_never_asks_for_a_try_on():
    """On ne prouve pas une soustraction avec un catalogue de vetements."""
    from app.engines.one_change.explanation import label_for

    ctx = context(Occasion.INTERVIEW, Goal.PROFESSIONAL)
    assert label_for(ctx, ChangeAction.REMOVE_ACCESSORY) == "Remove the accessory"


def test_no_culprit_is_named_when_none_stands_out():
    """Une tenue non decrite met toutes les pieces a egalite.

    Designer « le bas » dans ce cas serait une invention — exactement ce que le
    produit s'interdit ailleurs sur l'analyse de peau.
    """
    assessment = fit_of(context(Occasion.PRESENTATION, Goal.PROFESSIONAL))
    assert assessment.weakest_element is None
    assert "Nothing is off" in assessment.detail
    for element in ("jacket", "bottom", "shoes", "top", "accessories"):
        assert element not in assessment.detail


def test_articles_agree_with_the_occasion():
    """« an interview », « a wedding » : une faute d'article se remarque."""
    assert "an interview" in fit_of(context(Occasion.INTERVIEW, Goal.PROFESSIONAL)).detail
    assert "an event" in fit_of(context(Occasion.EVENT, Goal.ELEGANT)).detail
    assert "a wedding" in fit_of(context(Occasion.WEDDING, Goal.ELEGANT)).detail


def test_a_named_culprit_requires_a_real_gap():
    """Le coupable n'est nomme que s'il se detache vraiment du reste."""
    barely = outfit_with(OutfitElement.SHOES, level=0.82)   # ecart negligeable
    clearly = outfit_with(OutfitElement.SHOES, level=0.15)  # ecart net

    assert fit_of(context(Occasion.BUSINESS, Goal.PROFESSIONAL, barely, 0.9)).weakest_element is None
    assert fit_of(context(Occasion.BUSINESS, Goal.PROFESSIONAL, clearly, 0.9)).weakest_element == "shoes"


# --------------------------------------------- coherence verdict / action
def dressed(level: float):
    return {
        element: OutfitItem(
            present=True, known=True, formality=level, structure=level,
            color_harmony=0.65, condition=0.85,
        )
        for element in OutfitElement
    }


def test_the_screen_never_promises_readiness_then_demands_a_change():
    """« You're good to go » suivi de « Change the jacket » detruit le produit."""
    for level in (0.20, 0.45, 0.62, 0.88):
        for occasion in Occasion:
            outcome = default_engine.evaluate(context(occasion, Goal.PROFESSIONAL, dressed(level)))
            if outcome.fit.headline.startswith("You're good"):
                assert outcome.action is ChangeAction.NO_CHANGE, (
                    f"{occasion} / {level} promet d'etre pret et demande {outcome.action}"
                )


def test_nothing_worth_changing_is_said_plainly():
    """NO_CHANGE sur un look imparfait ne se maquille pas en « good to go »."""
    seen = False
    for level in (0.55, 0.7, 0.88):
        for occasion in Occasion:
            outcome = default_engine.evaluate(context(occasion, Goal.PROFESSIONAL, dressed(level)))
            if outcome.action is ChangeAction.NO_CHANGE and outcome.fit.state == "ALMOST_THERE":
                seen = True
                assert outcome.fit.headline == "Close enough."
                assert "worth changing" in outcome.fit.detail
    assert seen, "ce cas doit exister : sinon le libelle n'est jamais exerce"


def test_the_same_look_gets_different_verdicts_across_occasions():
    """La these du produit doit etre VISIBLE, pas seulement vraie.

    Avec une tenue decrite, un look decontracte doit convenir en voyage et
    detonner a un mariage. Sans cette differenciation, les dix occasions
    rendent le meme ecran et le produit ne demontre rien.
    """
    casual = dressed(0.22)
    verdicts = {
        occasion: default_engine.evaluate(context(occasion, Goal.PROFESSIONAL, casual)).fit.state
        for occasion in Occasion
    }
    assert len(set(verdicts.values())) >= 2, verdicts
    assert verdicts[Occasion.WEDDING] == "MISMATCH"
    assert verdicts[Occasion.TRAVEL] in {"FIT", "ALMOST_THERE"}


def test_being_overdressed_is_also_a_mismatch():
    """Trop habille pour un voyage est un ecart, pas une reussite."""
    formal = default_engine.evaluate(context(Occasion.TRAVEL, Goal.APPROACHABLE, dressed(0.92)))
    assert formal.fit.state != "FIT"


# ------------------------------- ce qui change ne peut pas etre « garde »
@pytest.mark.parametrize("action", [a for a in ChangeAction if a is not ChangeAction.NO_CHANGE])
def test_the_piece_the_preview_changes_is_never_kept(action):
    """Cas reel : « Adjust the colour balance » listait « Keep · Top »,
    pendant que l'apercu remplacait le haut. L'ecran se contredisait."""
    from app.engines.one_change.explanation import keep_list
    from app.models.enums import MATERIALISED_ELEMENT

    ctx = context(Occasion.DATE, Goal.ELEGANT, outfit_with())
    kept = keep_list(ctx, action)
    touched = MATERIALISED_ELEMENT[action]
    if touched is not None:
        assert str(touched) not in kept, f"{action} garde {touched} tout en le changeant"


def test_the_colour_change_says_what_the_preview_will_show():
    """Une intention abstraite n'annonce pas ce que l'image montrera."""
    from app.models.enums import ACTION_LABEL, MATERIALISED_ELEMENT

    label = ACTION_LABEL[ChangeAction.CHANGE_COLOR]
    assert "top" in label.lower()
    assert MATERIALISED_ELEMENT[ChangeAction.CHANGE_COLOR] is OutfitElement.TOP


def test_the_colour_change_is_not_treated_as_an_addition():
    """Changer une couleur n'ajoute rien, meme si le haut manquait."""
    from app.engines.one_change.explanation import is_addition

    outfit = outfit_with()
    outfit[OutfitElement.TOP] = OutfitItem(present=False)
    ctx = context(Occasion.DATE, Goal.ELEGANT, outfit)
    assert is_addition(ctx, ChangeAction.CHANGE_COLOR) is False
