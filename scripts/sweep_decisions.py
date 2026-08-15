#!/usr/bin/env python3
"""Exhaustive sweep of the decision space.

Every defect found so far surfaced the same way: someone tried a combination by
hand and the screen said something wrong. That does not scale — the input space
is tens of thousands of combinations, and the interesting ones are rarely the
ones a human happens to try.

This walks all of them and checks the invariants that must hold for every single
one. It is not a unit test: it is the systematic version of the manual testing
that found the bugs.

    python scripts/sweep_decisions.py
    python scripts/sweep_decisions.py --verbose     # print every violation
    python scripts/sweep_decisions.py --sample 500  # quick pass

Exit code 1 on the first invariant broken.
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from itertools import product
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
    ACTION_LABEL_ADD,
    MATERIALISED_ELEMENT,
    ChangeAction,
    Goal,
    Occasion,
    OutfitElement,
    TimeAvailable,
)
from app.services.framing import VISIBLE_ELEMENTS, Framing  # noqa: E402

#: Les niveaux proposes par l'interface.
DRESSINESS = (0.22, 0.55, 0.88)

#: Les combinaisons de pieces qu'un utilisateur declare en pratique.
WORN_SETS = (
    frozenset(OutfitElement),
    frozenset({OutfitElement.TOP, OutfitElement.BOTTOM, OutfitElement.SHOES}),
    frozenset({OutfitElement.TOP, OutfitElement.BOTTOM}),
    frozenset({OutfitElement.TOP}),
    frozenset({OutfitElement.JACKET, OutfitElement.TOP, OutfitElement.BOTTOM}),
)


def outfit(worn, dressiness, odd):
    """Exactement ce que l'interface envoie."""
    items = {}
    for element in OutfitElement:
        if element not in worn:
            items[element] = OutfitItem(present=False)
            continue
        level = max(0.1, dressiness - 0.4) if element is odd else dressiness
        items[element] = OutfitItem(
            present=True, known=True, formality=level, structure=level,
            color_harmony=0.55, condition=0.70,
        )
    return items


def check(case, outcome) -> list[str]:
    """Les invariants qui doivent tenir pour TOUTE entree."""
    problems: list[str] = []
    fit = outcome.fit
    action = outcome.action
    touched = MATERIALISED_ELEMENT[action]
    worn, visible = case["worn"], case["visible"]

    # 1. Le verdict et la decision ne peuvent pas se contredire.
    if fit.state == "FIT" and action is not ChangeAction.NO_CHANGE:
        problems.append(f"FIT but action={action}")
    if fit.headline.startswith("You're good") and action is not ChangeAction.NO_CHANGE:
        problems.append(f"promises readiness but action={action}")

    # 2. Nommer un coupable engage la decision.
    if fit.weakest_element is not None and str(touched) != fit.weakest_element:
        problems.append(f"names {fit.weakest_element} but acts on {touched}")

    # 3. Ce qui change n'est jamais « garde ».
    if touched is not None and str(touched) in outcome.keep:
        problems.append(f"keeps {touched} while changing it")

    # 4. On ne garde que ce qui est porte.
    absent = {str(e) for e in OutfitElement if e not in worn}
    if set(outcome.keep) & absent:
        problems.append(f"keeps absent pieces: {sorted(set(outcome.keep) & absent)}")

    # 5. On ne decide que sur ce que la photo montre.
    if touched is not None and visible is not None and touched not in visible:
        problems.append(f"acts on {touched}, not visible in photo")

    # 6. Un ajout vise une piece absente, et le dit.
    if outcome.is_addition:
        if touched in worn:
            problems.append(f"addition targets worn piece {touched}")
        if not outcome.label.lower().startswith("add"):
            problems.append(f"addition labelled {outcome.label!r}")
    elif action is not ChangeAction.NO_CHANGE and outcome.label in ACTION_LABEL_ADD.values():
        problems.append(f"non-addition labelled {outcome.label!r}")

    # 7. Les phrases affichees sont lisibles.
    for field, text in (("detail", fit.detail), ("what", outcome.explanation.what)):
        if not text or not text.endswith("."):
            problems.append(f"{field} not a sentence: {text!r}")
        for wrong in (" a travel ", " a business ", " a dinner ", " what other "):
            if wrong in text:
                problems.append(f"{field} ungrammatical: {text!r}")

    # 8. Les valeurs affichees restent dans leurs bornes.
    if not 0 <= fit.score <= 100:
        problems.append(f"fit score out of range: {fit.score}")
    if not 0 <= outcome.score <= 100:
        problems.append(f"impact score out of range: {outcome.score}")
    if outcome.confidence_level not in {"low", "medium", "high"}:
        problems.append(f"confidence: {outcome.confidence_level}")

    # 9. Rien a prouver pour une non-action ou une soustraction.
    if action in (ChangeAction.NO_CHANGE, ChangeAction.REMOVE_ACCESSORY):
        if outcome.requires_vto:
            problems.append(f"{action} requires a try-on")
    elif not outcome.requires_vto:
        problems.append(f"{action} claims no try-on needed")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep every decision combination")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--sample", type=int, default=0, help="check N random cases only")
    args = parser.parse_args()

    framings = [Framing.CHEST, Framing.KNEE, Framing.FULL, Framing.UNKNOWN]
    combos = list(product(Occasion, Goal, TimeAvailable, DRESSINESS, WORN_SETS, framings))
    if args.sample:
        combos = random.Random(11).sample(combos, min(args.sample, len(combos)))

    print(f"\nSweeping {len(combos):,} combinations…\n")

    failures: list[tuple[dict, list[str]]] = []
    crashes = 0
    actions: Counter = Counter()
    verdicts: Counter = Counter()

    for occasion, goal, time, dressiness, worn, framing in combos:
        visible = set(VISIBLE_ELEMENTS[framing]) if framing is not Framing.UNKNOWN else None
        # La piece qui detonne, quand il y en a plus d'une portee.
        odds = [None, *sorted(worn, key=str)] if len(worn) > 1 else [None]

        for odd in odds:
            case = {
                "occasion": occasion.value, "goal": goal.value, "time": time.value,
                "dressiness": dressiness, "worn": worn, "odd": odd,
                "framing": str(framing), "visible": visible,
            }
            moment = MomentSpec(occasion, goal, time)
            try:
                signals = build_appearance_signals(
                    moment, outfit(worn, dressiness, odd),
                    SkinObservations(available=False), ImageQuality(score=0.85),
                    visible_elements=visible,
                )
                outcome = default_engine.evaluate(DecisionContext(moment, signals))
            except Exception as exc:  # noqa: BLE001
                crashes += 1
                failures.append((case, [f"CRASH {type(exc).__name__}: {exc}"]))
                continue

            actions[str(outcome.action)] += 1
            verdicts[outcome.fit.state] += 1

            problems = check(case, outcome)
            if problems:
                failures.append((case, problems))

    checked = sum(actions.values()) + crashes
    print(f"  {checked:,} decisions evaluated · {crashes} crashes · {len(failures)} violations\n")

    print("  Actions chosen:")
    for action, count in actions.most_common():
        print(f"    {action:20} {count:6,}  {100 * count / max(checked, 1):5.1f}%")
    print("\n  Verdicts:")
    for state, count in verdicts.most_common():
        print(f"    {state:20} {count:6,}  {100 * count / max(checked, 1):5.1f}%")

    if failures:
        print(f"\n  {len(failures)} violation(s):\n")
        shown = failures if args.verbose else failures[:12]
        for case, problems in shown:
            worn = ",".join(sorted(str(e) for e in case["worn"]))
            print(f"    {case['occasion']}/{case['goal']}/{case['time']} "
                  f"dress={case['dressiness']} worn=[{worn}] odd={case['odd']} "
                  f"framing={case['framing']}")
            for problem in problems:
                print(f"        {problem}")
        if not args.verbose and len(failures) > 12:
            print(f"    … and {len(failures) - 12} more (--verbose)")
        return 1

    print("\n  Every invariant holds across the whole space.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
