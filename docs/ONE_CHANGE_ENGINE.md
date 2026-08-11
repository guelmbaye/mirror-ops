# ONE CHANGE — spécification d'implémentation

> *ONE CHANGE must be opinionated.*
> Le moteur ne dit jamais « vous pourriez changer la veste, les chaussures ou un accessoire ».
> Il dit « changez la veste », puis explique pourquoi.

Code : `apps/api/app/engines/one_change/` — **domaine pur**, aucune dépendance
FastAPI / SQLAlchemy / HTTP / LLM.

## 0. Le verdict précède le changement

```
DecisionContext → assess_fit() → FIT | ALMOST_THERE | MISMATCH
```

`fit.py` projette le look sur ce que l'occasion demande — pas sur une échelle de
qualité absolue. Il nomme l'élément qui tire l'ensemble vers le bas **seulement**
s'il se détache réellement du reste ; à égalité, il le dit sans désigner personne.

Un verdict `FIT` et une action autre que `NO_CHANGE` seraient contradictoires à
l'écran ; un test parcourt les dix occasions et trois niveaux de qualité pour
s'assurer que cela ne peut pas arriver.

## 1. Pipeline

```
DecisionContext
   │
   ├─ validate            Data Quality Gate : trois motifs distincts (voir §1 bis)
   ├─ generate_candidates espace fermé de 7 actions, filtrage contextuel
   ├─ score               7 features pondérées → 0-100
   ├─ tie_breaker         écart < 5 pts → moindre effort (NO_CHANGE exclu de ce départage)
   ├─ thresholds          seuil minimal + marge obligatoire face à NO_CHANGE
   ├─ confidence          qualité des données × séparation × complétude du contexte
   └─ explanation         templates déterministes, dérivés des facteurs réellement dominants
        ↓
   DecisionOutcome  (1 action, 1 score, 1 raison, la liste "keep", l'impact projeté)
```

## 1 bis. Le portail de qualité nomme ce qui manque

| Motif | Cause réelle | Ce qu'on demande |
|---|---|---|
| `no_outfit_declared` | aucune pièce déclarée | dire ce qu'on porte |
| `image_unusable` | qualité d'image sous 0,35 | reprendre la photo |
| `insufficient_data` | plancher absolu (0,20) | l'un ou l'autre |

Ne pas connaître les **attributs** d'une tenue n'est plus un motif de refus :
cela abaisse la confiance de décision, ce que le produit annonce déjà. Refuser
en plus serait plus sévère que nécessaire — et surtout, envoyer quelqu'un
reprendre une photo parfaite parce que sa *tenue* n'est pas décrite est une
impasse : rien de ce qu'il fera devant l'objectif n'y changera quoi que ce soit.

## 2. Espace de décision

`CHANGE_JACKET · CHANGE_TOP · CHANGE_BOTTOM · CHANGE_SHOES · CHANGE_ACCESSORY ·
CHANGE_COLOR · REMOVE_ACCESSORY · NO_CHANGE`

Trois gestes, pas un seul : **changer**, **ajouter** (quand la pièce manque) et
**retirer** (quand il y en a une de trop). Le libellé suit la réalité — « Add a
jacket », « Remove the accessory » — et un retrait ne demande aucun essayage.

Fermé volontairement : plus fiable, plus testable, plus démontrable.
Un candidat est écarté si la pièce est absente, si le changement est irréaliste dans le
temps disponible (`<5 min` exclut le bas), ou s'il n'y a pas assez d'éléments pour un
travail de couleur.

## 3. Features (toutes normalisées 0..1)

| Feature | Poids | Source |
|---|---|---|
| `goal_alignment` | 0.25 | vecteur d'objectif × capacité du levier (`GOAL_VECTORS` × `CAPABILITY`) |
| `context_fit` | 0.20 | `CONTEXT_FIT[occasion][action]` |
| `visual_impact` | 0.20 | `VISIBILITY[action] × (0.5 + 0.5 × gap)` |
| `current_gap` | 0.10 | `POTENTIAL_CEILING[élément] − suitability actuelle` |
| `time_fit` | 0.10 | `TIME_FIT[temps][action]` |
| `data_confidence` | 0.10 | qualité image × complétude des indices |
| `vto_feasibility` | 0.05 | `VTO_FEASIBILITY[action]` |

`final_score = round(Σ poids × feature × 100)`

Toutes les tables sont dans `tables.py` et sont **configurables** : elles encodent des
heuristiques produit destinées à la calibration, pas des vérités scientifiques.

## 4. NO_CHANGE est un vrai candidat

`NO_CHANGE` est évalué avec les mêmes features, mais mesuré sur l'état **actuel** :
adéquation courante à l'objectif et à l'occasion, marge restante, etc. Ses features
d'adéquation passent par une fonction convexe (`NO_CHANGE_SHARPNESS = 2.0`) :
« ne rien changer » doit se mériter — un look moyen ne suffit pas.

Deux garde-fous supplémentaires :

- si le meilleur changement est sous `ONE_CHANGE_THRESHOLD` (60) → `NO_CHANGE` ;
- si le meilleur changement ne bat pas `NO_CHANGE` d'au moins `ONE_CHANGE_NO_CHANGE_MARGIN`
  (2 pts) → `NO_CHANGE`.

C'est ce qui empêche le produit d'inventer une modification juste pour utiliser le VTO.

## 5. Départage déterministe

Écart < `ONE_CHANGE_TIE_DELTA` (5 pts) → priorité, dans l'ordre : moindre effort,
meilleur context fit, VTO plus simple, ordre produit figé. `NO_CHANGE` n'entre jamais dans
ce départage (sinon « ne rien faire » gagnerait tous les quasi ex æquo) : il est arbitré
par la politique de seuils. À contexte identique, le moteur rend toujours la même décision.

## 6. Confiance de décision ≠ score d'impact

- **Score d'impact** : qualité relative de l'intervention.
- **Decision confidence** : `qualité des données × séparation des candidats × complétude du contexte`,
  exposée en `low / medium / high` — jamais en pourcentage faussement précis.

Une décision prise sur un quasi ex æquo, ou sans indices sur la tenue, ressort logiquement
en confiance basse.

## 7. Le signal peau n'accapare jamais la décision

Skin AI enrichit le contexte d'apparence. Il n'agit que s'il est **matériel** (au-delà de
seuils explicites) et son influence est bornée (`SKIN_MAX_INFLUENCE = 0.08`). Un test
vérifie qu'une peau très marquée ne modifie pas l'action choisie : MIRROR OPS reste un
agent de décision d'apparence, pas un coach skincare.

## 8. Explication vraie

`explanation.py` classe les contributions **pondérées réelles** du gagnant et construit
la phrase à partir des deux facteurs dominants. Une justification générique, indépendante
du calcul, est impossible par construction.

## 9. Calibration

```bash
python scripts/calibrate_engine.py
```

Affiche le classement complet des candidats sur sept scénarios. Pour ajuster : modifier
`tables.py` ou les variables `ONE_CHANGE_*`, puis relancer `pytest tests/test_engine_scenarios.py`.
