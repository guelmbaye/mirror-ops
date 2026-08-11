# Positioning — single source of truth

> MIRROR OPS determines whether your current look fits the moment you're about
> to enter and, when it doesn't, identifies the ONE change worth making — then
> uses YouCam to prove the difference before you act.

This document overrides all others. Every code, copy and demo decision must
conform to it.

---

## 1. Category

**Contextual appearance decision engine.**

Not: AI stylist · shopping assistant · outfit generator · wardrobe manager ·
virtual try-on app · skin diagnostic tool · purchase optimiser.

| Signature | Promise | Distinctive question |
|---|---|---|
| **FIT THE MOMENT. ONE CHANGE.** | Don't redesign your look. Fix the mismatch. | *Will this look work here?* |

Distinctive action: *if the answer is no, make **one** change.*
Distinctive proof: *see it before you act.*

## 2. The distinction that decides everything

Several competing projects already address "check your look before an important
moment". That is not our territory.

```
Their territory:  CHECK      observe the state of your appearance
Our territory:    DECIDE     rule on what is worth changing
```

**CHECK YOUR LOOK ≠ DECIDE WHAT IS WORTH CHANGING.**

The problem is not a shortage of clothing options. It is **decision uncertainty**
in an appearance moment: *"I have five minutes before an important presentation
— should I change anything?"*

## 2 bis. The decision chain

```
MOMENT → CURRENT LOOK → CONTEXTUAL FIT → FIT / MISMATCH → ONE CHANGE → VTO → ACT
```

The **CONTEXTUAL FIT** step precedes the change, and that is not a sequencing
detail: the product first answers *"does this look work here?"*, and only then
*"what should change?"*. Three verdicts:

| State | What the screen says | Next |
|---|---|---|
| `FIT` | You're good to go. | no change, no try-on |
| `ALMOST_THERE` | Almost there. + the piece at fault | ONE CHANGE |
| `MISMATCH` | This doesn't fit the moment. | ONE CHANGE |

The verdict names an element only when one genuinely stands out from the rest.
When every piece is equal — the case for an undescribed outfit — it says so
without pointing at anyone: the product refuses to invent what it has not
observed.

**Contextual** means the same outfit is judged differently depending on the
moment. Ten occasions are covered, each with its own demand profile: interview,
presentation, date, business, event, **wedding**, **conference**, **dinner**,
**travel**, other.

## 3. What ONE CHANGE actually means

It is not "recommend one jacket". It is a **product constraint**:

> What is the smallest meaningful intervention with the highest expected value
> for this specific moment?

The intervention space holds three gestures, not one: **change** a piece,
**add** one that's missing, **remove** one too many. A removal needs no try-on —
there is nothing to put on, only something to take off — so the journey skips
the VTO step.

Two legitimate outcomes: **CHANGE** or **NO CHANGE**. A good decision engine
must be able to decide that no intervention is worth making — otherwise it is
not a decision engine, it is a recommendation generator.

## 4. YouCam's role

The innovation is **not** "Skin AI + VTO". It is the intervention engine that
deliberately limits itself to a single high-value change. The constraint creates
the differentiation.

```
Skin AI      informs the decision   (visual signals about the current appearance)
Apparel VTO  proves the decision    (before / after of the chosen intervention)
```

## 5. Where each rule lives in the code

| Positioning rule | Where it is applied | Where it is verified |
|---|---|---|
| 1 — never a stylist | `packages/config` (`PRODUCT`, `NOT_THIS`), screen copy | — |
| 2 — the innovation is not Skin AI + VTO | `README.md` §6, `docs/ONE_CHANGE_ENGINE.md` | — |
| 3 — never a list of recommendations | engine returns a single action; "Try another" swaps the piece, not the decision | `test_engine_scenarios.py`, `test_try_another.py`, `compare.test.tsx`, `one-change.test.tsx` |
| 4 — always tied to a moment and a goal | `MomentSpec` required before analysis | state machine, `test_state_machine.py` |
| 5 — preserve the rest of the look | `keep` field and visual ledger | `test_contract_shapes.py`, `test_contextual_fit.py` |
| 6 — always give a reason | `explanation.py`, derived from the factors that actually dominated | `test_engine_scenarios.py` |
| 7 — NO CHANGE allowed | threshold and margin policy | `test_engine_scenarios.py`, `test_api_flow.py` |
| 8 — VTO is proof | try-on only for the winner, never during scoring | `test_idempotency_and_units.py` |
| 9 — decision confidence first | `confidence` exposed as low/medium/high | `test_contract_shapes.py` |
| 10 — add nothing that dilutes the idea | see below | review |
| — the fit precedes the change | `engines/one_change/fit.py`, `/one-change` screen | `test_contextual_fit.py`, `verdict.test.tsx` |
| — no occasion may crash the engine | tables completed for all ten occasions | `test_contextual_fit.py`, parameterised over `Occasion` |

## 6. What will not be added

Wardrobe management · product catalogues · a chatbot · an endless stream of
recommendations · dashboards · social features · excessive personalisation ·
additional AI agents.

**The constraint is the product.** If a feature does not reinforce
`FIT THE MOMENT → FIND THE MISMATCH → ONE CHANGE → PROVE IT → MOVE FORWARD`, it
must be removed.

Non-negotiable principle: **don't redesign the person, fix the mismatch.**

## 7. Impact — stated carefully

Frame impact around **decision confidence**: under time pressure, people don't
need more inspiration, they need to know what to do next.

A plausible retail extension: customer uncertainty → ONE CHANGE → visual proof →
higher decision confidence → potential conversion.

Do **not** make "reducing product returns" the primary claim: we have no
evidence for it.

## 8. What a judge should take away

> "That AI made a decision for me."

Not: "that app calls a try-on API."

The three memorable visual moments: **ALMOST THERE** → **BEFORE / AFTER** →
**EVERYTHING ELSE STAYS**.
