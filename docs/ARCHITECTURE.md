# Architecture backend

## Principe

> Build the smallest architecture that can make the product look inevitable.

Un produit. Un dépôt. Un déployable. Pas de microservices, pas de Kubernetes,
pas de bus d'événements, pas de pipeline ML, pas de base vectorielle.

## Couches

```
app/api/v1/routes      transport HTTP, validation d'entrée, codes de statut
app/services           orchestration, transactions, machine à états, idempotence
app/engines            décision (ONE CHANGE) et perception (estimateur d'apparence)
app/integrations       adapters providers (YouCam), mocks locaux
app/models · app/db    persistance
app/core               config, erreurs, logging, sécurité, rate limit
```

Dépendances autorisées : `api → services → engines / integrations → infrastructure`.
Jamais l'inverse. `engines/one_change` n'importe que `models/enums` (des énumérations pures).

## Modèle de données

```
sessions ─┬─ moments
          ├─ image_assets          (métadonnées seulement : les octets sont dans le stockage objet)
          ├─ appearance_analyses
          ├─ recommendations
          └─ vto_results
idempotency_records                (protection des appels coûteux)
```

Clés primaires UUID, `created_at` / `updated_at`, `expires_at` sur tout ce qui est temporaire.

**Évolution du schéma.** Pas d'Alembic : `create_all` au démarrage suffit à créer
les tables. Mais `create_all` n'ajoute jamais une colonne à une table existante —
et comme SQLAlchemy sélectionne toutes les colonnes déclarées, un champ ajouté au
modèle rend inutilisable toute base persistante, y compris pour les requêtes qui
ne s'en servent pas. `db/schema_sync.py` comble exactement cet écart : il ajoute
les colonnes manquantes, avec une valeur par défaut pour les lignes existantes.

Volontairement **additif seulement**. Renommer, supprimer ou changer un type
relève d'une vraie migration ; c'est rare, et ce n'est pas une raison pour
laisser une démonstration tomber sur un `UndefinedColumnError`.

## Machine à états

```
SESSION_CREATED → MOMENT_CREATED → ANALYSIS_COMPLETED → DECISION_COMPLETED
                → VTO_PROCESSING → VTO_COMPLETED → SESSION_COMPLETED
```

Monotone : l'état n'avance jamais en arrière. Toute transition impossible → `409 INVALID_STATE`.

## Asynchrone

Pas de Celery, pas de Redis, pas de queue. Si un endpoint YouCam est asynchrone, le
polling reste dans le backend et le frontend ne voit que des états lisibles.
*Do not introduce infrastructure before the API requires it.*

## Stockage

Interface `ObjectStorage` (`put/get/exists/delete_prefix`) avec deux implémentations :
disque local (défaut, suffisant pour le hackathon) et S3/R2/MinIO. Clés :
`sessions/{session_id}/{input|vto}/{hash}.{ext}`. Accès uniquement par URL signée HMAC
à durée de vie limitée.

## Observabilité

Logs JSON assainis avec `request_id`, `session_id`, endpoint, latence, statut,
provider, `simulated`, code d'erreur. Pas de plateforme d'observabilité pour le MVP.

## Ce qui n'est volontairement pas construit

Microservices · Kubernetes · GraphQL · bus d'événements · entraînement ML · base vectorielle ·
framework multi-agents · cluster Redis · apps natives · backend e-commerce complet.
