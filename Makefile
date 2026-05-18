# TradingAgents-TW Makefile (v0.3.0 - Phase 3)
# 後續 Phase 會擴充（init-db/seed/backfill/frontend-dev/...）

.PHONY: help lint format test secrets-scan precommit clean \
        up down logs restart ps psql redis-cli qdrant-status \
        services-reset backend-dev backend-image backend-shell \
        backend-logs init-db migration-up migration-down migration-new \
        migration-status migration-history migration-redo \
        up-workers workers-logs workers-restart down-workers \
        seed-stocks seed-admin backfill verify-data celery-shell \
        celery-purge celery-inspect \
        frontend-install frontend-dev frontend-build frontend-start \
        frontend-test frontend-typecheck frontend-lint frontend-e2e \
        frontend-image frontend-up frontend-down \
        images-build bandit trivy-scan

help:  ## 顯示可用 target
	@echo "TradingAgents-TW Makefile (v0.3.0 - Phase 2)"
	@echo ""
	@echo "可用 target："
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "後續 Phase 會新增："
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

# ── Backend FastAPI（P3 新增） ──────────────────────

backend-dev:  ## 跑 backend dev mode（uvicorn --reload，host=0.0.0.0:8000）
	cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

backend-image:  ## Build backend Docker image（dev tag）
	docker build -t tradingagents-backend:dev -f backend/Dockerfile .

backend-shell:  ## 進 backend container shell（必先 make up）
	docker compose exec backend bash

backend-logs:  ## 跟 backend container log
	docker compose logs -f backend

# ── DB Migration / Init（P4 新增） ─────────────────

init-db:  ## 一次性：alembic upgrade head + Qdrant collections + admin 帳號
	cd backend && uv run python ../data-pipeline/scripts/init_db.py

migration-up:  ## alembic upgrade head
	cd backend && uv run alembic upgrade head

migration-down:  ## alembic downgrade -1
	cd backend && uv run alembic downgrade -1

migration-new:  ## 新增空白 migration（用 MSG="描述" 傳訊息）
	cd backend && uv run alembic revision -m "$(MSG)"

migration-status:  ## 看目前 migration version
	cd backend && uv run alembic current

migration-history:  ## 看 migration 歷史
	cd backend && uv run alembic history

migration-redo:  ## downgrade base + upgrade head（測試雙向用）
	cd backend && uv run alembic downgrade base && uv run alembic upgrade head

# ── Celery / Workers / Bootstrap（P7 新增） ───────

up-workers:  ## 啟動 celery_worker + celery_beat（已 make up 三服務後）
	docker compose up -d celery_worker celery_beat
	@echo ""
	@echo "等待 worker / beat 起來..."
	@sleep 8 && docker compose ps celery_worker celery_beat

down-workers:  ## 停止 worker + beat（保留 broker / DB）
	docker compose stop celery_worker celery_beat

workers-logs:  ## 跟 worker + beat log
	docker compose logs -f celery_worker celery_beat

workers-restart:  ## 重啟 worker + beat
	docker compose restart celery_worker celery_beat

celery-shell:  ## 進 celery worker container shell
	docker compose exec celery_worker bash

celery-purge:  ## 清空 celery broker queue（謹慎使用）
	docker compose exec celery_worker uv run celery -A app.workers.celery_app purge -f

celery-inspect:  ## 看 celery worker 註冊的 task / 佇列狀態
	docker compose exec celery_worker uv run celery -A app.workers.celery_app inspect registered

seed-stocks:  ## 抓 TWSE/TPEX/US 股票寫 stock_list（PLAN 13.1 step 3）
	cd backend && uv run python ../data-pipeline/scripts/seed_stock_list.py

seed-admin:  ## 建立第一個 admin 帳號（從 .env 讀 ADMIN_EMAIL/ADMIN_INITIAL_PASSWORD）
	cd backend && uv run python ../data-pipeline/scripts/seed_users.py

backfill:  ## 回填 OHLCV：make backfill ARGS="--region TW --symbol 2330 --years 1"
	cd backend && uv run python ../data-pipeline/scripts/backfill.py $(ARGS)

verify-data:  ## 驗證資料完整性（stock_list / stock_prices / audit_logs）
	cd backend && uv run python ../data-pipeline/scripts/verify_data.py

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

# ── Frontend Next.js（P15 新增） ───────────────────

frontend-install:  ## frontend: npm ci
	cd frontend && npm ci

frontend-dev:  ## frontend: dev mode（http://localhost:3000）
	cd frontend && npm run dev

frontend-build:  ## frontend: production build
	cd frontend && npm run build

frontend-start:  ## frontend: 啟動已 build 的 production server
	cd frontend && npm start

frontend-test:  ## frontend: vitest 單元測試
	cd frontend && npm test

frontend-typecheck:  ## frontend: tsc --noEmit
	cd frontend && npx tsc --noEmit

frontend-lint:  ## frontend: next lint
	cd frontend && npm run lint

frontend-e2e:  ## frontend: playwright(需先 dev 起來)
	cd frontend && npm run e2e

frontend-image:  ## Build frontend Docker image
	docker build -t tradingagents-frontend:dev ./frontend

frontend-up:  ## docker compose 啟動 frontend service(profile)
	docker compose --profile frontend up -d frontend

frontend-down:  ## docker compose 停止 frontend service
	docker compose --profile frontend stop frontend

# ── Phase 18: 安全掃描相關 ─────────────────────

images-build:  ## P18: build backend + frontend image 並 tag :latest（給 Trivy 掃描用）
	docker build -t tradingagents-backend:latest -f backend/Dockerfile .
	docker build -t tradingagents-frontend:latest -f frontend/Dockerfile ./frontend

bandit:  ## P18: 對 backend/app/ 跑 bandit static analysis
	cd backend && uv run bandit -r app/ -c .bandit -f json -o /tmp/bandit_report.json
	@echo "→ HIGH severity 必須為 0：" && python -c "import json,sys; d=json.load(open(r'/tmp/bandit_report.json')); h=[r for r in d['results'] if r['issue_severity']=='HIGH']; print(f'  HIGH={len(h)}'); sys.exit(0 if len(h)==0 else 1)"

trivy-scan: images-build  ## P18: 對 backend + frontend image 跑 Trivy HIGH+CRITICAL（用 docker 跑 trivy）
	# 用容器化 trivy 避免 host 必須裝。--ignore-unfixed: 上游無 patch 的不擋
	# 注意：需 docker engine 起來；Windows / Docker Desktop 直接掛 //var/run/docker.sock
	docker run --rm \
	  -v //var/run/docker.sock:/var/run/docker.sock \
	  -v $(HOME)/.cache/trivy:/root/.cache/trivy \
	  aquasec/trivy:latest image \
	    --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 \
	    tradingagents-backend:latest
	docker run --rm \
	  -v //var/run/docker.sock:/var/run/docker.sock \
	  -v $(HOME)/.cache/trivy:/root/.cache/trivy \
	  aquasec/trivy:latest image \
	    --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 \
	    tradingagents-frontend:latest
