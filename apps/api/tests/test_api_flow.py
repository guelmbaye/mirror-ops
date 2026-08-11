"""Parcours complet de bout en bout (Doc 02 §24 : Definition of Done)."""

from __future__ import annotations

import json

from tests.conftest import make_image


async def test_full_golden_journey(flow, client):
    """Moment -> Photo -> Skin AI -> ONE CHANGE -> VTO -> Before/After."""
    session_id = await flow.session()
    await flow.moment(session_id, "presentation", "professional", "<5m")

    analysis = await flow.analyze(session_id)
    assert analysis["status"] == "completed"
    assert 0.0 <= analysis["data_confidence"] <= 1.0
    assert analysis["appearance"]["professional_presence"] > 0
    assert analysis["skin"]["redness"] is not None
    # Mode mock : l'API dit clairement que ce n'est pas YouCam
    assert analysis["skin_simulated"] is True

    recommendation = await flow.one_change(session_id)
    assert recommendation["action"] == "CHANGE_JACKET"
    assert recommendation["requires_vto"] is True
    assert recommendation["confidence"] in {"low", "medium", "high"}
    assert recommendation["why"]
    assert "jacket" not in recommendation["keep"]
    assert set(recommendation["impact"]["before"]) == set(recommendation["impact"]["after"])

    response = await flow.vto(session_id)
    assert response.status_code == 201, response.text
    vto = response.json()
    assert vto["status"] == "completed"
    assert vto["action"] == "CHANGE_JACKET"
    assert vto["before_image_url"] and vto["result_image_url"]
    assert vto["simulated"] is True  # provider local, jamais presente comme YouCam
    assert vto["provider"] == "local_composite"

    # Les deux images du Before/After sont reellement servables
    for url in (vto["before_image_url"], vto["result_image_url"]):
        media = await client.get(url.replace("http://testserver", ""))
        assert media.status_code == 200
        assert media.headers["content-type"].startswith("image/")

    detail = await client.get(f"/api/v1/sessions/{session_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["session"]["state"] == "VTO_COMPLETED"
    assert body["moment"]["occasion"] == "presentation"
    assert body["recommendation"]["action"] == "CHANGE_JACKET"
    assert body["vto"]["result_image_url"]


async def test_no_change_journey_skips_vto(flow):
    """Un look deja fort doit produire NO_CHANGE et ne consommer aucun VTO."""
    session_id = await flow.session()
    await flow.moment(session_id, "presentation", "professional", "15_30m")

    strong = json.dumps(
        {
            element: {
                "present": True, "formality": 0.82, "structure": 0.9,
                "color_harmony": 0.88, "condition": 0.95,
            }
            for element in ("jacket", "top", "bottom", "shoes", "accessories")
        }
    )
    await flow.analyze(session_id, outfit=strong)
    recommendation = await flow.one_change(session_id)

    assert recommendation["action"] == "NO_CHANGE"
    assert recommendation["requires_vto"] is False

    response = await flow.vto(session_id)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VTO_NOT_APPLICABLE"


async def test_outfit_hints_change_the_decision(flow):
    """Une veste faible declaree doit renforcer la recommandation veste."""
    session_id = await flow.session()
    await flow.moment(session_id, "interview", "professional", "5_15m")
    weak_jacket = json.dumps(
        {
            "jacket": {"present": True, "formality": 0.2, "structure": 0.25, "color_harmony": 0.35, "condition": 0.6},
            "top": {"present": True, "formality": 0.85, "structure": 0.8, "color_harmony": 0.85, "condition": 0.9},
            "bottom": {"present": True, "formality": 0.85, "structure": 0.8, "color_harmony": 0.85, "condition": 0.9},
            "shoes": {"present": True, "formality": 0.85, "structure": 0.8, "color_harmony": 0.85, "condition": 0.9},
        }
    )
    await flow.analyze(session_id, outfit=weak_jacket)
    recommendation = await flow.one_change(session_id)
    assert recommendation["action"] == "CHANGE_JACKET"
    assert recommendation["score"] >= 60
    assert recommendation["confidence"] in {"medium", "high"}


async def test_absent_jacket_is_never_recommended(flow):
    session_id = await flow.session()
    await flow.moment(session_id, "date", "approachable", "15_30m")
    outfit = json.dumps({"jacket": {"present": False}})
    await flow.analyze(session_id, outfit=outfit)
    recommendation = await flow.one_change(session_id)
    assert recommendation["action"] != "CHANGE_JACKET"


async def test_garment_catalog_is_exposed(client):
    response = await client.get("/api/v1/garments", params={"category": "jacket"})
    assert response.status_code == 200
    garments = response.json()["garments"]
    assert garments and all(g["category"] == "jacket" for g in garments)


async def test_explicit_garment_selection(flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    await flow.one_change(session_id)
    response = await flow.vto(session_id, garment_asset_id="jacket_02")
    assert response.status_code == 201
    assert response.json()["garment_id"] == "jacket_02"


async def test_garment_must_match_recommended_change(flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    await flow.one_change(session_id)
    response = await flow.vto(session_id, garment_asset_id="shoes_01")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


async def test_health_endpoints(client):
    assert (await client.get("/health")).status_code == 200
    dependencies = await client.get("/api/v1/health/dependencies")
    assert dependencies.status_code == 200
    body = dependencies.json()
    assert body["database"] == "ok"
    assert body["youcam_mode"] == "mock"


async def test_analysis_never_exposes_provider_internals(flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    analysis = await flow.analyze(session_id, image=make_image(color=(190, 150, 140)))
    assert "raw" not in analysis
    assert "provider_task_id" not in json.dumps(analysis)
