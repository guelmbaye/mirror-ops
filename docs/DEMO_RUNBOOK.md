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
- [ ] **no sunglasses in the demo photo.** Measured, not assumed: a portrait with
      a 906 px face was rejected as "too small" while a full-length shot with a
      289 px face was accepted. The difference was the sunglasses
- [ ] **the recommended category holds at least three usable pieces.** The
      fallback tries one alternative and no more; `shoes` currently holds two,
      which leaves no margin on camera
- [ ] **the photo is full-length** — a waist-up shot removes shoes and bottom
      from the decision entirely, and the try-on could not show them either.
      `GET /appearance/analyze` reports the detected framing
- [ ] moment pair chosen from `python scripts/demo_pairs.py`, not from intuition.
      Change occasion **and** goal. Measured on a real photo through the live
      integration, dressiness "In between": `interview / professional` →
      *Change the jacket for something sharper.* · `dinner / elegant` →
      *You're good to go. / Don't change it.* · `travel / approachable` →
      *…for something easier.* `interview → wedding` shows nothing (the two
      closest occasions in the system)
- [ ] "How dressed up is it?" answered **honestly** — a blazer and chinos are
      "In between", and saying "Casual" to force a sharper contrast would be
      staging the demo. Verify the pairing separates instead:
      `python scripts/demo_pairs.py --dressiness 0.55`
- [ ] flag a piece as more casual than the rest **only if it is true** — that
      optional tap lets the verdict name a piece instead of saying "as a whole…",
      but only when the outfit genuinely has an odd one out
- [ ] every worn piece ticked on *Your look*, jacket included
- [ ] fallback path prepared (`YOUCAM_MODE=mock`) — and announced as such if used
- [ ] latencies measured: analysis, decision, try-on, total

> A judge should walk away thinking *"that AI made a decision for me"* — not
> *"that app calls a try-on API"*.
>
> The demo shows a **decision**, not a technology. To avoid at all costs: an API
> walkthrough, a generic chatbot demo, wardrobe browsing, "25 recommendations",
> a skin diagnosis, or a plain upload → API → image sequence.

## 1 bis. Pre-flight, measured on your own photo

Three commands, in order. Each one answers a question the recording cannot
afford to leave open.

```bash
python scripts/probe_skin.py your-photo.jpg
```
Reports the framing, the crop, and whether Skin AI accepts it. **Must read
`full`** — a waist-up shot removes the shoes and the bottom from the decision,
and takes the product's sharpest verdict with them.

```bash
python scripts/probe_vto.py your-photo.jpg <the piece the engine will pick>
```
One try-on, raw response. Run it on the exact piece the demo will use: the
automatic fallback tries only **one** alternative, and some categories hold only
two garments.

```bash
python scripts/check_garments.py
```
Everything must read `ok`. A piece that shows someone wearing it, or a generated
flat shape, is a rendering failure waiting to happen on camera.

## 2. Sequence (2 min 45)

| Time | Screen | Message |
|---|---|---|
| 0:00–0:20 | Landing | *Fit the moment. One change.* |
| 0:20–0:40 | Moment | presentation · professional · under five minutes |
| 0:40–1:00 | Capture + analysis | Skin AI enriches the context; this is not a diagnosis |
| 1:00–1:15 | **CONTEXTUAL FIT** | *Almost there.* 77/100 — the outfit fits the occasion, but the shoes reduce the level of formality |
| 1:15–1:30 | **ONE CHANGE** | *Replace the shoes for something sharper.* + why + what stays |
| 1:30–2:15 | Try-on | the recommendation becomes visible |
| 2:15–2:40 | Before / After | one thing changed, everything else stayed |
| 2:40–3:00 | Close | *Now you're ready.* |

## 2 bis. The comprehension test

Before recording anything, show **only this sequence** to someone who has never
heard of MIRROR OPS — a still frame per step is enough:

```
JOB INTERVIEW  ·  5 MINUTES  ·  [photo]
        ↓
CONTEXTUAL FIT — "Almost there."
        ↓
ONE CHANGE — "Replace the sneakers."
        ↓
[before / after]
        ↓
READY
```

Then ask one question: **"What does this product do?"**

The answer you are looking for, unprompted:

> *"It tells me what to change so I fit the situation."*

If they say "it suggests outfits" or "it's a virtual fitting room", the demo has
not landed and no amount of narration will fix it — the screens themselves need
to carry it.

This is the one check the team cannot perform on itself. Do it with two people,
before the recording, not after.

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

**Why does the wording change between moments?** The engine says *which way* to
go, not just what to change: sharper for an interview, easier for a flight, on
the same jacket. That single sentence is the clearest proof that the moment —
and not the garment — is driving the decision.

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
