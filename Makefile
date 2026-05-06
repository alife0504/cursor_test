# TradingAgents-TW Makefile (v0.3.0 - Phase 1 最小版)
# 後續 Phase 會擴充（up/down/init-db/seed/backfill/backend-dev/frontend-dev/...）

.PHONY: help lint format test secrets-scan precommit clean

help:  ## 顯示可用 target
	@echo "TradingAgents-TW Makefile (v0.3.0 - Phase 1)"
	@echo ""
	@echo "可用 target："
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "後續 Phase 會新增："
	@echo "  P2: make up / down / logs / restart / ps（Docker 服務）"
	@echo "  P3: make backend-dev / backend-image"
	@echo "  P4: make init-db / migration-up / migration-down"
	@echo "  P7: make seed-stocks / seed-admin / backfill / verify-data / up-workers"
	@echo "  P15: make frontend-dev / frontend-build / frontend-test"
	@echo "  P19: make prod-up / prod-down / backup / restore / verify-backup"

lint:  ## 跑 ruff 檢查
	cd backend && uv run ruff check app/ tests/

format:  ## 跑 ruff format
	cd backend && uv run ruff format app/ tests/

test:  ## 跑 pytest
	cd backend && uv run pytest

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
