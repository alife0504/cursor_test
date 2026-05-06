# ============================================================================
# TradingAgents-TW Backend Dockerfile (v0.3.0 - Phase 1 雛形)
# ============================================================================
# Phase 升級時程：
#   P3：加 healthcheck（curl /health/live）+ wait-for-services.sh entrypoint
#   P11：加 chromium + fonts-noto-cjk（Playwright PDF 匯出用）
#   P19：prod-ready（read_only fs、cap_drop ALL、最小 image）
# ============================================================================

FROM python:3.11-slim AS base

# 系統依賴（最小集合，後續 Phase 補）
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        # 編譯 asyncpg / cryptography 偶爾要
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 非 root user（uid 1000，依第 19.5 章安全規範）
RUN groupadd -g 1000 app && useradd -u 1000 -g app -m -s /bin/bash app

# 安裝 uv（Astral）
COPY --from=ghcr.io/astral-sh/uv:0.7.3 /uv /usr/local/bin/uv

WORKDIR /app

# 複製 pyproject.toml + uv.lock（不複製程式碼，避免 cache invalidate）
COPY backend/pyproject.toml backend/uv.lock /app/

# 同步依賴（frozen，依 uv.lock 嚴格）
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
RUN uv sync --frozen --no-dev

# 給 app user 權限
RUN chown -R app:app /app

USER app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=prod

EXPOSE 8000

# Phase 1 階段：尚無 main.py，container 啟動會失敗。
# Phase 3 main.py 完成後才會升級為實際 CMD。
CMD ["python", "-c", "print('Phase 1 stub: backend image built OK; main.py 待 Phase 3 寫')"]
