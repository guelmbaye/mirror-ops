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


def verdict_of(ctx):
    """Le verdict tel que l'ecran l'affiche : avec l'action reellement choisie.

    Le verdict ne nomme un element que si la decision le traite. Passer une
    action arbitraire produirait donc une phrase generique.
    """
    return default_engine.evaluate(ctx).fit


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
    assessment = verdict_of(
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
    plural = verdict_of(context(Occasion.BUSINESS, Goal.PROFESSIONAL, outfit_with(OutfitElement.SHOES), 0.9))
    singular = verdict_of(context(Occasion.BUSINESS, Goal.PROFESSIONAL, outfit_with(OutfitElement.JACKET), 0.9))
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

    assert verdict_of(context(Occasion.BUSINESS, Goal.PROFESSIONAL, barely, 0.9)).weakest_element is None
    assert verdict_of(context(Occasion.BUSINESS, Goal.PROFESSIONAL, clearly, 0.9)).weakest_element == "shoes"


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


@pytest.mark.parametrize("occasion", list(Occasion))
def test_the_sentence_is_grammatical_for_every_occasion(occasion):
    """« what a travel calls for » : une faute dans la phrase centrale du produit.

    Chaque occasion doit produire une phrase lisible — article correct, ou pas
    d'article du tout pour les noms indenombrables.
    """
    detail = fit_of(context(occasion, Goal.PROFESSIONAL, dressed(0.25))).detail

    assert " a travel " not in detail
    assert " a business " not in detail
    assert " a dinner " not in detail
    assert " what other " not in detail
    assert " a interview" not in detail and " a event" not in detail
    assert detail.endswith(".")

    if occasion is Occasion.OTHER:
        assert "this occasion" in detail
    else:
        assert str(occasion).replace("_", " ") in detail


# ------------------------------------ la matrice publiee doit rester vraie
#: Ce que produit EXACTEMENT la charge utile de l'interface : presence et
#: niveau d'habillement, rien d'autre. Reproduit dans PRODUCT_REVIEW.md,
#: SUBMISSION.md et le one-pager PDF.
#:
#: Une premiere version de ces chiffres avait ete calculee avec des attributs
#: de vetement que l'interface n'envoie jamais, et lisait 2 a 4 points trop
#: haut. Un chiffre qu'un jury peut verifier en une seconde est le pire endroit
#: ou se tromper — d'ou ce test.
PUBLISHED_MATRIX = {
    0.22: {"wedding": ("MISMATCH", 47), "interview": ("MISMATCH", 46),
           "dinner": ("ALMOST_THERE", 60), "travel": ("ALMOST_THERE", 69)},
    0.55: {"wedding": ("ALMOST_THERE", 64), "interview": ("ALMOST_THERE", 64),
           "dinner": ("FIT", 74), "travel": ("ALMOST_THERE", 67)},
    0.88: {"wedding": ("FIT", 81), "interview": ("FIT", 81),
           "dinner": ("ALMOST_THERE", 68), "travel": ("ALMOST_THERE", 60)},
}

MATRIX_GOALS = {
    "wedding": Goal.ELEGANT, "interview": Goal.PROFESSIONAL,
    "dinner": Goal.ELEGANT, "travel": Goal.APPROACHABLE,
}


def interface_outfit(dressiness: float):
    """La charge utile reelle : ni color_harmony, ni condition."""
    return {
        element: OutfitItem(
            present=True, known=True, formality=dressiness, structure=dressiness,
            color_harmony=0.55, condition=0.70,   # defauts de OutfitItemIn.to_domain
        )
        for element in OutfitElement
    }


@pytest.mark.parametrize("dressiness", sorted(PUBLISHED_MATRIX))
def test_the_published_matrix_still_holds(dressiness):
    for name, (state, score) in PUBLISHED_MATRIX[dressiness].items():
        occasion = Occasion(name)
        outcome = default_engine.evaluate(
            context(occasion, MATRIX_GOALS[name], interface_outfit(dressiness),
                    quality=0.85, time=TimeAvailable.FROM_15_TO_30M)
        )
        assert outcome.fit.state == state, (
            f"{name} at {dressiness}: engine says {outcome.fit.state}, docs say {state}"
        )
        assert outcome.fit.score == score, (
            f"{name} at {dressiness}: engine says {outcome.fit.score}, docs say {score}. "
            "Update PRODUCT_REVIEW.md, SUBMISSION.md and scripts/build_onepager.py."
        )


def test_the_matrix_actually_demonstrates_the_thesis():
    """Une matrice uniforme ne prouverait rien : l'ecart doit etre visible."""
    casual = PUBLISHED_MATRIX[0.22]
    formal = PUBLISHED_MATRIX[0.88]

    # Meme look decontracte : rejete pour un mariage, acceptable en voyage.
    assert casual["wedding"][0] == "MISMATCH"
    assert casual["travel"][0] != "MISMATCH"
    assert casual["travel"][1] - casual["wedding"][1] >= 15

    # Et l'inverse : trop habille pour un voyage est un ecart aussi.
    assert formal["wedding"][0] == "FIT"
    assert formal["travel"][0] != "FIT"
    assert formal["wedding"][1] - formal["travel"][1] >= 15


# ------------------------------------------ la paire de demonstration
#: Les occasions recommandees pour la video. Interview (0.90) et wedding (0.88)
#: sont les DEUX PLUS PROCHES du systeme : les opposer ne montre rien, et une
#: premiere version du script les recommandait quand meme.
DEMO_PAIR = (Occasion.INTERVIEW, Occasion.TRAVEL)


def test_the_demo_pair_flips_both_the_verdict_and_the_action():
    """La bascule d'occasion doit changer l'ECRAN, pas seulement un score."""
    casual = interface_outfit(0.25)
    goals = {Occasion.INTERVIEW: Goal.PROFESSIONAL, Occasion.TRAVEL: Goal.APPROACHABLE}

    first, second = (
        default_engine.evaluate(context(occasion, goals[occasion], casual, quality=0.85))
        for occasion in DEMO_PAIR
    )

    assert first.fit.state != second.fit.state, "meme verdict : la bascule ne montre rien"
    assert first.action != second.action, "meme action : l'ecran est identique"
    assert first.label != second.label
    assert abs(first.fit.score - second.fit.score) >= 15

    # Le second membre refuse de changer quoi que ce soit : c'est le meilleur
    # argument possible pour un moteur de decision.
    assert second.action is ChangeAction.NO_CHANGE


def test_near_identical_occasions_are_documented_as_such():
    """Les occasions proches ne peuvent pas servir de demonstration.

    interview / wedding / business partagent presque la meme exigence : les
    opposer produit deux ecrans identiques.
    """
    from app.engines.one_change.tables import OCCASION_TARGET_FORMALITY

    close = (Occasion.INTERVIEW, Occasion.WEDDING, Occasion.BUSINESS)
    targets = [OCCASION_TARGET_FORMALITY[o] for o in close]
    assert max(targets) - min(targets) <= 0.06, (
        "ces occasions ne sont plus proches : le conseil de demonstration a change"
    )

    casual = interface_outfit(0.25)
    verdicts = {
        occasion: default_engine.evaluate(
            context(occasion, Goal.PROFESSIONAL, casual, quality=0.85)
        ).fit.state
        for occasion in close
    }
    assert len(set(verdicts.values())) == 1, verdicts


def test_an_undeclared_dressiness_collapses_the_contrast():
    """Pourquoi la question d'habillement est obligatoire cote interface.

    Sans elle, chaque piece arrive avec `known=False` et une formalite moyenne :
    un entretien et un voyage rendent alors le meme verdict a deux points pres,
    et la these du produit devient invisible. Ce test documente la raison — si
    quelqu'un rend la question facultative a nouveau, il expliquera pourquoi.
    """
    unknown = {
        element: OutfitItem(present=True, known=False, formality=0.55, structure=0.55,
                            color_harmony=0.55, condition=0.70)
        for element in OutfitElement
    }
    verdicts = {
        occasion: default_engine.evaluate(
            context(occasion, Goal.PROFESSIONAL, unknown, quality=0.8,
                    time=TimeAvailable.UNDER_5M)
        )
        for occasion in (Occasion.INTERVIEW, Occasion.TRAVEL)
    }
    interview, travel = verdicts[Occasion.INTERVIEW], verdicts[Occasion.TRAVEL]

    assert interview.fit.state == travel.fit.state
    assert abs(interview.fit.score - travel.fit.score) <= 5
    assert interview.action == travel.action

    # Avec la reponse, le meme couple se separe nettement.
    casual = interface_outfit(0.22)
    apart = {
        occasion: default_engine.evaluate(
            context(occasion, goal, casual, quality=0.8, time=TimeAvailable.UNDER_5M)
        )
        for occasion, goal in [(Occasion.INTERVIEW, Goal.PROFESSIONAL),
                               (Occasion.TRAVEL, Goal.APPROACHABLE)]
    }
    first, second = apart[Occasion.INTERVIEW], apart[Occasion.TRAVEL]
    assert first.fit.state != second.fit.state
    assert first.action != second.action
    assert abs(first.fit.score - second.fit.score) >= 20


# ------------------------------- reparer l'ecart plutot qu'optimiser le gain
def outfit_with_odd_one(odd: OutfitElement, level: float = 0.82):
    """Ce que l'interface envoie quand une piece est signalee comme detonnante."""
    return {
        element: OutfitItem(
            present=True, known=True,
            formality=(max(0.1, level - 0.4) if element is odd else level),
            structure=(max(0.1, level - 0.4) if element is odd else level),
            color_harmony=0.55, condition=0.70,
        )
        for element in OutfitElement
    }


@pytest.mark.parametrize("odd", list(OutfitElement))
@pytest.mark.parametrize("time", [TimeAvailable.UNDER_5M, TimeAvailable.OVER_30M])
def test_the_verdict_never_names_a_piece_the_decision_ignores(odd, time):
    """« Les chaussures tirent l'ensemble vers le bas » puis « changez la veste ».

    Deux phrases qui se contredisent, l'une sous l'autre. Le verdict ne nomme
    donc un element que si la decision le traite reellement.
    """
    from app.models.enums import MATERIALISED_ELEMENT

    for occasion, goal in [(Occasion.INTERVIEW, Goal.PROFESSIONAL),
                           (Occasion.WEDDING, Goal.ELEGANT),
                           (Occasion.TRAVEL, Goal.APPROACHABLE)]:
        outcome = default_engine.evaluate(
            context(occasion, goal, outfit_with_odd_one(odd), quality=0.85, time=time)
        )
        named = outcome.fit.weakest_element
        if named is not None:
            assert str(MATERIALISED_ELEMENT[outcome.action]) == named, (
                f"{occasion}/{time}: names {named}, acts on {outcome.action}"
            )


def test_fixing_the_mismatch_beats_the_bigger_average_gain():
    """« Don't redesign your look. Fix the mismatch. »

    Des baskets dans une tenue habillee : le moteur recommandait de changer la
    veste — gain moyen superieur, mais hors sujet. La piece qui detonne doit
    l'emporter.
    """
    outcome = default_engine.evaluate(
        context(Occasion.INTERVIEW, Goal.PROFESSIONAL,
                outfit_with_odd_one(OutfitElement.SHOES), quality=0.85)
    )
    assert outcome.action is ChangeAction.CHANGE_SHOES
    assert outcome.fit.weakest_element == "shoes"
    assert "shoes" in outcome.fit.detail


def test_a_homogeneous_outfit_gets_no_anomaly_bonus():
    """La prime ne doit rien deplacer quand aucune piece ne se detache."""
    from app.engines.one_change.scorer import anomaly_lift

    ctx = context(Occasion.INTERVIEW, Goal.PROFESSIONAL, interface_outfit(0.55))
    assert all(anomaly_lift(ctx, action) == 0.0 for action in ChangeAction)


def test_the_middle_dressiness_is_the_one_that_shows_no_contrast():
    """Documente pourquoi la demonstration ne doit pas utiliser « In between ».

    Le niveau median est equidistant de toutes les occasions par construction :
    un entretien et un voyage y atterrissent a quelques points l'un de l'autre,
    avec la meme recommandation. Ce n'est pas un defaut — c'est la reponse
    juste — mais cela rend le contraste invisible, et un testeur en conclut que
    l'occasion ne sert a rien.
    """
    goals = {Occasion.INTERVIEW: Goal.PROFESSIONAL, Occasion.TRAVEL: Goal.APPROACHABLE}

    middle = {
        occasion: default_engine.evaluate(
            context(occasion, goal, interface_outfit(0.55), quality=0.85,
                    time=TimeAvailable.UNDER_5M)
        )
        for occasion, goal in goals.items()
    }
    assert abs(middle[Occasion.INTERVIEW].fit.score - middle[Occasion.TRAVEL].fit.score) <= 6
    assert middle[Occasion.INTERVIEW].action == middle[Occasion.TRAVEL].action

    # Les deux extremes, eux, separent nettement.
    for level in (0.22, 0.88):
        edges = {
            occasion: default_engine.evaluate(
                context(occasion, goal, interface_outfit(level), quality=0.85,
                        time=TimeAvailable.UNDER_5M)
            )
            for occasion, goal in goals.items()
        }
        gap = abs(edges[Occasion.INTERVIEW].fit.score - edges[Occasion.TRAVEL].fit.score)
        assert gap >= 18, f"dressiness {level}: only {gap} points apart"


# --------------------------------------------- le sens du changement
def test_opposite_situations_do_not_get_the_same_sentence():
    """Sous-habille pour un entretien et sur-habille pour un voyage.

    Les deux disaient « Change the jacket ». L'utilisateur ne pouvait pas savoir
    s'il fallait monter ou descendre en formalite, et trois reglages differents
    rendaient un titre identique — le produit paraissait sourd a ce qu'on lui
    disait.
    """
    under = default_engine.evaluate(
        context(Occasion.INTERVIEW, Goal.PROFESSIONAL, interface_outfit(0.22))
    )
    over = default_engine.evaluate(
        context(Occasion.TRAVEL, Goal.PROFESSIONAL, interface_outfit(0.88))
    )

    assert "sharper" in under.label
    assert "easier" in over.label
    assert under.label != over.label
    # Le titre reste une phrase d'action.
    for outcome in (under, over):
        assert outcome.label.startswith("Change")
        assert outcome.explanation.what.endswith(".")


def test_no_direction_when_the_level_is_not_the_problem():
    """Quand la formalite est deja juste, c'est la piece qui pose probleme."""
    from app.engines.one_change.explanation import formality_shift
    from app.engines.one_change.tables import OCCASION_TARGET_FORMALITY

    target = OCCASION_TARGET_FORMALITY[Occasion.INTERVIEW]
    ctx = context(Occasion.INTERVIEW, Goal.PROFESSIONAL, interface_outfit(target))
    assert formality_shift(ctx, ChangeAction.CHANGE_JACKET) is None


@pytest.mark.parametrize("level", [0.15, 0.5, 0.85])
def test_the_direction_always_points_the_right_way(level):
    """Jamais « go sharper » a quelqu'un qui est deja trop habille."""
    from app.engines.one_change.explanation import formality_shift
    from app.engines.one_change.tables import OCCASION_TARGET_FORMALITY

    for occasion in Occasion:
        ctx = context(occasion, Goal.PROFESSIONAL, interface_outfit(level))
        shift = formality_shift(ctx, ChangeAction.CHANGE_JACKET)
        if shift is None:
            continue
        target = OCCASION_TARGET_FORMALITY[occasion]
        assert shift == ("sharper" if level < target else "easier")
