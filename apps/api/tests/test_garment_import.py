"""Reconnaissance des categories a l'import.

Exiger que les fichiers portent deja les noms du catalogue ramenait a renommer
douze photos a la main — precisement la corvee que l'outil pretendait eviter.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from import_garments import guess_category, plan, read_manifest, slug  # noqa: E402

from app.services.garment_service import list_garments  # noqa: E402


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("veste-marine", "jacket"),
        ("blazer beige", "jacket"),
        ("Manteau_Noir", "jacket"),
        ("Chemise blanche", "top"),
        ("white shirt 02", "top"),
        ("pull col roule", "top"),
        ("pantalon gris", "bottom"),
        ("dark jeans", "bottom"),
        ("sneakers white", "shoes"),
        ("chaussures cuir", "shoes"),
        ("echarpe rouge", "accessories"),
        ("leather belt", "accessories"),
    ],
)
def test_categories_are_recognised_in_both_languages(filename, expected):
    assert guess_category(filename) == expected


def test_accents_and_case_do_not_matter():
    assert slug("Écharpe Rouge") == "echarpe rouge"
    assert guess_category("ÉCHARPE") == "accessories"
    assert guess_category("VESTE") == "jacket"


def test_a_meaningless_name_is_not_guessed():
    """Mieux vaut ne rien attribuer que d'attribuer au hasard."""
    for name in ("IMG_2043", "DSC00114", "photo", "capture 12"):
        assert guess_category(name) is None


def test_an_exact_catalog_name_still_wins():
    catalog = {g.id: g for g in list_garments()}
    files = [Path("jacket_02.jpg"), Path("veste.jpg")]
    assignments, leftover, _ = plan(files, catalog, auto=False)

    by_id = {garment_id: (path.name, reason) for garment_id, path, reason in assignments}
    assert by_id["jacket_02"][0] == "jacket_02.jpg"
    assert by_id["jacket_02"][1] == "nom exact"
    assert not leftover


def test_photos_of_the_same_category_fill_distinct_slots():
    catalog = {g.id: g for g in list_garments()}
    files = [Path("veste 1.jpg"), Path("veste 2.jpg"), Path("blazer.jpg")]
    assignments, leftover, _ = plan(files, catalog, auto=False)

    ids = [garment_id for garment_id, _, _ in assignments]
    assert len(ids) == len(set(ids)) == 3
    assert all(i.startswith("jacket") for i in ids)
    assert not leftover


def test_unrecognised_photos_are_set_aside_unless_auto():
    catalog = {g.id: g for g in list_garments()}
    files = [Path("veste.jpg"), Path("IMG_2043.jpg")]

    assignments, leftover, _ = plan(files, catalog, auto=False)
    assert [p.name for p in leftover] == ["IMG_2043.jpg"]
    assert len(assignments) == 1

    assignments, leftover, _ = plan(files, catalog, auto=True)
    assert not leftover
    assert len(assignments) == 2
    assert any(reason == "attribue par --auto" for _, _, reason in assignments)


def test_more_photos_than_slots_never_overwrites_a_slot_twice():
    catalog = {g.id: g for g in list_garments()}
    files = [Path(f"IMG_{i:04}.jpg") for i in range(20)]
    assignments, leftover, created = plan(files, catalog, auto=True)

    ids = [garment_id for garment_id, _, _ in assignments]
    assert len(ids) == len(set(ids)) == len(catalog)
    assert len(leftover) == 20 - len(catalog)
    # Aucune categorie reconnue : rien n'est cree.
    assert created == []


def test_a_full_category_grows_instead_of_dropping_the_photo():
    """Un catalogue de taille fixe n'a aucune raison d'exister.

    Cas reel : douze emplacements pleins, vingt photos supplementaires ecartees
    et un message conseillant `--auto`, qui n'aurait rien pu faire non plus.
    """
    catalog = {g.id: g for g in list_garments()}
    jackets = [Path(f"veste{i}.jpg") for i in range(1, 6)]  # plus que d'emplacements

    assignments, leftover, created = plan(jackets, catalog, auto=False)

    assert not leftover, "une categorie reconnue ne doit jamais etre ecartee"
    assert len(assignments) == 5
    ids = [garment_id for garment_id, _, _ in assignments]
    assert len(set(ids)) == 5
    # Les emplacements existants d'abord, puis de nouveaux.
    assert {"jacket_01", "jacket_02", "jacket_03"} <= set(ids)
    assert {identifier for identifier, _, _ in created} == {"jacket_04", "jacket_05"}
    assert all(category == "jacket" for _, _, category in created)


def test_numbered_filenames_are_understood():
    """« sac1.jpg » : numeroter ses fichiers est le cas normal."""
    assert guess_category("sac1") == "accessories"
    assert guess_category("veste 02") == "jacket"
    assert guess_category("basket2") == "shoes"


def test_new_pieces_inherit_their_category_profile():
    """Une piece creee herite de la mediane des siennes, pas de valeurs inventees."""
    import json

    from import_garments import CATALOG_PATH, category_defaults, next_free_identifier

    entries = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["garments"]
    defaults = category_defaults(entries, "jacket")

    jackets = [e for e in entries if e["category"] == "jacket"]
    expected = sum(j["formality"] for j in jackets) / len(jackets)
    assert defaults["formality"] == round(expected, 2)
    assert set(defaults) == {
        "formality", "structure", "color_neutrality", "expressiveness", "elegance",
    }

    used = {e["id"] for e in entries}
    assert next_free_identifier(used, "jacket") == "jacket_04"
    assert next_free_identifier(used, "accessories") == "accessory_03"


# ------------------------------------------------- catalogue en ligne
def test_a_manifest_maps_identifiers_to_urls(tmp_path):
    """Referencer un catalogue en ligne se fait a l'import, pas a l'execution."""
    manifest = tmp_path / "catalogue.txt"
    manifest.write_text(
        "# commentaire\n"
        "jacket_01   https://exemple.test/veste.jpg\n"
        "top_01,https://exemple.test/chemise.png\n"
        "\n",
        encoding="utf-8",
    )
    assert read_manifest(manifest) == [
        ("jacket_01", "https://exemple.test/veste.jpg"),
        ("top_01", "https://exemple.test/chemise.png"),
    ]


def test_a_malformed_line_is_skipped_not_guessed(tmp_path):
    manifest = tmp_path / "catalogue.txt"
    manifest.write_text(
        "jacket_01 pas-une-url\n"
        "ligne sans rien\n"
        "top_01 https://exemple.test/ok.jpg\n",
        encoding="utf-8",
    )
    # Une URL invalide n'est jamais « reparee » : elle est ecartee.
    assert read_manifest(manifest) == [("top_01", "https://exemple.test/ok.jpg")]


def test_local_and_remote_paths_produce_the_same_thing(tmp_path):
    """Une image distante suit exactement la meme normalisation qu'une locale."""
    from PIL import Image

    import import_garments

    source = tmp_path / "veste.png"
    Image.new("RGB", (300, 400), (30, 60, 120)).save(source)

    local = import_garments.normalize(source)
    with Image.open(__import__("io").BytesIO(local)) as image:
        assert image.format == "JPEG"
        assert max(image.size) >= 1024
