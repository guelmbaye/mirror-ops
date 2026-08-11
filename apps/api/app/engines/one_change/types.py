"""Types du domaine decisionnel ONE CHANGE.

Ce module est volontairement pur : aucune dependance FastAPI, SQLAlchemy,
HTTP ou YouCam (Doc 07 §8/§9). Il peut etre teste isolement.
"""

from __future__ import annotations

from enum import StrEnum

from dataclasses import dataclass, field

from app.models.enums import (
    ChangeAction,
    ConfidenceLevel,
    Goal,
    Occasion,
    OutfitElement,
    TimeAvailable,
)

#: Dimensions d'apparence manipulees par le moteur (toutes normalisees 0..1).
DIMENSIONS: tuple[str, ...] = (
    "professional_presence",
    "visual_coherence",
    "confidence_proxy",
    "approachability",
    "expressiveness",
    "elegance",
)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True, slots=True)
class MomentSpec:
    occasion: Occasion
    goal: Goal
    time_available: TimeAvailable


@dataclass(frozen=True, slots=True)
class SkinObservations:
    """Observations cosmetiques normalisees (jamais un diagnostic medical)."""

    texture: float | None = None
    redness: float | None = None
    oiliness: float | None = None
    radiance: float | None = None
    available: bool = False
    source: str = "unavailable"

    def as_dict(self) -> dict[str, float]:
        return {
            k: v
            for k, v in {
                "texture": self.texture,
                "redness": self.redness,
                "oiliness": self.oiliness,
                "radiance": self.radiance,
            }.items()
            if v is not None
        }


@dataclass(frozen=True, slots=True)
class OutfitItem:
    """Etat declare/estime d'une piece de la tenue.

    `known=False` signifie que l'utilisateur n'a fourni aucun indice : le moteur
    utilise alors un a priori neutre ET abaisse sa confiance de decision.
    """

    present: bool = True
    known: bool = False
    formality: float = 0.55
    structure: float = 0.55
    color_harmony: float = 0.55
    condition: float = 0.70
    descriptor: str | None = None


@dataclass(frozen=True, slots=True)
class AppearanceSignals:
    """Sortie de la couche Perception -> entree de la couche Decision."""

    dimensions: dict[str, float]
    element_suitability: dict[OutfitElement, float]
    element_known: dict[OutfitElement, bool]
    present_elements: set[OutfitElement]
    data_confidence: float
    image_quality: float
    skin: SkinObservations = field(default_factory=SkinObservations)
    skin_signal_used: bool = False


@dataclass(frozen=True, slots=True)
class DecisionContext:
    """Objet unique consomme par le moteur (Doc 04 §3)."""

    moment: MomentSpec
    appearance: AppearanceSignals

    @property
    def valid(self) -> bool:
        return bool(self.appearance.present_elements) and self.appearance.data_confidence > 0.0


@dataclass(frozen=True, slots=True)
class CandidateFeatures:
    goal_alignment: float
    context_fit: float
    visual_impact: float
    current_gap: float
    time_fit: float
    data_confidence: float
    vto_feasibility: float

    def as_dict(self) -> dict[str, float]:
        return {
            "goal_alignment": round(self.goal_alignment, 4),
            "context_fit": round(self.context_fit, 4),
            "visual_impact": round(self.visual_impact, 4),
            "current_gap": round(self.current_gap, 4),
            "time_fit": round(self.time_fit, 4),
            "data_confidence": round(self.data_confidence, 4),
            "vto_feasibility": round(self.vto_feasibility, 4),
        }


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    action: ChangeAction
    score: float
    features: CandidateFeatures
    simplicity: float
    projected_dimensions: dict[str, float]

    def as_dict(self) -> dict:
        return {
            "action": str(self.action),
            "score": round(self.score, 2),
            "features": self.features.as_dict(),
            "simplicity": round(self.simplicity, 3),
        }


@dataclass(frozen=True, slots=True)
class Explanation:
    what: str
    why: str
    how: str
    reason: str
    dominant_factors: list[str]


class FitState(StrEnum):
    """Le look convient-il au moment ? C'est la premiere question du produit."""

    FIT = "FIT"
    ALMOST_THERE = "ALMOST_THERE"
    MISMATCH = "MISMATCH"


@dataclass(frozen=True, slots=True)
class FitAssessment:
    state: FitState
    #: 0-100 : a quel point le look actuel convient a CE moment.
    score: int
    #: La phrase affichee en premier.
    headline: str
    #: Ce qui explique le verdict, en une phrase.
    detail: str
    #: L'element qui tire l'ensemble vers le bas, s'il y en a un.
    weakest_element: str | None


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    """Resultat complet, pret a etre persiste puis expose."""

    action: ChangeAction
    label: str
    score: float
    confidence_level: ConfidenceLevel
    confidence_value: float
    explanation: Explanation
    keep: list[str]
    impact_before: dict[str, int]
    impact_after: dict[str, int]
    winner: ScoredCandidate
    runner_up: ScoredCandidate | None
    candidates: list[ScoredCandidate]
    requires_vto: bool
    #: La piece visee est-elle absente ? Un ajout, pas un remplacement.
    #: Expose explicitement plutot que devine depuis le libelle : l'interface ne
    #: doit jamais avoir a interpreter une chaine pour savoir quoi afficher.
    is_addition: bool = False
    #: Verdict d'adequation, calcule AVANT le choix du levier.
    fit: FitAssessment | None = None
