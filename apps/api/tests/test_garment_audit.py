"""Le catalogue livre doit s'annoncer pour ce qu'il est.

Les visuels sont generes programmatiquement : des aplats. Le mode `mock` les
compose sans probleme, un vrai try-on echoue dessus en `error_editing_failed` —
un message qui ne mentionne jamais le catalogue. Ces tests garantissent que le
produit le signale de lui-meme.
"""

from __future__ import annotations

import io

from PIL import Image

from app.services.garment_audit import (
    PLACEHOLDER_COLOUR_CEILING,
    GarmentAudit,
    audit_garments,
    count_colours,
    placeholder_ids,
)
from app.services.garment_service import list_garments


def test_the_shipped_catalog_is_detected_as_placeholder():
    """Constat, pas reproche : il faut que le produit le sache."""
    ids = placeholder_ids(list_garments())
    assert ids, "si le catalogue devient reel, ce test doit etre retire"
    assert len(ids) == len(list_garments())


def test_a_photograph_is_not_flagged(tmp_path):
    import numpy as np

    noise = (np.random.default_rng(7).random((256, 256, 3)) * 255).astype("uint8")
    path = tmp_path / "real.png"
    Image.fromarray(noise, "RGB").save(path)

    assert count_colours(path) > PLACEHOLDER_COLOUR_CEILING


def test_a_flat_shape_is_flagged(tmp_path):
    path = tmp_path / "flat.png"
    image = Image.new("RGB", (512, 512), (240, 240, 236))
    for box in [(80, 60, 430, 300), (150, 300, 360, 460)]:
        Image.Image.paste(image, Image.new("RGB", (box[2] - box[0], box[3] - box[1]), (40, 50, 70)), box)
    image.save(path)

    assert count_colours(path) <= PLACEHOLDER_COLOUR_CEILING


def test_an_unreadable_file_never_raises(tmp_path):
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not-an-image")
    assert count_colours(broken) == 0


def test_the_audit_reports_every_garment():
    audits = audit_garments(list_garments())
    assert len(audits) == len(list_garments())
    assert all(isinstance(a, GarmentAudit) and a.colours >= 0 for a in audits)


async def test_health_announces_a_placeholder_catalog(client):
    body = (await client.get("/api/v1/health/dependencies")).json()
    assert body["garments"] == "placeholder"


async def test_the_catalog_says_which_pieces_are_real(client):
    """Une trace doit repondre seule a « ce vetement est-il une vraie photo ? ».

    Un essayage a reussi sur `jacket_01` et echoue sur `top_01`, sans qu'aucune
    reponse d'API ne permette de savoir lequel des deux avait ete remplace.
    """
    body = (await client.get("/api/v1/garments")).json()
    assert body["garments"], "le catalogue ne doit pas etre vide"

    for garment in body["garments"]:
        assert "placeholder" in garment, garment["id"]
        assert isinstance(garment["placeholder"], bool)

    # Le drapeau doit concorder avec l'audit d'images.
    from app.services.garment_audit import placeholder_ids
    from app.services.garment_service import list_garments

    expected = set(placeholder_ids(list_garments()))
    reported = {g["id"] for g in body["garments"] if g["placeholder"]}
    assert reported == expected


async def test_the_flag_follows_a_real_import(client, tmp_path, monkeypatch):
    """Remplacer un visuel doit faire basculer le drapeau, sans redemarrage."""
    import numpy as np
    from PIL import Image

    from app.services.garment_service import list_garments

    target = next(g for g in list_garments() if g.id == "jacket_01")
    original = target.image_path.read_bytes()
    try:
        noise = (np.random.default_rng(11).random((900, 700, 3)) * 200 + 30).astype("uint8")
        Image.fromarray(noise, "RGB").save(target.image_path)

        body = (await client.get("/api/v1/garments?category=jacket")).json()
        flags = {g["id"]: g["placeholder"] for g in body["garments"]}
        assert flags["jacket_01"] is False
        assert flags["jacket_02"] is True
    finally:
        target.image_path.write_bytes(original)


async def test_user_images_override_the_shipped_ones(tmp_path, monkeypatch):
    """Une mise a jour du projet ne doit jamais effacer les photos importees.

    Incident reel : l'archive du projet contient les visuels de substitution.
    La decompresser par-dessus le projet ecrasait les vetements importes, et
    `error_editing_failed` revenait sans que rien n'ait change en apparence.
    """
    import numpy as np
    from PIL import Image

    from app.services import garment_service

    override = tmp_path / "garments"
    override.mkdir()
    monkeypatch.setattr(garment_service, "OVERRIDE_DIR", override)

    garment = garment_service.list_garments()[0]
    shipped = garment.image_path
    assert shipped.parent.name == "garments"
    assert "assets" in str(shipped), "sans surcharge, on sert bien le visuel livre"

    noise = (np.random.default_rng(3).random((900, 700, 3)) * 200 + 30).astype("uint8")
    Image.fromarray(noise, "RGB").save(override / garment.image)

    # La photo de l'utilisateur prime, et le fichier livre n'a pas bouge.
    assert garment.image_path.parent == override
    assert count_colours(shipped) <= PLACEHOLDER_COLOUR_CEILING
    assert count_colours(garment.image_path) > PLACEHOLDER_COLOUR_CEILING


def test_extra_catalog_entries_come_from_the_user_directory(tmp_path, monkeypatch):
    """Les pieces ajoutees survivent aussi a une mise a jour."""
    import json

    from app.services import garment_service

    override = tmp_path / "garments"
    override.mkdir()
    (override / "catalog.extra.json").write_text(
        json.dumps({
            "garments": [{
                "id": "jacket_99", "category": "jacket", "name": "Imported",
                "description": "", "formality": 0.7, "structure": 0.7,
                "color_neutrality": 0.7, "expressiveness": 0.4, "elegance": 0.7,
                "color": "#333333", "image": "jacket_99.png",
            }]
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(garment_service, "OVERRIDE_DIR", override)
    garment_service.load_catalog.cache_clear()

    try:
        ids = {g.id for g in garment_service.list_garments()}
        assert "jacket_99" in ids
        # Le catalogue du depot n'a pas ete modifie.
        shipped = json.loads(
            (garment_service.CATALOG_DIR / "catalog.json").read_text(encoding="utf-8")
        )
        assert all(e["id"] != "jacket_99" for e in shipped["garments"])
    finally:
        garment_service.load_catalog.cache_clear()


def test_a_garment_worn_by_someone_is_flagged(tmp_path, monkeypatch):
    """L'essayage attend une piece SEULE.

    Une photo de quelqu'un portant le vetement demande au modele de deviner ou
    s'arrete la piece et ou commence la personne. Cause probable d'un
    `error_editing_failed` alors que l'image est nette et bien definie — le
    catalogue passait alors tous les controles precedents.
    """
    from app.services import garment_audit

    monkeypatch.setattr(garment_audit, "detect_largest_face", None, raising=False)
    monkeypatch.setattr(
        "app.services.face_crop.detect_largest_face", lambda _: (10, 10, 200, 200)
    )

    photo = tmp_path / "worn.jpg"
    photo.write_bytes(b"not-really-an-image")
    assert garment_audit.shows_a_person(photo) is True

    monkeypatch.setattr("app.services.face_crop.detect_largest_face", lambda _: None)
    assert garment_audit.shows_a_person(photo) is False


def test_usability_requires_both_checks():
    from app.services.garment_audit import GarmentAudit

    from pathlib import Path

    flat = GarmentAudit("a", Path("a.png"), colours=14, shows_a_person=False)
    worn = GarmentAudit("b", Path("b.png"), colours=9000, shows_a_person=True)
    good = GarmentAudit("c", Path("c.png"), colours=9000, shows_a_person=False)

    assert flat.is_usable is False
    assert worn.is_usable is False
    assert good.is_usable is True


def test_the_summary_never_contradicts_the_listing():
    """Le script annoncait « 2 visuels montrent quelqu'un » puis « tous
    exploitables ». Un resume qui contredit sa propre liste ne sert a rien."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    import check_garments

    source = Path(check_garments.__file__).read_text(encoding="utf-8")
    # Le verdict final doit se fonder sur l'utilisabilite, pas sur le seul aplat.
    verdict = source.split("tous exploitables")[0]
    assert "unusable" in verdict, "the final verdict still ignores the worn check"
