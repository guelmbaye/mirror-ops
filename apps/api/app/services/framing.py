"""Ce que la photo montre reellement.

MIRROR OPS promet trois choses : decider, expliquer, et PROUVER. La preuve
n'est pas un ornement — c'est le troisieme pilier. Recommander « replace the
shoes » sur un cliche qui s'arrete au ventre produit un before/after ou rien ne
bouge : la promesse se casse en silence, au moment ou elle compte.

Le cadrage se deduit de la taille du visage. Un visage occupant 40 % de la
hauteur est un portrait serre ; 12 %, un plan en pied. La regle est grossiere
mais robuste, et surtout elle repose sur une mesure plutot que sur le format de
l'image — un selfie en portrait passait jusqu'ici pour un plan complet.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

from app.models.enums import OutfitElement

logger = logging.getLogger("mirror_ops.framing")


class Framing(StrEnum):
    HEAD = "head"            # visage seul, quasiment aucun vetement
    CHEST = "chest"          # jusqu'a la poitrine : haut et veste
    WAIST = "waist"          # jusqu'au ventre : idem, plus large
    KNEE = "knee"            # jusqu'aux genoux : le bas apparait
    FULL = "full"            # corps entier : les chaussures aussi
    UNKNOWN = "unknown"      # aucun visage detecte : on ne prejuge de rien


#: Part de la hauteur d'image occupee par le visage, par cadrage.
#:
#: Calibre sur des photos reelles : un selfie de buste donne environ 0.35, un
#: plan en pied environ 0.08. Les paliers sont larges parce que la mesure est
#: approximative — mieux vaut restreindre trop peu que de refuser a tort une
#: piece que la photo montre.
FACE_RATIO_THRESHOLDS: tuple[tuple[float, Framing], ...] = (
    (0.45, Framing.HEAD),
    (0.26, Framing.CHEST),
    (0.18, Framing.WAIST),
    (0.12, Framing.KNEE),
)

_UPPER = frozenset({OutfitElement.TOP, OutfitElement.JACKET, OutfitElement.ACCESSORIES})

#: Ce qu'on peut esperer voir, et donc prouver, selon le cadrage.
VISIBLE_ELEMENTS: dict[Framing, frozenset[OutfitElement]] = {
    Framing.HEAD: frozenset({OutfitElement.ACCESSORIES}),
    Framing.CHEST: _UPPER,
    Framing.WAIST: _UPPER,
    Framing.KNEE: _UPPER | {OutfitElement.BOTTOM},
    Framing.FULL: frozenset(OutfitElement),
    # Sans visage detecte, on ne restreint rien : mieux vaut ne rien affirmer
    # que d'ecarter a tort une piece que la photo montre peut-etre.
    Framing.UNKNOWN: frozenset(OutfitElement),
}

HUMAN_LABEL: dict[Framing, str] = {
    Framing.HEAD: "your face only",
    Framing.CHEST: "head and chest",
    Framing.WAIST: "down to the waist",
    Framing.KNEE: "down to the knees",
    Framing.FULL: "full length",
    Framing.UNKNOWN: "unknown",
}


@dataclass(frozen=True, slots=True)
class FramingEstimate:
    framing: Framing
    face_ratio: float | None
    visible: frozenset[OutfitElement]

    @property
    def shows_full_look(self) -> bool:
        return self.framing is Framing.FULL

    def as_dict(self) -> dict:
        return {
            "framing": str(self.framing),
            "label": HUMAN_LABEL[self.framing],
            "face_ratio": None if self.face_ratio is None else round(self.face_ratio, 3),
            "visible_elements": sorted(str(element) for element in self.visible),
        }


def estimate_framing(image_bytes: bytes, face=None) -> FramingEstimate:
    """Deduit le cadrage de la taille du visage dans l'image.

    `face` evite une seconde detection : le recadrage Skin AI vient de la faire,
    et la reprendre coutait un passage complet du classifieur par analyse.
    """
    from app.services.face_crop import detect_largest_face

    if face is None:
        face = detect_largest_face(image_bytes)
    if face is None:
        return FramingEstimate(Framing.UNKNOWN, None, VISIBLE_ELEMENTS[Framing.UNKNOWN])

    height = _image_height(image_bytes)
    if not height:
        return FramingEstimate(Framing.UNKNOWN, None, VISIBLE_ELEMENTS[Framing.UNKNOWN])

    ratio = face[3] / height
    framing = Framing.FULL
    for threshold, candidate in FACE_RATIO_THRESHOLDS:
        if ratio >= threshold:
            framing = candidate
            break

    logger.info("framing_estimated", extra={"framing": str(framing), "face_ratio": round(ratio, 3)})
    return FramingEstimate(framing, ratio, VISIBLE_ELEMENTS[framing])


def _image_height(image_bytes: bytes) -> int | None:
    import io

    from PIL import Image

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            return image.height
    except Exception:  # pragma: no cover - image deja validee en amont
        return None
