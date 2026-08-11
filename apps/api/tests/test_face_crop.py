"""Recadrage du visage : la geometrie doit satisfaire la contrainte de Skin AI.

Skin AI rejette toute image ou le visage occupe moins de 60 % de la largeur.
MIRROR OPS photographie une TENUE. Ces tests verrouillent le pont entre les deux.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from tests.conftest import make_image
from app.services.face_crop import (
    MIN_SHORT_SIDE,
    TARGET_FACE_RATIO,
    compute_crop_box,
    crop_face_for_skin,
    detect_largest_face,
    opencv_available,
)


def test_crop_box_reaches_the_required_face_ratio():
    """Un visage de 200 px dans une photo en pied doit remplir le cadrage."""
    face = (900, 300, 200, 240)
    box = compute_crop_box(face, (2000, 3000))
    width = box[2] - box[0]
    ratio = face[2] / width

    assert ratio >= 0.60, "Skin AI rejetterait ce cadrage"
    assert ratio == pytest.approx(TARGET_FACE_RATIO, abs=0.02)


def test_crop_box_stays_inside_the_image():
    """Un visage colle au bord ne doit pas produire un cadre hors limites."""
    for face in [(0, 0, 200, 240), (1800, 2800, 200, 200), (10, 2900, 300, 90)]:
        box = compute_crop_box(face, (2000, 3000))
        assert box[0] >= 0 and box[1] >= 0
        assert box[2] <= 2000 and box[3] <= 3000
        assert box[2] > box[0] and box[3] > box[1]


def test_crop_box_is_portrait_oriented():
    """La documentation recommande le portrait plutot que le paysage."""
    box = compute_crop_box((900, 300, 200, 240), (2000, 3000))
    assert (box[3] - box[1]) > (box[2] - box[0])


def test_crop_box_keeps_the_forehead():
    """Le front porte une partie des metriques : il ne doit pas etre coupe."""
    face = (900, 600, 200, 240)
    box = compute_crop_box(face, (2000, 3000))
    assert box[1] < face[1], "le cadre doit commencer au-dessus du visage"


def test_crop_box_never_exceeds_a_small_image():
    box = compute_crop_box((10, 10, 300, 300), (400, 400))
    assert box[2] - box[0] <= 400
    assert box[3] - box[1] <= 400


def test_no_face_returns_none_rather_than_guessing():
    """Sans visage detecte, on ne fabrique pas un cadrage arbitraire."""
    buffer = io.BytesIO()
    Image.new("RGB", (900, 1200), (130, 120, 115)).save(buffer, format="JPEG")
    assert crop_face_for_skin(buffer.getvalue()) is None


def test_pipeline_produces_a_compliant_crop(monkeypatch):
    """Chaine complete, detecteur injecte.

    La detection elle-meme est celle d'OpenCV : on ne la teste pas ici (un
    visage dessine n'active pas un classifieur de Haar, qui attend de la texture
    photographique). Ce qui est verifie, c'est tout le reste — le cadrage, la
    mise a l'echelle et l'encodage — pour que ce qui part vers Skin AI soit
    conforme a sa specification.
    """
    from app.services import face_crop as module

    photo = Image.new("RGB", (1000, 1500), (200, 200, 196))
    buffer = io.BytesIO()
    photo.save(buffer, format="JPEG", quality=95)
    image_bytes = buffer.getvalue()

    face = (420, 240, 170, 210)  # 17 % de la largeur : rejete tel quel
    monkeypatch.setattr(module, "detect_largest_face", lambda _: face)

    crop = module.crop_face_for_skin(image_bytes)
    assert crop is not None
    assert crop.face_ratio >= 0.60          # la contrainte Skin AI est levee
    assert min(crop.width, crop.height) >= MIN_SHORT_SIDE
    assert crop.mime_type == "image/jpeg"
    assert crop.image_bytes != image_bytes  # l'original reste intact


def test_a_face_too_small_is_not_upscaled_into_fiction(monkeypatch):
    """Agrandir 40 px de visage ne creerait que des pixels interpolés."""
    from app.services import face_crop as module

    photo = Image.new("RGB", (1000, 1500), (200, 200, 196))
    buffer = io.BytesIO()
    photo.save(buffer, format="JPEG")
    monkeypatch.setattr(module, "detect_largest_face", lambda _: (480, 300, 40, 48))

    assert module.crop_face_for_skin(buffer.getvalue()) is None


@pytest.mark.skipif(not opencv_available(), reason="OpenCV absent")
def test_the_detector_runs_without_crashing_on_arbitrary_input():
    """Robustesse : une image sans visage ne doit jamais lever."""
    buffer = io.BytesIO()
    Image.new("RGB", (640, 480), (12, 40, 90)).save(buffer, format="JPEG")
    assert detect_largest_face(buffer.getvalue()) is None
    assert detect_largest_face(b"not-an-image") is None


async def test_live_provider_receives_the_crop_not_the_full_photo(client, flow, monkeypatch):
    """Ce qui part vers Skin AI est le cadrage ; le VTO garde l'original."""
    from app.integrations.youcam import set_providers
    from app.services import appearance_service
    from tests.conftest import make_image

    seen: dict[str, bytes] = {}

    class LiveLikeSkinProvider:
        provider_name = "youcam_skin_ai"
        requires_face_crop = True

        async def analyze(self, image_bytes, mime_type="image/jpeg", *, file_name="look.jpg"):
            from app.integrations.youcam.models import SkinAnalysisResult

            seen["payload"] = image_bytes
            return SkinAnalysisResult(
                observations={"redness": 0.3}, provider=self.provider_name, simulated=False
            )

    original = make_image(width=1000, height=1500)
    fake_crop = type(
        "Crop",
        (),
        {"image_bytes": b"cropped-face-bytes", "mime_type": "image/jpeg",
         "width": 600, "height": 800, "face_ratio": 0.68},
    )()
    monkeypatch.setattr(appearance_service, "crop_face_for_skin", lambda _: fake_crop)
    set_providers(skin=LiveLikeSkinProvider())

    session_id = await flow.session()
    await flow.moment(session_id)
    response = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("look.jpg", original, "image/jpeg")},
    )
    assert response.status_code == 201
    assert seen["payload"] == b"cropped-face-bytes"
    assert seen["payload"] != original


async def test_no_face_skips_the_call_and_saves_a_unit(client, flow, monkeypatch):
    """Aucun visage exploitable : inutile de payer pour un rejet certain."""
    from app.integrations.youcam import set_providers
    from app.services import appearance_service

    calls = {"n": 0}

    class LiveLikeSkinProvider:
        provider_name = "youcam_skin_ai"
        requires_face_crop = True

        async def analyze(self, image_bytes, mime_type="image/jpeg", *, file_name="look.jpg"):
            calls["n"] += 1  # pragma: no cover - ne doit jamais arriver
            raise AssertionError("Skin AI ne doit pas etre appele sans visage")

    monkeypatch.setattr(appearance_service, "crop_face_for_skin", lambda _: None)
    set_providers(skin=LiveLikeSkinProvider())

    session_id = await flow.session()
    await flow.moment(session_id)
    response = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("look.jpg", make_image(), "image/jpeg")},
    )
    assert response.status_code == 201
    assert calls["n"] == 0
    assert response.json()["skin_source"] == "unavailable_no_face"
    assert response.json()["skin"]["redness"] is None

    # Et le parcours va jusqu'au bout.
    recommendation = await flow.one_change(session_id)
    assert recommendation["action"]
