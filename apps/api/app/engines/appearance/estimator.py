"""Construction de l'Appearance Context (Doc 05 §9, Doc 09 Phase 5).

    Moment + Skin AI + tenue declaree + qualite d'image  ->  AppearanceSignals

Honnetete du modele (Doc 06 §25 "no fabricated visual analysis") :
- lorsque l'utilisateur ne fournit aucun indice sur une piece, on utilise un
  a priori neutre EXPLICITE et on abaisse la confiance de decision ;
- on n'invente jamais une mesure visuelle que l'on ne possede pas ;
- le signal peau n'influence l'apparence que s'il est materiel, et de facon
  bornee (Doc 06 §19 : "Skin AI informs; it does not hijack the decision").
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import pstdev

from app.engines.one_change.tables import (
    ELEMENT_WEIGHT,
    SKIN_MATERIALITY_THRESHOLDS,
    SKIN_MAX_INFLUENCE,
    UNKNOWN_ITEM_SUITABILITY,
)
from app.engines.one_change.contexts import target_formality
from app.engines.one_change.types import (
    AppearanceSignals,
    MomentSpec,
    OutfitItem,
    SkinObservations,
    clamp,
)
from app.models.enums import OutfitElement

#: Poids par dimension pour agreger les pieces (heuristiques produit).
DIMENSION_ELEMENT_WEIGHTS: dict[str, dict[OutfitElement, float]] = {
    "professional_presence": {
        OutfitElement.JACKET: 0.38, OutfitElement.TOP: 0.24, OutfitElement.BOTTOM: 0.18,
        OutfitElement.SHOES: 0.14, OutfitElement.ACCESSORIES: 0.06,
    },
    "elegance": {
        OutfitElement.JACKET: 0.28, OutfitElement.TOP: 0.22, OutfitElement.BOTTOM: 0.16,
        OutfitElement.SHOES: 0.24, OutfitElement.ACCESSORIES: 0.10,
    },
}


@dataclass(frozen=True, slots=True)
class ImageQuality:
    """Signaux techniques d'image, utilises uniquement pour la confiance."""

    score: float = 0.7
    brightness: float | None = None
    sharpness: float | None = None
    resolution_score: float | None = None
    full_look_visible: bool = True

    def as_dict(self) -> dict[str, float | bool | None]:
        return {
            "score": round(self.score, 3),
            "brightness": None if self.brightness is None else round(self.brightness, 3),
            "sharpness": None if self.sharpness is None else round(self.sharpness, 3),
            "resolution_score": None
            if self.resolution_score is None
            else round(self.resolution_score, 3),
            "full_look_visible": self.full_look_visible,
        }


def item_suitability(item: OutfitItem, moment: MomentSpec) -> float:
    """Adequation d'une piece au moment (0..1).

    40% adequation de formalite / 25% structure / 20% harmonie couleur / 15% etat.

    Si la piece n'est pas decrite (`known=False`), on renvoie un a priori moyen
    explicite plutot qu'un score derive d'attributs que l'on n'a pas mesures.
    """
    if not item.known:
        return UNKNOWN_ITEM_SUITABILITY
    target = target_formality(moment)
    formality_match = 1.0 - abs(item.formality - target)
    return clamp(
        0.40 * formality_match
        + 0.25 * item.structure
        + 0.20 * item.color_harmony
        + 0.15 * item.condition
    )


def _weighted_mean(values: dict[OutfitElement, float], weights: dict[OutfitElement, float]) -> float:
    usable = {e: v for e, v in values.items() if e in weights}
    total_weight = sum(weights[e] for e in usable) or 1.0
    return clamp(sum(v * weights[e] for e, v in usable.items()) / total_weight)


def _skin_material_signal(skin: SkinObservations) -> tuple[bool, float]:
    """Le signal peau est-il materiel ? Retourne (materiel, penalite bornee)."""
    if not skin.available:
        return False, 0.0
    penalty = 0.0
    material = False
    for name, threshold in SKIN_MATERIALITY_THRESHOLDS.items():
        value = getattr(skin, name, None)
        if value is not None and value > threshold:
            material = True
            penalty += (value - threshold) * 0.5
    return material, min(SKIN_MAX_INFLUENCE, penalty)


def build_appearance_signals(
    moment: MomentSpec,
    outfit: dict[OutfitElement, OutfitItem],
    skin: SkinObservations,
    image_quality: ImageQuality,
) -> AppearanceSignals:
    present = {e for e, item in outfit.items() if item.present}
    suitability = {e: item_suitability(outfit[e], moment) for e in present}
    known = {e: outfit[e].known for e in present}

    if not present:
        return AppearanceSignals(
            dimensions={},
            element_suitability={},
            element_known={},
            present_elements=set(),
            data_confidence=0.0,
            image_quality=image_quality.score,
            skin=skin,
        )

    values = list(suitability.values())
    mean_suitability = sum(values) / len(values)
    dispersion = pstdev(values) if len(values) > 1 else 0.0

    formality_gap = sum(
        abs(outfit[e].formality - target_formality(moment)) for e in present
    ) / len(present)
    color_harmony = sum(outfit[e].color_harmony for e in present) / len(present)
    structure = sum(outfit[e].structure for e in present) / len(present)

    skin_material, skin_penalty = _skin_material_signal(skin)

    professional_presence = _weighted_mean(
        suitability, DIMENSION_ELEMENT_WEIGHTS["professional_presence"]
    )
    elegance = _weighted_mean(suitability, DIMENSION_ELEMENT_WEIGHTS["elegance"])
    visual_coherence = clamp(0.85 * mean_suitability + 0.15 * (1.0 - min(1.0, dispersion * 3.0)))
    confidence_proxy = clamp(
        0.55 * ((professional_presence + visual_coherence) / 2.0)
        + 0.25 * mean_suitability
        + 0.20 * image_quality.score
        - skin_penalty
    )
    approachability = clamp(
        0.45 * (1.0 - formality_gap) + 0.30 * color_harmony + 0.25 * (1.0 - structure * 0.5)
    )
    expressiveness = clamp(
        0.45 * color_harmony
        + 0.30 * (1.0 if OutfitElement.ACCESSORIES in present else 0.35)
        + 0.25 * min(1.0, dispersion * 2.0)
    )

    dimensions = {
        "professional_presence": round(professional_presence, 4),
        "visual_coherence": round(visual_coherence, 4),
        "confidence_proxy": round(confidence_proxy, 4),
        "approachability": round(approachability, 4),
        "expressiveness": round(expressiveness, 4),
        "elegance": round(elegance, 4),
    }

    known_ratio = sum(1 for e in present if known[e]) / len(present)
    presence_ratio = len(present) / len(OutfitElement)
    data_confidence = clamp(
        image_quality.score * (0.62 + 0.28 * known_ratio + 0.10 * presence_ratio)
        + (0.05 if skin.available else 0.0)
    )

    return AppearanceSignals(
        dimensions=dimensions,
        element_suitability=suitability,
        element_known=known,
        present_elements=present,
        data_confidence=round(data_confidence, 4),
        image_quality=image_quality.score,
        skin=skin,
        skin_signal_used=skin_material,
    )


def default_outfit() -> dict[OutfitElement, OutfitItem]:
    """Tenue par defaut : toutes les pieces presentes, aucune connue precisement."""
    return {element: OutfitItem(present=True, known=False) for element in OutfitElement}


def element_weight(element: OutfitElement) -> float:
    return ELEMENT_WEIGHT[element]
