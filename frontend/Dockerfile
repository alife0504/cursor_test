# syntax=docker/dockerfile:1.7
# Phase 15:Next.js 14.2 frontend(production)
# 四階段建置:deps(全) → prod-deps(僅正式) → builder → runner,uid 1000 非 root

# ──────────────── deps（完整依賴，build 需 devDependencies）────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

# ──────────────── prod-deps（僅正式依賴，runner 用）────────────────
# 正式映像只需 next 執行期依賴；剔除 vitest/vite/esbuild/playwright/eslint 等 devDependencies，
# 縮小攻擊面（這些 dev 套件的 HIGH/CRITICAL CVE 會被 Trivy 標紅）與映像體積。
FROM node:20-alpine AS prod-deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev --no-audit --no-fund

# ──────────────── builder ────────────────
FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
# ⚠️ Next.js rewrites() 在 build 時求值並烤進 routes-manifest，執行期改 env 無效。
# 故後端內網位址必須在 build 時就給：stack-up 走 compose 內網 → http://backend:8000。
# prod 可用 build arg 覆寫（如指向 nginx 內部位址）。
ARG BACKEND_INTERNAL_URL=http://backend:8000
ENV BACKEND_INTERNAL_URL=${BACKEND_INTERNAL_URL}
# ⚠️ NEXT_PUBLIC_* 於 build 時 inline 進 client bundle（執行期改 env 無效）。WS/API/時區位址
# 必須在 build 時給，否則 useWebSocket 退化推導，prod（nginx 後、port 8000 不對外）連不到 WS。
# prod 應傳 NEXT_PUBLIC_WS_URL=wss://<PUBLIC_HOST>（不帶 :8000，由 nginx 於 443 反代 /api/v1/ws）。
ARG NEXT_PUBLIC_WS_URL
ARG NEXT_PUBLIC_API_BASE_URL=/api/v1
ARG NEXT_PUBLIC_DEFAULT_TIMEZONE=Asia/Taipei
ENV NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL} \
    NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_PUBLIC_DEFAULT_TIMEZONE=${NEXT_PUBLIC_DEFAULT_TIMEZONE}
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

# Next.js 14.2 standalone-less:複製必要產物；node_modules 改用「僅正式依賴」的 prod-deps。
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=prod-deps /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

# 非 root user：node:20-alpine 內建 node(uid/gid 1000)，直接沿用
# （原本另建 nextjs:1000 會與內建 node 的 gid 1000 衝突 → "gid 1000 in use"）。
# chown /app 讓 next start 能寫 .next/cache。
RUN chown -R node:node /app
USER node

EXPOSE 3000
CMD ["npm", "start"]
