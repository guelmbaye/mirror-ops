# Intégration YouCam

> Never build the product around the API response.
> Build the product around the user decision, then use YouCam to make that decision possible.

## 1. Frontière

```
Browser ──► MIRROR OPS backend ──► adapters ──► YouCam
                                     │
                          SkinAnalysisResult / VTOGenerationResult
```

Le navigateur ne parle **jamais** à YouCam. La clé reste côté serveur. Le code métier
n'appelle jamais `httpx` directement : il appelle `skin_provider.analyze(...)` ou
`vto_provider.generate(...)`.

## 2. Fichiers

| Fichier | Rôle |
|---|---|
| `client.py` | HTTP, auth + cache de token, timeouts, retries bornés, upload/tâches/polling |
| `skin_ai.py` | protocole Skin AI complet → observations normalisées |
| `apparel_vto.py` | protocole Apparel VTO → image transformée |
| `mappers.py` | seul endroit qui connaît les formes de réponse YouCam |
| `exceptions.py` | taxonomie d'erreurs interne (le reste du code ne voit que ça) |
| `mock.py` | providers locaux hors ligne, explicitement marqués « simulated » |
| `provider.py` | protocoles + fabrique `mock` / `live` |

## 2 bis. Authentification

**Le produit utilise l'API v2, qui n'a pas d'endpoint d'authentification.** La clé
API part directement en en-tête :

```
Authorization: Bearer VOTRE_CLE_API
```

Une seule variable suffit : `YOUCAM_API_KEY`, créée dans la console
(<https://yce.perfectcorp.com/api-console/en/api-keys/>).

### Vocabulaire de la console, qui prête à confusion

Dans la documentation YouCam, **l'« API Key » est le `client_id` et la
« Secret key » est le `client_secret`**. Il n'existe donc pas trois valeurs
distinctes : ce sont deux noms pour la même paire. La Secret key n'est affichée
qu'à sa création et ne peut plus être relue ensuite.

Ces deux valeurs ne servent qu'à l'API **v1**, qui exige en plus de chiffrer le
secret en RSA pour produire un `id_token`. C'est implémenté dans
`app/integrations/youcam/auth.py` et couvert par `tests/test_youcam_auth.py`,
mais **ce chemin n'est plus le chemin par défaut** : v2 rend tout cela inutile.

## 2 ter. Base URL

`https://yce-api-01.makeupar.com` — et non `perfectcorp.com`, que la marque
utilise pour son site et sa console mais pas pour l'API.

## 3. Flux réel (mode `live`)

```
image validée
   ↓ POST  /s2s/v2.0/file/skin-analysis      → file_id + URL d'upload pré-signée
   ↓ PUT   URL d'upload                      → octets de l'image
   ↓ POST  /s2s/v2.0/task/skin-analysis      → task_id
   ↓ GET   /s2s/v2.0/task/skin-analysis/{id} → polling (task_id dans le CHEMIN)
   ↓ mappers.normalize_skin_payload          → {texture, redness, oiliness, radiance}
```

L'enveloppe v2 est `{"status": 200, "data": {...}}`, et l'état de tâche s'appelle
`task_status`. Le VTO suit le même schéma sur `/s2s/v2.0/{file,task}/cloth` —
**« cloth » au singulier**.

### Une seule photo, deux exigences contradictoires

Skin AI rejette toute image où le visage occupe moins de **60 % de la largeur**
(`error_src_face_too_small`). MIRROR OPS photographie une **tenue**, où le visage
est forcément petit. Les deux ne tiennent pas sur un même cadrage.

Le parcours reste néanmoins à **une seule prise de vue** : demander un second
cliché ajouterait un écran, et la contrainte est le produit. La photo de tenue
est donc recadrée côté serveur (`services/face_crop.py`) avant l'appel Skin AI —
l'original, intact, part au VTO et s'affiche à l'écran.

```
photo de tenue ──┬─→ recadrage visage (68 % de la largeur) ──→ Skin AI
                 └─→ image d'origine ──────────────────────→ Apparel VTO
```

Conséquences assumées :

- Les actions sont en **SD** et non HD : HD exige un côté court ≥ 1080 px, qu'un
  cadrage de visage extrait d'une photo en pied atteint rarement.
- Un visage détecté sous 140 px de large ne donne **aucun** appel : l'agrandir ne
  produirait que des pixels interpolés, et analyser une invention est pire que ne
  rien analyser.
- Aucun visage détecté → aucun appel non plus. On économise une unité sur un rejet
  certain, et `skin_source` vaut `unavailable_no_face`.

La détection utilise le classifieur de Haar livré avec OpenCV. La dépendance est
**optionnelle à l'exécution** : sans elle, le parcours continue sans signal peau.

### Skin AI ne peut pas faire échouer un parcours

Une panne du provider — timeout, quota, image refusée — ne renvoie plus d'erreur :
l'analyse se poursuit avec `skin_source = "unavailable"`, sans valeur inventée, et
la confiance de décision baisse d'elle-même. C'est la conséquence directe du
positionnement : *Skin AI informe la décision, il ne la prend pas.* Un service
tiers ne doit pas pouvoir interrompre une démonstration.

Le rate limit fait exception : il reste remonté à l'utilisateur, parce que
réessayer plus tard a du sens.

### Sens des scores : une inversion nécessaire

Chez YouCam, un score **élevé** signifie une peau **saine**. Le moteur MIRROR OPS,
lui, raisonne en **sévérité** : plus la rougeur est marquée, plus la valeur est
haute. `mappers.INVERTED_METRICS` inverse donc `redness`, `oiliness` et `texture`,
et laisse `radiance` tel quel puisque c'est déjà une qualité. Sans cette
inversion, une peau parfaite serait lue comme très marquée et le signal peau
pousserait la décision dans le mauvais sens.

Le VTO suit le même schéma avec deux fichiers sources (look courant + vêtement), puis
téléchargement de l'image résultat.

Le polling reste **côté backend** : le frontend ne voit que `ANALYZING → VTO PREPARATION → READY`.

## 4. Normalisation

`mappers.py` accepte les échelles 0–100 comme 0–1, les valeurs imbriquées, les alias
(`hd_redness`, `skin_texture`, …) et ignore les métriques que le produit n'utilise pas.
On ne stocke que ce qui sert réellement à la décision.

Si aucune observation exploitable ne revient, l'adapter **lève une erreur** au lieu
d'inventer des valeurs.

## 4 bis. Une tâche qui échoue nomme sa cause

Un statut terminal `error` ne dit rien par lui-même. Le corps de la réponse, lui,
porte un `error_code` : `error_pose`, `error_multiple_people`, `error_no_shoulder`,
`error_unsupport_ratio`, `unknown_internal_error`…

Ce code est extrait, journalisé, porté par l'exception (`provider_code`) et
traduit en consigne par `services/photo_guidance.py`. Un problème de **photo**
devient un `422` avec une phrase actionnable — « We can only work with one person
in the photo » — et non un `502` générique : l'utilisateur peut agir, il faut le
lui dire.

Un `unknown_internal_error` reste, lui, une panne de service.

## 4 ter. `error_editing_failed` : d'abord le vêtement

Ce code signifie que le rendu n'a pas pu être produit. Dans ce projet, la cause
est presque toujours l'image de **référence** : un aplat n'est pas un vêtement,
le modèle n'a rien à segmenter.

`GET /garments` indique pour chaque pièce si son visuel est une vraie
photographie ou un aplat (`"placeholder": true`). Un essayage qui réussit sur
une pièce et échoue sur une autre s'explique donc sans inspecter un seul
fichier.

Tout échec d'essayage porte par ailleurs `garment_source` — `catalog` ou
`uploaded` — et `garment_id`. C'est la première chose à lire : elle dit en un
coup d'œil si le catalogue livré est en cause, ou s'il faut chercher ailleurs.

Le chemin le plus court reste **« Try a piece of your own »** : la personne
photographie la pièce qu'elle envisage, et le catalogue n'entre plus en jeu.

### Catalogue local ou catalogue en ligne ?

L'API accepte `ref_file_url` en alternative à `ref_file_id` : YouCam sait donc
récupérer une image de vêtement par URL. Ce chemin n'est **pas** celui retenu,
pour trois raisons : l'URL doit être joignable depuis les serveurs de YouCam —
donc jamais un `localhost` de démonstration ; un lien mort casse le parcours au
pire moment ; et on perd la normalisation (fond, format, dimensions) qui élimine
justement une famille d'échecs.

Le référencement en ligne se fait donc **à l'import** : téléchargement une fois,
normalisation, service local. On garde la souplesse d'un catalogue distant sans
en garder la fragilité.

Pour le catalogue lui-même, trois outils ferment la boucle :

```bash
python scripts/check_garments.py                  # le catalogue est-il réel ?
python scripts/import_garments.py <dossier>       # remplacer en une commande
python scripts/probe_vto.py photo.jpg jacket_01   # un seul essayage, réponses brutes
```

Quoi qu'on dépose dans le catalogue, `garment_service.normalized_garment_bytes`
convertit avant l'envoi : fond blanc, RGB, JPEG, côté long ≥ 1024 px. Format,
transparence et taille sont donc éliminés de l'équation.

## 5. Erreurs et retries

| Erreur provider | Retry | Message utilisateur |
|---|---|---|
| timeout / erreur transitoire | oui (max 2, backoff) | « Try again » |
| rate limit | non | « Try again in a moment » |
| auth / quota | non | « The service is unavailable » |
| image invalide | non | « We need a clearer view of your look » |

Aucune erreur brute YouCam n'atteint l'utilisateur.

## 6. Économie d'unités

```
1 photo → 1 analyse Skin AI → scoring de N candidats → 1 VTO (le gagnant uniquement)
```

- `NO_CHANGE` → **aucun** appel VTO.
- Cache court par empreinte d'image pour l'analyse.
- `Idempotency-Key` sur `analyze` et `vto/generate` : un double-clic ne consomme pas deux fois.
- Un test vérifie explicitement qu'un parcours coûte 1 analyse + 1 VTO.

## 7. Mode dégradé honnête

Si un aperçu porte la mention « simulated » alors que vous croyez être en `live`,
c'est que le processus tourne en `mock` : le tampon ne ment jamais. Le contrôle
décisif est `GET /api/v1/health/dependencies`, qui renvoie le mode réellement
actif — pas celui que le fichier annonce.

`YOUCAM_MODE=mock` fait tourner le parcours complet hors ligne. Les résultats portent
`provider = local_heuristic | local_composite`, `simulated = true`, et l'image générée
affiche « SIMULATED PREVIEW — not generated by YouCam ». Un résultat qui ne vient pas de
YouCam ne prétend jamais en venir — y compris pendant une démonstration.

## 8. Avant de passer en `live`

Le contrôle unique qui résume tout : `GET /api/v1/health/dependencies`.

| Réponse | Signification |
|---|---|
| `"configured"` | prêt |
| `"mock_mode"` | les aperçus seront marqués « simulated » |
| `"missing_credentials"` | identifiants ou `YOUCAM_SECRET_KEY` absents |
| `"missing_dependency"` | `cryptography` non installé — `pip install -r requirements.txt` |

0. Écrire la configuration dans **`apps/api/.env`**, et nulle part ailleurs. Le
   `.env` de la racine est réservé à docker-compose et n'est pas lu par uvicorn.
   Puis **redémarrer l'API** : la configuration et les providers sont résolus une
   seule fois, au démarrage.
1. Vérifier la clé et **les unités restantes**.
2. Confirmer dans le Playground les endpoints réellement accessibles au compte.
3. Aligner `YOUCAM_*_PATH` et `YOUCAM_SKIN_ACTIONS` sur ce qui est activé.
4. Contrôler `GET /api/v1/health/dependencies`.
5. Figer les assets de démonstration et relancer `scripts/demo_flow.py` plusieurs fois.
