"""Enumerations partagees entre le domaine, l'API et la base."""

from __future__ import annotations

from enum import StrEnum


class SessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"
    FAILED = "failed"


class SessionState(StrEnum):
    """Machine a etats du parcours (Doc 08 §21)."""

    SESSION_CREATED = "SESSION_CREATED"
    MOMENT_CREATED = "MOMENT_CREATED"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    DECISION_COMPLETED = "DECISION_COMPLETED"
    VTO_PROCESSING = "VTO_PROCESSING"
    VTO_COMPLETED = "VTO_COMPLETED"
    SESSION_COMPLETED = "SESSION_COMPLETED"


#: Ordre canonique du parcours -> permet de rejeter les transitions impossibles.
STATE_ORDER: dict[SessionState, int] = {
    SessionState.SESSION_CREATED: 0,
    SessionState.MOMENT_CREATED: 1,
    SessionState.ANALYSIS_COMPLETED: 2,
    SessionState.DECISION_COMPLETED: 3,
    SessionState.VTO_PROCESSING: 4,
    SessionState.VTO_COMPLETED: 5,
    SessionState.SESSION_COMPLETED: 6,
}


class Occasion(StrEnum):
    INTERVIEW = "interview"
    PRESENTATION = "presentation"
    DATE = "date"
    BUSINESS = "business"
    EVENT = "event"
    # Occasions ajoutees par le positionnement « Contextual » (§4) : un meme
    # look peut convenir a un diner et pas a un mariage.
    WEDDING = "wedding"
    CONFERENCE = "conference"
    DINNER = "dinner"
    TRAVEL = "travel"
    OTHER = "other"


class Goal(StrEnum):
    CONFIDENT = "confident"
    PROFESSIONAL = "professional"
    APPROACHABLE = "approachable"
    ELEGANT = "elegant"
    EXPRESSIVE = "expressive"


class TimeAvailable(StrEnum):
    UNDER_5M = "<5m"
    FROM_5_TO_15M = "5_15m"
    FROM_15_TO_30M = "15_30m"
    OVER_30M = "30m_plus"


class ChangeAction(StrEnum):
    CHANGE_JACKET = "CHANGE_JACKET"
    CHANGE_TOP = "CHANGE_TOP"
    CHANGE_BOTTOM = "CHANGE_BOTTOM"
    CHANGE_SHOES = "CHANGE_SHOES"
    CHANGE_ACCESSORY = "CHANGE_ACCESSORY"
    CHANGE_COLOR = "CHANGE_COLOR"
    #: Parfois la bonne intervention est de RETIRER, pas de remplacer (§5).
    REMOVE_ACCESSORY = "REMOVE_ACCESSORY"
    NO_CHANGE = "NO_CHANGE"


class OutfitElement(StrEnum):
    JACKET = "jacket"
    TOP = "top"
    BOTTOM = "bottom"
    SHOES = "shoes"
    ACCESSORIES = "accessories"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VTOStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


#: Action -> element cible (NO_CHANGE et CHANGE_COLOR n'ont pas d'element unique)
ACTION_ELEMENT: dict[ChangeAction, OutfitElement | None] = {
    ChangeAction.CHANGE_JACKET: OutfitElement.JACKET,
    ChangeAction.CHANGE_TOP: OutfitElement.TOP,
    ChangeAction.CHANGE_BOTTOM: OutfitElement.BOTTOM,
    ChangeAction.CHANGE_SHOES: OutfitElement.SHOES,
    ChangeAction.CHANGE_ACCESSORY: OutfitElement.ACCESSORIES,
    ChangeAction.REMOVE_ACCESSORY: OutfitElement.ACCESSORIES,
    ChangeAction.CHANGE_COLOR: None,
    ChangeAction.NO_CHANGE: None,
}

#: Libelles produit (Doc 04 §17 : "label")
ACTION_LABEL: dict[ChangeAction, str] = {
    ChangeAction.CHANGE_JACKET: "Change the jacket",
    ChangeAction.CHANGE_TOP: "Change the top",
    ChangeAction.CHANGE_BOTTOM: "Change the bottom",
    ChangeAction.CHANGE_SHOES: "Replace the shoes",
    ChangeAction.CHANGE_ACCESSORY: "Change one accessory",
    ChangeAction.REMOVE_ACCESSORY: "Remove the accessory",
    # Le libelle dit ce que la preuve visuelle montrera vraiment.
    ChangeAction.CHANGE_COLOR: "Change the top for a better colour",
    ChangeAction.NO_CHANGE: "Don't change it",
}

#: Quand la piece est absente, l'intervention n'est pas un remplacement mais un
#: ajout. Dire « change the jacket » a quelqu'un qui n'en porte pas est faux —
#: et le produit perd immediatement sa credibilite.
ACTION_LABEL_ADD: dict[ChangeAction, str] = {
    ChangeAction.CHANGE_JACKET: "Add a jacket",
    ChangeAction.CHANGE_ACCESSORY: "Add one accessory",
}

#: Elements qu'il est sense d'ajouter s'ils manquent. On n'« ajoute » pas un bas
#: ou des chaussures : leur absence dans la description signifie qu'on ne les
#: voit pas, pas qu'ils n'existent pas.
#: Nom lisible d'un element, pour les phrases que lit l'utilisateur.
ELEMENT_LABEL: dict[OutfitElement, str] = {
    OutfitElement.JACKET: "jacket",
    OutfitElement.TOP: "top",
    OutfitElement.BOTTOM: "bottom",
    OutfitElement.SHOES: "shoes",
    OutfitElement.ACCESSORIES: "accessories",
}

#: L'element que l'intervention touche REELLEMENT.
#:
#: « Adjust the colour balance » est une intention ; sur l'image, elle se
#: materialise par un changement de haut. Si le produit ne le sait pas, il
#: affiche « Keep · Top » pendant que l'apercu remplace le haut — et se
#: contredit sous les yeux de l'utilisateur.
MATERIALISED_ELEMENT: dict[ChangeAction, "OutfitElement | None"] = {
    **ACTION_ELEMENT,
    ChangeAction.CHANGE_COLOR: OutfitElement.TOP,
}

ADDABLE_ELEMENTS = frozenset({OutfitElement.JACKET, OutfitElement.ACCESSORIES})
