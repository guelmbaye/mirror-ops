<img src="apps/web/public/logo-mirror-ops.png" alt="Mirror Ops" height="72">

**FIT THE MOMENT. ONE CHANGE.**

MIRROR OPS is a **contextual appearance decision engine**. It reads the moment
you're about to walk into, weighs the look you're already wearing, identifies
**the single** intervention worth making — or decides none is — and proves it
visually before you act.

> *Don't redesign your look. Fix the mismatch.*

The product's question is five words: **"Will this look work here?"** The same
outfit can be right for a dinner and wrong for a wedding. Other tools **check**
your appearance and hand you options. MIRROR OPS **decides**.

```
CHECK YOUR LOOK   ≠   DECIDE WHAT IS WORTH CHANGING
```

Full positioning and non-negotiable rules: [`docs/POSITIONING.md`](docs/POSITIONING.md).
Product, UX and business review — measured findings and open trade-offs:
[`docs/PRODUCT_REVIEW.md`](docs/PRODUCT_REVIEW.md).
Hackathon submission kit: [`docs/SUBMISSION.md`](docs/SUBMISSION.md).
Production deployment, in French: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

This repository holds the complete implementation: the FastAPI backend
(`apps/api`) and the Next.js interface (`apps/web`), joined by a shared
TypeScript contract (`packages/types`).

---

## 1. What the product does

```
  MOMENT        →  CURRENT LOOK   →  CONTEXTUAL FIT  →  ONE CHANGE  →  PROOF     →  ACT
  occasion,        photo +           FIT / ALMOST /     the decisive   YouCam       you
  goal,            YouCam Skin AI    MISMATCH           lever          VTO          leave
  time
```

**CONTEXTUAL FIT** comes before the change, and that order *is* the positioning:
the product first answers "does this look work here?", and only then "what
should change?". Three verdicts — `FIT` ("You're good to go"), `ALMOST_THERE`
("Almost there", naming the piece that holds it back), `MISMATCH`.

The question isn't *"what should I wear?"* but *"should I change anything — and
if so, what?"*. The engine can answer **NO_CHANGE**, consuming no try-on credit:
a decision engine that cannot decide to do nothing isn't a decision engine.

Skin AI **informs** the decision. Apparel VTO **proves** it. A failure of the
first cannot interrupt the journey — the decision is made without it, and says
so. The innovation is not the combination of those two APIs: it is an
intervention engine that deliberately limits itself to one high-value change.
**The constraint is the product** — don't redesign the person, fix the mismatch.

An intervention takes three forms: **change** a piece, **add** one that's
missing, **remove** one too many. A removal needs no try-on.

---

## 2. Architecture

A modular monolith, one deployable.

```
                    Browser / Next.js
                           │  HTTPS  (the YouCam key never reaches the client)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                     FastAPI — MIRROR OPS API                 │
│                                                              │
│   api/routes ──► services ──► engines        integrations    │
│                     │            │                │          │
│                     │       ONE CHANGE       YouCam adapters │
│                     │      (pure domain)      Skin AI · VTO  │
│                     ▼                                        │
│              PostgreSQL  +  temporary object storage         │
└──────────────────────────────────────────────────────────────┘
```

**Dependency rule**: `api → services → engines / integrations → infrastructure`.
The ONE CHANGE engine imports neither FastAPI, nor SQLAlchemy, nor HTTP: it is
tested without network, database or YouCam.

```
mirror-ops/
├── apps/
│   ├── api/                         # FastAPI backend
│   │   ├── app/
│   │   │   ├── api/v1/routes/       # sessions, moments, appearance, one_change, vto, media, health
│   │   │   ├── core/                # config, errors, logging, security, rate limit
│   │   │   ├── db/                  # declarative base, async session, additive schema sync
│   │   │   ├── models/              # SQLAlchemy + shared enums
│   │   │   ├── schemas/             # public Pydantic contract
│   │   │   ├── engines/
│   │   │   │   ├── one_change/      # ★ decision engine (pure domain)
│   │   │   │   └── appearance/      # appearance context estimator
│   │   │   ├── integrations/youcam/ # client, adapters, mappers, offline providers
│   │   │   ├── services/            # orchestration, storage, idempotency, cleanup
│   │   │   └── assets/garments/     # small controlled catalogue
│   │   └── tests/                   # 320 tests
│   └── web/                         # Next.js interface (App Router, TypeScript)
│       └── src/
│           ├── app/                 # 7 screens: / moment look analyzing one-change compare ready
│           ├── components/          # Stage, Verdict ★, BeforeAfter, CameraCapture, Notice
│           └── lib/                 # typed API client, session, photo, formats
├── packages/types/                  # TypeScript mirror of the API contract
├── packages/config/                 # shared product copy
├── scripts/                         # audit, demo, garment import, VTO probe, cleanup
├── docs/                            # positioning, engine, YouCam, API, demo, deployment
├── docker-compose.yml
├── .env                             # docker-compose variables (shipped, ready to use)
├── apps/api/.env                    # backend config (shipped, mock mode)
└── apps/web/.env.local              # API URL for the interface (shipped)
```

---

## 3. Quick start (2 minutes, no YouCam account needed)

`mock` mode runs **the whole journey** offline, without consuming a single API
credit.

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate      # Python 3.11+
pip install -r requirements-dev.txt

# Re-run this after every repository update: new dependencies may have appeared
# (for example `cryptography`, required by live YouCam authentication).

uvicorn app.main:app --reload --port 8000
```

Then the interface, in a second terminal:

```bash
npm install                    # Node 18.18+
npm run dev                    # http://localhost:3000
```

The full journey is now usable in the browser. To check it without the
interface — or to rehearse the demo — a third terminal:

```bash
python scripts/demo_flow.py
```

```
  ✓ session                         62 ms
  ✓ moment                          48 ms
  ✓ appearance + skin AI           826 ms
  ✓ ONE CHANGE                      18 ms
  ┌─────────────────────────────────────────────
  │ FIT          Almost there.  (62/100)
  │ ONE CHANGE   Change the jacket
  │ Impact       71/100 · confidence medium
  │ Keep         accessories, bottom, shoes, top
  └─────────────────────────────────────────────
  ✓ apparel VTO                    287 ms
  Full journey: 1372 ms
```

Interactive docs: <http://localhost:8000/docs> · schema: `docs/openapi.json`.

### On Windows (PowerShell)

The `Makefile` is useless there without extra tooling. `scripts\mirror-ops.ps1`
covers the same tasks and locates the venv interpreter on its own:

```powershell
.\scripts\mirror-ops.ps1 help
.\scripts\mirror-ops.ps1 dev-api          # http://localhost:8000
.\scripts\mirror-ops.ps1 dev-web          # http://localhost:3000
.\scripts\mirror-ops.ps1 audit
```

If script execution is blocked:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

Two syntax traps: PowerShell does not expand `~` for native executables — use
`$HOME` — and paths take backslashes.

### With Docker

```bash
docker compose up --build      # web :3000 · api :8000 · PostgreSQL :5432
```

---

## 4. Connecting the real YouCam

1. Create the YouCam / Perfect Corp account and check **remaining credits**.
2. Create an API key: <https://yce.perfectcorp.com/api-console/en/api-keys/>
3. Fill in **`apps/api/.env`** — the only file the API reads, resolved by
   absolute path so it works from any working directory. The root `.env` is for
   `docker compose` alone:

   ```dotenv
   YOUCAM_MODE=live
   YOUCAM_AUTH_MODE=api_key
   YOUCAM_API_KEY=...
   ```

4. **Replace the catalogue visuals, or use the user's own piece.** Two paths
   lead to visual proof, and the second depends on no shipped file:

   - **"Try a piece of your own"**, on the decision screen *and* on
     Before/After: the person photographs the jacket they're considering and
     sees it on themselves. Nothing to install, nothing to prepare. It is also
     the most realistic use — people hesitate over a specific garment, not over
     a catalogue.
   - **The catalogue**, which guarantees proof always exists without asking
     anything of the user in the middle of a 90-second journey.

   The shipped visuals are programmatically generated flat shapes: fine for
   `mock`, unusable by a real try-on, which fails on them with
   `error_editing_failed`.

   ```bash
   python scripts/check_garments.py                    # what still needs replacing
   python scripts/import_garments.py ~/my-garments     # import a folder
   python scripts/import_garments.py --id jacket_01 ~/jacket.jpg
   python scripts/import_garments.py catalogue.txt     # from an online catalogue
   ```

   ```powershell
   .\scripts\mirror-ops.ps1 garments
   .\scripts\mirror-ops.ps1 import-garments -Path $HOME\Downloads\garments -DryRun
   .\scripts\mirror-ops.ps1 import-garments -Path $HOME\Downloads\garments
   ```

   Your files need not carry catalogue names: the importer recognises the
   category from the filename, in English and French — `navy-jacket.jpg`,
   `sneakers white.png`, `chemise blanche.jpeg`, `sac1.jpg`. **The catalogue
   grows on its own**: when a category is full, a new piece is created
   (`jacket_04`, `shoes_03`…), with the median attributes of its category and
   its dominant colour sampled from the image. Anything unrecognised is set
   aside and named; `--auto` (`-Auto` in PowerShell) assigns the rest to the
   remaining free slots.

   Everything is normalised (white background, RGB, JPEG, long side ≥ 1024 px)
   and written to **`apps/api/var/garments/`**, never into the source tree: your
   photos survive any project update, including an archive extracted on top.

   An online catalogue is referenced **at import time** — one line per piece,
   `id  URL`:

   ```
   jacket_01   https://your-cdn/navy-jacket.jpg
   shoes_01    https://your-cdn/black-derbies.jpg
   ```

   Images are downloaded **once**, normalised, then served locally: the journey
   never depends on a third-party host at the moment it matters.

   Before recording a demo, run both probes on the exact photo you will film
   with — the framing decides which pieces the engine may even recommend.

   To isolate a failure without running the whole journey:

   ```bash
   python scripts/probe_vto.py my-photo.jpg jacket_01   # one try-on, raw responses
   python scripts/probe_skin.py my-photo.jpg            # crop ratios, one by one
   ```

   `probe_skin.py` also works offline: it reports what the server actually
   detects on a given photo — face size, framing, which elements are in shot,
   and whether the crop has to be upscaled — without sending anything. That is
   the fastest way to explain a `skin_skipped_no_face` on a photo that looks
   perfectly usable.

   `probe_skin.py` exists because the 60%-of-width rule was not enough on its
   own: a crop satisfying it still came back `error_src_face_too_small`. It
   sends the same face at several tightness levels and reports which one the
   provider accepts, so the setting comes from measurement rather than from
   reading the documentation.

5. **Restart the API**, then check:
   `curl localhost:8000/api/v1/health/dependencies` → `"youcam": "configured"`.
   While that response says `"mock_mode"`, previews stay marked "simulated" —
   the stamp tells the truth about what produced the image.

No business code changes between `mock` and `live`: only the adapters differ.
Endpoint paths and metric names are **configurable**, because they depend on
what is actually enabled on your account.

> **Honest fallback.** In `mock` mode, results carry `simulated: true`, the
> provider is named `local_heuristic` / `local_composite`, and the image is
> watermarked *"SIMULATED PREVIEW — not generated by YouCam"*. A result that
> didn't come from YouCam never pretends it did.

---

## 5. API contract

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/sessions` | start an anonymous journey |
| `POST` | `/api/v1/moments` | occasion + goal + time available |
| `POST` | `/api/v1/appearance/analyze` | photo → Skin AI → appearance context |
| `POST` | `/api/v1/one-change/evaluate` | **the** recommendation |
| `POST` | `/api/v1/vto/generate` | visual proof (winner only) |
| `POST` | `/api/v1/garments/upload` | try a piece of your own |
| `GET` | `/api/v1/vto/{id}` | preview status / result |
| `GET` | `/api/v1/sessions/{id}` | the whole final screen in one request |
| `GET` | `/api/v1/garments` | catalogue, with `placeholder` per piece |
| `GET` | `/api/v1/media/{key}` | signed, expiring media |
| `GET` | `/api/v1/health` · `/health/dependencies` | health |

ONE CHANGE response:

```json
{
  "recommendation": {
    "action": "CHANGE_JACKET",
    "label": "Change the jacket",
    "score": 71,
    "confidence": "medium",
    "what": "Change the jacket.",
    "why": "Among the changes available to you right now, the jacket offers the highest expected improvement for professional presence — it is the lever most aligned with your goal, and it fits what this occasion calls for.",
    "how": "Keep the rest of your look exactly as it is.",
    "keep": ["accessories", "bottom", "shoes", "top"],
    "impact": {
      "before": {"professional_presence": 58, "visual_coherence": 64},
      "after":  {"professional_presence": 72, "visual_coherence": 75},
      "dominant_factors": ["goal_alignment", "context_fit"]
    },
    "requires_vto": true,
    "is_addition": false,
    "fit": {
      "state": "ALMOST_THERE",
      "score": 62,
      "headline": "Almost there.",
      "detail": "Your outfit fits the occasion, but the shoes reduce the level of formality.",
      "weakest_element": "shoes"
    },
    "suggested_garment": {"id": "jacket_01", "name": "Structured Neutral Jacket", "category": "jacket"}
  }
}
```

Every error shares one shape:

```json
{"error": {"code": "INVALID_IMAGE", "message": "We need a clearer view of your look.", "retryable": true}}
```

Full detail: [`docs/API.md`](docs/API.md).

---

## 6. The ONE CHANGE engine

```
INPUT → Validate → Contextual fit → Generate candidates → Score
      → Threshold → Tie-breaker → Winner → Explain → (VTO)
```

Score normalised 0–100, weights **configurable**:

| Feature | Weight | Question asked |
|---|---|---|
| `goal_alignment` | 0.25 | does this lever serve the goal? |
| `context_fit` | 0.20 | is it right for this occasion? |
| `visual_impact` | 0.20 | will the change be seen? |
| `current_gap` | 0.10 | is there room on this piece? |
| `time_fit` | 0.10 | is it realistic in the time available? |
| `data_confidence` | 0.10 | do we read this element reliably? |
| `vto_feasibility` | 0.05 | can we show it before deciding? |

Guaranteed properties, each covered by tests: **one** action only, determinism,
an explanation derived from the factors that actually dominated, `NO_CHANGE`
possible, time taken into account, no LLM required, no medical claim.

Calibration bench: `python scripts/calibrate_engine.py`.
Occasion contrast, for choosing a demo pair from data: `python scripts/demo_pairs.py`.
Exhaustive sweep of the decision space — 43,200 decisions, every invariant
checked: `python scripts/sweep_decisions.py`.
Detail: [`docs/ONE_CHANGE_ENGINE.md`](docs/ONE_CHANGE_ENGINE.md).

---

## 7. Tests

```bash
cd apps/api && python -m pytest -q      # 320 tests
```

| File | Covers |
|---|---|
| `test_engine_scenarios.py` | the five documented scenarios, determinism, filtering, thresholds |
| `test_contextual_fit.py` | the fit verdict, all ten occasions, and the ban on inventing a culprit |
| `test_api_flow.py` | full journey, NO_CHANGE, catalogue, served images |
| `test_api_errors.py` | error contract, corrupt/small/oversized images, provider failures |
| `test_state_machine.py` | impossible transitions → 409, expired session, cross-session resources |
| `test_idempotency_and_units.py` | one journey ≈ one analysis + one try-on, double-click neutralised |
| `test_going_back.py` | going back and correcting really changes the outcome |
| `test_decision_gate.py` | a refusal names what's missing: the photo or the outfit |
| `test_youcam_adapter.py` | v2 protocol, retries, health→severity inversion |
| `test_youcam_auth.py` | the RSA `id_token` round-trips, and never leaks the secret |
| `test_task_failures.py` | a failed task names its cause and guides recovery |
| `test_face_crop.py` | the crop sent to Skin AI satisfies its 60% constraint |
| `test_image_orientation.py` | a phone portrait photo is never processed sideways |
| `test_framing.py` | the decision never names a piece the photo cannot show |
| `test_action_space.py` | every declared action is actually evaluated, and can win |
| `test_invariants_sweep.py` | every invariant holds across thousands of input combinations |
| `test_own_garment.py` | a user can try their own piece, isolated per session |
| `test_try_another.py` | swapping a piece never changes the decision (rule 3) |
| `test_garment_audit.py` | the catalogue declares itself a placeholder while it is one; user photos survive updates |
| `test_garment_import.py` | the importer recognises categories without demanding renames |
| `test_schema_sync.py` | an existing database survives a new field |
| `test_security_privacy.py` | signed URLs, path traversal, logs without secrets, cleanup |
| `test_contract_shapes.py` | public contract stability |

On the interface side:

```bash
npm run test --workspace @mirror-ops/web    # 34 render tests (vitest + jsdom)
npm run typecheck                           # app and tests, two passes
npm run build                               # production build
```

The end-to-end audit checks the **assembled** system, in the machine's real
configuration — YouCam mode, database and catalogue included:

```bash
python scripts/audit_journey.py       # or: make audit
```

It walks the seven screens, prints the data going in and out of every call, and
verifies 42 invariants: coherence between what is declared, what changes and
what is kept; agreement between the fit verdict and the action; media actually
reachable; refusals that name the right remedy. `FAIL` blocks, `WARN` flags what
will limit the demo. **The API must be running** — the audit tests the system,
not the code.

---

## 8. Security & privacy

- The YouCam key stays **server-side only**; the frontend never talks to the
  provider.
- Uploads validated (real MIME, size, dimensions, decodability) and straightened
  according to EXIF orientation.
- Media served through **signed HMAC URLs with expiry**, never public; path
  traversal blocked.
- Structured logs are **sanitised**: no raw image, no key, no credentials.
- Anonymous, time-limited sessions; no account, no password.
- `expires_at` plus `scripts/cleanup.py` delete expired media and sessions.
- No raw provider response is retained.
- Basic rate limiting, restricted CORS, an error contract with no technical
  leakage.

---

## 9. Product positioning

MIRROR OPS is not an AI stylist, a shopping assistant, a wardrobe manager, a
try-on app, or a skin diagnostic tool. Those boundaries are held in the code:
`packages/config` carries `PRODUCT` and `NOT_THIS`, and the rule → test mapping
lives in [`docs/POSITIONING.md`](docs/POSITIONING.md) §5.

Skin AI output is presented as a **visual, cosmetic observation**, never as a
medical diagnosis, and its influence on the decision is bounded: it informs the
context, it does not hijack the clothing decision. Impact scores are explainable
heuristics meant to be calibrated — not scientific measurements of human
confidence.

Impact is framed around **decision confidence**. "Reduced returns" is not
claimed: we have no evidence for it.

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `409 INVALID_STATE` | step skipped | follow `moment → analyze → one-change → vto` |
| `422 INVALID_IMAGE` | unreadable photo, or under 320 px on either side | the message names the actual size — a screenshot or a cropped copy is the usual cause, so send the original file |
| `INVALID_REQUEST` on `/one-change/evaluate` | no piece declared | tick what you're wearing on *Your look* — the photo is not at fault. In `APP_ENV=development`, `details` carries the exact numbers |
| `409 VTO_NOT_APPLICABLE` | the decision is `NO_CHANGE` | normal: nothing to preview |
| `410 MEDIA_LINK_EXPIRED` | signed URL expired | re-read the session via `GET /sessions/{id}` |
| `"youcam": "mock_mode"` | live not enabled | set `YOUCAM_MODE=live` in `apps/api/.env`, restart |
| `"youcam": "missing_credentials"` | `YOUCAM_API_KEY` absent | one variable is enough on v2 |
| `"youcam": "missing_dependency"` | `cryptography` not installed | `cd apps/api && pip install -r requirements.txt`, restart |
| `"face_detection": "unavailable"`, or `module 'cv2' has no attribute 'CascadeClassifier'` in the logs | **OpenCV 5.0 removed Haar cascades** — `cv2.data.haarcascades` exists but is empty | `pip install "opencv-python-headless>=4.10,<5"`. Until then Skin AI is never called and framing is unmeasured — the journey still works, without a skin signal |
| `unable to open database file` | `var/` missing (git-ignored) | nothing to do: the API recreates it at startup |
| `column X does not exist` | database predating a new field | nothing to do: the API adds missing columns at startup. To apply it separately: `python scripts/sync_schema.py` |
| `error_editing_failed` with `"garment_source": "catalog"` | placeholder catalogue: the try-on has nothing to work from | `python scripts/import_garments.py <folder>`, then `python scripts/check_garments.py` |
| `"garments": "placeholder"` | same, reported by the API itself | same |
| `error_editing_failed` on a photo cropped into a strip | ratios beyond 1:2.1 confuse the try-on | handled automatically — the image is letterboxed to 9:16, look for `source_letterboxed` in the logs |
| `error_editing_failed` on one catalogue piece while another works | some references are refused by the renderer for reasons we cannot detect in advance | handled automatically — one fallback to the next piece in the same category, logged as `vto_fallback_garment` |
| `error_editing_failed` on a garment that is a real photograph | the reference shows someone **wearing** the piece — the try-on has to segment the garment and expects it alone: flat, on a hanger, or ghost-mannequin | `python scripts/check_garments.py` now flags these. Re-import with product-style shots |
| `error_editing_failed` with `"garment_source": "uploaded"` | not the catalogue any more: the garment photo or the source photo is at fault | garment alone on a plain background, and a head-to-knee photo, one person, facing the camera |
| `VTO_FAILED` with a `provider_code` | the photo doesn't suit the try-on: unreadable pose, several people, framing | the displayed message says what to redo |
| `error_src_face_too_small` although the crop met the 60% rule | the provider measures differently, or its own detector finds a smaller face — sunglasses and steep angles both defeat frontal detection | the crop now targets 80% on **both** axes and retries once at 92%. To settle it empirically: `python scripts/probe_skin.py your-photo.jpg` |
| repeated `502 ANALYSIS_FAILED` | auth rejected, or Skin AI endpoints/actions not enabled | read the `skin_provider_failed` log: it carries `error_code`, `reason` and the provider response |
| `404` on a task | wrong endpoint path | v2: `/s2s/v2.0/task/cloth` — **singular** |
| "We can't reach Mirror Ops" | API down, or origin missing from `CORS_ORIGINS` | start the API, add `http://localhost:3000` |
| "We need your photo again" | tab reloaded before the analysis | retake it: photos are never persisted client-side |
| the interface calls the wrong API | `NEXT_PUBLIC_API_BASE_URL` is baked in at build time | fix `apps/web/.env.local`, then restart `npm run dev` |
| "Take photo" missing | `getUserMedia` needs a secure context | serve over HTTPS, or use localhost |

---

## 11. The interface

Mobile-first (390 × 844), seven screens, one primary action each.

```
/            Home         the thesis and a single button
/moment      Moment       occasion + goal + time
/look        Your look    camera or upload, what you're wearing, how dressed up
/analyzing   Analyzing    analysis then decision, orchestrated server-side
/one-change  ONE CHANGE   the fit verdict, then the change
/compare     Before/After the visual proof · "Keep it / Try another"
/ready       Ready        the way out
```

The interface decides nothing: it displays what the engine chose. Only the
session id lives in the browser — every screen re-reads `GET /sessions/{id}`, so
a refresh recovers exactly the same decision. The photo persists nowhere on the
client: reloaded before the analysis, it is asked for again rather than
silently replaced.

The signature element is the **impact needle**: one axis, a thin tick for the
current state, a solid one for the projected state. The movement *is* the
information. Below it, the ledger lists what changes (one line, in the signal
colour) and everything that stays (in mercury, marked "Keep") — the visual
hierarchy carries the product thesis itself.

Detail: [`apps/web/README.md`](apps/web/README.md).

---

## Licence

MIT — see [`LICENSE`](LICENSE). Third-party resources, catalogue visuals and
fonts: [`NOTICE.md`](NOTICE.md).

---

**MIRROR OPS** — Fit the moment. One change.
