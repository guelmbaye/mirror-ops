# ---------------------------------------------------------------- dépendances
FROM node:20-alpine AS deps
WORKDIR /srv

COPY package.json package-lock.json* ./
COPY apps/web/package.json ./apps/web/
COPY packages/types/package.json ./packages/types/
COPY packages/config/package.json ./packages/config/
RUN npm install --no-audit --no-fund

# --------------------------------------------------------------------- build
FROM node:20-alpine AS builder
WORKDIR /srv

COPY --from=deps /srv/node_modules ./node_modules
COPY package.json ./
COPY packages ./packages
COPY apps/web ./apps/web

# L'URL de l'API est figée dans le bundle client : elle doit être connue au build.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
# Origine publique du site : sert a resoudre les URLs absolues des images
# sociales. Comme l'autre, elle est figee dans le bundle au moment du build.
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build --workspace @mirror-ops/web

# ------------------------------------------------------------------ exécution
FROM node:20-alpine AS runner
WORKDIR /srv

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000

RUN addgroup -g 10001 mirror && adduser -u 10001 -G mirror -S mirror

COPY --from=builder --chown=mirror:mirror /srv/apps/web/.next/standalone ./
COPY --from=builder --chown=mirror:mirror /srv/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=mirror:mirror /srv/apps/web/public ./apps/web/public

USER mirror
EXPOSE 3000

CMD ["node", "apps/web/server.js"]
