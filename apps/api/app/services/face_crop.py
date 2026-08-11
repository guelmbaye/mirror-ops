"""Recadrage du visage pour Skin AI, depuis la photo de tenue.

Le probleme : Skin AI exige que le visage occupe **au moins 60 % de la largeur**
de l'image, sinon `error_src_face_too_small`. MIRROR OPS, lui, demande une photo
de la TENUE, ou le visage est forcement petit.

Deux exigences incompatibles sur une meme photo — mais le parcours doit rester a
une seule prise de vue : ajouter un second cliche ajouterait un ecran, et la
contrainte est le produit.

La reponse est donc ici : on detecte le visage cote serveur et on en extrait un
cadrage conforme. La photo d'origine, elle, reste intacte pour le VTO et pour
l'affichage — on ne recadre que ce qui part vers l'analyse de peau.

OpenCV est optionnel. S'il manque, ce module le dit et le parcours continue sans
signal peau, plutot que d'echouer : Skin AI *informe* la decision, il ne la prend
pas.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from PIL import Image

logger = logging.getLogger("mirror_ops.face_crop")

#: Part de la largeur du cadrage occupee par le visage. La specification exige
#: > 60 % ; on vise un peu au-dessus pour absorber les imprecisions de detection.
TARGET_FACE_RATIO = 0.68

#: Cote court minimal exige par l'analyse SD.
MIN_SHORT_SIDE = 480

#: En deca, le visage est trop petit dans l'original : agrandir ne creerait que
#: du flou, et l'analyse porterait sur des pixels inventes par l'interpolation.
MIN_DETECTED_FACE_WIDTH = 140


@dataclass(frozen=True, slots=True)
class FaceCrop:
    image_bytes: bytes
    mime_type: str
    width: int
    height: int
    face_ratio: float


def opencv_available() -> bool:
    """Verifiable au demarrage, plutot que decouvert au premier parcours."""
    try:
        import cv2  # noqa: F401
    except ImportError:
        return False
    return True


def detect_largest_face(image_bytes: bytes) -> tuple[int, int, int, int] | None:
    """Retourne (x, y, w, h) du plus grand visage, ou None."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    try:
        buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if frame is None:
            return None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        if cascade.empty():  # pragma: no cover - installation incomplete
            return None

        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda box: int(box[2]) * int(box[3]))
        return int(x), int(y), int(w), int(h)
    except Exception as exc:  # pragma: no cover - robustesse
        logger.warning("face_detection_failed", extra={"reason": str(exc)})
        return None


def compute_crop_box(
    face: tuple[int, int, int, int], size: tuple[int, int]
) -> tuple[int, int, int, int]:
    """Cadre centre sur le visage, dimensionne pour atteindre le ratio cible.

    Le cadre est ramene dans les bornes de l'image par translation plutot que par
    rognage : rogner reduirait la largeur et ferait remonter le ratio au-dela du
    cadrage voulu, ce qui coupe le front ou le menton.
    """
    fx, fy, fw, fh = face
    image_w, image_h = size

    crop_w = min(image_w, max(1, round(fw / TARGET_FACE_RATIO)))
    crop_h = min(image_h, max(1, round(crop_w * 4 / 3)))  # portrait, comme recommande

    center_x = fx + fw / 2
    # Le visage est place un peu au-dessus du centre : on garde le front, qui
    # porte une partie des metriques (rides, pores).
    center_y = fy + fh * 0.45

    left = round(center_x - crop_w / 2)
    top = round(center_y - crop_h / 2)
    left = max(0, min(left, image_w - crop_w))
    top = max(0, min(top, image_h - crop_h))
    return left, top, left + crop_w, top + crop_h


def crop_face_for_skin(image_bytes: bytes) -> FaceCrop | None:
    """Extrait un cadrage conforme a Skin AI, ou None si ce n'est pas possible."""
    face = detect_largest_face(image_bytes)
    if face is None:
        return None
    if face[2] < MIN_DETECTED_FACE_WIDTH:
        logger.info("face_too_small_to_crop", extra={"face_width": face[2]})
        return None

    with Image.open(io.BytesIO(image_bytes)) as source:
        image = source.convert("RGB")
        box = compute_crop_box(face, image.size)
        crop = image.crop(box)

        short_side = min(crop.size)
        if short_side < MIN_SHORT_SIDE:
            scale = MIN_SHORT_SIDE / short_side
            crop = crop.resize(
                (round(crop.width * scale), round(crop.height * scale)), Image.LANCZOS
            )

        output = io.BytesIO()
        crop.save(output, format="JPEG", quality=92)

    face_ratio = round(face[2] / (box[2] - box[0]), 3)
    return FaceCrop(
        image_bytes=output.getvalue(),
        mime_type="image/jpeg",
        width=crop.width,
        height=crop.height,
        face_ratio=face_ratio,
    )
