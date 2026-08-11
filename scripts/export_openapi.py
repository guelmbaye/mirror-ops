#!/usr/bin/env python3
"""Exporte la specification OpenAPI (Doc 08 §25) dans docs/openapi.json."""

from __future__ import annotations

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

from app.main import app  # noqa: E402

output = ROOT / "docs" / "openapi.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False), encoding="utf-8")
print(f"OpenAPI ecrit dans {output.relative_to(ROOT)}")
