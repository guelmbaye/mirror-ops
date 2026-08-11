# ONE CHANGE — implementation specification

> *ONE CHANGE must be opinionated.*
> The engine never says "you could change the jacket, the shoes or an
> accessory". It says "change the jacket", then explains why.

Code: `apps/api/app/engines/one_change/` — a **pure domain**, with no FastAPI,
SQLAlchemy, HTTP or LLM dependency.

## 0. The verdict precedes the change

```
DecisionContext → assess_fit() → FIT | ALMOST_THERE | MISMATCH
```

`fit.py` projects the look onto what the occasion demands — not onto an absolute
quality scale. It names the element dragging the whole down **only** if it
genuinely stands apart; at parity, it says so without pointing at anyone.

A `FIT` verdict alongside an action other than `NO_CHANGE` would contradict
itself on screen, so the two are reconciled by construction. A test walks all
ten occasions and four dressiness levels to make sure no screen ever promises
readiness while demanding a change.

## 1. Pipeline

```
DecisionContext
   │
   ├─ validate            data quality gate: two refusals, each with a remedy
   ├─ assess_fit          does this look work HERE?
   ├─ generate_candidates closed space of 8 actions, contextual filtering
   ├─ score               7 weighted features → 0-100
   ├─ tie_breaker         gap < 5 pts → least effort (NO_CHANGE excluded)
   ├─ thresholds          minimum score, and a mandatory margin over NO_CHANGE
   ├─ confidence          data quality × candidate separation × context completeness
   └─ explanation         deterministic templates, from the factors that dominated
        ↓
   DecisionOutcome  (1 action, 1 score, 1 reason, the "keep" list, projected impact)
```

## 1 bis. The quality gate names what is missing

| Reason | Real cause | What we ask for |
|---|---|---|
| `no_outfit_declared` | no piece declared | say what you're wearing |
| `image_unusable` | image quality below 0.35 | retake the photo |

Not knowing an outfit's **attributes** is no longer grounds for refusal: it
lowers decision confidence, which the product already reports. Refusing on top
of that would be harsher than necessary — and above all, sending someone to
retake a perfectly good photo because their *outfit* is undescribed is a dead
end: nothing they do in front of the lens will change it.

Every refusal must open onto a specific gesture. A third gate based on overall
confidence pointed at neither the photo nor the outfit, so it was removed.

## 2. Decision space

`CHANGE_JACKET · CHANGE_TOP · CHANGE_BOTTOM · CHANGE_SHOES · CHANGE_ACCESSORY ·
CHANGE_COLOR · REMOVE_ACCESSORY · NO_CHANGE`

Three gestures, not one: **change**, **add** (when the piece is missing) and
**remove** (when there is one too many). Labels follow reality — "Add a jacket",
"Remove the accessory" — and a removal asks for no try-on.

The space is deliberately closed: more reliable, more testable, more
demonstrable. A candidate is dropped when the piece is absent and cannot
sensibly be added, when the change is unrealistic in the time available (`<5 min`
rules out the bottom), or when there aren't enough elements for colour work.

An intention is distinguished from the element it actually touches.
"Change the top for a better colour" materialises on the top, so the top must
not appear in the `keep` list — otherwise the screen contradicts the preview.

## 3. Features (all normalised 0..1)

| Feature | Weight | Source |
|---|---|---|
| `goal_alignment` | 0.25 | goal vector × lever capability (`GOAL_VECTORS` × `CAPABILITY`) |
| `context_fit` | 0.20 | `CONTEXT_FIT[occasion][action]` |
| `visual_impact` | 0.20 | `VISIBILITY[action] × (0.5 + 0.5 × gap)` |
| `current_gap` | 0.10 | `POTENTIAL_CEILING[element] − current suitability` |
| `time_fit` | 0.10 | `TIME_FIT[time][action]` |
| `data_confidence` | 0.10 | image quality × completeness of the declared outfit |
| `vto_feasibility` | 0.05 | `VTO_FEASIBILITY[action]` |

`final_score = round(Σ weight × feature × 100)`

Every table lives in `tables.py` and is **configurable**: they encode product
heuristics meant to be calibrated, not scientific truths.

## 4. NO_CHANGE is a real candidate

`NO_CHANGE` is scored with the same features, but measured on the **current**
state. Its fitness features pass through a convex function
(`NO_CHANGE_SHARPNESS = 2.0`): doing nothing has to be earned — an average look
is not enough.

Two further guards:

- if the best change is below `ONE_CHANGE_THRESHOLD` (60) → `NO_CHANGE`;
- if the best change fails to beat `NO_CHANGE` by at least
  `ONE_CHANGE_NO_CHANGE_MARGIN` (2 pts) → `NO_CHANGE`.

This is what stops the product inventing a change just to use the try-on.

## 5. Deterministic tie-breaking

Gap below `ONE_CHANGE_TIE_DELTA` (5 pts) → priority, in order: least effort,
better context fit, simpler try-on, fixed product order. `NO_CHANGE` never
enters this tie-break — otherwise "do nothing" would win every near-tie — and is
arbitrated by the threshold policy instead. Given identical context, the engine
always returns the same decision.

## 6. Decision confidence ≠ impact score

- **Impact score**: relative quality of the intervention.
- **Decision confidence**: `data quality × candidate separation × context
  completeness`, exposed as `low / medium / high` — never as a falsely precise
  percentage.

A decision made on a near-tie, or without any information about the outfit,
comes out as low confidence. That is honest, and it is stated rather than hidden.

## 7. The skin signal never hijacks the decision

Skin AI enriches the appearance context. It acts only when **material** (past
explicit thresholds) and its influence is capped (`SKIN_MAX_INFLUENCE = 0.08`).
A test verifies that heavily marked skin does not change the chosen action:
MIRROR OPS remains an appearance decision agent, not a skincare coach.

YouCam returns **health** scores (higher = healthier). The engine reasons in
**severity**, so `redness`, `oiliness` and `texture` are inverted on the way in;
`radiance` is already a quality and stays as is. Without that inversion, flawless
skin would read as heavily marked.

## 8. True explanations

`explanation.py` ranks the winner's **actual weighted contributions** and builds
the sentence from the two dominant factors. A generic justification, disconnected
from the computation, is impossible by construction.

## 9. Calibration

```bash
python scripts/calibrate_engine.py
```

Prints the full candidate ranking across eleven scenarios, with the fit verdict.
To adjust: edit `tables.py` or the `ONE_CHANGE_*` variables, then re-run
`pytest tests/test_engine_scenarios.py tests/test_contextual_fit.py`.
