# YouCam integration

> Never build the product around the API response.
> Build the product around the user decision, then use YouCam to make that
> decision possible.

## 1. The boundary

```
Browser ──► MIRROR OPS backend ──► adapters ──► YouCam
                                     │
                          SkinAnalysisResult / VTOGenerationResult
```

The browser **never** talks to YouCam. The key stays server-side. Business code
never calls `httpx` directly: it calls `skin_provider.analyze(...)` or
`vto_provider.generate(...)`.

## 2. Files

| File | Role |
|---|---|
| `client.py` | HTTP, auth, timeouts, bounded retries, uploads, tasks, polling |
| `skin_ai.py` | full Skin AI protocol → normalised observations |
| `apparel_vto.py` | Apparel VTO protocol → transformed image |
| `mappers.py` | the only place that knows YouCam response shapes |
| `auth.py` | RSA `id_token` for the legacy v1 auth |
| `exceptions.py` | internal error taxonomy (the rest of the code sees only this) |
| `mock.py` | offline local providers, explicitly marked "simulated" |
| `provider.py` | protocols + `mock` / `live` factory |

## 2 bis. Authentication

**The product uses API v2, which has no authentication endpoint.** The API key
goes straight into a header:

```
Authorization: Bearer YOUR_API_KEY
```

One variable is enough: `YOUCAM_API_KEY`, created in the console
(<https://yce.perfectcorp.com/api-console/en/api-keys/>).

### Console vocabulary, which is confusing

In YouCam's documentation, the **"API Key" is the `client_id` and the "Secret
key" is the `client_secret`**. There are not three distinct values: those are
two names for the same pair. The Secret key is shown only at creation time and
cannot be read back.

Those two values are only needed by API **v1**, which additionally requires
RSA-encrypting the secret to produce an `id_token`. That is implemented in
`auth.py` and covered by `tests/test_youcam_auth.py`, but **it is no longer the
default path**: v2 makes all of it unnecessary.

## 2 ter. Base URL

`https://yce-api-01.makeupar.com` — not `perfectcorp.com`, which the brand uses
for its site and console but not for the API.

## 3. Live flow

```
validated image
   ↓ POST  /s2s/v2.0/file/skin-analysis      → file_id + pre-signed upload URL
   ↓ PUT   upload URL                        → image bytes
   ↓ POST  /s2s/v2.0/task/skin-analysis      → task_id
   ↓ GET   /s2s/v2.0/task/skin-analysis/{id} → polling (task_id in the PATH)
   ↓ mappers.normalize_skin_payload          → {texture, redness, oiliness, radiance}
```

The v2 envelope is `{"status": 200, "data": {...}}`, and the task state is called
`task_status`. The try-on follows the same shape on
`/s2s/v2.0/{file,task}/cloth` — **"cloth", singular**.

The cloth task expects `src_file_id` and `ref_file_id` — **singular**, never an
array — plus `garment_category` and `change_shoes`.

Polling stays **in the backend**: the frontend only ever sees
`ANALYZING → VTO PREPARATION → READY`.

## 4. One photo, two contradictory requirements

Skin AI rejects any image where the face occupies less than **60% of the width**
(`error_src_face_too_small`). MIRROR OPS photographs an **outfit**, where the
face is necessarily small. The two do not fit in one framing.

The journey nonetheless stays at **one shot**: asking for a second would add a
screen, and the constraint is the product. The outfit photo is therefore cropped
server-side (`services/face_crop.py`) before the Skin AI call — the original,
untouched, goes to the try-on and to the screen.

```
outfit photo ──┬─→ face crop (68% of the width) ──→ Skin AI
               └─→ original image ─────────────────→ Apparel VTO
```

Accepted consequences:

- Actions are **SD**, not HD: HD requires a short side ≥ 1080 px, which a face
  crop taken from a full-length photo rarely reaches.
- A detected face under 140 px wide produces **no** call: enlarging it would only
  yield interpolated pixels, and analysing an invention is worse than analysing
  nothing.
- No face detected → no call either. That saves a credit on a certain rejection,
  and `skin_source` reads `unavailable_no_face`.

Detection uses the Haar classifier shipped with OpenCV. The dependency is
**optional at runtime**: without it, the journey continues without a skin signal.

## 4 bis. A failed task names its cause

A terminal `error` status says nothing by itself. The response body carries an
`error_code`: `error_pose`, `error_multiple_people`, `error_no_shoulder`,
`error_unsupport_ratio`, `error_editing_failed`, `unknown_internal_error`…

That code is extracted, logged, carried on the exception (`provider_code`) and
translated into guidance by `services/photo_guidance.py`. A **photo** problem
becomes a `422` with an actionable sentence — *"We can only work with one person
in the photo"* — rather than a generic `502`: the user can act, so they must be
told.

An `unknown_internal_error` remains a service failure.

## 4 ter. `error_editing_failed`: look at the garment first

This code means the render could not be produced. In this project the cause is
almost always the **reference** image: a flat shape is not a garment, and the
model has nothing to segment.

Every try-on failure now carries `garment_source` — `catalog` or `uploaded` —
and `garment_id`. That is the first thing to read: it says at a glance whether
the shipped catalogue is at fault.

The shortest path remains **"Try a piece of your own"**: the person photographs
the piece they're considering, and the catalogue is out of the equation.

For the catalogue itself, three tools close the loop:

```bash
python scripts/check_garments.py                  # is the catalogue real?
python scripts/import_garments.py <folder>        # replace it in one command
python scripts/probe_vto.py photo.jpg jacket_01   # one try-on, raw responses
```

Whatever is dropped into the catalogue, `garment_service.normalized_garment_bytes`
converts before sending: white background, RGB, JPEG, long side ≥ 1024 px.
Format, transparency and size are therefore removed from the equation.

### Local catalogue or online catalogue?

The API accepts `ref_file_url` as an alternative to `ref_file_id`: YouCam can
fetch a garment image by URL. That path was **not** chosen, for three reasons:
the URL must be reachable from YouCam's servers — so never a demo `localhost`; a
dead link breaks the journey at the worst moment; and it forfeits the
normalisation that removes a whole family of failures.

Online referencing therefore happens **at import time**: download once,
normalise, serve locally. You keep the flexibility of a remote catalogue without
its fragility.

## 5. Normalisation

`mappers.py` accepts 0–100 as readily as 0–1 scales, nested values, aliases
(`hd_redness`, `skin_texture`, …), and ignores metrics the product does not use.
Only what actually feeds the decision is stored.

If no usable observation comes back, the adapter **raises** rather than inventing
values.

### Score direction: a necessary inversion

At YouCam, a **high** score means **healthy** skin. MIRROR OPS reasons in
**severity**: the more marked the redness, the higher the value.
`mappers.INVERTED_METRICS` therefore inverts `redness`, `oiliness` and
`texture`, and leaves `radiance` alone since it is already a quality. Without
that inversion, flawless skin would read as heavily marked and the skin signal
would push the decision the wrong way.

## 6. Errors and retries

| Provider error | Retry | User-facing message |
|---|---|---|
| timeout / transient error | yes (max 2, backoff) | "Try again" |
| rate limit | no | "Try again in a moment" |
| auth / quota | no | "The service is unavailable" |
| invalid image | no | the specific guidance for that code |

No raw YouCam error ever reaches the user.

### Skin AI cannot fail a journey

A provider outage — timeout, quota, rejected image — no longer returns an error:
the analysis continues with `skin_source = "unavailable"`, without invented
values, and decision confidence drops on its own. That follows directly from the
positioning: *Skin AI informs the decision, it does not make it.* A third-party
service must not be able to interrupt a demo.

Rate limiting is the exception: it stays surfaced to the user, because trying
again later makes sense.

## 7. Credit economy

```
1 photo → 1 Skin AI analysis → N candidates scored → 1 try-on (winner only)
```

- `NO_CHANGE` → **no** try-on call.
- Short-lived cache keyed by image fingerprint for the analysis.
- `Idempotency-Key` on `analyze` and `vto/generate`, derived from **all** the
  inputs: a double-click costs nothing, a corrected outfit is genuinely
  re-analysed.
- A test explicitly checks that one journey costs one analysis and one try-on.

## 8. Honest degraded mode

`YOUCAM_MODE=mock` runs the full journey offline. Results carry
`provider = local_heuristic | local_composite`, `simulated = true`, and the
generated image displays "SIMULATED PREVIEW — not generated by YouCam". A result
that did not come from YouCam never pretends it did — including during a demo.

## 9. Before going live

The single check that summarises everything: `GET /api/v1/health/dependencies`.

| Response | Meaning |
|---|---|
| `"configured"` | ready |
| `"mock_mode"` | previews will be marked "simulated" |
| `"missing_credentials"` | key absent |
| `"missing_dependency"` | `cryptography` not installed |

Then:

1. Write the configuration into **`apps/api/.env`**, and nowhere else. The root
   `.env` is for docker-compose and is not read by uvicorn. Restart the API:
   configuration and providers are resolved once, at startup.
2. Verify the key and **remaining credits**.
3. Confirm in the Playground which endpoints your account can reach.
4. Align `YOUCAM_*_PATH` and `YOUCAM_SKIN_ACTIONS` with what is enabled.
5. Replace the catalogue visuals, freeze the demo assets, and re-run
   `scripts/audit_journey.py` several times.

If a preview carries "simulated" while you believe you are in `live`, the process
is running in `mock`: the stamp never lies. The decisive check is
`/health/dependencies`, which reports the mode actually in force — not the one
the file announces.
