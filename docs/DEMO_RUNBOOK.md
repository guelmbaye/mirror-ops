# Demo runbook

The goal: a judge understands the product in 30 seconds, and the full journey
fits in 90.

## 1. Before the demo

- [ ] `YOUCAM_MODE=live`, valid key, **credits verified**
- [ ] `python scripts/audit_journey.py` → 0 FAIL, and read every WARN
- [ ] `python scripts/check_garments.py` → no placeholder left
- [ ] `GET /api/v1/health/dependencies` → `"garments": "ok"`, `"youcam": "configured"`
- [ ] `python scripts/demo_flow.py` run **five times** in a row without error
- [ ] input photo frozen, winning garment frozen, expected recommendation known
- [ ] fallback path prepared (`YOUCAM_MODE=mock`) — and announced as such if used
- [ ] latencies measured: analysis, decision, try-on, total

> A judge should walk away thinking *"that AI made a decision for me"* — not
> *"that app calls a try-on API"*.
>
> The demo shows a **decision**, not a technology. To avoid at all costs: an API
> walkthrough, a generic chatbot demo, wardrobe browsing, "25 recommendations",
> a skin diagnosis, or a plain upload → API → image sequence.

## 2. Sequence (2 min 45)

| Time | Screen | Message |
|---|---|---|
| 0:00–0:20 | Landing | *Fit the moment. One change.* |
| 0:20–0:40 | Moment | presentation · professional · under five minutes |
| 0:40–1:00 | Capture + analysis | Skin AI enriches the context; this is not a diagnosis |
| 1:00–1:15 | **CONTEXTUAL FIT** | *Almost there* — the outfit works, but the sneakers reduce the formality |
| 1:15–1:30 | **ONE CHANGE** | *Replace the sneakers* + why + what stays |
| 1:30–2:15 | Try-on | the recommendation becomes visible |
| 2:15–2:40 | Before / After | one thing changed, everything else stayed |
| 2:40–3:00 | Close | *Now you're ready.* |

## 3. Three moments to land

1. `ALMOST THERE` — the fit verdict, which poses the product's question
2. `BEFORE → AFTER`
3. `Everything else stays.`

## 4. Short answers for the jury

**Why a single change?** The problem isn't a shortage of options, it's
uncertainty at the moment of deciding. We don't redesign the person; we fix the
mismatch.

**How do you know it doesn't fit?** The look is projected onto what the occasion
demands, not judged in the abstract. The same wardrobe yields a different
verdict for travel and for a wedding — verifiable by changing one answer on
screen 2.

**Why Skin AI on a clothing product?** It provides visual context signals, so
style isn't treated as an isolated garment recommendation. Its influence on the
decision is capped at 0.08 and tested: heavily marked skin does not change the
chosen action.

**Why the try-on?** A recommendation becomes useful when you can see it before
you make it.

**What if nothing should change?** The verdict is `FIT`, the engine returns
`NO_CHANGE`, and no try-on credit is consumed — a confidence feature, not a
technical fallback.

**How much technical room is there?** Weights, thresholds and endpoints are
configurable; the engine is deterministic and tested in isolation.

**What isn't ready?** There is no user feedback on the decision, and the shipped
catalogue is a fallback. Both are documented in `docs/PRODUCT_REVIEW.md` —
better said than found out.

## 5. After the demo

- [ ] demo session cleaned up (`python scripts/cleanup.py`)
- [ ] no key visible in screenshots or the recording
- [ ] `docs/openapi.json` regenerated if the contract moved
