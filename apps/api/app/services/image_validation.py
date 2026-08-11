"""Validation et lecture technique de l'image (Doc 08 §23, Doc 09 Phase 3).

Objectif : detecter tot une image inutilisable et l'expliquer en langage
produit ("We need a clearer view of your look"), jamais en langage technique.
"""

from __future__ import annotations

import io
import logging

import numpy as np
from PIL import Image, ImageFilter, UnidentifiedImageError

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.engines.appearance.estimator import ImageQuality

logger = logging.getLogger("mirror_ops.image")

_PIL_FORMAT_TO_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


class ValidatedImage:
    __slots__ = ("data", "mime_type", "width", "height", "size_bytes", "quality")

    def __init__(
        self,
        data: bytes,
        mime_type: str,
        width: int,
        height: int,
        quality: ImageQuality,
    ) -> None:
        self.data = data
        self.mime_type = mime_type
        self.width = width
        self.height = height
        self.size_bytes = len(data)
        self.quality = quality


def validate_image(data: bytes, declared_mime: str | None = None) -> ValidatedImage:
    settings = get_settings()

    if not data:
        raise AppError(ErrorCode.INVALID_IMAGE, "We didn't receive a photo.")
    if len(data) > settings.MAX_IMAGE_BYTES:
        raise AppError(ErrorCode.IMAGE_TOO_LARGE)

    Image.MAX_IMAGE_PIXELS = settings.MAX_IMAGE_PIXELS
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.info("image_unreadable", extra={"reason": type(exc).__name__})
        raise AppError(ErrorCode.INVALID_IMAGE, "We couldn't read this photo. Try another one.")

    original_format = (image.format or "").upper()

    # Redresser selon l'orientation EXIF.
    #
    # Un telephone stocke souvent une photo portrait en paysage, avec un tag
    # indiquant la rotation a appliquer. Le navigateur l'applique, PIL non :
    # l'utilisateur voit son image droite pendant que le serveur la traite
    # couchee. Consequences en cascade — visage non detecte par Skin AI, pose
    # illisible pour le try-on, qualite d'image mal evaluee.
    data, image = _upright(data, image, original_format)

    mime_type = _PIL_FORMAT_TO_MIME.get(original_format)
    if mime_type is None or mime_type not in settings.allowed_mime_list:
        raise AppError(ErrorCode.IMAGE_UNSUPPORTED)
    if declared_mime and declared_mime not in settings.allowed_mime_list:
        raise AppError(ErrorCode.IMAGE_UNSUPPORTED)

    width, height = image.size
    if width < settings.MIN_IMAGE_WIDTH or height < settings.MIN_IMAGE_HEIGHT:
        raise AppError(
            ErrorCode.INVALID_IMAGE,
            "We need a clearer, larger view of your look. Try retaking the photo.",
        )

    quality = assess_quality(image)
    return ValidatedImage(data, mime_type, width, height, quality)


def _upright(data: bytes, image: "Image.Image", image_format: str) -> tuple[bytes, "Image.Image"]:
    """Applique l'orientation EXIF, et reencode si l'image a tourne."""
    from PIL import ImageOps

    try:
        rotated = ImageOps.exif_transpose(image)
    except Exception:  # pragma: no cover - EXIF illisible
        return data, image

    if rotated is None or rotated.size == image.size:
        return data, image

    buffer = io.BytesIO()
    save_format = "PNG" if image_format == "PNG" else "JPEG"
    if save_format == "JPEG":
        rotated = rotated.convert("RGB")
        rotated.save(buffer, format="JPEG", quality=94)
    else:
        rotated.save(buffer, format="PNG")

    logger.info(
        "image_reoriented",
        extra={"from": f"{image.width}x{image.height}", "to": f"{rotated.width}x{rotated.height}"},
    )
    return buffer.getvalue(), rotated


def assess_quality(image: Image.Image) -> ImageQuality:
    """Qualite technique -> alimente uniquement la confiance de decision."""
    settings = get_settings()
    grayscale = image.convert("L").resize((160, 160))
    array = np.asarray(grayscale, dtype=np.float32) / 255.0

    brightness = float(array.mean())
    edges = np.asarray(grayscale.filter(ImageFilter.FIND_EDGES), dtype=np.float32) / 255.0
    sharpness = float(min(1.0, edges.std() * 6.0))

    width, height = image.size
    resolution_score = float(
        min(1.0, (width * height) / (settings.MIN_IMAGE_WIDTH * settings.MIN_IMAGE_HEIGHT * 6.0))
    )
    brightness_score = 1.0 - min(1.0, abs(brightness - 0.52) / 0.42)
    portrait_ratio = height / max(width, 1)
    full_look_visible = portrait_ratio >= 1.15

    score = float(
        max(
            0.0,
            min(
                1.0,
                0.40 * brightness_score
                + 0.35 * sharpness
                + 0.25 * resolution_score,
            ),
        )
    )
    return ImageQuality(
        score=round(score, 4),
        brightness=round(brightness, 4),
        sharpness=round(sharpness, 4),
        resolution_score=round(resolution_score, 4),
        full_look_visible=full_look_visible,
    )
