# Backend architecture

## Principle

> Build the smallest architecture that can make the product look inevitable.

One product. One repository. One deployable. No microservices, no Kubernetes,
no event bus, no ML pipeline, no vector database.

## Layers

```
app/api/v1/routes      HTTP transport, input validation, status codes
app/services           orchestration, transactions, state machine, idempotency
app/engines            decision (ONE CHANGE) and perception (appearance estimator)
app/integrations       provider adapters (YouCam), offline providers
app/models · app/db    persistence
app/core               config, errors, logging, security, rate limit
```

Allowed dependencies: `api → services → engines / integrations → infrastructure`.
Never the reverse. `engines/one_change` imports only `models/enums` — pure
enumerations.

## Data model

```
sessions ─┬─ moments
          ├─ image_assets          (metadata only: bytes live in object storage)
          ├─ appearance_analyses
          ├─ recommendations
          └─ vto_results
idempotency_records                (protects the expensive calls)
```

UUID primary keys, `created_at` / `updated_at`, and `expires_at` on everything
temporary.

**Schema evolution.** No Alembic: `create_all` at startup is enough to create
tables. But `create_all` never adds a column to an existing table — and since
SQLAlchemy selects every declared column, a new field makes any persistent
database unusable, including for queries that don't touch it.
`db/schema_sync.py` closes exactly that gap: it adds missing columns, with a
default value for existing rows.

Deliberately **additive only**. Renaming, dropping or retyping a column belongs
to a real migration; those are rare, and that is no reason to let a demo fall
over on an `UndefinedColumnError`.

## State machine

```
SESSION_CREATED → MOMENT_CREATED → ANALYSIS_COMPLETED → DECISION_COMPLETED
                → VTO_PROCESSING → VTO_COMPLETED → SESSION_COMPLETED
```

Monotonic: state never moves backwards. Any impossible transition →
`409 INVALID_STATE`.

## Asynchrony

No Celery, no Redis, no queue. When a YouCam endpoint is asynchronous, the
polling stays inside the backend and the frontend only ever sees readable
states. *Do not introduce infrastructure before the API requires it.*

## Storage

An `ObjectStorage` interface (`put/get/exists/delete_prefix`) with two
implementations: local disk (the default, sufficient here) and S3/R2/MinIO.
Keys: `sessions/{session_id}/{input|vto|garment}/{hash}.{ext}`. Access only
through HMAC-signed, expiring URLs.

User-imported garments live outside the source tree, under
`apps/api/var/garments/`, resolved before the shipped visuals. A project update
— including an archive extracted on top — can therefore never destroy them.
**A deliverable must never write where the user writes.**

## Observability

Sanitised JSON logs carrying `request_id`, `session_id`, endpoint, latency,
status, provider, `simulated` and error code. No observability platform for this
scope.

Events worth alerting on:

| Message | Meaning |
|---|---|
| `skin_provider_degraded` | Skin AI unavailable; the journey continues without it |
| `vto_provider_failed` | try-on impossible — read `garment_source` and `provider_code` |
| `garment_catalog_is_placeholder` | catalogue not replaced at startup |
| `youcam_live_without_credentials` | incomplete configuration |

## What was deliberately not built

Microservices · Kubernetes · GraphQL · event bus · ML training · vector database ·
multi-agent framework · Redis cluster · native apps · a full e-commerce backend.
