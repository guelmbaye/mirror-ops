"""Revenir en arriere et corriger doit changer le resultat.

Incident : apres un retour sur l'ecran precedent, modifier l'occasion ou la
tenue puis relancer ne changeait rien. Deux causes distinctes — un second
moment cree en doublon dont le depart se jouait sur un UUID aleatoire, et une
cle d'idempotence qui n'ecoutait que la session.
"""

from __future__ import annotations

import json

from tests.conftest import make_image

OUTFIT_A = json.dumps({"jacket": {"present": True}, "top": {"present": True}})
OUTFIT_B = json.dumps({"shoes": {"present": True}, "bottom": {"present": True}})


async def analyze(client, session_id, outfit, photo, key=None):
    headers = {"Idempotency-Key": key} if key else {}
    return await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id, "outfit": outfit},
        files={"image": ("look.jpg", photo, "image/jpeg")},
        headers=headers,
    )


async def test_correcting_the_moment_is_taken_into_account(client, flow):
    session_id = await flow.session()
    await flow.moment(session_id, "presentation", "professional", "<5m")
    await flow.moment(session_id, "wedding", "elegant", "30m_plus")

    detail = (await client.get(f"/api/v1/sessions/{session_id}")).json()
    assert detail["moment"]["occasion"] == "wedding"
    assert detail["moment"]["goal"] == "elegant"
    assert detail["moment"]["time_available"] == "30m_plus"


async def test_a_session_never_accumulates_moments(client, flow, db):
    """Une session porte UN moment : sinon le depart se joue au hasard."""
    from sqlalchemy import func, select

    from app.models.moment import Moment

    session_id = await flow.session()
    for occasion in ("presentation", "date", "wedding", "interview"):
        await flow.moment(session_id, occasion, "professional", "<5m")

    count = await db.scalar(
        select(func.count()).select_from(Moment).where(Moment.session_id == session_id)
    )
    assert count == 1


async def test_correcting_the_outfit_produces_a_new_analysis(client, flow):
    """Meme photo, tenue differente : l'analyse doit etre refaite."""
    photo = make_image()
    session_id = await flow.session()
    await flow.moment(session_id)

    first = (await analyze(client, session_id, OUTFIT_A, photo)).json()
    second = (await analyze(client, session_id, OUTFIT_B, photo)).json()

    assert first["analysis_id"] != second["analysis_id"], (
        "la correction de tenue a ete ignoree"
    )


async def test_identical_inputs_still_cost_a_single_analysis(client, flow):
    """La protection contre le double-clic reste entiere."""
    photo = make_image()
    session_id = await flow.session()
    await flow.moment(session_id)

    first = (await analyze(client, session_id, OUTFIT_A, photo)).json()
    second = (await analyze(client, session_id, OUTFIT_A, photo)).json()
    assert first["analysis_id"] == second["analysis_id"]


async def test_the_decision_follows_the_corrected_inputs(client, flow):
    """Bout en bout : corriger le moment ET la tenue change bien la decision."""
    photo = make_image()
    session_id = await flow.session()

    await flow.moment(session_id, "travel", "approachable", "30m_plus")
    await analyze(client, session_id, OUTFIT_B, photo)
    before = (await client.post(
        "/api/v1/one-change/evaluate", json={"session_id": session_id}
    )).json()["recommendation"]

    # Retour en arriere : nouvelle occasion, nouvelle tenue.
    await flow.moment(session_id, "interview", "professional", "<5m")
    await analyze(client, session_id, OUTFIT_A, photo)
    after = (await client.post(
        "/api/v1/one-change/evaluate", json={"session_id": session_id}
    )).json()["recommendation"]

    detail = (await client.get(f"/api/v1/sessions/{session_id}")).json()
    assert detail["moment"]["occasion"] == "interview"
    assert after["id"] != before["id"], "la decision n'a pas ete recalculee"
