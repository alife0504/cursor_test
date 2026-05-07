# TradingAgents-TW Makefile (v0.3.0 - Phase 2)
# 後續 Phase 會擴充（init-db/seed/backfill/backend-dev/frontend-dev/...）

.PHONY: help lint format test secrets-scan precommit clean \
        up down logs restart ps psql redis-cli qdrant-status \
        services-reset

help:  ## 顯示可用 target
	@echo "TradingAgents-TW Makefile (v0.3.0 - Phase 2)"
	@echo ""
	@echo "可用 target："
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "後續 Phase 會新增："
	@echo "  P3: make backend-dev / backend-image"
	@echo "  P4: make init-db / migration-up / migration-down"
	@echo "  P7: make seed-stocks / seed-admin / backfill / verify-data / up-workers"
	@echo "  P15: make frontend-dev / frontend-build / frontend-test"
	@echo "  P19: make prod-up / prod-down / backup / restore / verify-backup"

# ── Docker 服務（P2 新增） ──────────────────────────

up:  ## 啟動 Docker 三服務（timescaledb/redis/qdrant）
	docker compose up -d
	@echo ""
	@echo "等待 healthcheck（最多 60 秒）..."
	@sleep 5 && docker compose ps

down:  ## 停止三服務（保留 volume，資料不會清）
	docker compose down

down-volumes:  ## 停止 + 砍 volume（會清資料！）
	@echo "⚠️  即將砍除所有 volume，資料會清空！按 Ctrl+C 中止，或 5 秒後繼續..."
	@sleep 5
	docker compose down -v

logs:  ## 跟著看 log
	docker compose logs -f

logs-tail:  ## 看最近 100 行 log
	docker compose logs --tail=100

restart:  ## 重啟三服務
	docker compose restart

ps:  ## 看服務狀態
	docker compose ps

psql:  ## 用 superuser 進 psql（互動）
	docker compose exec timescaledb psql -U postgres -d tradingagents_tw

redis-cli:  ## 進 redis-cli（互動）
	@docker compose exec redis sh -c 'redis-cli -a $$REDIS_PASSWORD'

qdrant-status:  ## Qdrant 健康檢查
	@curl -sf http://localhost:6333/healthz && echo " ✓ Qdrant healthy"
	@curl -s -H "api-key: $$(grep ^QDRANT_API_KEY= .env | cut -d= -f2)" http://localhost:6333/collections | head -3

services-reset:  ## 完全重設三服務（停止 + 砍 volume + 重啟，會清資料）
	@echo "⚠️  即將完全重設服務（資料會清空）！按 Ctrl+C 中止，或 5 秒後繼續..."
	@sleep 5
	docker compose down -v
	docker compose up -d
	@sleep 10 && docker compose ps

# ── 程式碼品質（P1 已有） ───────────────────────────

lint:  ## 跑 ruff 檢查
	cd backend && uv run ruff check app/ tests/

format:  ## 跑 ruff format
	cd backend && uv run ruff format app/ tests/

test:  ## 跑 pytest
	cd backend && uv run pytest

test-integration:  ## 跑 integration tests（需 docker compose up）
	cd backend && uv run pytest -m integration -v

secrets-scan:  ## 偵測 secret 是否洩漏
	cd backend && uv run detect-secrets scan --baseline ../.secrets.baseline

precommit:  ## 跑所有 pre-commit hooks
	cd backend && uv run pre-commit run --all-files --config ../.pre-commit-config.yaml

clean:  ## 清快取
	find . -type d -name "__pycache__" -not -path "./legacy/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -not -path "./legacy/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -not -path "./legacy/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -not -path "./legacy/*" -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cache cleared"
