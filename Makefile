# MIRROR OPS — raccourcis de developpement
API := apps/api
WEB := apps/web

.PHONY: help install install-api install-web dev dev-api dev-web build test lint \
        demo calibrate openapi clean docker-up docker-down

help:
	@echo "install      Installer backend + frontend"
	@echo "dev-api      Lancer l'API          (http://localhost:8000)"
	@echo "dev-web      Lancer l'interface    (http://localhost:3000)"
	@echo "test         Lancer les tests backend + frontend"
	@echo "build        Compiler le frontend en production"
	@echo "audit        Verifier le parcours de bout en bout, champ par champ"
	@echo "demo         Derouler le parcours complet contre l'API locale"
	@echo "calibrate    Afficher le classement des candidats ONE CHANGE"
	@echo "openapi      Exporter la specification dans docs/openapi.json"
	@echo "schema       Lister les colonnes manquantes dans la base"
	@echo "garments     Verifier que le catalogue contient de vraies photos"
	@echo "docker-up    Lancer PostgreSQL + API + interface"

install: install-api install-web

install-api:
	cd $(API) && pip install -r requirements-dev.txt

install-web:
	npm install

dev: 
	@echo "Ouvrir deux terminaux : 'make dev-api' et 'make dev-web'."

dev-api:
	cd $(API) && uvicorn app.main:app --reload --port 8000

dev-web:
	npm run dev

build:
	npm run build

test: test-api test-web

test-api:
	cd $(API) && python -m pytest -q

test-web:
	npm run test --workspace @mirror-ops/web

lint:
	cd $(API) && ruff check app tests
	npm run typecheck

audit:
	python scripts/audit_journey.py

demo:
	python scripts/demo_flow.py

calibrate:
	python scripts/calibrate_engine.py

openapi:
	python scripts/export_openapi.py

schema:
	python scripts/sync_schema.py --dry-run

garments:
	python scripts/check_garments.py

import-garments:
	@echo "Usage : python scripts/import_garments.py <dossier de photos>"

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} + ; \
	rm -rf $(API)/var/*.db $(API)/.pytest_cache $(WEB)/.next $(WEB)/tsconfig.tsbuildinfo
