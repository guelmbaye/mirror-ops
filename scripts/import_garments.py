#!/usr/bin/env python3
"""Remplace les visuels du catalogue par de vraies photographies de vetements.

Le catalogue livre contient des aplats generes programmatiquement. Ils suffisent
au mode `mock` et font echouer tout essayage reel en `error_editing_failed`.

Vos fichiers n'ont PAS a porter les noms du catalogue : le script reconnait la
categorie depuis le nom (« veste-marine.jpg », « sneakers white.png »,
« chemise_01.jpeg »...), en francais comme en anglais, et attribue chaque photo
a un emplacement libre. Ce qu'il ne reconnait pas, il le dit — il n'invente pas.

    # voir ce qui serait fait, sans rien ecrire
    python scripts/import_garments.py ~/photos --dry-run

    # importer
    python scripts/import_garments.py ~/photos

    # forcer une correspondance precise
    python scripts/import_garments.py --id jacket_01 ~/veste-marine.jpg

    # depuis un catalogue en ligne : un manifeste « identifiant  URL »
    python scripts/import_garments.py catalogue.txt

    # remplir les emplacements restants dans l'ordre, meme sans indice de nom
    python scripts/import_garments.py ~/photos --auto

Vos images sont ecrites dans `apps/api/var/garments/`, jamais dans le code
source. Elles survivent donc a toute mise a jour du projet — decompresser une
archive par-dessus n'efface plus rien.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Depot monorepo, ou image de l'API ou `app/` est a la racine : les scripts
# doivent fonctionner dans les deux, sinon la moitie d'entre eux est
# inutilisable en production.
for candidate in (ROOT / "apps" / "api", ROOT):
    if (candidate / "app").is_dir():
        sys.path.insert(0, str(candidate))
        break

from app.services.garment_audit import count_colours  # noqa: E402
from app.services.garment_service import (  # noqa: E402
    CATALOG_DIR,
    OVERRIDE_DIR,
    list_garments,
)

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
MIN_LONG_SIDE = 1024

#: Mots qui trahissent la categorie d'une photo, en francais et en anglais.
#: Volontairement genereux : une correspondance visible dans le tableau
#: recapitulatif vaut mieux qu'un fichier refuse sans explication.
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "jacket": (
        "jacket", "blazer", "coat", "overcoat", "parka", "cardigan",
        "veste", "manteau", "blouson", "vareuse", "gilet", "veston", "doudoune",
    ),
    "top": (
        "top", "shirt", "tshirt", "tee", "blouse", "sweater", "pullover", "knit",
        "polo", "turtleneck",
        "haut", "chemise", "chemisier", "pull", "maillot", "debardeur",
    ),
    "bottom": (
        "bottom", "trousers", "pants", "jeans", "chino", "skirt", "shorts",
        "bas", "pantalon", "jupe", "jean", "bermuda", "short",
    ),
    "shoes": (
        "shoe", "shoes", "sneaker", "sneakers", "boot", "boots", "loafer",
        "derby", "oxford", "heel", "heels",
        "chaussure", "chaussures", "basket", "baskets", "mocassin", "mocassins",
        "bottine", "escarpin", "derby", "sandale",
    ),
    "accessories": (
        "accessory", "accessories", "scarf", "bag", "belt", "tie", "watch",
        "necklace", "glasses",
        "accessoire", "accessoires", "echarpe", "foulard", "sac", "ceinture",
        "cravate", "montre", "collier", "lunettes",
    ),
}


MANIFEST_SUFFIXES = {".txt", ".tsv", ".csv", ".list"}


def read_manifest(path: Path) -> list[tuple[str, str]]:
    """Lit un manifeste « identifiant<espace>URL », une entree par ligne.

    Referencer un catalogue en ligne se fait ICI, a l'import, et non a chaque
    appel : l'image est telechargee une fois, normalisee comme les autres, puis
    servie localement. Le parcours ne depend donc d'aucun hebergeur tiers au
    moment ou il compte — pendant une demonstration, notamment.
    """
    entries: list[tuple[str, str]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.replace("\t", " ").replace(",", " ").split()
        if len(parts) < 2 or not parts[1].startswith(("http://", "https://")):
            print(f"  ! ligne {number} ignoree (format attendu : identifiant URL) : {line[:60]}")
            continue
        entries.append((parts[0], parts[1]))
    return entries


def download(url: str, into: Path) -> Path:
    """Recupere une image distante dans un fichier temporaire."""
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": "mirror-ops/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        data = response.read()
    into.write_bytes(data)
    return into


def slug(value: str) -> str:
    """Minuscules, sans accents, separateurs uniformes."""
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def guess_category(stem: str) -> str | None:
    normalized = slug(stem)
    # « sac1 », « veste 02 » : un chiffre colle au mot ne doit pas le masquer.
    # Numeroter ses fichiers est le cas normal, pas l'exception.
    words = {word.rstrip("0123456789") or word for word in normalized.split()}
    for category, keywords in CATEGORY_KEYWORDS.items():
        if words & set(keywords):
            return category

    # Mot compose sans separateur : « vestenoire », « blackjacket ».
    flat = normalized.replace(" ", "")
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in flat for keyword in keywords if len(keyword) >= 4):
            return category
    return None


# Derive du service, et non du depot : dans l'image de l'API, `app/` est a la
# racine et le chemin monorepo n'existe pas.
CATALOG_PATH = CATALOG_DIR / "catalog.json"
#: Les pieces ajoutees vivent a part, pour la meme raison que les images.
EXTRA_CATALOG_PATH = OVERRIDE_DIR / "catalog.extra.json"


def dominant_colour(path: Path) -> str:
    """Teinte dominante du vetement, echantillonnee sur l'image reelle."""
    from PIL import Image

    try:
        with Image.open(path) as opened:
            image = opened.convert("RGB")
            image.thumbnail((64, 64))
            colours = image.getcolors(maxcolors=1 << 16) or []
            # On ignore le fond clair : ce qui compte est le vetement.
            pigment = [c for c in colours if sum(c[1]) < 690]
            red, green, blue = max(pigment or colours, key=lambda c: c[0])[1]
        return f"#{red:02X}{green:02X}{blue:02X}"
    except Exception:  # pragma: no cover
        return "#808080"


def category_defaults(entries: list[dict], category: str) -> dict:
    """Attributs medians de la categorie.

    Une nouvelle piece herite du profil moyen de ses semblables plutot que de
    valeurs inventees. C'est un point de depart honnete, et `catalog.json`
    reste editable a la main.
    """
    peers = [e for e in entries if e["category"] == category]
    keys = ("formality", "structure", "color_neutrality", "expressiveness", "elegance")
    if not peers:
        return dict.fromkeys(keys, 0.6)
    return {
        key: round(sum(p.get(key, 0.6) for p in peers) / len(peers), 2) for key in keys
    }


def next_free_identifier(used: set[str], category: str) -> str:
    prefix = "accessory" if category == "accessories" else category
    index = 1
    while f"{prefix}_{index:02d}" in used:
        index += 1
    return f"{prefix}_{index:02d}"


def extend_catalog(new_entries: list[dict]) -> None:
    """Ajoute des pieces SANS toucher au catalogue du depot."""
    import json

    OVERRIDE_DIR.mkdir(parents=True, exist_ok=True)
    document = {"garments": []}
    if EXTRA_CATALOG_PATH.exists():
        try:
            document = json.loads(EXTRA_CATALOG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    known = {entry.get("id") for entry in document.get("garments", [])}
    document.setdefault("garments", []).extend(
        entry for entry in new_entries if entry["id"] not in known
    )
    EXTRA_CATALOG_PATH.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def normalize(source: Path) -> bytes:
    """Fond blanc, RGB, cote long >= 1024 px, JPEG de bonne qualite."""
    from PIL import Image

    with Image.open(source) as opened:
        image = opened.convert("RGBA")
        canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
        canvas.alpha_composite(image)
        flat = canvas.convert("RGB")

        long_side = max(flat.size)
        if long_side < MIN_LONG_SIDE:
            scale = MIN_LONG_SIDE / long_side
            flat = flat.resize(
                (round(flat.width * scale), round(flat.height * scale)), Image.LANCZOS
            )

        buffer = io.BytesIO()
        flat.save(buffer, format="JPEG", quality=94)
        return buffer.getvalue()


def plan(
    files: list[Path], catalog: dict, auto: bool
) -> tuple[list[tuple[str, Path, str]], list[Path]]:
    """Associe chaque photo a un emplacement. Retourne (plan, non attribuees)."""
    taken: set[str] = set()
    assignments: list[tuple[str, Path, str]] = []

    by_category: dict[str, list[str]] = {}
    for garment_id, garment in catalog.items():
        by_category.setdefault(garment.category, []).append(garment_id)
    for ids in by_category.values():
        ids.sort()

    # 1) Nom exact d'un identifiant du catalogue : sans ambiguite.
    remaining: list[Path] = []
    for path in files:
        if path.stem in catalog and path.stem not in taken:
            taken.add(path.stem)
            assignments.append((path.stem, path, "nom exact"))
        else:
            remaining.append(path)

    # 2) Categorie devinee depuis le nom du fichier.
    unmatched: list[Path] = []
    created: list[tuple[str, Path, str]] = []
    known_ids = set(catalog)

    for path in remaining:
        category = guess_category(path.stem)
        if category is None:
            unmatched.append(path)
            continue

        free = [i for i in by_category.get(category, []) if i not in taken]
        if free:
            taken.add(free[0])
            assignments.append((free[0], path, f"reconnu « {category} »"))
            continue

        # La categorie est reconnue mais tous ses emplacements sont pris :
        # le catalogue s'agrandit plutot que d'ecarter la photo. Un catalogue
        # de taille fixe n'a aucune raison d'exister.
        identifier = next_free_identifier(known_ids, category)
        known_ids.add(identifier)
        taken.add(identifier)
        created.append((identifier, path, category))
        assignments.append((identifier, path, f"nouvelle piece « {category} »"))

    # 3) Le reste : uniquement sur demande explicite, jamais en silence.
    leftover = unmatched
    if auto:
        free = [i for i in sorted(catalog) if i not in taken]
        for path, garment_id in zip(unmatched, free):
            taken.add(garment_id)
            assignments.append((garment_id, path, "attribue par --auto"))
        leftover = unmatched[len(free):]

    assignments.sort(key=lambda item: item[0])
    return assignments, leftover, created


def import_from_manifest(manifest: Path, catalog: dict, dry_run: bool) -> int:
    import tempfile

    entries = read_manifest(manifest)
    if not entries:
        print(f"Aucune entree exploitable dans {manifest.resolve()}")
        print("Format attendu, une ligne par piece :")
        print("  jacket_01  https://exemple.test/veste-marine.jpg")
        return 1

    unknown = [i for i, _ in entries if i not in catalog]
    if unknown:
        print("Identifiants inconnus : " + ", ".join(sorted(set(unknown))))
        print("Disponibles : " + ", ".join(sorted(catalog)))

    print(f"{len(entries)} entree(s) :\n")
    written = 0
    with tempfile.TemporaryDirectory() as scratch:
        for garment_id, url in entries:
            if garment_id not in catalog:
                continue
            if dry_run:
                print(f"  · {garment_id:<14} <- {url[:60]}")
                continue

            try:
                downloaded = download(url, Path(scratch) / f"{garment_id}.bin")
                data = normalize(downloaded)
            except Exception as exc:
                print(f"  x {garment_id:<14} <- {url[:48]}  echec ({exc})")
                continue

            target = catalog[garment_id].image_path
            backup = target.with_suffix(target.suffix + ".placeholder")
            if not backup.exists():
                shutil.copy2(target, backup)
            target.write_bytes(data)

            colours = count_colours(target)
            state = "ok" if colours > 64 else "TOUJOURS UN APLAT"
            print(f"  + {garment_id:<14} <- {url[:48]}  {colours} couleurs  {state}")
            written += 1

    if dry_run:
        print("\nRien n'a ete ecrit. Relancez sans --dry-run.")
        return 0
    print(f"\n{written} vetement(s) importes depuis le manifeste.")
    print("Les images sont desormais LOCALES : plus aucune dependance a l'hebergeur.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Importer de vraies photos de vetements")
    parser.add_argument("source", type=Path, help="dossier de photos, ou fichier unique avec --id")
    parser.add_argument("--id", dest="garment_id", help="identifiant cible pour un fichier unique")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="attribuer aussi les photos dont la categorie n'est pas reconnue",
    )
    parser.add_argument("--dry-run", action="store_true", help="afficher sans ecrire")
    args = parser.parse_args()

    source = args.source.expanduser()
    catalog = {garment.id: garment for garment in list_garments()}
    leftover: list[Path] = []

    # --- catalogue en ligne : un manifeste « identifiant URL »
    if source.is_file() and source.suffix.lower() in MANIFEST_SUFFIXES and not args.garment_id:
        return import_from_manifest(source, catalog, args.dry_run)

    if args.garment_id:
        if args.garment_id not in catalog:
            print(f"Identifiant inconnu : {args.garment_id}")
            print("Disponibles : " + ", ".join(sorted(catalog)))
            return 2
        if not source.is_file():
            print(f"Fichier introuvable : {source.resolve()}")
            return 2
        assignments = [(args.garment_id, source, "impose par --id")]
        created = []
    else:
        if not source.is_dir():
            print(f"{source.resolve()} n'est pas un dossier.")
            print("Pour un fichier unique : --id jacket_01 <fichier>")
            return 2

        everything = sorted(p for p in source.iterdir() if p.is_file())
        files = [p for p in everything if p.suffix.lower() in SUPPORTED]

        if not files:
            print(f"Aucune image exploitable dans {source.resolve()}")
            if everything:
                print(f"  {len(everything)} fichier(s) trouve(s), aucun au bon format :")
                for path in everything[:8]:
                    print(f"    · {path.name}")
            print("  Formats acceptes : " + ", ".join(sorted(SUPPORTED)))
            return 1

        assignments, leftover, created = plan(files, catalog, args.auto)

    if not assignments:
        print(f"{len(leftover)} photo(s) trouvee(s), aucune categorie reconnue :")
        for path in leftover[:12]:
            print(f"  · {path.name}")
        print("\nTrois facons de resoudre cela :")
        print("  1. glisser un mot dans le nom : veste, chemise, pantalon, chaussures, accessoire")
        print("  2. cibler un emplacement precis : --id jacket_01 <fichier>")
        print("  3. tout attribuer dans l'ordre : --auto")
        return 1

    new_by_id = {identifier: (path, category) for identifier, path, category in created}

    print(f"{len(assignments)} correspondance(s) :\n")
    written = 0
    added_entries: list[dict] = []

    import json as _json

    document = _json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    existing = document["garments"]
    images_dir = CATALOG_PATH.parent

    OVERRIDE_DIR.mkdir(parents=True, exist_ok=True)

    for garment_id, path, reason in assignments:
        if garment_id in new_by_id:
            target = OVERRIDE_DIR / f"{garment_id}.png"
        else:
            # On ecrit TOUJOURS dans le repertoire utilisateur : le visuel livre
            # reste intact, et une mise a jour du projet ne detruit rien.
            target = OVERRIDE_DIR / Path(catalog[garment_id].image).name

        if args.dry_run:
            print(f"  · {garment_id:<14} <- {path.name:<34} ({reason})")
            continue

        try:
            data = normalize(path)
        except Exception as exc:
            print(f"  x {garment_id:<14} <- {path.name:<34} illisible ({exc})")
            continue

        target.write_bytes(data)

        if garment_id in new_by_id:
            _, category = new_by_id[garment_id]
            entry = {
                "id": garment_id,
                "category": category,
                "name": path.stem.replace("_", " ").replace("-", " ").strip().title(),
                "description": "Imported garment.",
                **category_defaults(existing, category),
                "color": dominant_colour(target),
                "image": target.name,
            }
            added_entries.append(entry)

        colours = count_colours(target)
        state = "ok" if colours > 64 else "TOUJOURS UN APLAT"
        print(f"  + {garment_id:<14} <- {path.name:<34} {colours} couleurs  {state}")
        written += 1

    if added_entries:
        extend_catalog(added_entries)
        print(f"\n{len(added_entries)} nouvelle(s) piece(s) ajoutee(s) au catalogue :")
        for entry in added_entries:
            print(f"  · {entry['id']:<14} {entry['category']:<12} {entry['color']}  « {entry['name']} »")
        print("  Attributs herites de la mediane de leur categorie — ajustables")
        print("  dans apps/api/app/assets/garments/catalog.json.")

    if leftover:
        print(f"\n{len(leftover)} photo(s) sans categorie reconnue :")
        for path in leftover[:12]:
            print(f"  · {path.name}")
        print("  Renommez-les avec un mot-cle (veste, chemise, pantalon, chaussures,")
        print("  accessoire), ou placez-les une par une avec --id.")

    if args.dry_run:
        print("\nRien n'a ete ecrit. Relancez sans --dry-run.")
        return 0

    print(f"\n{written} vetement(s) ecrits dans {OVERRIDE_DIR}")
    print("  Ce repertoire n'est jamais ecrase par une mise a jour du projet.")
    if added_entries:
        print("  Redemarrez l'API pour que les nouvelles pieces apparaissent.")
    print("\nVerifiez avec :  python scripts/check_garments.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
