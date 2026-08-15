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


def test_a_false_detection_low_in_the_frame_is_rejected():
    """Cas reel : lunettes de soleil, et le classifieur par defaut a designe un
    morceau de veste a mi-hauteur. Le produit envoyait alors du tissu a Skin AI
    et en deduisait un cadrage faux.
    """
    from app.services.face_crop import _plausible

    # Une boite plausible : haut de l'image, taille raisonnable.
    assert _plausible((376, 502, 906, 906), (1920, 2560)) is True
    # La fausse detection observee : centre a 66 % de la hauteur.
    assert _plausible((897, 1579, 213, 213), (1920, 2560)) is False
    # Minuscule, ou couvrant tout : ecartees aussi.
    assert _plausible((10, 10, 40, 40), (1920, 2560)) is False
    assert _plausible((0, 0, 1900, 400), (1920, 2560)) is False


def test_several_cascades_are_tried():
    """Un seul classifieur ne suffit pas : `default` echoue sur des lunettes."""
    from app.services.face_crop import CASCADES

    assert len(CASCADES) >= 2
    assert CASCADES[0] == "haarcascade_frontalface_alt2.xml"


def test_opencv_5_is_named_as_the_cause(monkeypatch):
    """OpenCV 5.0 a SUPPRIME les cascades de Haar.

    `CascadeClassifier` n'existe plus et `cv2.data.haarcascades` pointe vers un
    repertoire vide. Un `pip install opencv-python-headless` sans borne haute
    installe 5.x : le module s'importe proprement et echoue a chaque appel.
    Verifie contre une vraie installation d'OpenCV 5.0.0.
    """
    import sys
    import types

    from app.services import face_crop

    five = types.ModuleType("cv2")
    five.__version__ = "5.0.0"
    five.data = types.SimpleNamespace(haarcascades="/empty/")
    monkeypatch.setitem(sys.modules, "cv2", five)

    ready, reason = face_crop.opencv_status()
    assert ready is False
    assert "5.0.0" in reason
    assert "removed Haar cascades" in reason
    assert '>=4.10,<5' in reason, "the message must carry the exact fix"


def test_an_unrelated_cv2_is_also_caught(monkeypatch):
    """Le paquet PyPI nomme `cv2` masque le vrai module."""
    import sys
    import types

    from app.services import face_crop

    stub = types.ModuleType("cv2")
    stub.__version__ = "0.0.1"
    stub.__file__ = "/site-packages/cv2/__init__.py"
    monkeypatch.setitem(sys.modules, "cv2", stub)

    ready, reason = face_crop.opencv_status()
    assert ready is False
    assert "not usable OpenCV" in reason


def test_the_requirement_is_pinned_below_five():
    """Sans borne haute, pip installe 5.x et la detection meurt en silence."""
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if l.startswith("opencv-python-headless"))
    assert "<5" in line, f"unpinned: {line}"


def test_a_missing_opencv_is_reported_plainly(monkeypatch):
    import builtins

    from app.services import face_crop

    real_import = builtins.__import__

    def fail(name, *args, **kwargs):
        if name == "cv2":
            raise ImportError("No module named 'cv2'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail)
    ready, reason = face_crop.opencv_status()
    assert ready is False
    assert "not installed" in reason


def test_detection_is_not_repeated_for_the_same_photo():
    """Une analyse detectait le visage deux fois — 560 ms perdues a chaque appel."""
    import io

    import numpy as np
    from PIL import Image

    from app.services import face_crop

    noise = (np.random.default_rng(4).random((700, 500, 3)) * 200 + 30).astype("uint8")
    buffer = io.BytesIO()
    Image.fromarray(noise, "RGB").save(buffer, format="JPEG")
    data = buffer.getvalue()

    calls = {"n": 0}
    original = face_crop._detect

    def counting(image_bytes):
        calls["n"] += 1
        return original(image_bytes)

    face_crop._LAST_DETECTION = None
    face_crop._detect = counting
    try:
        first = face_crop.detect_largest_face(data)
        second = face_crop.detect_largest_face(data)
    finally:
        face_crop._detect = original
        face_crop._LAST_DETECTION = None

    assert first == second
    assert calls["n"] == 1, "the second call re-ran the classifiers"


def test_the_crop_dominates_both_dimensions():
    """Le visage doit depasser 60 % en largeur ET en hauteur.

    Un premier reglage (0.68, cadrage 4:3) satisfaisait la largeur et laissait
    le visage a 51 % de la hauteur — et YouCam repondait quand meme
    `error_src_face_too_small`. Leur mesure porte peut-etre sur une autre
    dimension ; viser large sur les deux axes coute peu et leve le doute.
    """
    from app.services.face_crop import FALLBACK_FACE_RATIO, TARGET_FACE_RATIO

    face = (376, 502, 906, 906)
    size = (1920, 2560)

    for target in (TARGET_FACE_RATIO, FALLBACK_FACE_RATIO):
        box = compute_crop_box(face, size, target)
        width, height = box[2] - box[0], box[3] - box[1]
        assert face[2] / width >= 0.60, f"width ratio too low at target {target}"
        assert face[3] / height >= 0.60, f"height ratio too low at target {target}"

    assert FALLBACK_FACE_RATIO > TARGET_FACE_RATIO


async def test_a_too_small_face_triggers_exactly_one_tighter_retry(client, flow):
    """Une seconde tentative, jamais une boucle : chaque essai coute une unite."""
    from app.integrations.youcam import set_providers
    from app.integrations.youcam.exceptions import YouCamInvalidImageError
    from tests.conftest import make_image

    attempts: list[int] = []

    class TooSmallThenFine:
        provider_name = "youcam_skin_ai"
        requires_face_crop = True

        async def analyze(self, image_bytes, mime_type="image/jpeg", *, file_name="look.jpg"):
            attempts.append(len(image_bytes))
            raise YouCamInvalidImageError(
                "Provider task failed (error)",
                detail="error_src_face_too_small",
                provider_code="error_src_face_too_small",
            )

    set_providers(skin=TooSmallThenFine())
    session_id = await flow.session()
    await flow.moment(session_id)
    response = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("look.jpg", make_image(noisy=True), "image/jpeg")},
    )

    # Le parcours continue sans signal peau, quoi qu'il arrive.
    assert response.status_code == 201
    assert response.json()["skin_source"] in {"unavailable", "unavailable_no_face"}
    assert len(attempts) <= 2, f"retried {len(attempts)} times"


def test_the_ratio_is_calibrated_against_the_real_api():
    """Trois ratios ont ete verifies contre l'API reelle, tous acceptes.

    Le choix ne se joue donc pas sur la conformite mais sur la qualite : plus le
    cadrage est serre, plus il faut l'agrandir, et plus les pixels sont
    interpoles — or `texture` est l'une des metriques mesurees.
    """
    from app.services.face_crop import (
        CROP_ASPECT,
        FALLBACK_FACE_RATIO,
        MIN_SHORT_SIDE,
        TARGET_FACE_RATIO,
        compute_crop_box,
    )

    # Le plan en pied de reference : visage de 289 px dans 1306x4080.
    face = (476, 1106, 289, 289)
    size = (1306, 4080)

    box = compute_crop_box(face, size, TARGET_FACE_RATIO)
    width, height = box[2] - box[0], box[3] - box[1]

    # Les deux axes restent au-dessus de la regle des 60 %.
    assert face[2] / width >= 0.60
    assert face[3] / height >= 0.60

    # Et l'agrandissement reste plus doux qu'au reglage precedent (0.80).
    previous = compute_crop_box(face, size, 0.80)
    previous_short = min(previous[2] - previous[0], previous[3] - previous[1])
    assert min(width, height) > previous_short, "the crop should keep more real pixels"

    assert TARGET_FACE_RATIO < FALLBACK_FACE_RATIO
    assert CROP_ASPECT > 1.0, "slightly portrait, to keep forehead and chin"


def test_a_face_too_small_message_names_the_real_cause():
    """La photo REFUSEE portait un visage de 906 px ; celle qui passe, 289 px.

    Ce code ne parle donc pas de taille mais de detection : le message doit
    dire ce qui aide vraiment.
    """
    from app.services.photo_guidance import guidance_for

    message = guidance_for("error_src_face_too_small")
    assert "sunglasses" in message
    assert "closer" not in message, "size is not the actual problem"
