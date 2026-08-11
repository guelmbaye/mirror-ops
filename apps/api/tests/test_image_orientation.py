"""Orientation EXIF : ce que voit l'utilisateur et ce que voit le serveur.

Un telephone stocke souvent une photo portrait en paysage, avec un tag
indiquant la rotation. Le navigateur l'applique, PIL non — l'utilisateur voit
son image droite pendant que MIRROR OPS la traite couchee.

Consequences observees : visage non detecte par Skin AI, pose illisible pour le
try-on, qualite d'image mal evaluee. Invisible dans les tests tant qu'on ne
fabrique pas d'EXIF.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.services.image_validation import validate_image


def photo(width: int, height: int, orientation: int | None = None, fmt: str = "JPEG") -> bytes:
    image = Image.new("RGB", (width, height), (190, 150, 130))
    buffer = io.BytesIO()
    if orientation is None:
        image.save(buffer, format=fmt)
    else:
        exif = image.getexif()
        exif[274] = orientation  # tag « Orientation »
        image.save(buffer, format=fmt, exif=exif)
    return buffer.getvalue()


@pytest.mark.parametrize("orientation", [6, 8])
def test_a_rotated_photo_is_straightened(orientation):
    validated = validate_image(photo(1200, 800, orientation), "image/jpeg")
    assert (validated.width, validated.height) == (800, 1200), "la photo reste couchee"


@pytest.mark.parametrize("orientation", [None, 1])
def test_an_upright_photo_is_left_alone(orientation):
    before = photo(1200, 800, orientation)
    validated = validate_image(before, "image/jpeg")
    assert (validated.width, validated.height) == (1200, 800)
    # Aucun reencodage inutile : les octets d'origine sont conserves.
    assert validated.data == before


def test_the_stored_bytes_are_the_straightened_ones():
    """Ce qui part vers YouCam doit etre l'image redressee, pas l'originale."""
    validated = validate_image(photo(1200, 800, 6), "image/jpeg")
    with Image.open(io.BytesIO(validated.data)) as stored:
        assert stored.size == (800, 1200)


def test_mirrored_orientations_are_handled():
    """Les orientations en miroir (2, 4, 5, 7) ne doivent jamais lever."""
    for orientation in (2, 3, 4, 5, 7):
        validated = validate_image(photo(1000, 700, orientation), "image/jpeg")
        assert validated.width > 0 and validated.height > 0


def test_a_png_keeps_its_format():
    validated = validate_image(photo(1000, 700, 6, fmt="PNG"), "image/png")
    assert validated.mime_type == "image/png"
    with Image.open(io.BytesIO(validated.data)) as stored:
        assert stored.format == "PNG"
        assert stored.size == (700, 1000)


def test_a_face_stays_findable_after_straightening():
    """Le cadrage visage travaille sur l'image redressee.

    Un visage couche n'est detecte par aucun classifieur frontal : c'est la
    cause silencieuse d'un `skin_source = unavailable_no_face`.
    """
    from app.services.face_crop import compute_crop_box

    validated = validate_image(photo(1200, 800, 6), "image/jpeg")
    box = compute_crop_box((300, 200, 200, 240), (validated.width, validated.height))
    assert box[2] <= validated.width and box[3] <= validated.height
