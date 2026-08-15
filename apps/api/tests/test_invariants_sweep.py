"""Le balayage exhaustif, reduit a une taille compatible avec la suite.

`scripts/sweep_decisions.py` couvre 43 200 decisions en quelques minutes. Ce
test en verifie un echantillon deterministe a chaque execution : assez pour
attraper une regression, assez rapide pour rester dans la suite.
"""

from __future__ import annotations

import sys
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from sweep_decisions import DRESSINESS, WORN_SETS, check, outfit  # noqa: E402

from app.engines.appearance.estimator import ImageQuality, build_appearance_signals  # noqa: E402
from app.engines.one_change import (  # noqa: E402
    DecisionContext,
    MomentSpec,
    SkinObservations,
    default_engine,
)
from app.models.enums import Goal, Occasion, TimeAvailable  # noqa: E402
from app.services.framing import VISIBLE_ELEMENTS, Framing  # noqa: E402


def test_every_invariant_holds_across_the_space():
    violations: list[str] = []
    checked = 0

    framings = (Framing.CHEST, Framing.FULL, Framing.UNKNOWN)
    for occasion, goal, time, dressiness, worn, framing in product(
        Occasion, (Goal.PROFESSIONAL, Goal.ELEGANT, Goal.APPROACHABLE),
        (TimeAvailable.UNDER_5M, TimeAvailable.OVER_30M),
        DRESSINESS, WORN_SETS, framings,
    ):
        visible = set(VISIBLE_ELEMENTS[framing]) if framing is not Framing.UNKNOWN else None
        for odd in ([None, *sorted(worn, key=str)] if len(worn) > 1 else [None]):
            moment = MomentSpec(occasion, goal, time)
            signals = build_appearance_signals(
                moment, outfit(worn, dressiness, odd),
                SkinObservations(available=False), ImageQuality(score=0.85),
                visible_elements=visible,
            )
            outcome = default_engine.evaluate(DecisionContext(moment, signals))
            checked += 1

            problems = check(
                {"worn": worn, "visible": visible, "occasion": occasion.value,
                 "goal": goal.value, "time": time.value, "dressiness": dressiness,
                 "odd": odd, "framing": str(framing)},
                outcome,
            )
            if problems:
                violations.append(
                    f"{occasion.value}/{goal.value}/{time.value} dress={dressiness} "
                    f"odd={odd} framing={framing}: {problems}"
                )

    assert checked > 5000, f"sweep too small to be meaningful: {checked}"
    assert not violations, "\n".join(violations[:10])
