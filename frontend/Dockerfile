# syntax=docker/dockerfile:1.7
# Phase 15:Next.js 14.2 frontend(production)
# 三階段建置:deps → builder → runner,uid 1000 非 root

# ──────────────── deps ────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

# ──────────────── builder ────────────────
FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ──────────────── runner ────────────────
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Next.js 14.2 standalone-less:複製必要產物
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

# 非 root user
RUN addgroup -g 1000 nextjs && adduser -u 1000 -G nextjs -s /bin/sh -D nextjs
USER nextjs

EXPOSE 3000
CMD ["npm", "start"]
