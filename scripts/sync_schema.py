#!/usr/bin/env python3
"""Aligne une base existante sur les modeles, sans la recreer.

L'API le fait deja au demarrage. Ce script sert quand on veut verifier ou
appliquer l'operation separement — par exemple avant un deploiement, ou pour
inspecter ce qui manque sans rien modifier :

    python scripts/sync_schema.py --dry-run
    python scripts/sync_schema.py
"""

from __future__ import annotations

import argparse
import asyncio
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

from app.db.base import Base  # noqa: E402
from app.db.session import dispose_engine, engine, ensure_sqlite_directory  # noqa: E402
from app.db.schema_sync import plan_additive_changes, sync_additive_columns  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronisation additive du schema")
    parser.add_argument("--dry-run", action="store_true", help="lister sans modifier")
    args = parser.parse_args()

    ensure_sqlite_directory(str(engine.url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        missing = await conn.run_sync(plan_additive_changes)

        if not missing:
            print("Schema a jour : aucune colonne manquante.")
        elif args.dry_run:
            print("Colonnes manquantes :")
            for table, column in missing:
                print(f"  - {table}.{column.name} ({column.type})")
        else:
            for name in await conn.run_sync(sync_additive_columns):
                print(f"Ajoutee : {name}")

    await dispose_engine()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
