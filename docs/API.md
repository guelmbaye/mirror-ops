# MIRROR OPS API contract

Base: `/api/v1` · JSON · images as `multipart/form-data` · anonymous session.
Full schema: `docs/openapi.json`, Swagger: `/docs`, ReDoc: `/redoc`.

> The API should expose **decisions**, not implementation details.

## Journey

```
POST /sessions
  → POST /moments
      → POST /appearance/analyze     (multipart)
          → POST /one-change/evaluate
              → POST /vto/generate
                  → GET /sessions/{id}
```

Any out-of-order call returns `409 INVALID_STATE`.

## POST /sessions → 201

```json
{"id": "uuid", "status": "active", "state": "SESSION_CREATED", "expires_at": "2026-08-01T20:00:00Z"}
```

## POST /moments → 201

```json
{"session_id": "uuid", "occasion": "presentation", "goal": "professional", "time_available": "<5m"}
```

`occasion`: `interview · presentation · date · business · event · wedding ·
conference · dinner · travel · other`
`goal`: `confident · professional · approachable · elegant · expressive`
`time_available`: `<5m · 5_15m · 15_30m · 30m_plus`

A session carries **one** moment. Posting again updates it rather than creating
a second: going back to correct the occasion must change the outcome, not race
against a duplicate.

## POST /appearance/analyze → 201 *(multipart)*

Fields: `session_id` (required), `image` (required), `outfit` (optional JSON),
`moment_id` (optional). Optional header: `Idempotency-Key`.

```json
{
  "jacket": {"present": true, "formality": 0.25, "structure": 0.3, "color_harmony": 0.4, "condition": 0.6},
  "top":    {"present": true, "formality": 0.85},
  "shoes":  {"present": false}
}
```

`odd_one_out` names the piece the user flagged as more casual than the rest —
the choice, not a level. The server drops it one notch in the scale the user was
shown. Deriving it here rather than in the browser keeps a decision rule in the
engine, where it can be corrected without rebuilding a client.

Every numeric field is optional. When absent, MIRROR OPS applies a neutral prior
**and** lowers decision confidence: the product never claims to have measured
what it hasn't.

The photo is straightened according to its EXIF orientation before anything else
happens. A phone portrait stored as landscape would otherwise be analysed
sideways — an undetectable face for Skin AI, an unreadable pose for the try-on.

Response: `analysis_id`, `appearance` (6 dimensions 0–1), `skin`, `skin_source`,
`skin_simulated`, `element_suitability`, `image_quality`, `data_confidence`,
`image_url`.

`skin_source` is `unavailable_no_face` when no usable face was found in the
photo. The journey continues without a skin signal — Skin AI informs the
decision, it does not make it.

## POST /one-change/evaluate → 201

Body: `session_id` (+ optional `moment_id` / `analysis_id`).
Response: the `recommendation` object, which carries the fit verdict:

```json
"fit": {
  "state": "ALMOST_THERE",
  "score": 81,
  "headline": "Almost there.",
  "detail": "Your outfit fits the occasion, but the shoes reduce the level of formality.",
  "weakest_element": "shoes"
}
```

`state` is `FIT`, `ALMOST_THERE` or `MISMATCH`. `weakest_element` stays `null`
when no element genuinely stands out: the product does not name a culprit it has
not observed.

`is_addition` is `true` when the target piece was absent — the interface must
then write "Add", not "Change", wherever it names the intervention. The verb
comes from the backend, never from parsing the label.

`suggested_garment` names the piece the proof will use, so the button can say
what it will show without offering a catalogue to browse.

`requires_vto` is `false` when the action is `NO_CHANGE` **or**
`REMOVE_ACCESSORY` — you don't prove a subtraction with a garment catalogue.

## POST /vto/generate → 201

Body: `session_id`, `recommendation_id?`, `garment_asset_id?`. `Idempotency-Key`
recommended.

```json
{
  "id": "uuid", "status": "completed", "action": "CHANGE_JACKET", "garment_id": "jacket_01",
  "provider": "youcam_apparel_vto", "simulated": false,
  "before_image_url": "…", "result_image_url": "…", "latency_ms": 13003,
  "created_at": "2026-08-01T18:02:30Z"
}
```

`409 VTO_NOT_APPLICABLE` when the decision is `NO_CHANGE`.

Any failure carries `garment_source` — `catalog` or `uploaded` — and
`garment_id`. That is the first thing to read: it says at a glance whether the
shipped catalogue is at fault, or whether to look elsewhere.

## POST /garments/upload → 201 *(multipart)*

Fields: `session_id`, `image`. Returns `{id, width, height, size_bytes}`. The
`id` is used directly as `garment_asset_id` on `POST /vto/generate`.

The photo is normalised like the catalogue's (white background, RGB, JPEG, long
side ≥ 1024 px), stored with the session's other temporary media, and deleted on
expiry. A piece is only reachable from the session that uploaded it.

## GET /sessions/{id}

Returns `session`, `moment`, `analysis`, `recommendation`, `vto`: the final
screen rebuilds in a single request — refresh, recovery, demo.

## GET /garments?category=jacket · GET /vto/{id} · GET /media/{key}?exp&sig

Each garment reports whether its visual is a real photograph or a generated flat
shape (`"placeholder": true`). Media are only reachable through a signed,
short-lived URL.

## Errors

```json
{"error": {"code": "INVALID_IMAGE", "message": "We need a clearer view of your look.", "retryable": true}}
```

| Code | HTTP | Meaning |
|---|---|---|
| `INVALID_REQUEST` | 400/422 | inconsistent request, or no outfit declared |
| `INVALID_IMAGE` | 422 | unreadable or too small a photo |
| `IMAGE_TOO_LARGE` | 413 | over 10 MB |
| `IMAGE_UNSUPPORTED` | 422 | unsupported format |
| `INVALID_STATE` | 409 | step skipped |
| `SESSION_EXPIRED` | 409 | session expired |
| `VTO_NOT_APPLICABLE` | 409 | nothing to visualise (`NO_CHANGE`) |
| `ANALYSIS_FAILED` | 502 | Skin AI unavailable |
| `VTO_FAILED` / `VTO_TIMEOUT` | 502 / 504 | preview impossible |
| `PROVIDER_UNAVAILABLE` | 502 | provider down or out of quota |
| `RATE_LIMITED` | 429 | too many calls |
| `MEDIA_LINK_EXPIRED` | 410 | signed URL expired |
| `NOT_FOUND` | 404 | unknown resource |
| `INTERNAL_ERROR` | 500 | internal error |

Every response carries an `X-Request-ID` header (echoed from the request when
supplied). In `APP_ENV=development`, provider failures also carry a `details`
object with the exact cause — production keeps the contract opaque.
