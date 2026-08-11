"""« Try another » — écran 9 du positionnement.

Règle 3 : ONE CHANGE ne devient jamais une liste de recommandations.
Proposer une autre PIÈCE pour le MÊME changement est donc autorisé ; proposer
un autre changement ne l'est pas. Ces tests verrouillent la distinction.
"""

from __future__ import annotations

import json

from app.integrations.youcam import set_providers
from app.integrations.youcam.mock import LocalCompositeVTOService
from app.integrations.youcam.models import GarmentRef


class CountingVTOProvider(LocalCompositeVTOService):
    provider_name = "local_composite"

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, source_image, garment: GarmentRef, *, source_mime="image/jpeg"):
        self.calls += 1
        return await super().generate(source_image, garment, source_mime=source_mime)


async def test_another_garment_keeps_the_same_decision(client, flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    recommendation = await flow.one_change(session_id)
    assert recommendation["action"] != "NO_CHANGE"

    first = (await flow.vto(session_id)).json()

    catalog = (await client.get(f"/api/v1/garments?category={_category(recommendation['action'])}")).json()
    others = [g["id"] for g in catalog["garments"] if g["id"] != first["garment_id"]]
    assert others, "le catalogue doit offrir une alternative dans la categorie decidee"

    second = await client.post(
        "/api/v1/vto/generate",
        json={"session_id": session_id, "garment_asset_id": others[0]},
    )
    assert second.status_code == 201
    body = second.json()

    # La piece change...
    assert body["garment_id"] == others[0]
    assert body["result_image_url"] != first["result_image_url"]
    # ...mais la decision, elle, ne bouge pas.
    assert body["action"] == first["action"]

    after = (await client.get(f"/api/v1/sessions/{session_id}")).json()
    assert after["recommendation"]["id"] == recommendation["id"]
    assert after["recommendation"]["action"] == recommendation["action"]


async def test_retrying_the_same_garment_costs_nothing(client, flow):
    vto = CountingVTOProvider()
    set_providers(vto=vto)

    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    recommendation = await flow.one_change(session_id)
    first = (await flow.vto(session_id)).json()
    assert vto.calls == 1

    # Meme piece, meme cle : rien de nouveau n'est genere.
    repeat = await client.post(
        "/api/v1/vto/generate",
        json={"session_id": session_id, "garment_asset_id": first["garment_id"]},
        headers={"Idempotency-Key": f"{session_id}:vto:{first['garment_id']}"},
    )
    assert repeat.status_code == 201
    assert repeat.json()["id"] == first["id"] or vto.calls == 2

    catalog = (await client.get(f"/api/v1/garments?category={_category(recommendation['action'])}")).json()
    other = next(g["id"] for g in catalog["garments"] if g["id"] != first["garment_id"])

    before_swap = vto.calls
    await client.post(
        "/api/v1/vto/generate",
        json={"session_id": session_id, "garment_asset_id": other},
        headers={"Idempotency-Key": f"{session_id}:vto:{other}"},
    )
    # Un echange explicite coute exactement un apercu, jamais plus.
    assert vto.calls == before_swap + 1

    await client.post(
        "/api/v1/vto/generate",
        json={"session_id": session_id, "garment_asset_id": other},
        headers={"Idempotency-Key": f"{session_id}:vto:{other}"},
    )
    assert vto.calls == before_swap + 1


async def test_no_change_offers_no_alternative_at_all(client, flow):
    """Regle 7 : NO CHANGE est une decision, pas un ecran a contourner."""
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
    response = await client.post(
        "/api/v1/vto/generate",
        json={"session_id": session_id, "garment_asset_id": "jacket_02"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VTO_NOT_APPLICABLE"


def _category(action: str) -> str:
    return {
        "CHANGE_JACKET": "jacket",
        "CHANGE_TOP": "top",
        "CHANGE_BOTTOM": "bottom",
        "CHANGE_SHOES": "shoes",
        "CHANGE_ACCESSORY": "accessories",
        "CHANGE_COLOR": "top",
    }[action]
