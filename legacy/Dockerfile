# Hardened Dockerfile for TradingAgents
#
# Security improvements over upstream:
# 1. Base image documented for digest pinning (see comment below)
# 2. System packages updated to patch CVEs at build time
# 3. pip upgraded to fix known pip CVEs
# 4. Non-root user with restricted home permissions (0700)
# 5. .env not copied into image (mount at runtime)
# 6. HEALTHCHECK added
# 7. Uses requirements.lock for reproducible builds
#
# To pin to specific digest in production:
#   docker pull python:3.12-slim
#   docker images --digests python
#   Replace FROM line with: FROM python:3.12-slim@sha256:<digest>

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip

WORKDIR /build
COPY pyproject.toml requirements.lock ./
COPY tradingagents ./tradingagents
COPY cli ./cli
COPY README.md LICENSE ./

RUN pip install --no-cache-dir -r requirements.lock && \
    pip install --no-cache-dir --no-deps .

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --shell /bin/bash appuser && \
    chmod 700 /home/appuser

USER appuser
WORKDIR /home/appuser/app

COPY --from=builder --chown=appuser:appuser /build/tradingagents ./tradingagents
COPY --from=builder --chown=appuser:appuser /build/cli ./cli
COPY --from=builder --chown=appuser:appuser /build/pyproject.toml ./

RUN mkdir -p /home/appuser/.tradingagents && \
    chmod 700 /home/appuser/.tradingagents

HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import tradingagents" || exit 1

ENTRYPOINT ["tradingagents"]
