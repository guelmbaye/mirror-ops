#!/usr/bin/env python3
"""Verifie que le catalogue contient de vraies photographies de vetements.

Le catalogue livre est genere programmatiquement : des aplats de quelques
couleurs. Ils suffisent au mode `mock`, mais un vrai try-on echoue dessus en
`error_editing_failed` — un message qui ne pointe jamais vers le catalogue.

    python scripts/check_garments.py

Code de sortie 1 s'il reste au moins un visuel de substitution : utilisable dans
une verification avant demonstration.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Depot monorepo, ou image de l'API ou `app/` est a la racine : les scripts
# doivent fonctionner dans les deux, sinon la moitie d'entre eux est
# inutilisable en production.
for candidate in (ROOT / "apps" / "api", ROOT):
    if (candidate / "app").is_dir():
        sys.path.insert(0, str(candidate))
        break

from app.services.garment_audit import PLACEHOLDER_COLOUR_CEILING, audit_garments  # noqa: E402
from app.services.garment_service import list_garments  # noqa: E402


def main() -> int:
    audits = audit_garments(list_garments())
    placeholders = [a for a in audits if a.is_placeholder]
    unusable = [a for a in audits if not a.is_usable]

    for audit in audits:
        if audit.is_placeholder:
            state = "SUBSTITUTION"
        elif audit.shows_a_person:
            state = "QUELQU'UN LE PORTE"
        else:
            state = "ok"
        print(f"  {audit.garment_id:<14} {audit.colours:>6} couleurs   {state}")

    worn = [a for a in audits if a.shows_a_person]
    if worn:
        print(f"\n{len(worn)} visuel(s) montrent quelqu'un portant le vetement.")
        print("L'essayage attend une piece SEULE — a plat, sur cintre, ou en")
        print("mannequin fantome. Une photo de personne habillee demande au")
        print("modele de deviner ou s'arrete le vetement, et produit souvent")
        print("un `error_editing_failed` alors que l'image est nette.")

    if not unusable:
        print(f"\n{len(audits)} vetements : tous exploitables par un try-on reel.")
        return 0

    if not placeholders:
        # Uniquement des vetements portes : le catalogue n'est pas de
        # substitution, mais il n'est pas exploitable pour autant.
        print(f"\n{len(audits) - len(unusable)} vetement(s) sur {len(audits)} sont")
        print("exploitables ; les autres sont listes ci-dessus.")
        return 1

    print(
        f"\n{len(placeholders)} vetement(s) sur {len(audits)} sont des aplats "
        f"(<= {PLACEHOLDER_COLOUR_CEILING} couleurs).\n"
        "Un try-on reel echouera dessus. Remplacez les fichiers PNG de\n"
        "apps/api/app/assets/garments/ par de vraies photographies de vetements,\n"
        "en conservant exactement les memes noms de fichiers.\n"
        "Recommande : vetement seul, fond uni clair, cote long >= 1024 px."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
