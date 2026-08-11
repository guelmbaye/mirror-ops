"""Protection des unites API (Doc 05 §19, Doc 08 §22, Doc 12 §14).

Regle d'or : un parcours utilisateur = une analyse + un VTO.
"""

from __future__ import annotations

from app.integrations.youcam import set_providers
from app.integrations.youcam.mock import LocalCompositeVTOService, LocalSkinHeuristicService
from app.integrations.youcam.models import GarmentRef
from tests.conftest import make_image


class CountingSkinProvider(LocalSkinHeuristicService):
    provider_name = "local_heuristic"

    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, image_bytes, mime_type="image/jpeg", *, file_name="look.jpg"):
        self.calls += 1
        return await super().analyze(image_bytes, mime_type, file_name=file_name)


class CountingVTOProvider(LocalCompositeVTOService):
    provider_name = "local_composite"

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, source_image, garment: GarmentRef, *, source_mime="image/jpeg"):
        self.calls += 1
        return await super().generate(source_image, garment, source_mime=source_mime)


async def test_double_click_on_analyze_consumes_one_unit(client, flow):
    skin = CountingSkinProvider()
    set_providers(skin=skin)

    session_id = await flow.session()
    await flow.moment(session_id)
    image = make_image()

    first = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("look.jpg", image, "image/jpeg")},
        headers={"Idempotency-Key": "same-key"},
    )
    second = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("look.jpg", image, "image/jpeg")},
        headers={"Idempotency-Key": "same-key"},
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["analysis_id"] == second.json()["analysis_id"]
    assert skin.calls == 1


async def test_same_image_reuses_cached_analysis_without_key(client, flow):
    skin = CountingSkinProvider()
    set_providers(skin=skin)
    session_id = await flow.session()
    await flow.moment(session_id)
    image = make_image(color=(150, 130, 120))

    await flow.analyze(session_id, image=image)
    await flow.analyze(session_id, image=image)
    assert skin.calls == 1


async def test_double_click_on_vto_consumes_one_unit(client, flow):
    vto = CountingVTOProvider()
    set_providers(vto=vto)

    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    await flow.one_change(session_id)

    first = await client.post(
        "/api/v1/vto/generate",
        json={"session_id": session_id},
        headers={"Idempotency-Key": "vto-key"},
    )
    second = await client.post(
        "/api/v1/vto/generate",
        json={"session_id": session_id},
        headers={"Idempotency-Key": "vto-key"},
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert vto.calls == 1


async def test_one_journey_costs_one_analysis_and_one_vto(client, flow):
    skin, vto = CountingSkinProvider(), CountingVTOProvider()
    set_providers(skin=skin, vto=vto)

    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    recommendation = await flow.one_change(session_id)
    assert recommendation["action"] != "NO_CHANGE"
    response = await flow.vto(session_id)
    assert response.status_code == 201

    assert skin.calls == 1
    assert vto.calls == 1  # jamais de VTO pour les candidats perdants


async def test_losing_candidates_never_trigger_vto(client, flow):
    """6 candidats scores, 1 seul VTO (Doc 05 §12)."""
    vto = CountingVTOProvider()
    set_providers(vto=vto)
    session_id = await flow.session()
    await flow.moment(session_id, "event", "elegant", "30m_plus")
    await flow.analyze(session_id)
    recommendation = await flow.one_change(session_id)
    assert vto.calls == 0  # aucun VTO pendant le scoring
    if recommendation["requires_vto"]:
        await flow.vto(session_id)
        assert vto.calls == 1
