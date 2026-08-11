"""Le portail de qualite doit dire ce qui manque REELLEMENT.

Incident : « We need a clearer view of your look » s'affichait alors que la
photo etait parfaite — ce qui manquait, c'etait la description de la tenue.
Envoyer quelqu'un reprendre une bonne photo est une impasse : rien de ce qu'il
fera devant l'objectif n'y changera quelque chose.
"""

from __future__ import annotations

import json

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
from app.engines.one_change.engine import InsufficientDataError
from app.models.enums import Goal, Occasion, OutfitElement, TimeAvailable


def context(outfit=None, quality=0.85):
    moment = MomentSpec(Occasion.PRESENTATION, Goal.PROFESSIONAL, TimeAvailable.FROM_15_TO_30M)
    signals = build_appearance_signals(
        moment,
        outfit if outfit is not None else default_outfit(),
        SkinObservations(available=False),
        ImageQuality(score=quality),
    )
    return DecisionContext(moment, signals)


def test_an_empty_outfit_is_reported_as_such():
    nothing = {element: OutfitItem(present=False) for element in OutfitElement}
    with pytest.raises(InsufficientDataError) as caught:
        default_engine.evaluate(context(nothing))
    assert str(caught.value) == "no_outfit_declared"


def test_an_unusable_photo_is_reported_as_such():
    with pytest.raises(InsufficientDataError) as caught:
        default_engine.evaluate(context(quality=0.10))
    assert str(caught.value) == "image_unusable"


def test_an_undescribed_outfit_no_longer_blocks_the_decision():
    """Ne pas connaitre les attributs abaisse la confiance, il ne refuse pas.

    Le produit annonce deja sa confiance : refuser en plus serait plus severe
    que necessaire, et priverait l'utilisateur d'une decision utilisable.
    """
    declared_only = {
        element: OutfitItem(present=True)  # present, mais aucun attribut connu
        for element in (OutfitElement.TOP, OutfitElement.BOTTOM, OutfitElement.SHOES)
    }
    declared_only.update(
        {e: OutfitItem(present=False) for e in (OutfitElement.JACKET, OutfitElement.ACCESSORIES)}
    )

    outcome = default_engine.evaluate(context(declared_only, quality=0.62))
    assert outcome.action
    assert outcome.confidence_level in {"low", "medium", "high"}


# ------------------------------------------------------------------ via l'API
async def test_the_api_says_what_is_missing_not_what_is_convenient(client, flow):
    session_id = await flow.session()
    await flow.moment(session_id)

    nothing = json.dumps({e: {"present": False} for e in
                          ("jacket", "top", "bottom", "shoes", "accessories")})
    await flow.analyze(session_id, outfit=nothing)

    response = await client.post("/api/v1/one-change/evaluate", json={"session_id": session_id})
    assert response.status_code in (400, 422)
    body = response.json()["error"]

    # La photo n'est pas en cause : le message ne doit pas l'accuser.
    assert body["code"] == "INVALID_REQUEST"
    assert "wearing" in body["message"]
    assert "clearer view" not in body["message"]


async def test_a_declared_outfit_reaches_a_decision(client, flow):
    """Le parcours normal de l'interface : presence declaree, attributs inconnus."""
    session_id = await flow.session()
    await flow.moment(session_id)

    declared = json.dumps({
        "jacket": {"present": True}, "top": {"present": True}, "bottom": {"present": True},
        "shoes": {"present": True}, "accessories": {"present": False},
    })
    await flow.analyze(session_id, outfit=declared)

    recommendation = await flow.one_change(session_id)
    assert recommendation["action"]
    assert recommendation["fit"]["state"] in {"FIT", "ALMOST_THERE", "MISMATCH"}
