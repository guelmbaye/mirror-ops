"""Catalogue de vetements controle + selection du vetement gagnant.

Doc 09 Phase 8 : "Creer un petit catalogue controle... pour la demo principale,
1 winning garment is enough."

La selection est deterministe : meme moment + meme action -> meme vetement.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.errors import AppError, ErrorCode
from app.engines.one_change.contexts import target_formality
from app.engines.one_change.types import MomentSpec
from app.integrations.youcam.models import GarmentRef
from app.models.enums import ACTION_ELEMENT, ChangeAction, Goal, OutfitElement

logger = logging.getLogger("mirror_ops.garments")

CATALOG_DIR = Path(__file__).resolve().parents[1] / "assets" / "garments"

#: Ce que chaque objectif valorise dans un vetement.
GOAL_PREFERENCE: dict[Goal, dict[str, float]] = {
    Goal.PROFESSIONAL: {"formality": 0.45, "structure": 0.30, "color_neutrality": 0.20, "expressiveness": 0.00, "elegance": 0.05},
    Goal.CONFIDENT: {"formality": 0.25, "structure": 0.35, "color_neutrality": 0.15, "expressiveness": 0.10, "elegance": 0.15},
    Goal.APPROACHABLE: {"formality": 0.10, "structure": 0.15, "color_neutrality": 0.20, "expressiveness": 0.40, "elegance": 0.15},
    Goal.ELEGANT: {"formality": 0.25, "structure": 0.20, "color_neutrality": 0.10, "expressiveness": 0.05, "elegance": 0.40},
    Goal.EXPRESSIVE: {"formality": 0.05, "structure": 0.10, "color_neutrality": 0.05, "expressiveness": 0.60, "elegance": 0.20},
}

#: Action ONE CHANGE -> categorie de vetement a essayer.
ACTION_CATEGORY: dict[ChangeAction, str | None] = {
    ChangeAction.CHANGE_JACKET: "jacket",
    ChangeAction.CHANGE_TOP: "top",
    ChangeAction.CHANGE_BOTTOM: "bottom",
    ChangeAction.CHANGE_SHOES: "shoes",
    ChangeAction.CHANGE_ACCESSORY: "accessories",
    ChangeAction.CHANGE_COLOR: "top",  # le travail couleur se materialise sur le haut
    ChangeAction.NO_CHANGE: None,
}


@dataclass(frozen=True, slots=True)
class Garment:
    id: str
    category: str
    name: str
    description: str
    formality: float
    structure: float
    color_neutrality: float
    expressiveness: float
    elegance: float
    color: str
    image: str

    @property
    def image_path(self) -> Path:
        """Vos photos d'abord, les visuels livres ensuite.

        Le catalogue du depot ne contient que des aplats de substitution. Les
        ecraser a chaque mise a jour du projet — ce qui arrive des qu'on
        decompresse une archive par-dessus — detruisait silencieusement les
        photos importees. Les imports vivent donc dans `var/garments/`, que rien
        d'autre ne touche.
        """
        override = OVERRIDE_DIR / self.image
        return override if override.exists() else CATALOG_DIR / self.image

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "attributes": {
                "formality": self.formality,
                "structure": self.structure,
                "color_neutrality": self.color_neutrality,
                "expressiveness": self.expressiveness,
                "elegance": self.elegance,
            },
        }


#: Repertoire des vetements fournis par l'utilisateur. Hors du code source,
#: hors des archives, ignore par git : rien ne l'ecrase.
OVERRIDE_DIR = Path(
    os.environ.get("GARMENT_OVERRIDE_DIR", Path(__file__).resolve().parents[2] / "var" / "garments")
)


@lru_cache
def load_catalog() -> tuple[Garment, ...]:
    payload = json.loads((CATALOG_DIR / "catalog.json").read_text(encoding="utf-8"))
    entries = list(payload["garments"])

    # Les pieces ajoutees par import vivent a part, pour la meme raison.
    extra = OVERRIDE_DIR / "catalog.extra.json"
    if extra.exists():
        try:
            known = {entry["id"] for entry in entries}
            for entry in json.loads(extra.read_text(encoding="utf-8")).get("garments", []):
                if entry.get("id") not in known:
                    entries.append(entry)
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("garment_override_catalog_unreadable", extra={"path": str(extra)})

    return tuple(Garment(**entry) for entry in entries)


def list_garments(category: str | None = None) -> list[Garment]:
    garments = load_catalog()
    if category:
        return [g for g in garments if g.category == category]
    return list(garments)


def get_garment(garment_id: str) -> Garment:
    for garment in load_catalog():
        if garment.id == garment_id:
            return garment
    raise AppError(ErrorCode.NOT_FOUND, "We couldn't find that garment.")


def category_for_action(action: ChangeAction) -> str | None:
    return ACTION_CATEGORY[action]


def element_for_action(action: ChangeAction) -> OutfitElement | None:
    return ACTION_ELEMENT[action]


def score_garment(garment: Garment, moment: MomentSpec) -> float:
    """Adequation d'un vetement au moment (deterministe, explicable)."""
    preference = GOAL_PREFERENCE[moment.goal]
    target = target_formality(moment)
    formality_match = 1.0 - abs(garment.formality - target)
    return (
        preference["formality"] * formality_match
        + preference["structure"] * garment.structure
        + preference["color_neutrality"] * garment.color_neutrality
        + preference["expressiveness"] * garment.expressiveness
        + preference["elegance"] * garment.elegance
    )


def select_garment(action: ChangeAction, moment: MomentSpec) -> Garment:
    """Choisit LE vetement a envoyer au VTO pour l'action gagnante."""
    category = category_for_action(action)
    if category is None:
        raise AppError(ErrorCode.VTO_NOT_APPLICABLE, "There is no change to visualize.")
    candidates = list_garments(category)
    if not candidates:  # pragma: no cover - catalogue vide
        raise AppError(ErrorCode.VTO_FAILED, "No garment available for this change.")
    return max(candidates, key=lambda g: (score_garment(g, moment), g.id))


def normalized_garment_bytes(path: Path, *, min_long_side: int = 1024) -> bytes:
    """JPEG opaque, cote long >= 1024 px, fond blanc si transparence."""
    import io

    from PIL import Image

    with Image.open(path) as source:
        image = source.convert("RGBA")
        # Une transparence laissee telle quelle devient noire en JPEG et brouille
        # la segmentation du vetement.
        canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
        canvas.alpha_composite(image)
        flat = canvas.convert("RGB")

        long_side = max(flat.size)
        if long_side < min_long_side:
            scale = min_long_side / long_side
            flat = flat.resize(
                (round(flat.width * scale), round(flat.height * scale)), Image.LANCZOS
            )

        buffer = io.BytesIO()
        flat.save(buffer, format="JPEG", quality=94)
        return buffer.getvalue()


def to_ref(garment: Garment) -> GarmentRef:
    return GarmentRef(
        garment_id=garment.id,
        category=garment.category,
        name=garment.name,
        # Normalise avant l'envoi : quelle que soit l'image deposee dans le
        # catalogue — PNG, transparence, petite taille — le provider recoit
        # toujours un JPEG opaque assez grand. Une variable de moins quand un
        # essayage echoue.
        image_bytes=normalized_garment_bytes(garment.image_path),
        mime_type="image/jpeg",
    )
