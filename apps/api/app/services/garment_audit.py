"""Detection des vetements de substitution.

Le catalogue livre est genere programmatiquement : des aplats de quelques
couleurs. C'est suffisant pour la composition locale du mode `mock`, et
totalement inexploitable par un vrai modele de try-on, qui a besoin d'une
photographie de vetement.

Symptome cote provider : la tache est acceptee, puis echoue en
`error_editing_failed`. Rien dans ce message ne pointe vers le catalogue — d'ou
ce module, qui rend le probleme evident avant qu'il ne coute une unite.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("mirror_ops.garments")

#: Une photographie compte des milliers de teintes. En deca de ce seuil, l'image
#: est une forme aplatie, pas un vetement.
PLACEHOLDER_COLOUR_CEILING = 64


@dataclass(frozen=True, slots=True)
class GarmentAudit:
    garment_id: str
    path: Path
    colours: int

    @property
    def is_placeholder(self) -> bool:
        return self.colours <= PLACEHOLDER_COLOUR_CEILING


def count_colours(path: Path) -> int:
    """Nombre de teintes distinctes, echantillonne pour rester rapide."""
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow est une dependance
        return 0

    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail((128, 128))
            colours = image.getcolors(maxcolors=1 << 16)
    except Exception as exc:  # pragma: no cover - fichier illisible
        logger.warning("garment_unreadable", extra={"path": str(path), "reason": str(exc)})
        return 0

    return len(colours) if colours else 1 << 16


def audit_garments(garments) -> list[GarmentAudit]:
    """Inspecte chaque visuel du catalogue."""
    audits: list[GarmentAudit] = []
    for garment in garments:
        path = Path(garment.image_path)
        audits.append(GarmentAudit(garment.id, path, count_colours(path)))
    return audits


def placeholder_ids(garments) -> list[str]:
    return [audit.garment_id for audit in audit_garments(garments) if audit.is_placeholder]
