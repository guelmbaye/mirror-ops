#!/usr/bin/env python3
"""Finds the occasion pairs that actually make different screens.

The demo hinges on one move: same photo, change the occasion, watch the answer
change. But some occasions are near-twins — interview (0.90) and wedding (0.88)
demand almost exactly the same thing, so opposing them shows nothing.

This ranks every pair by how visibly they differ, so the demo pairing comes from
measurement rather than intuition.

    python scripts/demo_pairs.py                 # full outfit, casual
    python scripts/demo_pairs.py --dressiness 0.85
    python scripts/demo_pairs.py --no-jacket     # jacket left undeclared
"""

from __future__ import annotations

import argparse
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "apps" / "api", ROOT):
    if (candidate / "app").is_dir():
        sys.path.insert(0, str(candidate))
        break

from app.engines.appearance.estimator import (  # noqa: E402
    ImageQuality,
    build_appearance_signals,
)
from app.engines.one_change import (  # noqa: E402
    DecisionContext,
    MomentSpec,
    OutfitItem,
    SkinObservations,
    default_engine,
)
from app.models.enums import (  # noqa: E402
    ChangeAction,
    Goal,
    Occasion,
    OutfitElement,
    TimeAvailable,
)

#: The goal a user would plausibly pick for each occasion.
GOALS = {
    Occasion.INTERVIEW: Goal.PROFESSIONAL,
    Occasion.PRESENTATION: Goal.PROFESSIONAL,
    Occasion.BUSINESS: Goal.PROFESSIONAL,
    Occasion.CONFERENCE: Goal.PROFESSIONAL,
    Occasion.WEDDING: Goal.ELEGANT,
    Occasion.EVENT: Goal.ELEGANT,
    Occasion.DINNER: Goal.ELEGANT,
    Occasion.DATE: Goal.APPROACHABLE,
    Occasion.TRAVEL: Goal.APPROACHABLE,
    Occasion.OTHER: Goal.CONFIDENT,
}


def outfit(dressiness: float, worn: set) -> dict:
    """Exactly what the interface sends: presence, formality, structure."""
    return {
        element: (
            OutfitItem(
                present=True, known=True, formality=dressiness, structure=dressiness,
                color_harmony=0.55, condition=0.70,
            )
            if element in worn
            else OutfitItem(present=False)
        )
        for element in OutfitElement
    }


def evaluate(occasion: Occasion, items: dict):
    moment = MomentSpec(occasion, GOALS[occasion], TimeAvailable.UNDER_5M)
    signals = build_appearance_signals(
        moment, items, SkinObservations(available=False), ImageQuality(score=0.85)
    )
    return default_engine.evaluate(DecisionContext(moment, signals))


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank occasion pairs for the demo")
    parser.add_argument("--dressiness", type=float, default=0.25,
                        help="0.22 casual · 0.55 in between · 0.88 dressed up")
    parser.add_argument("--no-jacket", action="store_true",
                        help="leave the jacket undeclared")
    args = parser.parse_args()

    worn = set(OutfitElement)
    if args.no_jacket:
        worn.discard(OutfitElement.JACKET)

    items = outfit(args.dressiness, worn)
    results = {occasion: evaluate(occasion, items) for occasion in Occasion}

    print(f"\nOne photo · dressiness {args.dressiness}"
          f"{' · no jacket declared' if args.no_jacket else ''}\n")
    for occasion, outcome in sorted(results.items(), key=lambda kv: -kv[1].fit.score):
        marker = "  <- refuses to change anything" if outcome.action is ChangeAction.NO_CHANGE else ""
        print(f"  {occasion.value:13} {outcome.fit.state:14} {outcome.fit.score:3}"
              f"   {outcome.label}{marker}")

    scored = []
    for a, b in combinations(Occasion, 2):
        first, second = results[a], results[b]
        gap = abs(first.fit.score - second.fit.score)
        different_state = first.fit.state != second.fit.state
        different_action = first.action != second.action
        # A pair only demonstrates something when the SCREEN changes.
        rank = gap + (25 if different_state else 0) + (25 if different_action else 0)
        scored.append((rank, gap, different_state, different_action, a, b))

    print("\nBest pairs for the moment flip:\n")
    for rank, gap, state, action, a, b in sorted(scored, reverse=True)[:6]:
        marks = ("verdict" if state else "") + (" + action" if action else "")
        print(f"  {a.value} / {GOALS[a].value}  ->  {b.value} / {GOALS[b].value}"
              f"   {gap} pts   changes: {marks or 'score only'}")
        print(f"      {results[a].fit.state:13} {results[a].label}")
        print(f"      {results[b].fit.state:13} {results[b].label}\n")

    print("The goal counts as much as the occasion. travel/professional and")
    print("travel/approachable give the same verdict and different decisions —")
    print("the moment is all three answers, not just the first.")

    print("Avoid: interview / wedding / business demand almost the same thing")
    print("(0.90 / 0.88 / 0.85). Opposing them produces two identical screens.")
    print("Avoid --dressiness 0.55 as well: the middle level is equidistant from")
    print("every occasion, so no pair separates. Use 0.22 or 0.88.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
