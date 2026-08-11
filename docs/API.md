# Contrat d'API MIRROR OPS

Base : `/api/v1` · JSON · images en `multipart/form-data` · session anonyme.
Schéma complet : `docs/openapi.json`, Swagger : `/docs`, ReDoc : `/redoc`.

> The API should expose **decisions**, not implementation details.

## Parcours

```
POST /sessions
  → POST /moments
      → POST /appearance/analyze     (multipart)
          → POST /one-change/evaluate
              → POST /vto/generate
                  → GET /sessions/{id}
```

Un appel hors séquence renvoie `409 INVALID_STATE`.

## POST /sessions → 201

```json
{"id": "uuid", "status": "active", "state": "SESSION_CREATED", "expires_at": "2026-08-01T20:00:00Z"}
```

## POST /moments → 201

```json
{"session_id": "uuid", "occasion": "presentation", "goal": "professional", "time_available": "<5m"}
```

`occasion` : `interview · presentation · date · business · event · wedding ·
conference · dinner · travel · other`
`goal` : `confident · professional · approachable · elegant · expressive`
`time_available` : `<5m · 5_15m · 15_30m · 30m_plus`

## POST /appearance/analyze → 201 *(multipart)*

Champs : `session_id` (requis), `image` (requis), `outfit` (JSON optionnel), `moment_id` (optionnel).
En-tête optionnel : `Idempotency-Key`.

```json
{
  "jacket": {"present": true, "formality": 0.25, "structure": 0.3, "color_harmony": 0.4, "condition": 0.6},
  "top":    {"present": true, "formality": 0.85},
  "shoes":  {"present": false}
}
```

Tous les champs numériques sont facultatifs. Absents → a priori neutre **et** confiance
de décision réduite : le produit ne prétend jamais avoir mesuré ce qu'il n'a pas mesuré.

Réponse : `analysis_id`, `appearance` (6 dimensions 0–1), `skin`, `skin_source`,
`skin_simulated`, `element_suitability`, `image_quality`, `data_confidence`, `image_url`.

## POST /one-change/evaluate → 201

Corps : `session_id` (+ `moment_id` / `analysis_id` optionnels).
Réponse : l'objet `recommendation` (voir README §5), qui porte désormais le
verdict d'adéquation :

```json
"fit": {
  "state": "ALMOST_THERE",
  "score": 81,
  "headline": "Almost there.",
  "detail": "Your outfit fits the occasion, but the shoes reduce the level of formality.",
  "weakest_element": "shoes"
}
```

`state` vaut `FIT`, `ALMOST_THERE` ou `MISMATCH`. `weakest_element` reste `null`
quand aucun élément ne se détache : le produit ne désigne pas un coupable qu'il
n'a pas observé.

`requires_vto = false` quand l'action est `NO_CHANGE` **ou** `REMOVE_ACCESSORY` —
on ne prouve pas une soustraction avec un catalogue de vêtements.

## POST /vto/generate → 201

Corps : `session_id`, `recommendation_id?`, `garment_asset_id?`. En-tête `Idempotency-Key` recommandé.

```json
{
  "id": "uuid", "status": "completed", "action": "CHANGE_JACKET", "garment_id": "jacket_01",
  "provider": "youcam_apparel_vto", "simulated": false,
  "before_image_url": "…", "result_image_url": "…", "latency_ms": 4210,
  "created_at": "2026-08-01T18:02:30Z"
}
```

`409 VTO_NOT_APPLICABLE` si la décision est `NO_CHANGE`.

## GET /sessions/{id}

Retourne `session`, `moment`, `analysis`, `recommendation`, `vto` : l'écran final se
reconstruit en une seule requête (refresh, recovery, démo).

## POST /garments/upload → 201 *(multipart)*

Champs : `session_id`, `image`. Renvoie `{id, width, height, size_bytes}`.
L'`id` s'utilise tel quel comme `garment_asset_id` sur `POST /vto/generate`.

La photo est normalisée comme celles du catalogue (fond blanc, RGB, JPEG, côté
long ≥ 1024 px), rangée avec les autres médias temporaires de la session, et
supprimée à expiration. Une pièce n'est visible que depuis la session qui l'a
téléversée.

## GET /garments?category=jacket · GET /vto/{id} · GET /media/{key}?exp&sig

Les médias ne sont accessibles que via une URL signée à durée de vie limitée.

## Erreurs

```json
{"error": {"code": "INVALID_IMAGE", "message": "We need a clearer view of your look.", "retryable": true}}
```

| Code | HTTP | Sens |
|---|---|---|
| `INVALID_REQUEST` | 400/422 | requête incohérente |
| `INVALID_IMAGE` | 422 | photo illisible / trop petite |
| `IMAGE_TOO_LARGE` | 413 | > 10 Mo |
| `IMAGE_UNSUPPORTED` | 422 | format non supporté |
| `INVALID_STATE` | 409 | étape sautée |
| `SESSION_EXPIRED` | 409 | session périmée |
| `VTO_NOT_APPLICABLE` | 409 | rien à visualiser (`NO_CHANGE`) |
| `ANALYSIS_FAILED` | 502 | Skin AI indisponible |
| `VTO_FAILED` / `VTO_TIMEOUT` | 502 / 504 | aperçu impossible |
| `PROVIDER_UNAVAILABLE` | 502 | provider hors service / quota |
| `RATE_LIMITED` | 429 | trop d'appels |
| `MEDIA_LINK_EXPIRED` | 410 | URL signée périmée |
| `NOT_FOUND` | 404 | ressource inconnue |
| `INTERNAL_ERROR` | 500 | erreur interne |

Chaque réponse porte un en-tête `X-Request-ID` (repris de la requête si fourni).
