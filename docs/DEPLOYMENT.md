# Guide de déploiement — MIRROR OPS sur DigitalOcean

## Contextual Appearance Decision Engine · Next.js + FastAPI + PostgreSQL

> **Domaines cibles**
> - `mirror-ops.vylantic.com` — frontend Next.js
> - `api.mirror-ops.vylantic.com` — API FastAPI
>
> Ce guide installe MIRROR OPS sur un droplet DigitalOcean **avec une
> infrastructure mutualisable** : reverse proxy Nginx partagé, réseaux Docker
> isolés. Si le droplet héberge déjà une autre application, MIRROR OPS s'ajoute
> sans conflit.

---

## Architecture cible

| Service | Domaine | Technologie | Port interne |
|---|---|---|---|
| Frontend | `mirror-ops.vylantic.com` | Next.js 14 (App Router, standalone) | 3000 |
| API | `api.mirror-ops.vylantic.com` | FastAPI + Python 3.12 | 8000 |
| Base de données | (interne) | PostgreSQL 16 | 5432 |

Pas de Redis, pas de file d'attente, pas de moteur de recherche, pas de stockage
S3. Le Doc 07 l'énonce ainsi : *ne pas introduire d'infrastructure avant que
l'API ne l'exige*. Le polling YouCam reste dans le backend, les médias
temporaires vivent sur un volume, et la décision est synchrone.

> Aucun port n'est publié sur l'hôte sauf 80/443 (Nginx).

---

# 1. Architecture globale

```text
Internet
   │
   ▼
Cloudflare (optionnel — DNS + CDN + WAF)
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│  Droplet Ubuntu 24.04 LTS  (2 vCPU / 4 Go RAM / 50 Go SSD)  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Réseau Docker partagé : proxy-network                 │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  proxy-nginx  (reverse proxy global mutualisé)   │  │  │
│  │  │  • ports 80 / 443                                │  │  │
│  │  │  • TLS via Let's Encrypt                         │  │  │
│  │  │  • route par domaine vers chaque app             │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─────────────── MIRROR OPS ───────────────────────────┐    │
│  │  Réseau : mirror-ops-network                         │    │
│  │   • mirror-ops-web       :3000  (Next.js)            │    │
│  │   • mirror-ops-api       :8000  (FastAPI)            │    │
│  │   • mirror-ops-postgres  :5432                       │    │
│  │                                                       │    │
│  │  Volumes persistants                                  │    │
│  │   • mirror_pgdata    base de données                  │    │
│  │   • mirror_media     photos et aperçus temporaires    │    │
│  │   • mirror_garments  vêtements importés               │    │
│  └───────────────────────────────────────────────────────┘    │
│                                                              │
│                    ┌──────────────┐                          │
│                    │  YouCam API  │  (sortant, HTTPS)        │
│                    │ makeupar.com │                          │
│                    └──────────────┘                          │
└──────────────────────────────────────────────────────────────┘
```

---

# 2. Prérequis droplet

Si le droplet existe déjà, passer directement à la section 5. Sinon :

- **Plan** : 2 vCPU / 4 Go RAM / 50 Go SSD NVMe suffit — la charge est faible
  (une décision est calculée en quelques millisecondes ; l'attente vient de
  YouCam, pas de nous). Prévoir 4 vCPU si d'autres applications cohabitent.
- **OS** : Ubuntu 24.04 LTS
- **Région** : Frankfurt (`fra1`) ou Amsterdam (`ams3`)
- **Backups** : activés

---

# 3. Hardening (si nouveau droplet)

```bash
apt update && apt upgrade -y
apt install -y curl wget vim git ufw fail2ban unzip ca-certificates gnupg lsb-release htop btop ncdu jq tree net-tools dnsutils

# Utilisateur non-root
adduser deploy && usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh && chmod 700 /home/deploy/.ssh

# SSH
sed -i 's/^PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh

# Timezone
timedatectl set-timezone Africa/Casablanca

# fail2ban
systemctl enable --now fail2ban
```

---

# 4. Firewall + Docker (si nouveau droplet)

```bash
# UFW
ufw default deny incoming && ufw default allow outgoing
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw enable

# Docker
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
usermod -aG docker deploy
```

---

# 5. DNS

Créer les enregistrements A :

```
Type  Nom                              Valeur          Proxy
A     mirror-ops.vylantic.com          XX.XX.XX.XX     ☁️
A     api.mirror-ops.vylantic.com      XX.XX.XX.XX     ☁️
```

Vérifier :

```bash
dig +short mirror-ops.vylantic.com
dig +short api.mirror-ops.vylantic.com
```

---

# 6. Structure serveur

```
/var/www/
├── proxy/                           # Nginx mutualisé (existe déjà si autre app)
│   ├── docker-compose.yml
│   ├── certbot/{conf,www}
│   └── nginx/{nginx.conf,conf.d/,snippets/}
│
└── mirror-ops/                      # Monorepo MIRROR OPS
    ├── docker-compose.prod.yml
    ├── .env
    ├── apps/
    │   ├── api/                     # FastAPI (Dockerfile inclus)
    │   └── web/                     # Next.js (Dockerfile inclus)
    ├── packages/{types,config}      # contrat TypeScript partagé
    └── scripts/                     # audit, import vêtements, cleanup
```

```bash
mkdir -p /var/www/mirror-ops
chown -R deploy:deploy /var/www/mirror-ops
```

---

# 7. Réseaux Docker

```bash
# Réseau proxy (existe déjà si une autre app est installée)
docker network create proxy-network 2>/dev/null || true

# Réseau dédié MIRROR OPS
docker network create mirror-ops-network
```

---

# 8. Reverse proxy Nginx (vhosts MIRROR OPS)

> Si le proxy est déjà installé, il suffit d'ajouter les deux vhosts ci-dessous
> dans `/var/www/proxy/nginx/conf.d/`.

### `/var/www/proxy/nginx/conf.d/mirror-ops-web.conf`

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name mirror-ops.vylantic.com;

    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name mirror-ops.vylantic.com;

    ssl_certificate     /etc/letsencrypt/live/mirror-ops.vylantic.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mirror-ops.vylantic.com/privkey.pem;

    include /etc/nginx/snippets/ssl.conf;
    include /etc/nginx/snippets/security.conf;

    access_log /var/log/nginx/mirror-ops-web-access.log main;
    error_log  /var/log/nginx/mirror-ops-web-error.log warn;

    location /_next/static/ {
        proxy_pass http://mirror-ops-web:3000;
        include /etc/nginx/snippets/proxy.conf;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    location / {
        proxy_pass http://mirror-ops-web:3000;
        include /etc/nginx/snippets/proxy.conf;
    }
}
```

### `/var/www/proxy/nginx/conf.d/mirror-ops-api.conf`

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name api.mirror-ops.vylantic.com;

    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name api.mirror-ops.vylantic.com;

    ssl_certificate     /etc/letsencrypt/live/api.mirror-ops.vylantic.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.mirror-ops.vylantic.com/privkey.pem;

    include /etc/nginx/snippets/ssl.conf;
    include /etc/nginx/snippets/security.conf;

    access_log /var/log/nginx/mirror-ops-api-access.log main;
    error_log  /var/log/nginx/mirror-ops-api-error.log warn;

    # Les photos montent jusqu'à 10 Mo (MAX_IMAGE_BYTES). Sans cette ligne,
    # Nginx coupe à 1 Mo et l'upload échoue avant d'atteindre l'API.
    client_max_body_size 12M;

    # Un essayage YouCam prend 13 à 15 secondes en pratique, et le polling
    # backend peut aller jusqu'à 90 s (YOUCAM_POLL_TIMEOUT_MS). En dessous de
    # ce seuil, Nginx coupe une requête qui allait aboutir.
    proxy_read_timeout 120s;
    proxy_send_timeout 120s;

    location / {
        proxy_pass http://mirror-ops-api:8000;
        include /etc/nginx/snippets/proxy.conf;
    }
}
```

---

# 9. Variables d'environnement

### `/var/www/mirror-ops/.env`

> Ce fichier alimente `docker compose`. Sous Docker, les variables passées par
> compose deviennent de **vraies variables d'environnement**, qui priment sur
> `apps/api/.env` — lequel ne sert qu'au développement local. C'est donc ici, et
> nulle part ailleurs, que se règle la production.

```bash
# ─── PostgreSQL ─────────────────────────────────────
POSTGRES_DB=mirror_ops
POSTGRES_USER=mirror
POSTGRES_PASSWORD=                    # openssl rand -base64 32

# ─── Domaines publics ───────────────────────────────
# PUBLIC_BASE_URL fabrique les URLs média signées. Si elle ne correspond pas à
# l'adresse réelle de l'API, les images sont introuvables pour TOUT LE MONDE
# alors que l'API répond 201. Panne silencieuse : à vérifier en premier.
PUBLIC_BASE_URL=https://api.mirror-ops.vylantic.com
CORS_ORIGINS=https://mirror-ops.vylantic.com

# ─── Frontend (compilées dans le bundle client) ─────
NEXT_PUBLIC_API_BASE_URL=https://api.mirror-ops.vylantic.com
NEXT_PUBLIC_SITE_URL=https://mirror-ops.vylantic.com

# ─── Sécurité ───────────────────────────────────────
# Signe les URLs média. La changer invalide tous les liens en circulation.
MEDIA_SIGNING_SECRET=                 # openssl rand -base64 48

# ─── YouCam (Perfect Corp) ──────────────────────────
# mock = aucun appel réseau, aperçus marqués « simulated »
# live = appels réels Skin AI + Apparel VTO
YOUCAM_MODE=live
YOUCAM_AUTH_MODE=api_key
YOUCAM_API_KEY=                       # https://yce.perfectcorp.com/api-console/en/api-keys/
```

```bash
chmod 600 /var/www/mirror-ops/.env
```

> **`NEXT_PUBLIC_API_BASE_URL` est compilée dans le bundle JavaScript**, pas lue
> à l'exécution. La modifier impose un `docker compose build web`, pas un simple
> redémarrage.

---

# 10. Docker Compose production

### `/var/www/mirror-ops/docker-compose.prod.yml`

> Adaptation du `docker-compose.yml` du dépôt : aucun port publié, réseaux
> externes, secrets depuis `.env`, volumes nommés pour tout ce qui doit survivre
> à un redéploiement.

```yaml
services:

  # ─── PostgreSQL ───────────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    container_name: mirror-ops-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB:       ${POSTGRES_DB}
      POSTGRES_USER:     ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - mirror_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 10
    networks:
      - mirror-ops-network

  # ─── API FastAPI ──────────────────────────────────────────────
  api:
    build:
      # Racine du monorepo : l'image embarque aussi scripts/ (import de
      # vêtements, nettoyage, audit), indispensables en exploitation.
      context: .
      dockerfile: apps/api/Dockerfile
    container_name: mirror-ops-api
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      APP_ENV: production
      LOG_JSON: "true"
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@mirror-ops-postgres:5432/${POSTGRES_DB}
      PUBLIC_BASE_URL: ${PUBLIC_BASE_URL}
      CORS_ORIGINS: ${CORS_ORIGINS}
      MEDIA_SIGNING_SECRET: ${MEDIA_SIGNING_SECRET}
      STORAGE_BACKEND: local
      STORAGE_DIR: /srv/api/var/storage
      # Les vêtements importés vivent hors du code source : une image
      # reconstruite ne doit jamais les effacer.
      GARMENT_OVERRIDE_DIR: /srv/api/var/garments
      YOUCAM_MODE:      ${YOUCAM_MODE:-mock}
      YOUCAM_AUTH_MODE: ${YOUCAM_AUTH_MODE:-api_key}
      YOUCAM_API_KEY:   ${YOUCAM_API_KEY:-}
    volumes:
      - mirror_media:/srv/api/var/storage
      - mirror_garments:/srv/api/var/garments
    networks:
      - mirror-ops-network
      - proxy-network

  # ─── Frontend Next.js ─────────────────────────────────────────
  web:
    build:
      # Contexte = racine du monorepo : le Dockerfile a besoin de
      # packages/types et packages/config, hors de apps/web.
      context: .
      dockerfile: apps/web/Dockerfile
      args:
        NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL}
        NEXT_PUBLIC_SITE_URL:     ${NEXT_PUBLIC_SITE_URL}
    container_name: mirror-ops-web
    restart: unless-stopped
    environment:
      NODE_ENV: production
      NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL}
      NEXT_PUBLIC_SITE_URL:     ${NEXT_PUBLIC_SITE_URL}
    depends_on:
      - api
    networks:
      - proxy-network

volumes:
  mirror_pgdata:
  mirror_media:
  mirror_garments:

networks:
  mirror-ops-network:
    external: true
  proxy-network:
    external: true
```

> Les Dockerfiles sont ceux **déjà présents** dans le dépôt
> (`apps/api/Dockerfile`, `apps/web/Dockerfile`). Aucune modification nécessaire.

---

# 11. Points de configuration propres à MIRROR OPS

### 11.1 — Next.js en mode standalone

Déjà réglé dans `apps/web/next.config.mjs` :

```javascript
const nextConfig = {
  output: "standalone",                                   // requis par le Dockerfile
  transpilePackages: ["@mirror-ops/types", "@mirror-ops/config"],
};
```

### 11.2 — Le build ne dépend pas des outils de test

`tsconfig.json` exclut `tests/` et `vitest.config.ts` : `next build` ne
type-vérifie que l'application. Une image construite sans dépendances de
développement compile donc normalement. Les tests restent vérifiés localement
par `npm run typecheck`, qui fait deux passes.

### 11.3 — HTTPS obligatoire pour la prise de photo

L'écran *Your look* ouvre un vrai flux caméra via `getUserMedia`, qui exige un
**contexte sécurisé**. En HTTP, le bouton « Take photo » disparaît et seul
l'import de fichier reste. C'est une raison de plus de ne jamais exposer le
frontend sans TLS.

### 11.4 — Pas de migrations à lancer

Il n'y a pas d'Alembic. Au démarrage, l'API crée les tables manquantes puis
ajoute les colonnes manquantes aux tables existantes (`db/schema_sync.py`).
L'opération est **additive uniquement** : renommer ou supprimer une colonne
relève d'une migration manuelle.

Pour inspecter avant de déployer :

```bash
docker compose -f docker-compose.prod.yml exec api python scripts/sync_schema.py --dry-run
```

### 11.5 — Le catalogue de vêtements

Les visuels livrés sont des aplats générés : suffisants pour `YOUCAM_MODE=mock`,
**inexploitables par un try-on réel**, qui échoue dessus en
`error_editing_failed`. Le volume `mirror_garments` reçoit vos vraies photos et
survit aux reconstructions d'image.

```bash
# Copier vos photos dans le volume, puis importer
docker cp ~/vetements/. mirror-ops-api:/srv/api/var/import/
docker compose -f docker-compose.prod.yml exec api \
  python scripts/import_garments.py /srv/api/var/import
docker compose -f docker-compose.prod.yml restart api
```

Vérifier : `GET /api/v1/garments` doit renvoyer `"placeholder": false` partout.

---

# 12. Récupération du code

```bash
cd /var/www/mirror-ops
git clone git@github.com:VOTRE-ORG/mirror-ops.git .
```

---

# 13. Certificats Let's Encrypt

### 13.1 — Bootstrap HTTP (première fois)

```bash
cat > /var/www/proxy/nginx/conf.d/_mirror-ops-bootstrap.conf << 'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name mirror-ops.vylantic.com api.mirror-ops.vylantic.com;

    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 200 "Mirror Ops Bootstrap OK"; add_header Content-Type text/plain; }
}
EOF
```

Désactiver les vhosts HTTPS :

```bash
cd /var/www/proxy/nginx/conf.d
for f in mirror-ops-web.conf mirror-ops-api.conf; do
  [ -f "$f" ] && mv "$f" "${f}.disabled"
done
docker exec proxy-nginx nginx -s reload
```

### 13.2 — Émettre les certificats

```bash
cd /var/www/proxy
docker compose run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot \
  --email VOTRE-EMAIL --agree-tos --no-eff-email \
  -d mirror-ops.vylantic.com \
  -d api.mirror-ops.vylantic.com
```

### 13.3 — Réactiver les vhosts complets

```bash
cd /var/www/proxy/nginx/conf.d
for f in mirror-ops-web.conf mirror-ops-api.conf; do
  [ -f "${f}.disabled" ] && mv "${f}.disabled" "$f"
done
rm -f _mirror-ops-bootstrap.conf
docker exec proxy-nginx nginx -s reload
```

### 13.4 — Tester

```bash
curl -I https://mirror-ops.vylantic.com
curl -I https://api.mirror-ops.vylantic.com/health
```

---

# 14. Premier déploiement

```bash
cd /var/www/mirror-ops

# Valider le compose
docker compose -f docker-compose.prod.yml config

# Build + démarrage
docker compose -f docker-compose.prod.yml up -d --build

# Logs
docker compose -f docker-compose.prod.yml logs -f
```

Le démarrage de l'API crée les tables et journalise le mode YouCam. Trois lignes
à lire immédiatement :

```bash
docker compose -f docker-compose.prod.yml logs api | grep -E "startup|youcam|garment"
```

- `youcam_mock_mode_active` → les aperçus porteront « simulated »
- `youcam_live_without_credentials` → clé absente
- `garment_catalog_is_placeholder` → un essayage réel échouera

---

# 15. Vérifications

```bash
docker ps | grep mirror-ops

# Santé
curl -s https://api.mirror-ops.vylantic.com/api/v1/health/dependencies | jq
```

Réponse attendue en production :

```json
{
  "api": "ok",
  "database": "ok",
  "storage": "ok",
  "youcam": "configured",
  "youcam_mode": "live",
  "garments": "ok"
}
```

| Valeur | Signification | Action |
|---|---|---|
| `"youcam": "mock_mode"` | aperçus simulés | renseigner `YOUCAM_MODE=live` |
| `"youcam": "missing_credentials"` | clé absente | renseigner `YOUCAM_API_KEY` |
| `"youcam": "missing_dependency"` | `cryptography` absent | reconstruire l'image |
| `"garments": "placeholder"` | catalogue non remplacé | voir §11.5 |

### L'audit de bout en bout

Le dépôt contient un contrôle du système **assemblé** — sept écrans, données en
entrée et en sortie, 38 invariants :

```bash
docker compose -f docker-compose.prod.yml exec api \
  python scripts/audit_journey.py --base-url https://api.mirror-ops.vylantic.com
```

`FAIL` bloque, `WARN` signale ce qui limitera l'usage. À lancer après chaque
déploiement.

---

# 16. Backups automatiques

### `/usr/local/bin/backup-mirror-ops.sh`

```bash
#!/bin/bash
set -euo pipefail

BACKUP_ROOT=/var/backups/mirror-ops
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p "$BACKUP_ROOT/$TS"

cd /var/www/mirror-ops

# PostgreSQL
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U mirror mirror_ops | gzip > "$BACKUP_ROOT/$TS/postgres.sql.gz"

# Vêtements importés — la seule donnée irremplaçable du volume.
# Les médias de session expirent en deux heures : les sauvegarder n'a pas de sens.
docker run --rm -v mirror-ops_mirror_garments:/data -v "$BACKUP_ROOT/$TS":/backup \
  alpine tar -czf /backup/garments.tar.gz -C /data . 2>/dev/null || true

# Rotation 7 jours
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +7 -exec rm -rf {} \;

echo "✅ Backup MIRROR OPS : $BACKUP_ROOT/$TS"
```

```bash
chmod +x /usr/local/bin/backup-mirror-ops.sh
crontab -e
# 0 3 * * * /usr/local/bin/backup-mirror-ops.sh >> /var/log/backup-mirror-ops.log 2>&1
```

---

# 17. Nettoyage des médias expirés

Les sessions et leurs images expirent après deux heures. Le dépôt fournit le job :

```bash
crontab -e
# */15 * * * * cd /var/www/mirror-ops && docker compose -f docker-compose.prod.yml exec -T api python scripts/cleanup.py >> /var/log/mirror-ops-cleanup.log 2>&1
```

Sans lui, le volume `mirror_media` croît indéfiniment.

---

# 18. Déploiement continu

### `/usr/local/bin/deploy-mirror-ops.sh`

```bash
#!/bin/bash
set -euo pipefail

cd /var/www/mirror-ops

git pull origin main

# Le frontend doit être reconstruit : NEXT_PUBLIC_API_BASE_URL est compilée
# dans le bundle, un redémarrage ne suffirait pas.
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# Le schéma se met à jour au démarrage de l'API (colonnes additives).
sleep 10
curl -fsS https://api.mirror-ops.vylantic.com/api/v1/health/dependencies | jq

echo "✅ MIRROR OPS déployé."
```

```bash
chmod +x /usr/local/bin/deploy-mirror-ops.sh
```

---

# 19. Logs & monitoring

```bash
cd /var/www/mirror-ops
docker compose -f docker-compose.prod.yml logs -f          # tous
docker compose -f docker-compose.prod.yml logs -f api      # FastAPI
docker compose -f docker-compose.prod.yml logs -f web      # Next.js

# Nginx (via proxy)
docker exec proxy-nginx tail -f /var/log/nginx/mirror-ops-api-access.log

# Monitoring système
docker stats | grep mirror-ops
```

Les logs de l'API sont en JSON, avec `request_id`, latence et code d'erreur.
Aucune clé, aucun secret, aucune image brute n'y figure — la fonction
`sanitize()` s'en charge.

Événements qui méritent une alerte :

| Message | Signification |
|---|---|
| `skin_provider_degraded` | Skin AI indisponible ; le parcours continue sans lui |
| `vto_provider_failed` | essayage impossible — lire `garment_source` et `provider_code` |
| `garment_catalog_is_placeholder` | catalogue non remplacé au démarrage |
| `youcam_live_without_credentials` | configuration incomplète |

---

# 20. Optimisations production

### Swap

```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile
mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### PostgreSQL

La charge est faible : quelques lignes par session, aucune requête analytique.
Les réglages par défaut de `postgres:16-alpine` conviennent. Inutile d'ajuster
`shared_buffers` avant d'avoir mesuré.

### Cloudflare

Activer le proxy (orange cloud) pour le CDN, la protection DDoS et le masquage
d'IP. Mode SSL : Full (strict).

> Vérifier que le délai d'attente de Cloudflare (100 s sur le plan gratuit)
> reste supérieur à celui d'un essayage YouCam (13–15 s en pratique, 90 s au
> pire). C'est le cas, mais de peu en cas d'incident chez le provider.

---

# 21. Checklist sécurité

- [ ] Firewall UFW activé (22/80/443 uniquement)
- [ ] SSH root par mot de passe désactivé
- [ ] fail2ban actif
- [ ] `POSTGRES_PASSWORD` et `MEDIA_SIGNING_SECRET` régénérés (`openssl rand -base64 32`)
- [ ] `.env` en `chmod 600`
- [ ] `APP_ENV=production` — sinon les erreurs exposent les diagnostics provider
- [ ] `CORS_ORIGINS` limité au domaine du frontend
- [ ] Clé YouCam **uniquement** côté serveur, jamais dans une variable `NEXT_PUBLIC_*`
- [ ] Cloudflare devant le droplet
- [ ] Backups quotidiens vérifiés
- [ ] Cron de nettoyage actif

---

# 22. Dépannage

### Les images ne s'affichent pas, alors que l'API répond 201

```bash
docker compose -f docker-compose.prod.yml exec api env | grep PUBLIC_BASE_URL
```

`PUBLIC_BASE_URL` fabrique les URLs média signées. Si elle ne correspond pas à
l'adresse publique de l'API, les liens sont générés vers une adresse
injoignable — panne silencieuse, la plus coûteuse à diagnostiquer.

### Upload de photo qui échoue en 413

`client_max_body_size 12M;` est-il bien présent dans le vhost API ? Nginx coupe
à 1 Mo par défaut.

### `error_editing_failed` sur un essayage

```bash
curl -s https://api.mirror-ops.vylantic.com/api/v1/garments | jq '.garments[] | {id, placeholder}'
```

`"placeholder": true` → le visuel est un aplat généré, le try-on n'a rien à
segmenter. Voir §11.5. Le champ `garment_source` de l'erreur dit par ailleurs si
la pièce venait du catalogue ou d'un import utilisateur.

### 502 Bad Gateway

```bash
docker exec proxy-nginx nginx -t
docker network inspect proxy-network | grep mirror-ops
# mirror-ops-api et mirror-ops-web doivent être dans proxy-network
```

### Le frontend appelle la mauvaise API

`NEXT_PUBLIC_API_BASE_URL` est compilée dans le bundle. Corriger `.env` puis :

```bash
docker compose -f docker-compose.prod.yml build web
docker compose -f docker-compose.prod.yml up -d web
```

### « Take photo » absent de l'écran

`getUserMedia` exige un contexte sécurisé. Vérifier que le domaine est bien
servi en HTTPS, sans redirection cassée.

### Certbot refuse

```bash
curl http://mirror-ops.vylantic.com/.well-known/acme-challenge/test
# Doit renvoyer 404 (pas 502) → Nginx joignable
dig +short mirror-ops.vylantic.com
```

### Disque saturé

```bash
docker system prune -af
ncdu /var
journalctl --vacuum-time=7d
```

Vérifier aussi que le cron de nettoyage tourne (§17) : sans lui, les médias de
session s'accumulent.

---

# 23. Architecture finale

```
                   Internet
                       │
                  Cloudflare DNS
                       │
                   Port 80/443
                       ▼
            ┌────────────────────┐
            │   proxy-nginx      │  (proxy-network)
            └────────────────────┘
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
      mirror-ops-web        mirror-ops-api ───────► YouCam API
        (Next.js)              (FastAPI)            (Skin AI + VTO)
                                   │
                                   ▼
                       ┌───────────────────────┐
                       │ mirror-ops-postgres   │
                       │ volumes : media,      │
                       │           garments    │
                       └───────────────────────┘
                        (mirror-ops-network)
```

MIRROR OPS est en production sur `mirror-ops.vylantic.com`.

---

*Fin du guide MIRROR OPS.*
