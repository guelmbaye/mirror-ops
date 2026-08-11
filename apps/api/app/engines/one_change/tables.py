"""Tables de configuration du moteur ONE CHANGE.

Doc 04 §5 : "Les ponderations sont configurables dans une table de configuration,
pas codees directement dans l'interface."

IMPORTANT : ces valeurs sont des heuristiques produit, pas des affirmations
scientifiques (Doc 04 §6). Elles sont destinees a etre calibrees.
"""

from __future__ import annotations

from app.models.enums import ChangeAction, Goal, Occasion, OutfitElement, TimeAvailable

HIGH, MEDIUM, LOW = 0.90, 0.65, 0.35

CHANGE_ACTIONS: tuple[ChangeAction, ...] = (
    ChangeAction.CHANGE_JACKET,
    ChangeAction.CHANGE_TOP,
    ChangeAction.CHANGE_BOTTOM,
    ChangeAction.CHANGE_SHOES,
    ChangeAction.CHANGE_ACCESSORY,
    ChangeAction.CHANGE_COLOR,
)

# --------------------------------------------------------------------------- #
# 1. Ponderation du score final (Doc 06 §9). Somme = 1.0
# --------------------------------------------------------------------------- #
SCORE_WEIGHTS: dict[str, float] = {
    "goal_alignment": 0.25,
    "context_fit": 0.20,
    "visual_impact": 0.20,
    "current_gap": 0.10,
    "time_fit": 0.10,
    "data_confidence": 0.10,
    "vto_feasibility": 0.05,
}

# --------------------------------------------------------------------------- #
# 2. Vecteurs d'objectif (Doc 06 §6). Somme = 1.0 par objectif.
# --------------------------------------------------------------------------- #
GOAL_VECTORS: dict[Goal, dict[str, float]] = {
    Goal.PROFESSIONAL: {
        "professional_presence": 0.35, "visual_coherence": 0.25, "confidence_proxy": 0.20,
        "approachability": 0.15, "expressiveness": 0.05, "elegance": 0.00,
    },
    Goal.CONFIDENT: {
        "professional_presence": 0.15, "visual_coherence": 0.25, "confidence_proxy": 0.35,
        "approachability": 0.15, "expressiveness": 0.05, "elegance": 0.05,
    },
    Goal.APPROACHABLE: {
        "professional_presence": 0.05, "visual_coherence": 0.20, "confidence_proxy": 0.25,
        "approachability": 0.35, "expressiveness": 0.15, "elegance": 0.00,
    },
    Goal.ELEGANT: {
        "professional_presence": 0.05, "visual_coherence": 0.30, "confidence_proxy": 0.20,
        "approachability": 0.00, "expressiveness": 0.10, "elegance": 0.35,
    },
    Goal.EXPRESSIVE: {
        "professional_presence": 0.00, "visual_coherence": 0.20, "confidence_proxy": 0.25,
        "approachability": 0.15, "expressiveness": 0.35, "elegance": 0.05,
    },
}

# --------------------------------------------------------------------------- #
# 3. Vecteurs de contexte / occasion (Doc 04 §5). Somme = 1.0 par occasion.
# --------------------------------------------------------------------------- #
OCCASION_VECTORS: dict[Occasion, dict[str, float]] = {
    Occasion.INTERVIEW: {
        "professional_presence": 0.40, "visual_coherence": 0.25, "confidence_proxy": 0.20,
        "approachability": 0.10, "expressiveness": 0.05, "elegance": 0.00,
    },
    Occasion.PRESENTATION: {
        "professional_presence": 0.35, "visual_coherence": 0.25, "confidence_proxy": 0.20,
        "approachability": 0.15, "expressiveness": 0.05, "elegance": 0.00,
    },
    Occasion.BUSINESS: {
        "professional_presence": 0.35, "visual_coherence": 0.25, "confidence_proxy": 0.20,
        "approachability": 0.10, "expressiveness": 0.00, "elegance": 0.10,
    },
    Occasion.DATE: {
        "professional_presence": 0.05, "visual_coherence": 0.20, "confidence_proxy": 0.25,
        "approachability": 0.35, "expressiveness": 0.15, "elegance": 0.00,
    },
    Occasion.EVENT: {
        "professional_presence": 0.10, "visual_coherence": 0.25, "confidence_proxy": 0.20,
        "approachability": 0.00, "expressiveness": 0.15, "elegance": 0.30,
    },
    Occasion.OTHER: {
        "professional_presence": 0.20, "visual_coherence": 0.25, "confidence_proxy": 0.20,
        "approachability": 0.15, "expressiveness": 0.10, "elegance": 0.10,
    },
}

#: Formalite cible par occasion (0 = tres decontracte, 1 = tres formel).
# Ajouts du positionnement « Contextual » §4 : un meme look peut convenir a un
# diner et pas a un mariage. Chaque occasion doit donc porter son propre profil.
OCCASION_VECTORS[Occasion.WEDDING] = {
    "professional_presence": 0.05, "visual_coherence": 0.25, "confidence_proxy": 0.10,
    "approachability": 0.10, "expressiveness": 0.10, "elegance": 0.40,
}
OCCASION_VECTORS[Occasion.CONFERENCE] = {
    "professional_presence": 0.35, "visual_coherence": 0.25, "confidence_proxy": 0.15,
    "approachability": 0.15, "expressiveness": 0.10, "elegance": 0.00,
}
OCCASION_VECTORS[Occasion.DINNER] = {
    "professional_presence": 0.05, "visual_coherence": 0.25, "confidence_proxy": 0.15,
    "approachability": 0.25, "expressiveness": 0.15, "elegance": 0.15,
}
OCCASION_VECTORS[Occasion.TRAVEL] = {
    "professional_presence": 0.10, "visual_coherence": 0.30, "confidence_proxy": 0.20,
    "approachability": 0.25, "expressiveness": 0.15, "elegance": 0.00,
}


OCCASION_TARGET_FORMALITY: dict[Occasion, float] = {
    Occasion.INTERVIEW: 0.90,
    Occasion.BUSINESS: 0.85,
    Occasion.PRESENTATION: 0.80,
    Occasion.EVENT: 0.70,
    Occasion.DATE: 0.50,
    # Un mariage exige plus de tenue qu'un entretien ; un voyage en exige moins
    # que tout le reste. C'est exactement ce que « contextuel » veut dire.
    Occasion.WEDDING: 0.88,
    Occasion.CONFERENCE: 0.72,
    Occasion.DINNER: 0.58,
    Occasion.TRAVEL: 0.30,
    Occasion.OTHER: 0.60,
}

# --------------------------------------------------------------------------- #
# 4. Capacite d'un levier a ameliorer chaque dimension (Doc 04 §6).
# --------------------------------------------------------------------------- #
CAPABILITY: dict[ChangeAction, dict[str, float]] = {
    ChangeAction.CHANGE_JACKET: {
        "professional_presence": 0.90, "visual_coherence": 0.85, "confidence_proxy": 0.75,
        "approachability": 0.45, "expressiveness": 0.50, "elegance": 0.75,
    },
    ChangeAction.CHANGE_TOP: {
        "professional_presence": 0.65, "visual_coherence": 0.80, "confidence_proxy": 0.70,
        "approachability": 0.70, "expressiveness": 0.70, "elegance": 0.65,
    },
    ChangeAction.CHANGE_BOTTOM: {
        "professional_presence": 0.60, "visual_coherence": 0.70, "confidence_proxy": 0.60,
        "approachability": 0.50, "expressiveness": 0.50, "elegance": 0.60,
    },
    ChangeAction.CHANGE_SHOES: {
        "professional_presence": 0.45, "visual_coherence": 0.60, "confidence_proxy": 0.55,
        "approachability": 0.45, "expressiveness": 0.55, "elegance": 0.70,
    },
    ChangeAction.CHANGE_ACCESSORY: {
        "professional_presence": 0.40, "visual_coherence": 0.55, "confidence_proxy": 0.60,
        "approachability": 0.55, "expressiveness": 0.75, "elegance": 0.60,
    },
    ChangeAction.CHANGE_COLOR: {
        "professional_presence": 0.70, "visual_coherence": 0.75, "confidence_proxy": 0.65,
        "approachability": 0.65, "expressiveness": 0.70, "elegance": 0.60,
    },
}

# Retirer un accessoire de trop : le gain se joue sur la coherence et la tenue,
# pas sur l'expressivite — c'est precisement ce qu'on retranche.
CAPABILITY[ChangeAction.REMOVE_ACCESSORY] = {
    "professional_presence": 0.70, "visual_coherence": 0.80, "confidence_proxy": 0.55,
    "approachability": 0.50, "expressiveness": 0.20, "elegance": 0.70,
}


# --------------------------------------------------------------------------- #
# 5. Context fit : le levier est-il pertinent pour cette occasion (Doc 04 §7)
# --------------------------------------------------------------------------- #
CONTEXT_FIT: dict[Occasion, dict[ChangeAction, float]] = {
    Occasion.PRESENTATION: {
        ChangeAction.CHANGE_JACKET: HIGH, ChangeAction.CHANGE_TOP: MEDIUM,
        ChangeAction.CHANGE_BOTTOM: MEDIUM, ChangeAction.CHANGE_SHOES: MEDIUM,
        ChangeAction.CHANGE_ACCESSORY: LOW, ChangeAction.CHANGE_COLOR: MEDIUM,
    },
    Occasion.INTERVIEW: {
        ChangeAction.CHANGE_JACKET: HIGH, ChangeAction.CHANGE_TOP: MEDIUM,
        ChangeAction.CHANGE_BOTTOM: MEDIUM, ChangeAction.CHANGE_SHOES: MEDIUM,
        ChangeAction.CHANGE_ACCESSORY: LOW, ChangeAction.CHANGE_COLOR: MEDIUM,
    },
    Occasion.BUSINESS: {
        ChangeAction.CHANGE_JACKET: HIGH, ChangeAction.CHANGE_TOP: MEDIUM,
        ChangeAction.CHANGE_BOTTOM: MEDIUM, ChangeAction.CHANGE_SHOES: MEDIUM,
        ChangeAction.CHANGE_ACCESSORY: MEDIUM, ChangeAction.CHANGE_COLOR: MEDIUM,
    },
    Occasion.DATE: {
        ChangeAction.CHANGE_JACKET: MEDIUM, ChangeAction.CHANGE_TOP: HIGH,
        ChangeAction.CHANGE_BOTTOM: MEDIUM, ChangeAction.CHANGE_SHOES: MEDIUM,
        ChangeAction.CHANGE_ACCESSORY: MEDIUM, ChangeAction.CHANGE_COLOR: HIGH,
    },
    Occasion.EVENT: {
        ChangeAction.CHANGE_JACKET: MEDIUM, ChangeAction.CHANGE_TOP: HIGH,
        ChangeAction.CHANGE_BOTTOM: MEDIUM, ChangeAction.CHANGE_SHOES: HIGH,
        ChangeAction.CHANGE_ACCESSORY: HIGH, ChangeAction.CHANGE_COLOR: HIGH,
    },
    Occasion.OTHER: {
        ChangeAction.CHANGE_JACKET: MEDIUM, ChangeAction.CHANGE_TOP: MEDIUM,
        ChangeAction.CHANGE_BOTTOM: MEDIUM, ChangeAction.CHANGE_SHOES: MEDIUM,
        ChangeAction.CHANGE_ACCESSORY: MEDIUM, ChangeAction.CHANGE_COLOR: MEDIUM,
    },
}

# --------------------------------------------------------------------------- #
# 6. Visibilite d'un changement dans l'image (utilise par visual_impact).
# --------------------------------------------------------------------------- #
# Adequation des leviers aux occasions ajoutees.
CONTEXT_FIT[Occasion.WEDDING] = {
    ChangeAction.CHANGE_JACKET: HIGH, ChangeAction.CHANGE_TOP: MEDIUM,
    ChangeAction.CHANGE_BOTTOM: MEDIUM, ChangeAction.CHANGE_SHOES: HIGH,
    ChangeAction.CHANGE_ACCESSORY: MEDIUM, ChangeAction.CHANGE_COLOR: MEDIUM,
}
CONTEXT_FIT[Occasion.CONFERENCE] = {
    ChangeAction.CHANGE_JACKET: HIGH, ChangeAction.CHANGE_TOP: MEDIUM,
    ChangeAction.CHANGE_BOTTOM: MEDIUM, ChangeAction.CHANGE_SHOES: MEDIUM,
    ChangeAction.CHANGE_ACCESSORY: LOW, ChangeAction.CHANGE_COLOR: MEDIUM,
}
CONTEXT_FIT[Occasion.DINNER] = {
    ChangeAction.CHANGE_JACKET: MEDIUM, ChangeAction.CHANGE_TOP: HIGH,
    ChangeAction.CHANGE_BOTTOM: MEDIUM, ChangeAction.CHANGE_SHOES: MEDIUM,
    ChangeAction.CHANGE_ACCESSORY: MEDIUM, ChangeAction.CHANGE_COLOR: HIGH,
}
CONTEXT_FIT[Occasion.TRAVEL] = {
    ChangeAction.CHANGE_JACKET: MEDIUM, ChangeAction.CHANGE_TOP: MEDIUM,
    ChangeAction.CHANGE_BOTTOM: LOW, ChangeAction.CHANGE_SHOES: HIGH,
    ChangeAction.CHANGE_ACCESSORY: LOW, ChangeAction.CHANGE_COLOR: LOW,
}


VISIBILITY: dict[ChangeAction, float] = {
    ChangeAction.CHANGE_JACKET: 0.90,
    ChangeAction.CHANGE_TOP: 0.85,
    ChangeAction.CHANGE_BOTTOM: 0.70,
    ChangeAction.CHANGE_SHOES: 0.45,
    ChangeAction.CHANGE_ACCESSORY: 0.40,
    ChangeAction.CHANGE_COLOR: 0.65,
    # Retirer se voit moins qu'ajouter, mais corrige un exces immediatement.
    ChangeAction.REMOVE_ACCESSORY: 0.35,
}

# --------------------------------------------------------------------------- #
# 7. Simplicite / effort (Doc 06 §11). 1.0 = effort minimal.
# --------------------------------------------------------------------------- #
SIMPLICITY: dict[ChangeAction, float] = {
    ChangeAction.CHANGE_JACKET: 0.75,
    ChangeAction.CHANGE_TOP: 0.70,
    ChangeAction.CHANGE_BOTTOM: 0.55,
    ChangeAction.CHANGE_SHOES: 0.65,
    ChangeAction.CHANGE_ACCESSORY: 0.90,
    ChangeAction.CHANGE_COLOR: 0.95,
    # Le geste le plus simple qui existe : on enleve, c'est tout.
    ChangeAction.REMOVE_ACCESSORY: 0.98,
    ChangeAction.NO_CHANGE: 1.00,
}

# --------------------------------------------------------------------------- #
# 8. Time fit (Doc 04 §10) + faisabilite dure selon le temps disponible.
# --------------------------------------------------------------------------- #
TIME_FIT: dict[TimeAvailable, dict[ChangeAction, float]] = {
    TimeAvailable.UNDER_5M: {
        ChangeAction.CHANGE_JACKET: 0.85, ChangeAction.CHANGE_TOP: 0.60,
        ChangeAction.CHANGE_BOTTOM: 0.45, ChangeAction.CHANGE_SHOES: 0.90,
        ChangeAction.CHANGE_ACCESSORY: 1.00, ChangeAction.CHANGE_COLOR: 0.95,
    },
    TimeAvailable.FROM_5_TO_15M: {
        ChangeAction.CHANGE_JACKET: 0.95, ChangeAction.CHANGE_TOP: 0.90,
        ChangeAction.CHANGE_BOTTOM: 0.80, ChangeAction.CHANGE_SHOES: 0.95,
        ChangeAction.CHANGE_ACCESSORY: 1.00, ChangeAction.CHANGE_COLOR: 0.95,
    },
    TimeAvailable.FROM_15_TO_30M: {
        ChangeAction.CHANGE_JACKET: 1.00, ChangeAction.CHANGE_TOP: 1.00,
        ChangeAction.CHANGE_BOTTOM: 0.95, ChangeAction.CHANGE_SHOES: 1.00,
        ChangeAction.CHANGE_ACCESSORY: 1.00, ChangeAction.CHANGE_COLOR: 1.00,
    },
    TimeAvailable.OVER_30M: {
        ChangeAction.CHANGE_JACKET: 1.00, ChangeAction.CHANGE_TOP: 1.00,
        ChangeAction.CHANGE_BOTTOM: 1.00, ChangeAction.CHANGE_SHOES: 1.00,
        ChangeAction.CHANGE_ACCESSORY: 0.95, ChangeAction.CHANGE_COLOR: 0.95,
    },
}

#: Changements consideres comme irrealistes dans le temps imparti -> filtres.
TIME_INFEASIBLE: dict[TimeAvailable, set[ChangeAction]] = {
    TimeAvailable.UNDER_5M: {ChangeAction.CHANGE_BOTTOM},
    TimeAvailable.FROM_5_TO_15M: set(),
    TimeAvailable.FROM_15_TO_30M: set(),
    TimeAvailable.OVER_30M: set(),
}

# --------------------------------------------------------------------------- #
# 9. Faisabilite VTO (Doc 08 §7 : "vto_feasibility").
# --------------------------------------------------------------------------- #
VTO_FEASIBILITY: dict[ChangeAction, float] = {
    ChangeAction.CHANGE_JACKET: 0.95,
    ChangeAction.CHANGE_TOP: 0.90,
    ChangeAction.CHANGE_BOTTOM: 0.75,
    ChangeAction.CHANGE_SHOES: 0.55,
    ChangeAction.CHANGE_ACCESSORY: 0.45,
    ChangeAction.CHANGE_COLOR: 0.60,
    # Rien a essayer : on ne prouve pas visuellement une soustraction avec un
    # catalogue de vetements. La recommandation se suffit a elle-meme.
    ChangeAction.REMOVE_ACCESSORY: 0.00,
    ChangeAction.NO_CHANGE: 1.00,
}

# --------------------------------------------------------------------------- #
# 10. Plafond realiste atteignable en remplacant une piece par une bonne piece.
# --------------------------------------------------------------------------- #
POTENTIAL_CEILING: dict[OutfitElement, float] = {
    OutfitElement.JACKET: 0.90,
    OutfitElement.TOP: 0.88,
    OutfitElement.BOTTOM: 0.86,
    OutfitElement.SHOES: 0.86,
    OutfitElement.ACCESSORIES: 0.84,
}

#: Poids des pieces dans la lecture globale de la tenue (estimateur d'apparence).
ELEMENT_WEIGHT: dict[OutfitElement, float] = {
    OutfitElement.JACKET: 0.32,
    OutfitElement.TOP: 0.26,
    OutfitElement.BOTTOM: 0.18,
    OutfitElement.SHOES: 0.14,
    OutfitElement.ACCESSORIES: 0.10,
}

#: Ordre stable pour les departages deterministes (Doc 04 §16 / §24).
ACTION_PRIORITY: tuple[ChangeAction, ...] = (
    ChangeAction.CHANGE_JACKET,
    ChangeAction.CHANGE_TOP,
    ChangeAction.CHANGE_COLOR,
    ChangeAction.CHANGE_SHOES,
    ChangeAction.CHANGE_ACCESSORY,
    ChangeAction.REMOVE_ACCESSORY,
    ChangeAction.CHANGE_BOTTOM,
    ChangeAction.NO_CHANGE,
)

#: Seuils au-dela desquels un signal peau devient materiel pour la decision
#: (Doc 06 §19 : "Skin AI informs, it does not hijack the fashion decision").
SKIN_MATERIALITY_THRESHOLDS: dict[str, float] = {
    "redness": 0.60,
    "oiliness": 0.70,
    "texture": 0.70,
}

#: Influence maximale du signal peau sur une dimension d'apparence.
SKIN_MAX_INFLUENCE: float = 0.08

#: NO_CHANGE ne devient competitif que si la tenue actuelle est REELLEMENT alignee.
#: On applique une fonction convexe (exposant) a ses features d'adequation :
#: fit=0.62 -> 0.38 ; fit=0.89 -> 0.79. Empeche "ne rien changer" par defaut.
NO_CHANGE_SHARPNESS: float = 2.0

#: A priori de suitability quand l'utilisateur ne decrit pas une piece.
#: Volontairement moyen : on ne pretend pas avoir mesure ce qu'on n'a pas mesure.
UNKNOWN_ITEM_SUITABILITY: float = 0.58

# Chaque occasion doit aussi savoir si RETIRER est pertinent chez elle : c'est un
# levier de sobriete, donc precieux la ou la formalite compte.
for _occasion, _levels in CONTEXT_FIT.items():
    _levels.setdefault(
        ChangeAction.REMOVE_ACCESSORY,
        HIGH if OCCASION_TARGET_FORMALITY.get(_occasion, 0.6) >= 0.75 else MEDIUM,
    )
