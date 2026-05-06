#!/bin/bash
# scripts/health_checks/phase_01.sh
# Phase 1 健康檢查：驗證原版遷移 + 新骨架 + 工程規範完整
# 後續 Phase 開頭跑此 script 確保 P1 結果還能跑

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Phase 01 健康檢查 ==="
echo "PROJECT_ROOT: $PROJECT_ROOT"

# 1. legacy 隔離
test -d legacy/tradingagents || { echo "❌ legacy/tradingagents 不存在"; exit 1; }
test -d legacy/cli           || { echo "❌ legacy/cli 不存在"; exit 1; }
test ! -e tradingagents      || { echo "❌ 根目錄不該有 tradingagents/"; exit 1; }
test ! -e cli                || { echo "❌ 根目錄不該有 cli/"; exit 1; }
test -f legacy/README.md     || { echo "❌ legacy/README.md 缺"; exit 1; }
echo "✓ legacy 隔離 OK"

# 2. backend 骨架
for d in backend/app/core backend/app/api/v1 backend/app/services \
         backend/app/data_sources/tw backend/app/data_sources/us \
         backend/app/data_sources/base backend/app/repos backend/app/schemas \
         backend/app/agents/analysts backend/app/agents/researchers \
         backend/app/agents/managers backend/app/agents/tools/tw \
         backend/app/agents/tools/us backend/app/llm \
         backend/app/workers backend/app/notifications backend/app/exports \
         backend/migrations backend/scripts \
         backend/tests/unit backend/tests/integration backend/tests/security; do
  test -d "$d" || { echo "❌ 缺少目錄：$d"; exit 1; }
done
echo "✓ backend 骨架 OK"

# 3. frontend / data-pipeline / docker 骨架
for d in frontend/src/app frontend/src/components frontend/src/lib \
         frontend/src/store frontend/src/hooks frontend/src/i18n \
         frontend/tests/unit frontend/tests/e2e \
         data-pipeline/schemas data-pipeline/scripts \
         docker/timescaledb docker/nginx/certs docker/backups docker/playwright; do
  test -d "$d" || { echo "❌ 缺少目錄：$d"; exit 1; }
done
echo "✓ frontend / data-pipeline / docker 骨架 OK"

# 4. 工程規範文件
for f in docs/engineering-standards.md docs/setup.md docs/contributing.md \
         docs/phase_progress.md; do
  test -f "$f" || { echo "❌ 缺少文件：$f"; exit 1; }
done
echo "✓ 工程規範文件 OK"

# 5. 設定檔
test -f .pre-commit-config.yaml || { echo "❌ .pre-commit-config.yaml 缺"; exit 1; }
test -f .secrets.baseline       || { echo "❌ .secrets.baseline 缺"; exit 1; }
test -f .gitignore              || { echo "❌ .gitignore 缺"; exit 1; }
test -f .env.example            || { echo "❌ .env.example 缺"; exit 1; }
test -f .vscode/settings.json   || { echo "❌ .vscode/settings.json 缺"; exit 1; }
test -f .github/workflows/ci.yml       || { echo "❌ ci.yml 缺"; exit 1; }
test -f .github/workflows/security.yml || { echo "❌ security.yml 缺"; exit 1; }
test -f Makefile                || { echo "❌ Makefile 缺"; exit 1; }
echo "✓ 設定檔齊全 OK"

# 6. backend 套件管理
test -f backend/pyproject.toml || { echo "❌ backend/pyproject.toml 缺"; exit 1; }
test -f backend/uv.lock        || { echo "❌ backend/uv.lock 缺"; exit 1; }
test -f backend/Dockerfile     || { echo "❌ backend/Dockerfile 缺"; exit 1; }
echo "✓ backend 套件管理檔 OK"

# 7. .env.example 必要欄位
for var in APP_ENV ADMIN_EMAIL SECRET_KEY DATA_ENCRYPTION_KEY \
           POSTGRES_DB REDIS_HOST QDRANT_HOST GOOGLE_API_KEY \
           LLM_DEFAULT_PROVIDER FINMIND_TOKEN ALPHA_VANTAGE_API_KEY; do
  grep -q "^${var}=" .env.example || { echo "❌ .env.example 缺 ${var}"; exit 1; }
done
echo "✓ .env.example 必要欄位齊全 OK"

# 8. ruff 檢查通過
cd backend
uv run ruff check app/ tests/ > /dev/null 2>&1 || {
  echo "❌ ruff check 失敗"; exit 1;
}
echo "✓ ruff check 通過"

# 9. pytest collect ≥ 5
COLLECTED=$(uv run pytest --collect-only -q 2>&1 | tail -1 | grep -oE '[0-9]+' | head -1)
if [ -z "$COLLECTED" ] || [ "$COLLECTED" -lt 5 ]; then
  echo "❌ pytest collect = $COLLECTED < 5"; exit 1;
fi
echo "✓ pytest 已 collect $COLLECTED tests"

# 10. detect-secrets baseline 通過
uv run detect-secrets scan --baseline ../.secrets.baseline > /dev/null 2>&1 || {
  echo "❌ detect-secrets 偵測到 baseline 外的 secret"; exit 1;
}
echo "✓ detect-secrets 通過"

cd "$PROJECT_ROOT"
echo ""
echo "✅ Phase 01 健康檢查全部通過"
