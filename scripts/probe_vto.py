#!/usr/bin/env python3
"""Teste UN essayage contre l'API YouCam reelle, et affiche tout.

Diagnostiquer un `error_editing_failed` en passant par le parcours complet coute
une session, une analyse et beaucoup de temps. Ce script fait l'appel nu :
upload de la photo, upload du vetement, creation de la tache, polling — et
imprime la reponse brute de chaque etape.

    python scripts/probe_vto.py ma-photo.jpg jacket_01
    python scripts/probe_vto.py ma-photo.jpg ~/Downloads/veste.jpg --category upper_body

Aucune base de donnees, aucune session : uniquement l'adaptateur YouCam.
Consomme une unite d'essayage.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
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

from PIL import Image  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.integrations.youcam.apparel_vto import ApparelVTOService  # noqa: E402
from app.integrations.youcam.exceptions import YouCamError  # noqa: E402
from app.integrations.youcam.models import GarmentRef  # noqa: E402
from app.services.garment_service import list_garments, normalized_garment_bytes  # noqa: E402


def resolve_garment(reference: str, category: str | None) -> GarmentRef:
    """Un identifiant du catalogue, ou un chemin vers une photo quelconque."""
    catalog = {garment.id: garment for garment in list_garments()}

    if reference in catalog:
        garment = catalog[reference]
        return GarmentRef(
            garment_id=garment.id,
            category=category or garment.category,
            name=garment.name,
            image_bytes=normalized_garment_bytes(garment.image_path),
            mime_type="image/jpeg",
        )

    path = Path(reference).expanduser()
    if not path.exists():
        raise SystemExit(f"Ni un identifiant du catalogue, ni un fichier : {reference}")

    return GarmentRef(
        garment_id=path.stem,
        category=category or "jacket",
        name=path.stem,
        image_bytes=normalized_garment_bytes(path),
        mime_type="image/jpeg",
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description="Sonder l'essayage YouCam")
    parser.add_argument("photo", type=Path, help="photo de la personne")
    parser.add_argument("garment", help="identifiant du catalogue, ou chemin d'une photo")
    parser.add_argument("--category", help="upper_body · lower_body · shoes · auto")
    args = parser.parse_args()

    settings = get_settings()
    print(f"mode        : {settings.YOUCAM_MODE}")
    print(f"base url    : {settings.YOUCAM_API_BASE_URL}")
    print(f"task path   : {settings.YOUCAM_VTO_TASK_PATH}")
    if not settings.is_live_youcam:
        print("\nYOUCAM_MODE n'est pas `live` : cette sonde n'a d'interet qu'en mode reel.")
        return 2

    photo = args.photo.expanduser()
    if not photo.exists():
        # Afficher le chemin ABSOLU : « ma-photo.jpg » ne dit pas ou l'on a
        # cherche, et « ma-photo.jpg » etait justement le nom d'exemple.
        print(f"Photo introuvable : {photo.resolve()}")
        print(f"Repertoire courant : {Path.cwd()}")
        candidates = sorted(
            p.name for p in Path.cwd().iterdir()
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )
        if candidates:
            print("Images presentes ici : " + ", ".join(candidates[:8]))
        else:
            print("Aucune image dans ce repertoire. Donnez un chemin complet.")
        return 2

    garment = resolve_garment(args.garment, args.category)
    print(f"vetement    : {garment.garment_id} ({garment.category}), "
          f"{len(garment.image_bytes) // 1024} Ko")
    print(f"photo       : {photo.name}, {photo.stat().st_size // 1024} Ko\n")

    # La sonde doit envoyer EXACTEMENT ce que l'application envoie.
    #
    # Elle transmettait les octets bruts du fichier : ni redressement EXIF, ni
    # bornage, ni normalisation de ratio. Elle testait donc un chemin que le
    # produit n'emprunte jamais — et son verdict ne prouvait rien sur lui.
    from app.services.image_validation import validate_image
    from app.services.vto_service import _bounded

    validated = validate_image(photo.read_bytes(), "image/jpeg")
    prepared = _bounded(validated.data)

    with Image.open(io.BytesIO(prepared)) as ready:
        print(f"envoye      : {ready.width}x{ready.height}  ratio 1:{ready.height / ready.width:.2f}"
              f"  ({len(prepared) // 1024} Ko)")
    if len(prepared) != len(validated.data):
        print("              (photo preparee : orientation, bornage ou cadre)")
    print()

    service = ApparelVTOService()
    try:
        result = await service.generate(prepared, garment)
    except YouCamError as exc:
        code = getattr(exc, "provider_code", None) or ""
        print("ECHEC")
        print(f"  classe        : {type(exc).__name__}")
        print(f"  code provider : {code or '—'}")
        print(f"  detail        : {exc.detail or '—'}")

        if code == "error_editing_failed":
            print("\n`error_editing_failed` : le rendu n'a pas pu etre produit.")
            print("Le vetement et la photo ont ete acceptes, c'est la composition")
            print("qui echoue. Causes possibles, par frequence observee :")
            print("  1. le vetement de reference n'est pas une photo produit —")
            print("     aplat genere, ou quelqu'un qui le porte :")
            print("       python scripts/check_garments.py")
            print("  2. la photo source ne montre pas un corps entier exploitable :")
            print("     de face, une seule personne, bras le long du corps")
            print("  3. la piece et la categorie ne concordent pas — une veste")
            print("     annoncee `jacket` mais qui est un manteau long, par exemple")
            print("\nLe test qui tranche : la meme photo avec une piece differente.")
            print("  python scripts/probe_vto.py <photo> jacket_02")
        return 1
    finally:
        from app.integrations.youcam.client import close_youcam_client

        await close_youcam_client()

    print("SUCCES")
    print(json.dumps({
        "provider": result.provider,
        "simulated": result.simulated,
        "task_id": result.provider_task_id,
        "bytes": len(result.image_bytes or b""),
    }, indent=2))

    output = ROOT / "probe_vto_result.jpg"
    if result.image_bytes:
        output.write_bytes(result.image_bytes)
        print(f"\nResultat ecrit dans {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
