# Runbook de démonstration

Objectif : un juge doit comprendre le produit en 30 secondes, et le parcours complet
doit tenir en 90 secondes.

## 1. Avant la démo

- [ ] `YOUCAM_MODE=live`, clé valide, **unités vérifiées**
- [ ] `python scripts/audit_journey.py` → 0 FAIL, et lire chaque WARN
- [ ] `python scripts/check_garments.py` → aucune substitution restante
- [ ] `GET /api/v1/health/dependencies` → `"garments": "ok"`
- [ ] `GET /api/v1/health/dependencies` → tout `ok` / `configured`
- [ ] `python scripts/demo_flow.py` exécuté **5 fois** de suite sans erreur
- [ ] photo d'entrée figée, vêtement gagnant figé, recommandation attendue connue
- [ ] chemin de repli préparé (`YOUCAM_MODE=mock`) — et annoncé comme tel s'il est utilisé
- [ ] latences mesurées : analyse, décision, VTO, total

## 2. Séquence (2 min 45)

| Temps | Écran | Message |
|---|---|---|
| 0:00–0:20 | Landing | *Fit the moment. One change.* |
| 0:20–0:40 | Moment | présentation · professionnel · moins de 5 minutes |
| 0:40–1:00 | Capture + analyse | Skin AI enrichit le contexte, ce n'est pas un diagnostic |
| 1:00–1:15 | **CONTEXTUAL FIT** | *Almost there* — la tenue convient, mais les baskets font baisser la formalité |
| 1:15–1:30 | **ONE CHANGE** | *Replace the sneakers* + pourquoi + ce qu'on garde |
| 1:30–2:15 | VTO | la recommandation devient visible |
| 2:15–2:40 | Before / After | une seule chose a changé · « Keep it / Try another » |
| 2:40–3:00 | Clôture | *Now you're ready.* |

> **Ce que le jury doit repartir en pensant** : « cette IA a pris une décision à ma
> place » — et non « cette application appelle une API de VTO ».
>
> La démonstration montre une **décision**, pas une technologie. À éviter
> absolument : la visite guidée d'API, la démo de chatbot générique, le parcours
> de garde-robe, les « 25 recommandations », le diagnostic de peau, ou le simple
> enchaînement upload → API → image.

## 3. Trois moments à réussir

1. `ALMOST THERE` — le verdict d'adéquation, qui pose la question du produit
2. `BEFORE → AFTER`
3. `Everything else stays.`

## 4. Réponses courtes aux questions de jury

**Pourquoi une seule modification ?** Le problème n'est pas le manque d'options,
c'est l'incertitude au moment de décider. On ne redessine pas la personne : on
corrige l'écart.

**Comment savez-vous que ça ne convient pas ?** Le look est projeté sur ce que
l'occasion demande, pas jugé dans l'absolu. Le même vestiaire donne un verdict
différent pour un voyage et pour un mariage — c'est vérifiable en changeant une
seule réponse à l'écran 2.

**Pourquoi Skin AI ?** Il fournit des signaux visuels de contexte, pour ne pas traiter le
style comme une recommandation de vêtement isolée. Son influence sur la décision est bornée
et testée.

**Pourquoi le VTO ?** Une recommandation devient utile quand on peut la voir avant de la faire.

**Et si rien ne doit changer ?** Le verdict est `FIT`, le moteur retourne
`NO_CHANGE` et ne consomme aucun VTO — c'est une fonctionnalité de confiance,
pas un repli technique.

**Quelle est la marge de manœuvre technique ?** Les pondérations, seuils et endpoints sont
configurables ; le moteur est déterministe et testé isolément.

**En quoi est-ce différent des autres projets « vérifiez votre look » ?** Ils
constatent, MIRROR OPS tranche. `CHECK YOUR LOOK ≠ DECIDE WHAT IS WORTH CHANGING`.

**« Try another » ne contredit-il pas ONE CHANGE ?** Non : il échange la pièce qui
incarne le changement, jamais le changement lui-même. La décision affichée reste
la même, et un test le verrouille.

## 5. Après la démo

- [ ] session de démonstration nettoyée (`python scripts/cleanup.py`)
- [ ] aucune clé visible dans les captures d'écran ou l'enregistrement
- [ ] `docs/openapi.json` régénéré si le contrat a bougé
