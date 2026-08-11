<img src="apps/web/public/logo-mirror-ops.png" alt="Mirror Ops" height="72">

**FIT THE MOMENT. ONE CHANGE.**

MIRROR OPS est un **moteur de décision d'apparence contextuel**. Il comprend le moment
que vous vivez, lit votre look actuel, identifie **la seule** intervention qui vaut la
peine — ou décide qu'il n'y en a aucune — et la prouve visuellement avant que vous
n'agissiez.

> *Don't redesign your look. Fix the mismatch.*

La question du produit tient en cinq mots : **« Will this look work here? »**
La même tenue peut convenir à un dîner et détonner à un mariage. D'autres outils
**constatent** votre apparence et vous rendent des options. MIRROR OPS **décide**.

```
CHECK YOUR LOOK   ≠   DECIDE WHAT IS WORTH CHANGING
```

Positionnement complet et règles non négociables : [`docs/POSITIONING.md`](docs/POSITIONING.md).
Mise en production sur `mirror-ops.vylantic.com` : [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
Revue produit, UX et business — constats mesurés, corrections et arbitrages
ouverts : [`docs/PRODUCT_REVIEW.md`](docs/PRODUCT_REVIEW.md).

Ce dépôt contient l'implémentation complète : le backend FastAPI (`apps/api`)
et l'interface Next.js (`apps/web`), reliés par un contrat TypeScript partagé
(`packages/types`).

---

## 1. Ce que fait le produit

```
  MOMENT        →  CURRENT LOOK   →  CONTEXTUAL FIT  →  ONE CHANGE  →  PROOF     →  ACT
  occasion,        photo +           FIT / ALMOST /     le levier      YouCam       vous
  objectif,        YouCam Skin AI    MISMATCH           décisif        VTO          partez
  temps
```

L'étape **CONTEXTUAL FIT** précède le changement, et cet ordre *est* le
positionnement : le produit répond d'abord « ce look va-t-il ici ? », ensuite
seulement « que changer ? ». Trois verdicts — `FIT` (« You're good to go »),
`ALMOST_THERE` (« Almost there », avec l'élément en cause nommé), `MISMATCH`.

La question n'est pas *« quelle tenue porter ? »* mais *« dois-je changer quelque chose —
et si oui, quoi ? »*. Le moteur peut aussi répondre **NO_CHANGE**, sans consommer de VTO :
un moteur de décision qui ne peut pas décider de ne rien faire n'est pas un moteur de
décision.

Skin AI **informe** la décision. Apparel VTO la **prouve**. Une panne du premier
ne peut pas interrompre le parcours : la décision se prend sans lui, en le disant. L'innovation n'est pas la
combinaison de ces deux API — c'est un moteur d'intervention qui se limite délibérément
à un seul changement à forte valeur. **La contrainte est le produit** — on ne
redessine pas la personne, on corrige l'écart.

L'intervention peut prendre trois formes : **changer** une pièce, en **ajouter**
une qui manque, en **retirer** une de trop. Un retrait ne demande aucun essayage.

---

## 2. Architecture

Monolithe modulaire, un seul déployable (Doc 07).

```
                    Browser / Next.js
                           │  HTTPS  (jamais de clé YouCam côté client)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                     FastAPI — MIRROR OPS API                 │
│                                                              │
│   api/routes ──► services ──► engines        integrations    │
│                     │            │                │          │
│                     │       ONE CHANGE       YouCam adapters │
│                     │      (domaine pur)      Skin AI · VTO  │
│                     ▼                                        │
│              PostgreSQL  +  stockage objet temporaire        │
└──────────────────────────────────────────────────────────────┘
```

**Règle de dépendance** : `api → services → engines / integrations → infrastructure`.
Le moteur ONE CHANGE n'importe ni FastAPI, ni SQLAlchemy, ni HTTP : il se teste sans
réseau, sans base et sans YouCam.

```
mirror-ops/
├── apps/
│   └── api/                         # backend FastAPI (ce qui est livré ici)
│       ├── app/
│       │   ├── api/v1/routes/       # sessions, moments, appearance, one_change, vto, media, health
│       │   ├── core/                # config, erreurs, logging, sécurité, rate limit
│       │   ├── db/                  # base déclarative + session async
│       │   ├── models/              # SQLAlchemy + enums partagés
│       │   ├── schemas/             # contrat public Pydantic
│       │   ├── engines/
│       │   │   ├── one_change/      # ★ moteur de décision (domaine pur)
│       │   │   └── appearance/      # estimateur de contexte d'apparence
│       │   ├── integrations/youcam/ # client, adapters, mappers, mocks locaux
│       │   ├── services/            # orchestration, stockage, idempotence, cleanup
│       │   └── assets/garments/     # petit catalogue contrôlé + visuels
│       └── tests/                   # 72 tests (moteur, API, sécurité, adapters)
│   └── web/                         # interface Next.js (App Router, TypeScript)
│       └── src/
│           ├── app/                 # 7 écrans : / moment look analyzing one-change compare ready
│           ├── components/          # Stage, Verdict ★, BeforeAfter, ChoiceGroup, Notice
│           └── lib/                 # client API typé, session, photo, formats
├── packages/types/                  # types TypeScript du contrat d'API
├── packages/config/                 # libellés produit partagés
├── scripts/                         # demo_flow, calibrate_engine, cleanup, export_openapi
├── docs/                            # architecture, moteur, intégration, API, runbook démo
├── docker-compose.yml
├── .env                             # variables docker-compose (fourni, prêt à l'emploi)
├── apps/api/.env                    # config backend (fourni, mode mock)
└── apps/web/.env.local              # URL de l'API pour l'interface (fourni)
```

---

## 3. Démarrage rapide (2 minutes, sans YouCam)

Le mode `mock` fait tourner **tout le parcours** hors ligne, sans consommer une seule unité API.

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate      # Python 3.11+
pip install -r requirements-dev.txt

# Après toute mise à jour du dépôt, relancer cette commande : de nouvelles
# dépendances peuvent être apparues (par ex. `cryptography`, requise par
# l'authentification YouCam en mode live).

uvicorn app.main:app --reload --port 8000
```

Puis l'interface, dans un second terminal :

```bash
npm install                    # Node 18.18+
npm run dev                    # http://localhost:3000
```

Le parcours complet est alors utilisable dans le navigateur. Pour le vérifier
sans interface — ou pour répéter la démonstration — un troisième terminal :

```bash
python scripts/demo_flow.py
```

```
  ✓ session                         62 ms
  ✓ moment                          48 ms
  ✓ appearance + skin AI           826 ms
  ✓ ONE CHANGE                      18 ms
  ┌─────────────────────────────────────────────
  │ ONE CHANGE   Change the jacket
  │ Impact       71/100
  │ Confidence   medium
  │ Keep         accessories, bottom, shoes, top
  └─────────────────────────────────────────────
  ✓ apparel VTO                    287 ms
  Parcours complet : 1372 ms
```

Documentation interactive : <http://localhost:8000/docs> · schéma : `docs/openapi.json`.

### Avec Docker (tout compris)

```bash
docker compose up --build      # interface :3000 · API :8000 · PostgreSQL :5432
```

---

### Sous Windows (PowerShell)

Le `Makefile` ne sert à rien sans outillage supplémentaire. `scripts\mirror-ops.ps1`
couvre les mêmes tâches et trouve seul l'interpréteur du venv, quel que soit le
répertoire courant :

```powershell
.\scripts\mirror-ops.ps1 help
.\scripts\mirror-ops.ps1 dev-api          # http://localhost:8000
.\scripts\mirror-ops.ps1 dev-web          # http://localhost:3000
.\scripts\mirror-ops.ps1 test
.\scripts\mirror-ops.ps1 health
```

Si l'exécution de scripts est bloquée :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Deux différences de syntaxe qui piègent : PowerShell ne développe pas `~` pour un
exécutable natif — utilisez `$HOME` — et les chemins prennent des antislashs.

## 4. Brancher le vrai YouCam

1. Créer le compte YouCam / Perfect Corp, vérifier la clé **et les unités disponibles**.
2. Tester Skin AI et Apparel VTO dans le Playground, **noter les chemins d'endpoints réels**.
3. Renseigner dans **`apps/api/.env`** — c'est le seul fichier lu par l'API.
   Le `.env` racine ne sert qu'à `docker compose` :

```dotenv
YOUCAM_MODE=live
YOUCAM_AUTH_MODE=api_key
YOUCAM_API_KEY=...        # console : https://yce.perfectcorp.com/api-console/en/api-keys/
YOUCAM_SKIN_TASK_PATH=/s2s/v1.0/task/skin-analysis    # à confirmer selon le compte
YOUCAM_VTO_TASK_PATH=/s2s/v1.0/task/clothes           # à confirmer selon le compte
```

4. **Le catalogue, ou la pièce de l'utilisateur.** Deux chemins mènent à une
   preuve visuelle, et le second ne dépend d'aucun fichier livré :

   - **« Try a piece of your own »**, sur l'écran de décision *et* sur
     Before/After : la personne
     photographie la veste qu'elle envisage et la voit sur elle. Rien à
     installer, rien à préparer. C'est aussi le meilleur usage réel du produit —
     on hésite rarement devant un catalogue, souvent devant une pièce précise.
   - **Le catalogue**, qui garantit qu'une preuve existe toujours sans rien
     demander à l'utilisateur au milieu d'un parcours de 90 secondes.

   Les visuels livrés sont des aplats générés programmatiquement : suffisants
   pour le mode `mock`, inexploitables par un vrai try-on, qui échoue dessus en
   `error_editing_failed`.

   ```bash
   python scripts/check_garments.py                    # ce qui reste à remplacer
   python scripts/import_garments.py ~/mes-vetements   # importe un dossier
   python scripts/import_garments.py --id jacket_01 ~/veste.jpg
   python scripts/import_garments.py catalogue.txt     # depuis un catalogue en ligne
   ```

   Le manifeste est une ligne par pièce — `identifiant  URL` :

   ```
   jacket_01   https://votre-cdn/veste-marine.jpg
   shoes_01    https://votre-cdn/derbies-noires.jpg
   ```

   Les images sont téléchargées **une fois**, normalisées, puis servies
   localement : le parcours ne dépend d'aucun hébergeur tiers au moment où
   cela compte.

   ```powershell
   .\scripts\mirror-ops.ps1 garments
   .\scripts\mirror-ops.ps1 import-garments -Path $HOME\Downloads\vetements -DryRun
   .\scripts\mirror-ops.ps1 import-garments -Path $HOME\Downloads\vetements
   .\scripts\mirror-ops.ps1 import-garments -Path $HOME\veste.jpg -Id jacket_01
   ```

   Vos fichiers n'ont pas à porter les noms du catalogue : l'import reconnaît la
   catégorie depuis le nom, en français comme en anglais — `veste-marine.jpg`,
   `sneakers white.png`, `chemise blanche.jpeg`, `sac1.jpg`. **Le catalogue
   grandit tout seul** : si une catégorie est pleine, une nouvelle pièce est
   créée (`jacket_04`, `shoes_03`…), avec les attributs médians de sa catégorie
   et sa teinte dominante échantillonnée sur l'image. Ce qui n'est pas reconnu
   est laissé de côté et nommé ; `--auto` (`-Auto` sous PowerShell) attribue le
   reste aux emplacements encore libres.
   Tout est normalisé (fond blanc, RGB, JPEG, côté long ≥ 1024 px) et **écrit
   dans `apps/api/var/garments/`**, jamais dans le code source : vos photos
   survivent à toute mise à jour du projet, y compris à une archive
   décompressée par-dessus. Les visuels livrés servent uniquement de repli.

   Commencez toujours par `--dry-run` : il affiche la correspondance sans écrire.

   Pour isoler une panne d'essayage sans dérouler tout le parcours :

   ```bash
   python scripts/probe_vto.py ma-photo.jpg jacket_01
   ```

   ```powershell
   .\scripts\mirror-ops.ps1 probe -Photo .\ma-photo.jpg -Garment jacket_01
   ```

   La sonde fait l'appel nu et affiche le code d'erreur du provider.

5. **Redémarrer l'API**, puis vérifier :
   `curl localhost:8000/api/v1/health/dependencies` → `"youcam": "configured"`.
   Tant que cette réponse indique `"mock_mode"`, les aperçus resteront marqués
   « simulated » — le tampon dit la vérité sur ce qui a réellement produit l'image.

Aucun code métier ne change entre `mock` et `live` : seuls les adapters diffèrent.
Les chemins d'endpoints et les noms de métriques sont **configurables**, parce qu'ils
dépendent des capacités réellement activées sur le compte.

> **Honnêteté du fallback.** En mode `mock`, les résultats sont marqués `simulated: true`,
> le provider s'appelle `local_heuristic` / `local_composite`, et l'image porte le filigrane
> *« SIMULATED PREVIEW — not generated by YouCam »*. Un résultat qui ne vient pas de YouCam
> ne prétend jamais en venir.

---

## 5. Contrat d'API

| Méthode | Route | Rôle |
|---|---|---|
| `POST` | `/api/v1/sessions` | démarrer un parcours anonyme |
| `POST` | `/api/v1/moments` | occasion + objectif + temps disponible |
| `POST` | `/api/v1/appearance/analyze` | photo → Skin AI → contexte d'apparence |
| `POST` | `/api/v1/one-change/evaluate` | **la** recommandation |
| `POST` | `/api/v1/vto/generate` | preuve visuelle (uniquement pour le gagnant) |
| `POST` | `/api/v1/garments/upload` | essayer sa propre pièce |
| `GET` | `/api/v1/vto/{id}` | état / résultat d'un aperçu |
| `GET` | `/api/v1/sessions/{id}` | tout l'écran final en une requête |
| `GET` | `/api/v1/garments` | catalogue, avec `placeholder` par pièce |
| `GET` | `/api/v1/media/{key}` | média temporaire signé |
| `GET` | `/api/v1/health` · `/health/dependencies` | santé |

Réponse ONE CHANGE :

```json
{
  "recommendation": {
    "id": "…",
    "action": "CHANGE_JACKET",
    "label": "Change the jacket",
    "score": 71,
    "confidence": "medium",
    "what": "Change the jacket.",
    "why": "Among the changes available to you right now, the jacket offers the highest expected improvement for professional presence — it is the lever most aligned with your goal, and it fits what this occasion calls for.",
    "how": "Keep the rest of your look exactly as it is.",
    "keep": ["accessories", "bottom", "shoes", "top"],
    "impact": {
      "before": {"professional_presence": 58, "visual_coherence": 64, "confidence_proxy": 64},
      "after":  {"professional_presence": 74, "visual_coherence": 79, "confidence_proxy": 76},
      "dominant_factors": ["goal_alignment", "context_fit"]
    },
    "requires_vto": true,
    "suggested_garment": {"id": "jacket_01", "name": "Structured Neutral Jacket", "category": "jacket"}
  }
}
```

Toutes les erreurs partagent une seule forme :

```json
{"error": {"code": "INVALID_IMAGE", "message": "We need a clearer view of your look.", "retryable": true}}
```

Détail complet : [`docs/API.md`](docs/API.md).

---

## 6. Le moteur ONE CHANGE

```
INPUT → Validate → Build Context → Generate Candidates → Score
      → Threshold → Tie-breaker → Winner → Explain → (VTO)
```

Score normalisé 0–100, pondérations **configurables** :

| Feature | Poids | Question posée |
|---|---|---|
| `goal_alignment` | 0.25 | ce levier sert-il l'objectif ? |
| `context_fit` | 0.20 | est-il adapté à l'occasion ? |
| `visual_impact` | 0.20 | le changement se verra-t-il ? |
| `current_gap` | 0.10 | y a-t-il de la marge sur cette pièce ? |
| `time_fit` | 0.10 | est-ce réaliste dans le temps disponible ? |
| `data_confidence` | 0.10 | lisons-nous cet élément de façon fiable ? |
| `vto_feasibility` | 0.05 | peut-on le montrer avant décision ? |

Propriétés garanties (couvertes par des tests) : **une seule** action, déterminisme,
explication dérivée des facteurs réellement dominants, `NO_CHANGE` possible,
prise en compte du temps, aucun LLM requis, aucun claim médical.

Banc de calibration : `python scripts/calibrate_engine.py`.
Détail : [`docs/ONE_CHANGE_ENGINE.md`](docs/ONE_CHANGE_ENGINE.md).

---

## 7. Tests

```bash
cd apps/api && python -m pytest -q      # 72 tests
```

| Fichier | Couvre |
|---|---|
| `test_engine_scenarios.py` | les 5 scénarios du spec + déterminisme, filtrage, seuils |
| `test_api_flow.py` | parcours complet, NO_CHANGE, catalogue, images servies |
| `test_api_errors.py` | contrat d'erreur, image corrompue/trop petite/trop lourde, pannes provider |
| `test_state_machine.py` | transitions impossibles → 409, session expirée, ressources croisées |
| `test_idempotency_and_units.py` | 1 parcours ≈ 1 analyse + 1 VTO, double-clic neutralisé |
| `test_youcam_adapter.py` | normalisation multi-format, retries, protocole live simulé |
| `test_security_privacy.py` | URLs signées, traversal, logs sans secrets, cleanup |
| `test_contract_shapes.py` | stabilité du contrat public |
| `test_try_another.py` | changer de pièce ne change jamais la décision (règle 3) |
| `test_face_crop.py` | le cadrage envoyé à Skin AI satisfait sa contrainte de 60 % |
| `test_image_orientation.py` | une photo portrait de téléphone n'est jamais traitée couchée |
| `test_going_back.py` | revenir en arrière et corriger change réellement le résultat |
| `test_schema_sync.py` | une base existante survit à l'ajout d'un champ |
| `test_task_failures.py` | un échec de tâche nomme sa cause et guide la reprise |
| `test_garment_audit.py` | le catalogue s'annonce comme substitution tant qu'il l'est |
| `test_garment_import.py` | l'import reconnaît les catégories sans exiger de renommage |
| `test_garment_audit.py` | vos photos priment sur les visuels livrés et survivent aux mises à jour |
| `test_own_garment.py` | on peut essayer sa propre pièce, isolée par session |
| `test_decision_gate.py` | le refus nomme ce qui manque : la photo ou la tenue |
| `test_contextual_fit.py` | le verdict d'adéquation, les dix occasions, et l'interdiction d'inventer un coupable |

Une pièce absente n'est plus écartée : elle devient une **addition**. Le libellé
suit la réalité — « Add a jacket » et non « Change the jacket » à quelqu'un qui
n'en porte pas. Le champ `is_addition` porte cette vérité jusqu'à l'interface :
le verbe affiché vient du backend, jamais d'une lecture du libellé, pour que le
titre et le registre ne puissent pas se contredire à l'écran. L'écran *Your look* déclare ce qui est porté ; sans cette
information, le moteur supposerait toutes les pièces présentes.

Côté interface :

L'audit de bout en bout contrôle le système **assemblé**, dans la configuration
réelle de la machine — mode YouCam, base, catalogue compris :

```bash
python scripts/audit_journey.py       # ou : make audit
```

**L'API doit tourner** : l'audit interroge le système assemblé, pas le code.

```powershell
.\scripts\mirror-ops.ps1 audit
```

Il déroule les sept écrans, imprime les données en entrée et en sortie de chaque
appel, et vérifie 37 invariants : cohérence entre ce qui est déclaré, ce qui
change et ce qui est gardé ; concordance du verdict d'adéquation et de l'action ;
accessibilité réelle des médias ; refus qui nomment le bon geste. `FAIL` bloque,
`WARN` signale ce qui limitera la démonstration. À lancer avant tout
enregistrement.

```bash
npm run test --workspace @mirror-ops/web    # tests de rendu (vitest + jsdom)
npm run typecheck                           # tsc --noEmit, TypeScript strict
npm run build                               # build de production
```

`apps/web/tests/analyzing.test.tsx` monte l'écran d'analyse **sous StrictMode**,
c'est-à-dire dans les conditions du mode développement où React monte, démonte
puis remonte chaque composant. Il vérifie que le parcours atteint bien la
décision, qu'il ne consomme qu'une analyse et un VTO, qu'un échec d'analyse
donne un état d'erreur exploitable, et qu'une orchestration bloquée est
rattrapée par relecture de l'état serveur.

---

## 8. Sécurité & confidentialité

- Clé YouCam **exclusivement côté serveur** ; le frontend ne parle jamais au provider.
- Uploads validés (MIME réel, taille, dimensions, décodabilité).
- Médias servis par **URL signée HMAC + expiration**, jamais publics ; protection contre le path traversal.
- Logs structurés **assainis** : ni image brute, ni clé, ni credentials.
- Sessions anonymes à durée de vie limitée ; aucun compte, aucun mot de passe.
- `expires_at` + `scripts/cleanup.py` suppriment médias et sessions expirés.
- Aucune réponse brute du provider n'est conservée.
- Rate limiting basique, CORS restreint, contrat d'erreur sans fuite technique.

---

## 9. Positionnement produit

MIRROR OPS n'est ni un styliste IA, ni un assistant d'achat, ni un gestionnaire de
garde-robe, ni une application de VTO, ni un outil de diagnostic de peau. Ces frontières
sont tenues dans le code : `packages/config` porte `PRODUCT` et `NOT_THIS`, et la table de
correspondance règle → test se trouve dans [`docs/POSITIONING.md`](docs/POSITIONING.md) §5.

Le résultat Skin AI est présenté comme une **observation visuelle/cosmétique**, jamais comme
un diagnostic médical, et n'a qu'une influence bornée sur la décision : il informe le contexte,
il ne détourne pas la décision vestimentaire. Les scores d'impact sont des heuristiques
explicables destinées à être calibrées — pas des mesures scientifiques de la confiance humaine.

L'impact est positionné sur la **confiance de décision**. « Réduire les retours produit »
n'est pas revendiqué : nous n'en avons pas la preuve.

---

## 10. Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `409 INVALID_STATE` | étape sautée | respecter `moment → analyze → one-change → vto` |
| `422 INVALID_IMAGE` | photo illisible ou < 320 px | reprendre la photo |
| `INVALID_REQUEST` sur `/one-change/evaluate` | aucune pièce déclarée | cocher ce que vous portez sur l'écran *Your look* — la photo n'est pas en cause. En `APP_ENV=development`, `details` donne les chiffres exacts |
| `409 VTO_NOT_APPLICABLE` | la décision est `NO_CHANGE` | comportement normal : rien à prévisualiser |
| `410 MEDIA_LINK_EXPIRED` | URL signée périmée | relire la session via `GET /sessions/{id}` |
| `"youcam": "missing_credentials"` | `YOUCAM_MODE=live` sans identifiants | renseigner `apps/api/.env` ou repasser en `mock` |
| « Simulated preview » alors que `live` est configuré | l'API tourne encore en `mock` | `apps/api/.env` seul fait foi ; redémarrer l'API, puis vérifier `/health/dependencies` → `"youcam": "configured"` |
| `unable to open database file` | dossier `var/` absent (il est ignoré par git) | plus rien à faire : l'API le recrée au démarrage |
| `la colonne X n'existe pas` | base persistante antérieure à un nouveau champ | plus rien à faire : l'API ajoute les colonnes manquantes au démarrage. Pour l'appliquer à part : `python scripts/sync_schema.py` |
| `error_editing_failed` avec `"garment_source": "catalog"` | catalogue de substitution : le try-on n'a rien à quoi se raccrocher | `python scripts/import_garments.py <dossier>` puis `python scripts/check_garments.py`. Pour isoler la cause en un seul appel : `python scripts/probe_vto.py photo.jpg jacket_01` |
| `"garments": "placeholder"` | idem, signalé par l'API elle-même | idem |
| `error_editing_failed` avec `"garment_source": "uploaded"` | ce n'est plus le catalogue : la photo du vêtement ou la photo source est en cause | vêtement seul sur fond uni, et une photo de vous tête-aux-genoux, une seule personne, de face |
| `VTO_FAILED` avec `provider_code` | la photo ne convient pas au try-on : pose illisible, plusieurs personnes, cadrage | le message affiché dit quoi refaire ; pour le VTO, une photo tête-aux-genoux, une seule personne, de face |
| `502 ANALYSIS_FAILED` répété | auth rejetée, ou endpoints/actions Skin AI non activés | lire le log `skin_provider_failed` : il porte `error_code`, `reason` et la réponse du provider. En `APP_ENV=development`, la cause remonte aussi dans `details` |
| `"youcam": "missing_credentials"` | `YOUCAM_API_KEY` absente | une seule variable suffit en v2 |
| `401` côté provider | clé inactive, ou préfixe `Bearer` manquant | vérifier la clé dans la console |
| `404` sur une tâche | chemin d'endpoint erroné | v2 : `/s2s/v2.0/task/cloth` — au **singulier** |
| `"youcam": "missing_dependency"` | `cryptography` non installé | `cd apps/api && pip install -r requirements.txt` puis redémarrer |
| « We can't reach Mirror Ops » | API arrêtée, ou origine absente de `CORS_ORIGINS` | démarrer l'API, ajouter `http://localhost:3000` |
| « We need your photo again » | onglet rechargé avant l'analyse | reprendre la photo : elle n'est jamais persistée côté navigateur |
| l'écran d'analyse ne progresse plus | ancienne version du fichier, ou cache Next | `rm -rf apps/web/.next && npm run dev` ; le filet de sécurité reprend sinon la main en 8 s |
| l'interface appelle la mauvaise API | `NEXT_PUBLIC_API_BASE_URL` est figée au build | corriger `apps/web/.env.local` puis relancer `npm run dev` |

---

## 11. L'interface

Mobile-first (390 × 844), sept écrans, une seule action principale par écran.

```
/            Home         la thèse et un seul bouton
/moment      Moment       occasion + objectif + temps
/look        Your look    caméra ou import, ce que vous portez, à quel point c'est habillé
/analyzing   Analyzing    analyse puis décision, orchestrées côté backend
/one-change  ONE CHANGE   l'écran signature
/compare     Before/After la preuve visuelle · « Keep it / Try another »
/ready       Ready        la sortie
```

L'interface ne décide de rien : elle affiche ce que le moteur a choisi. Seul
l'identifiant de session vit dans le navigateur — chaque écran relit
`GET /sessions/{id}`, si bien qu'un rafraîchissement retrouve exactement la même
décision. La photo, elle, ne persiste nulle part côté client : rechargée avant
l'analyse, elle est redemandée plutôt que remplacée.

L'élément signature est l'**aiguille d'impact** : un axe, un trait fin pour
l'état actuel, un trait plein pour l'état projeté. Le déplacement *est*
l'information. En dessous, le registre liste ce qui change (une ligne, en
magenta) et tout ce qui reste (en mercure, marqué « Keep ») — la hiérarchie
visuelle porte elle-même la thèse du produit.

Détail : [`apps/web/README.md`](apps/web/README.md).

---

**MIRROR OPS** — Fit the moment. One change.
