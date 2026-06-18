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
# ⚠️ Next.js rewrites() 在 build 時求值並烤進 routes-manifest，執行期改 env 無效。
# 故後端內網位址必須在 build 時就給：stack-up 走 compose 內網 → http://backend:8000。
# prod 可用 build arg 覆寫（如指向 nginx 內部位址）。
ARG BACKEND_INTERNAL_URL=http://backend:8000
ENV BACKEND_INTERNAL_URL=${BACKEND_INTERNAL_URL}
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

# 非 root user：node:20-alpine 內建 node(uid/gid 1000)，直接沿用
# （原本另建 nextjs:1000 會與內建 node 的 gid 1000 衝突 → "gid 1000 in use"）。
# chown /app 讓 next start 能寫 .next/cache。
RUN chown -R node:node /app
USER node

EXPOSE 3000
CMD ["npm", "start"]
