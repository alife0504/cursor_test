# ============================================================================
# TradingAgents-TW Backend Dockerfile (v0.3.0 - Phase 3)
# ============================================================================
# Phase 升級時程：
#   P3：app 程式碼 + uvicorn + healthcheck（本檔）
#   P11：加 chromium + fonts-noto-cjk（Playwright PDF 匯出用）
#   P19：prod-ready（read_only fs、cap_drop ALL、最小 image）
# ============================================================================

FROM python:3.11-slim AS base

# 系統依賴（最小集合，後續 Phase 補）
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        # asyncpg / cryptography 編譯偶爾需要
        gcc \
        libpq-dev \
        # postgresql-client 給 wait-for-services.sh 的 pg_isready 用
        postgresql-client \
        # redis-cli + nc 給 wait-for-services.sh 用
        redis-tools \
        netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# 非 root user（uid 1000，依 PLAN 第 19.5 章安全規範）
RUN groupadd -g 1000 app && useradd -u 1000 -g app -m -s /bin/bash app

# 安裝 uv（從 Astral 官方 image 複製 binary，避免 pip install）
COPY --from=ghcr.io/astral-sh/uv:0.7.3 /uv /usr/local/bin/uv

WORKDIR /app

# 複製 pyproject.toml + uv.lock（先複製這兩個 → 利用 layer cache）
COPY backend/pyproject.toml backend/uv.lock /app/

# 同步依賴（frozen，依 uv.lock 嚴格）
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
RUN uv sync --frozen --no-dev

# 複製應用程式碼 + scripts（會 invalidate cache，故放在 deps 之後）
COPY backend/app /app/app
COPY backend/scripts /app/scripts

# 給 app user 權限
RUN chown -R app:app /app && chmod +x /app/scripts/wait-for-services.sh

USER app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=prod

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/live > /dev/null || exit 1

# wait-for-services.sh 會等 timescaledb / redis / qdrant ready 才啟動 uvicorn
CMD ["./scripts/wait-for-services.sh", \
     "uv", "run", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--no-access-log"]
