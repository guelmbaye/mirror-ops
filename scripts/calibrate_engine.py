#!/usr/bin/env python3
"""Banc de calibration du moteur ONE CHANGE (Doc 04 §25 Phase 5).

Affiche le classement complet des candidats pour une batterie de scenarios.
Aucun reseau, aucune base : utile pour ajuster les tables de ponderation.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Depot monorepo, ou image de l'API ou `app/` est a la racine : les scripts
# doivent fonctionner dans les deux, sinon la moitie d'entre eux est
# inutilisable en production.
for candidate in (ROOT / "apps" / "api", ROOT):
    if (candidate / "app").is_dir():
        sys.path.insert(0, str(candidate))
        break

from app.engines.appearance.estimator import (  # noqa: E402
    ImageQuality,
    build_appearance_signals,
    default_outfit,
)
from app.engines.one_change import (  # noqa: E402
    DecisionContext,
    MomentSpec,
    OutfitItem,
    SkinObservations,
    default_engine,
)
from app.models.enums import Goal, Occasion, OutfitElement, TimeAvailable  # noqa: E402

SKIN = SkinObservations(texture=0.42, redness=0.31, oiliness=0.64, available=True, source="bench")


def build(occasion, goal, time_available, outfit=None, image_score=0.78) -> DecisionContext:
    moment = MomentSpec(occasion, goal, time_available)
    signals = build_appearance_signals(
        moment, outfit or default_outfit(), SKIN, ImageQuality(score=image_score)
    )
    return DecisionContext(moment, signals)


def strong_outfit():
    return {
        e: OutfitItem(present=True, known=True, formality=0.82, structure=0.88,
                      color_harmony=0.86, condition=0.92)
        for e in OutfitElement
    }


def weak_jacket_outfit():
    outfit = {
        e: OutfitItem(present=True, known=True, formality=0.80, structure=0.80,
                      color_harmony=0.80, condition=0.85)
        for e in OutfitElement
    }
    outfit[OutfitElement.JACKET] = OutfitItem(
        present=True, known=True, formality=0.25, structure=0.30,
        color_harmony=0.40, condition=0.60,
    )
    return outfit


SCENARIOS = [
    ("A · presentation / professional / <5m", build(Occasion.PRESENTATION, Goal.PROFESSIONAL, TimeAvailable.UNDER_5M)),
    ("B · date / approachable / 5-15m", build(Occasion.DATE, Goal.APPROACHABLE, TimeAvailable.FROM_5_TO_15M)),
    ("C · event / elegant / 30m+", build(Occasion.EVENT, Goal.ELEGANT, TimeAvailable.OVER_30M)),
    ("D · look deja fort", build(Occasion.PRESENTATION, Goal.PROFESSIONAL, TimeAvailable.FROM_15_TO_30M, strong_outfit(), 0.9)),
    ("E · veste faible", build(Occasion.INTERVIEW, Goal.PROFESSIONAL, TimeAvailable.FROM_5_TO_15M, weak_jacket_outfit(), 0.85)),
    ("F · interview / confident / 30m+", build(Occasion.INTERVIEW, Goal.CONFIDENT, TimeAvailable.OVER_30M)),
    ("G · business / elegant / 15-30m", build(Occasion.BUSINESS, Goal.ELEGANT, TimeAvailable.FROM_15_TO_30M)),
    ("H · mariage / elegant / 30m+", build(Occasion.WEDDING, Goal.ELEGANT, TimeAvailable.OVER_30M)),
    ("I · voyage / approachable / <5m", build(Occasion.TRAVEL, Goal.APPROACHABLE, TimeAvailable.UNDER_5M)),
    ("J · diner / expressive / 15-30m", build(Occasion.DINNER, Goal.EXPRESSIVE, TimeAvailable.FROM_15_TO_30M)),
    ("K · conference / professional / 5-15m", build(Occasion.CONFERENCE, Goal.PROFESSIONAL, TimeAvailable.FROM_5_TO_15M)),
]


def main() -> None:
    for label, context in SCENARIOS:
        outcome = default_engine.evaluate(context)
        print(f"\n{label}")
        if outcome.fit:
            print(f"  fit  {outcome.fit.state:13} {outcome.fit.score:>3}/100  {outcome.fit.detail}")
        print(f"  →    {outcome.action}  score={outcome.score}  confidence={outcome.confidence_level}")
        for candidate in outcome.candidates:
            marker = "★" if candidate.action == outcome.action else " "
            print(f"    {marker} {str(candidate.action):<18} {candidate.score:6.2f}")
        print(f"    why: {outcome.explanation.why}")


if __name__ == "__main__":
    main()
