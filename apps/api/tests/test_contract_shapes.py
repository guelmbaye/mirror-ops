"""Stabilite du contrat public (Doc 08 §32/§33) : le frontend peut s'y fier."""

from __future__ import annotations

RECOMMENDATION_KEYS = {
    "id", "action", "label", "score", "confidence",
    "reason", "what", "why", "how", "keep", "impact", "requires_vto", "is_addition",
    "fit", "suggested_garment",
}
VTO_KEYS = {
    "id", "status", "action", "garment_id", "provider", "simulated",
    "before_image_url", "result_image_url", "latency_ms", "created_at",
}


async def test_session_response_shape(client, flow):
    session_id = await flow.session()
    body = (await client.get(f"/api/v1/sessions/{session_id}/summary")).json()
    assert set(body) == {"id", "status", "state", "created_at", "expires_at"}
    assert body["created_at"].endswith("Z")


async def test_recommendation_response_shape(flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    recommendation = await flow.one_change(session_id)
    assert set(recommendation) == RECOMMENDATION_KEYS
    assert isinstance(recommendation["score"], (int, float))
    # Le verbe affiche par l'interface vient du backend, jamais d'une lecture
    # du libelle : « Add a jacket » et « Change · Jacket » ne doivent pas
    # pouvoir se contredire a l'ecran.
    assert isinstance(recommendation["is_addition"], bool)

    # Le verdict d'adequation precede le changement : « FIT THE MOMENT » avant
    # « ONE CHANGE ». Il doit donc toujours etre la.
    fit = recommendation["fit"]
    assert set(fit) == {"state", "score", "headline", "detail", "weakest_element"}
    assert fit["state"] in {"FIT", "ALMOST_THERE", "MISMATCH"}
    assert 0 <= fit["score"] <= 100
    assert fit["headline"] and fit["detail"]
    if recommendation["action"] == "NO_CHANGE":
        assert fit["state"] == "FIT"

    # La piece de la preuve est nommee des la decision : le bouton peut dire ce
    # qu'il montrera, sans offrir un catalogue a parcourir.
    suggested = recommendation["suggested_garment"]
    if recommendation["requires_vto"]:
        assert suggested and set(suggested) == {"id", "name", "category"}
        assert suggested["name"]
    else:
        assert suggested is None
    if recommendation["is_addition"]:
        assert recommendation["label"].lower().startswith("add")
    elif recommendation["action"] != "NO_CHANGE":
        assert recommendation["label"].lower().startswith("change")
    assert isinstance(recommendation["keep"], list)
    assert set(recommendation["impact"]) == {"before", "after", "dominant_factors"}


async def test_vto_response_shape(flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    await flow.one_change(session_id)
    response = await flow.vto(session_id)
    assert set(response.json()) == VTO_KEYS


async def test_session_detail_rebuilds_the_final_screen_in_one_request(client, flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    await flow.one_change(session_id)
    await flow.vto(session_id)

    body = (await client.get(f"/api/v1/sessions/{session_id}")).json()
    assert set(body) == {"session", "moment", "analysis", "recommendation", "vto"}
    assert body["analysis"]["image_url"]
    assert body["vto"]["result_image_url"]
    assert body["recommendation"]["what"]


async def test_partial_session_detail_is_tolerant(client, flow):
    session_id = await flow.session()
    body = (await client.get(f"/api/v1/sessions/{session_id}")).json()
    assert body["moment"] is None
    assert body["recommendation"] is None
    assert body["vto"] is None


async def test_request_id_header_is_returned(client):
    response = await client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert response.headers["X-Request-ID"] == "trace-123"
