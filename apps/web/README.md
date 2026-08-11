# MIRROR OPS — interface

Next.js 14 (App Router), TypeScript strict, mobile-first (390 × 844).
L'interface ne contient **aucune logique de décision** : elle affiche ce que le
moteur a choisi, et ne parle jamais à YouCam directement.

## Lancer

```bash
npm install                     # depuis la racine du dépôt
cp apps/web/.env.local.example apps/web/.env.local
npm run dev                     # http://localhost:3000
```

L'API doit tourner en parallèle (`make dev-api`) et autoriser `http://localhost:3000`
dans `CORS_ORIGINS`.

| Variable | Rôle |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | racine de l'API MIRROR OPS (défaut `http://localhost:8000`) |

Cette variable est **compilée dans le bundle client** : la changer impose un rebuild.
Aucune clé YouCam n'apparaît ici, ni ne doit y apparaître.

## Écrans

```
/            Home        la thèse et un seul bouton
/moment      Moment      occasion + objectif + temps
/look        Your look   caméra ou import, preview, reprise
/analyzing   Analyzing   analyse puis décision, orchestrées côté backend
/one-change  ONE CHANGE  l'écran signature
/compare     Before/After la preuve visuelle
/ready       Ready       la sortie
```

Un seul appel API porte chaque transition, dans l'ordre imposé par la machine à
états du backend. Sauter une étape renvoie `409` : l'interface renvoie alors
l'utilisateur à l'écran manquant plutôt que d'afficher une erreur technique.

## Structure

```
src/
├── app/                 un dossier par écran + layout, error, not-found
├── components/
│   ├── Stage.tsx        plateau commun : en-tête, fil d'étapes
│   ├── Action.tsx       boutons (primaire / fantôme / discret)
│   ├── ChoiceGroup.tsx  groupes de choix à sélection unique
│   ├── Verdict.tsx      ★ plaque de verdict, aiguille d'impact, registre
│   ├── CameraCapture.tsx prise de photo réelle, avec repli honnête
│   ├── BeforeAfter.tsx  comparateur (souris, tactile, clavier)
│   └── Notice.tsx       états d'échec et tampon « simulated »
└── lib/
    ├── api.ts           client typé, erreurs normalisées
    ├── session.ts       identifiant de session + clés d'idempotence
    ├── photo.ts         la photo vit en mémoire, le temps d'un parcours
    └── format.ts        conversions d'affichage
```

Les types viennent de `@mirror-ops/types` (miroir des schémas Pydantic) et les
libellés de `@mirror-ops/config`. Le backend renvoie des identifiants stables ;
la façon de les nommer à l'utilisateur appartient à l'interface.

## « Try another » sans trahir ONE CHANGE

Le positionnement prévoit un écran « Keep it / Try another ». La règle 3 interdit
pourtant de transformer ONE CHANGE en liste de recommandations. Les deux tiennent
ensemble à une condition : **« Try another » échange la pièce, jamais la décision.**

Le bouton n'interroge le catalogue que dans la catégorie décidée par le moteur, il
disparaît s'il n'existe aucune alternative, et la clé d'idempotence inclut le
vêtement — réessayer la même pièce ne coûte rien, en changer coûte un aperçu, à la
demande explicite de l'utilisateur et jamais automatiquement.

## Choix d'implémentation

**L'état officiel est côté serveur.** Seul l'identifiant de session est conservé
dans le navigateur (`sessionStorage`). Chaque écran relit `GET /sessions/{id}` :
un rafraîchissement retrouve exactement la même décision — ce qui compte autant
pour une démonstration que pour la confiance.

**L'écran d'analyse ne peut pas rester bloqué.** C'est le seul qui enchaîne deux
appels asynchrones avant de naviguer, donc le seul qui puisse se figer si une
promesse ne revient jamais. Un filet de sécurité relit l'état de la session
toutes les 8 secondes et reprend le parcours là où le serveur en est : décision
déjà prise → on y va ; analyse faite mais décision manquante → on la demande ;
rien après quatre tentatives → un message explicite plutôt qu'une animation qui
tourne. C'est un simple `GET` : aucune unité API n'est consommée.

**La photo ne persiste pas.** Elle vit dans un module en mémoire, le temps d'un
parcours. Onglet rechargé avant l'analyse → l'écran le dit et la redemande,
plutôt que d'analyser autre chose.

**Un double-clic ne coûte pas deux unités.** Les appels coûteux (analyse, VTO)
portent un en-tête `Idempotency-Key` dérivé de la session et de l'étape.

**Le repli est visible.** Quand l'aperçu vient d'une composition locale
(`simulated: true`), l'écran Before/After l'affiche. Un résultat qui ne vient pas
de YouCam ne prétend jamais en venir.

## Design

La palette est dérivée du logo. La règle, elle, est antérieure et ne bouge pas :
**une seule couleur signal, réservée à ce qui change.**

| Jeton | Valeur | Emploi |
|---|---|---|
| `--porcelain` | `#F0F1F3` | fond |
| `--ink` | `#0B1A2E` | texte principal (bleu marine poussé en valeur de texte) |
| `--navy` | `#0A326E` | bleu du logo · étiquette « Before » |
| `--graphite` | `#5C6675` | texte secondaire |
| `--mercury` | `#D3D6DC` | filets, rails, état « gardé » |
| `--signal` | `#C1005C` | **le changement**, en typographie |
| `--signal-bright` | `#E6006E` | **le changement**, en tracé (aiguille, filets) |
| `--sky` | `#46AAE6` | l'état **avant**, et rien d'autre |

Deux valeurs de magenta parce que le magenta de marque donne 4.05:1 sur
porcelaine — sous le seuil AA. Les capitales de 10 à 12 px utilisent donc la
version assombrie (5.4:1) ; le magenta de marque reste sur les tracés, où le
contraste de texte ne s'applique pas.

Le bleu clair du logo n'a qu'un seul emploi : marquer l'état **avant** sur
l'aiguille d'impact. C'est le contrepoint du signal, pas une décoration — il
donne au troisième ton de la marque un travail réel plutôt qu'un rôle ornemental.

Fraunces pour le verdict, Archivo pour l'interface, JetBrains Mono pour les
données. Les familles sont chargées à distance, avec une pile de repli explicite :
hors ligne, la mise en page tient.

### Ressources de marque

| Fichier | Emploi |
|---|---|
| `public/logo-mirror-ops.png` · `@2x` | en-tête (26 px) et accueil (44–54 px) |
| `public/mark-mirror-ops.png` | le symbole seul, pour les supports hors application |
| `src/app/icon.png` · `favicon.ico` · `apple-icon.png` | icônes, détectées automatiquement par Next |
| `src/app/opengraph-image.png` · `twitter-image.png` | aperçu de partage (1200 × 630) |
| `src/app/manifest.ts` | manifeste d'application (épinglage écran d'accueil) |

Les icônes sont posées sur un fond porcelaine plutôt que transparent : le bleu
marine du symbole disparaîtrait sur un chrome de navigateur sombre.

L'élément signature est **l'aiguille d'impact** : un axe, un trait fin pour l'état
actuel, un trait plein pour l'état projeté. Le déplacement *est* l'information —
ni jauge circulaire, ni radar, ni tableau de bord (Doc 03 §14). En dessous, le
**registre** : une ligne décalée en magenta pour la pièce qui change, toutes les
autres en mercure marquées « Keep ». La hiérarchie visuelle porte la thèse du
produit.

Plancher de qualité : responsive jusqu'à 320 px, focus clavier visible,
`prefers-reduced-motion` respecté, comparateur pilotable aux flèches.

## Vérifier

```bash
npm run test          # vitest + jsdom
npm run typecheck     # tsc --noEmit
npm run build         # build de production
```

`tests/analyzing.test.tsx` couvre le point le plus fragile du parcours : l'écran
d'analyse enchaîne deux appels asynchrones puis navigue. Il est monté **sous
StrictMode**, donc dans les conditions du mode développement où React monte,
démonte puis remonte chaque composant — un enchaînement qui a déjà fait
échouer silencieusement l'orchestration une fois.
