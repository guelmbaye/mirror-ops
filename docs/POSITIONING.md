# Positionnement — source de vérité unique

> MIRROR OPS détermine si votre look convient au moment dans lequel vous entrez
> et, quand ce n'est pas le cas, identifie **le** changement qui vaut la peine —
> puis le prouve avant que vous n'agissiez.

Ce document prime sur tous les autres. Toute décision de code, de copie ou de
démonstration doit s'y conformer.

## 1. Catégorie

**Contextual appearance decision engine** — moteur de décision d'apparence contextuel.

Pas : styliste IA · assistant d'achat · générateur de tenues · gestionnaire de
garde-robe · application de VTO · outil de diagnostic de peau · optimiseur d'achat.

| Signature | Promesse | Question distinctive |
|---|---|---|
| **FIT THE MOMENT. ONE CHANGE.** | Don't redesign your look. Fix the mismatch. | *Will this look work here?* |

Action distinctive : *si la réponse est non, faites **un** changement.*
Preuve distinctive : *voyez-le avant d'agir.*

## 2. La distinction qui décide de tout

Plusieurs projets concurrents traitent déjà « vérifiez votre look avant un moment
important ». Ce n'est pas notre territoire.

```
Leur territoire :   CHECK      constater l'état de son apparence
Notre territoire :  DECIDE     trancher ce qui mérite d'être changé
```

**CHECK YOUR LOOK ≠ DECIDE WHAT IS WORTH CHANGING.**

Le problème n'est pas le manque d'options vestimentaires. C'est **l'incertitude de
décision** dans un moment d'apparence : « j'ai cinq minutes avant une présentation
importante — dois-je changer quelque chose ? »

## 2 bis. La chaîne de décision

```
MOMENT → CURRENT LOOK → CONTEXTUAL FIT → FIT / MISMATCH → ONE CHANGE → VTO → ACT
```

L'étape **CONTEXTUAL FIT** précède le changement, et ce n'est pas un détail
d'ordonnancement : le produit répond d'abord *« ce look va-t-il ici ? »*, et
seulement ensuite *« que changer ? »*. Trois verdicts :

| État | Ce que l'écran dit | Suite |
|---|---|---|
| `FIT` | You're good to go. | aucun changement, aucun VTO |
| `ALMOST_THERE` | Almost there. + l'élément en cause | ONE CHANGE |
| `MISMATCH` | This doesn't fit the moment. | ONE CHANGE |

Le verdict ne nomme un élément que s'il se détache réellement du reste. Quand
toutes les pièces sont à égalité — cas d'une tenue non décrite — il le dit sans
désigner personne : le produit s'interdit d'inventer ce qu'il n'a pas observé.

**Contextuel** veut dire que la même tenue est jugée différemment selon le
moment. Dix occasions sont couvertes, chacune avec son propre profil d'exigence :
entretien, présentation, rendez-vous, affaires, événement, **mariage**,
**conférence**, **dîner**, **voyage**, autre.

## 3. Ce que ONE CHANGE veut dire

Ce n'est pas « recommander une veste ». C'est une **contrainte produit** :

> Quelle est la plus petite intervention significative à plus forte valeur
> attendue pour ce moment précis ?

L'espace d'intervention comporte trois gestes, pas un seul : **changer** une
pièce, en **ajouter** une qui manque, en **retirer** une de trop. Un retrait ne
demande aucun essayage — il n'y a rien à mettre, seulement quelque chose à
enlever — et le parcours saute donc l'étape VTO.

Deux issues légitimes : **CHANGE** ou **NO CHANGE**. Un bon moteur de décision doit
pouvoir décider qu'aucune intervention ne vaut la peine — sinon ce n'est pas un
moteur de décision, c'est un générateur de recommandations.

## 4. Rôle de YouCam

L'innovation n'est **pas** « Skin AI + VTO ». C'est le moteur d'intervention qui
se limite délibérément à un seul changement à forte valeur. La contrainte crée la
différenciation.

```
Skin AI      informe la décision   (signaux visuels sur l'apparence actuelle)
Apparel VTO  prouve la décision    (before / after de l'intervention retenue)
```

## 5. Où cela vit dans le code

| Règle du positionnement | Où elle est appliquée | Où elle est vérifiée |
|---|---|---|
| 1 — jamais un styliste | `packages/config` (`PRODUCT`, `NOT_THIS`), copie des écrans | — |
| 2 — l'innovation n'est pas Skin AI + VTO | `README.md` §6, `docs/ONE_CHANGE_ENGINE.md` | — |
| 3 — jamais une liste de recommandations | moteur : une seule action retournée ; « Try another » échange la pièce, pas la décision | `test_engine_scenarios.py`, `test_try_another.py`, `compare.test.tsx` |
| — le fit précède le changement | `engines/one_change/fit.py`, écran `/one-change` | `test_contextual_fit.py`, `verdict.test.tsx` |
| — aucune occasion ne fait tomber le moteur | tables complétées pour les dix occasions | `test_contextual_fit.py` (paramétré sur `Occasion`) |
| 4 — toujours rattaché à un moment et un objectif | `MomentSpec` obligatoire avant l'analyse | machine à états, `test_state_machine.py` |
| 5 — préserver le reste du look | champ `keep` + registre visuel | `test_contract_shapes.py` |
| 6 — toujours une raison | `explanation.py`, dérivée des facteurs dominants réels | `test_engine_scenarios.py` |
| 7 — NO CHANGE autorisé | politique de seuils et de marge | `test_engine_scenarios.py`, `test_api_flow.py` |
| 8 — le VTO est une preuve | VTO uniquement pour le gagnant, jamais pendant le scoring | `test_idempotency_and_units.py` |
| 9 — la confiance de décision prime | `confidence` exposée en low/medium/high | `test_contract_shapes.py` |
| 10 — ne rien ajouter qui dilue l'idée | voir ci-dessous | revue |

## 6. Ce qu'on n'ajoutera pas

Gestion de garde-robe · catalogues produit · agent conversationnel · flot continu
de recommandations · tableaux de bord · fonctions sociales · personnalisation
excessive · agents IA supplémentaires.

**La contrainte est le produit.** Si une fonctionnalité ne renforce pas
`FIT THE MOMENT → FIND THE MISMATCH → ONE CHANGE → PROVE IT → MOVE FORWARD`,
elle doit être retirée.

Principe non négociable : **on ne redessine pas la personne, on corrige l'écart.**

## 7. Impact — formulation prudente

Positionner l'impact sur la **confiance de décision** : sous pression temporelle,
les gens n'ont pas besoin de plus d'inspiration, ils ont besoin de savoir quoi
faire ensuite.

Extension retail plausible : incertitude client → ONE CHANGE → preuve visuelle →
confiance de décision accrue → conversion potentielle.

Ne **pas** faire de « la réduction des retours produit » la revendication
principale : nous n'en avons pas la preuve.

## 8. Ce qu'un jury doit retenir

> « Cette IA a pris une décision à ma place. »

Et non : « cette application appelle une API de VTO. »

Les trois moments visuels mémorables : **CHANGE THE JACKET** → **BEFORE / AFTER**
→ **EVERYTHING ELSE STAYS**.
