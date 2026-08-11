# Revue produit, UX et business

Cette revue ne porte pas sur la qualité du code — les tests s'en chargent. Elle
porte sur ce que vit l'utilisateur et sur ce que le produit vaut. Elle est
délibérément sévère : ce qui est bon n'a pas besoin d'être écrit.

Chaque constat porte un état : **corrigé**, **à trancher** (décision produit qui
vous revient), ou **hors périmètre** (assumé pour un hackathon, bloquant pour un
déploiement réel).

---

## 1. Le défaut le plus grave — corrigé

**Constat.** Mesuré, pas supposé : avec ce que l'interface envoyait, les **dix
occasions rendaient le même verdict**.

```
interview     ALMOST_THERE  61   presentation  ALMOST_THERE  62
wedding       ALMOST_THERE  61   travel        ALMOST_THERE  63
dinner        ALMOST_THERE  65   conference    ALMOST_THERE  62
…soit 10 / 10 identiques, toujours « Nothing is off »
```

La thèse du produit — *le même look est jugé différemment selon le moment* —
était vraie dans le moteur et **invisible à l'écran**. Un jury qui teste
« mariage » puis « voyage » voit deux fois la même chose et conclut, à raison,
que l'occasion ne sert à rien.

**Cause.** L'interface ne déclarait que la *présence* des pièces. Le moteur
appliquait donc l'a priori neutre (0,58) à tout le monde.

**Correction.** Une question, trois réponses, sur l'écran *Your look* :
**« How dressed up is it? »** — Casual / In between / Dressed up. Elle reste
facultative : sans elle, le produit décide quand même, avec moins de certitude,
et le dit.

Résultat :

| | mariage | entretien | dîner | voyage |
|---|---|---|---|---|
| **décontracté** | MISMATCH 51 | MISMATCH 50 | ALMOST 63 | **FIT 73** |
| **entre-deux** | ALMOST 67 | ALMOST 67 | **FIT 77** | ALMOST 70 |
| **habillé** | **FIT 84** | **FIT 85** | Close enough 72 | ALMOST 63 |

La diagonale se lit d'un coup d'œil, y compris le cas *trop habillé pour un
voyage* — un écart lui aussi.

## 2. Une contradiction à l'écran — corrigée

Le même relevé a révélé : `travel` affichait **FIT 73** *et* « Change the
jacket ». « Vous êtes prêt », puis « changez la veste ». Deux lignes qui se
contredisent détruisent la crédibilité plus sûrement qu'une erreur technique.

Le verdict est désormais **réconcilié avec la décision par construction** : FIT
si et seulement si rien n'est à changer. Et le cas intermédiaire — rien à
changer sur un look imparfait — a son propre libellé, *« Close enough. »*, au
lieu d'être maquillé en réussite. Un test parcourt les dix occasions et quatre
niveaux d'habillement pour garantir qu'aucun écran ne promet d'être prêt tout en
exigeant un changement.

---

## 3. Une intention qui ne disait pas ce qu'elle ferait — corrigé

Un test en conditions live a produit : action `CHANGE_COLOR`, libellé « Adjust
the colour balance », `keep` contenant **top** — et l'aperçu remplaçait
précisément le haut. L'écran annonçait « Keep · Top » pendant que l'image
changeait le haut.

Racine unique : le produit confondait l'**intention** (travailler la couleur) et
l'**élément réellement touché** (le haut). Corrigé par `MATERIALISED_ELEMENT`, et
le libellé annonce désormais ce que la preuve montrera — *« Change the top for a
better colour »*. Un test paramétré vérifie, pour **chaque** action, que la pièce
modifiée n'est jamais listée comme conservée.

## 4. Le try-on live est vérifié

Trace réelle, même session :

| Vêtement | Résultat |
|---|---|
| catalogue (`top_01`) | `error_editing_failed` |
| pièce téléversée | **201 · `simulated: false` · 14,4 s · rendu YouCam** |

L'intégration fonctionne de bout en bout. Confirmation obtenue ensuite sur une
autre session : `jacket_01`, **remplacé par une vraie photo**, réussit depuis le
catalogue ; `top_01`, resté un aplat, échoue. La nature du visuel est donc bien
la cause unique — et `GET /garments` expose désormais `placeholder` par pièce
pour que ce diagnostic ne demande plus aucune inspection manuelle. Reste que **14 secondes** d'attente dans un parcours de 90 est
considérable : le bouton annonce désormais la durée attendue.

## 3. À trancher — décisions produit qui vous reviennent

### 3.1 Le parcours ne capture aucune valeur

L'écran *Ready* se termine sur « Start another moment ». Le document de
positionnement §10 évoque pourtant une extension retail : *incertitude →
ONE CHANGE → preuve → conversion*. Aucun crochet n'existe.

Options, par ordre de coût : un lien « où trouver une pièce comme celle-ci »
(faible, mais frôle l'assistant d'achat que le positionnement interdit) ·
enregistrer la décision pour la retrouver plus tard (nécessite un compte, que
le produit évite délibérément) · ne rien faire et l'assumer.

**Ma recommandation : ne rien faire pour le hackathon.** La règle 10 — ne rien
ajouter qui dilue l'idée — vaut plus qu'un crochet business improvisé, et le
jury évalue *decision confidence*, pas la conversion.

### 3.2 Aucun retour utilisateur sur la décision

Le produit tranche et n'écoute jamais. Un « ce n'était pas la bonne pièce » sur
l'écran final coûterait un bouton et donnerait la seule donnée qui permette de
calibrer le moteur autrement qu'à l'intuition. C'est aussi ce qu'un acheteur
entreprise demandera en premier.

Non fait : cela suppose de décider quoi mesurer, et où le stocker.

### 3.3 Le catalogue reste une béquille

Douze aplats générés. « Try a piece of your own » contourne le problème et
constitue le meilleur usage réel, mais la démonstration par défaut passe encore
par le catalogue. Tant qu'il n'est pas remplacé par de vraies photos, le
parcours nominal en mode live échoue (`error_editing_failed`).

`scripts/import_garments.py` fait le travail en une commande — depuis un dossier
local ou depuis un manifeste d'URLs. Il faut vos images.

Pour l'extension retail du §10 du positionnement, c'est le manifeste qui compte :
un distributeur a déjà ses visuels produits en ligne, et son catalogue devient
une liste `identifiant → URL` sans autre intégration.

### 3.4 Le signal peau est presque toujours absent en conditions réelles

Skin AI exige un visage occupant 60 % de la largeur ; MIRROR OPS photographie
une tenue. Le recadrage serveur répond au problème, mais échoue dès que le
visage fait moins de 140 px — cas fréquent d'une photo en pied. Le parcours
continue sans signal peau, ce qui est honnête, mais l'intégration Skin AI est
alors invisible au jury, qui la note (critère ① Technological Implementation).

**À trancher** : accepter, ou demander un second cliché rapproché — ce qui coûte
un écran et contredit la contrainte des 90 secondes.

---

## 4. Hors périmètre — assumé ici, bloquant en production

| Manque | Pourquoi c'est bloquant ailleurs |
|---|---|
| Aucune authentification, sessions anonymes | multi-tenant, RGPD, quotas par client |
| Aucune télémétrie de funnel | impossible de mesurer où les gens abandonnent |
| Rate limiting en mémoire | inopérant dès deux instances |
| Aucune internationalisation | l'interface est en anglais uniquement |
| Pas d'audit d'accessibilité formel | contraste, ordre de tabulation et lecteurs d'écran ont été soignés, jamais mesurés |
| Coût API non exposé | un acheteur veut connaître le coût par parcours |

---

## 5. Ce qui tient

La contrainte est respectée de bout en bout : une seule recommandation, jamais
de liste, `NO_CHANGE` possible, aucune valeur inventée, le repli avoué en toutes
lettres, l'écart déclaré nommé avant chaque décision. `scripts/audit_journey.py`
vérifie 37 invariants sur le système assemblé, dont les contradictions d'écran
qui, précédemment, ne se découvraient qu'à l'usage.
