"""Security tests 共用 fixture — 直接 import integration conftest 的 fixture。

Phase 20 修正：原本只 import 部分 fixture，導致 test_owasp_top10 / test_secret_handling
等使用 login_helper / flush_rate_limit / seed_* 時 pytest 找不到 fixture 而 ERROR。
這裡補齊所有 security/ 下測試會用到的 fixture。
"""

from __future__ import annotations

# 把上層 integration conftest 的 fixture 全部繼承過來（auth_client, make_test_user, ...）
# 用 sys.path 改不漂亮，這裡用 pytest 慣例：security/ 內的 test 也可用 integration/conftest.py 的 fixture
# 因為 pytest 會沿 directory tree 往上找 conftest.py。
# 但 tests/security/ 與 tests/integration/ 平行，找不到對方。
#
# 解法：直接從 integration/conftest 引入需要的 fixture。
import pytest

from tests.integration.conftest import (  # type: ignore[import-not-found]
    _flush_auth_redis_dbs,
    _skip_if_docker_down,
    auth_app,
    auth_client,
    db_session_maker,
    env_vars,
    flush_rate_limit,
    login_helper,
    make_test_user,
    pg_db,
    pg_host,
    pg_port,
    qdrant_host,
    qdrant_port,
    redis_host,
    redis_port,
    seed_analysis,
    seed_ohlcv,
    seed_pending_order,
    seed_stocks,
)

# 抑制 unused import warning（pytest 透過名稱找 fixture）
_ = (
    _flush_auth_redis_dbs,
    _skip_if_docker_down,
    auth_app,
    auth_client,
    db_session_maker,
    env_vars,
    flush_rate_limit,
    login_helper,
    make_test_user,
    pg_db,
    pg_host,
    pg_port,
    qdrant_host,
    qdrant_port,
    redis_host,
    redis_port,
    seed_analysis,
    seed_ohlcv,
    seed_pending_order,
    seed_stocks,
    pytest,
)
