#!/usr/bin/env python3
"""Job de nettoyage des medias et sessions expires (Doc 08 §29).

A brancher sur un cron : `*/15 * * * * python scripts/cleanup.py`
"""

from __future__ import annotations

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

from app.db.session import SessionLocal, dispose_engine  # noqa: E402
from app.services.cleanup_service import cleanup_expired  # noqa: E402


async def main() -> None:
    async with SessionLocal() as db:
        report = await cleanup_expired(db)
        await db.commit()
    await dispose_engine()
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
