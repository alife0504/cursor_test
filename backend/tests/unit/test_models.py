"""ORM model 單元測試（不依賴 DB）。

驗證 model 定義層級的 schema 正確性：
- 型別（Numeric / JSONB / UUID / DateTime）
- 預設值（version=1, resolved=false）
- 主鍵 / 唯一鍵 / FK
- Helper（IdempotencyKey TTL 計算）
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.models import (
    IDEMPOTENCY_TTL_HOURS,
    AnalysisReport,
    AuditLog,
    CeleryDeadLetter,
    IdempotencyKey,
    LLMUsage,
    NotificationLog,
    PendingOrder,
    StockPrice,
    User,
    UserWatchlist,
)

pytestmark = pytest.mark.unit


def _col(model_cls, name):  # type: ignore[no-untyped-def]
    """取 model 的 Column 物件（透過 __table__）。"""
    return model_cls.__table__.columns[name]


def test_user_model_decimal_field_type() -> None:
    """User 沒有大金額欄位，但驗證 ORM 對 Numeric 型別正確識別。

    用 PendingOrder.target_price 作為「大金額用 Numeric」的代表。
    """
    col = _col(PendingOrder, "target_price")
    assert isinstance(col.type, Numeric), f"target_price 應為 Numeric，實為 {type(col.type)}"
    assert col.type.precision == 20
    assert col.type.scale == 6


def test_audit_log_immutable_fields() -> None:
    """AuditLog 應有 prev_hash + entry_hash + timestamp 欄位，且 entry_hash 為 String(64)。"""
    cols = AuditLog.__table__.columns
    for required in ("id", "timestamp", "actor_id", "action", "details", "prev_hash", "entry_hash"):
        assert required in cols, f"AuditLog 缺欄位：{required}"
    # entry_hash 為 String 且 length 64（sha256 hex）
    assert cols["entry_hash"].type.length == 64
    assert cols["prev_hash"].type.length == 64


def test_analysis_report_version_default_1() -> None:
    """AnalysisReport.version 預設為 1（樂觀鎖起始值）。"""
    col = _col(AnalysisReport, "version")
    assert isinstance(col.type, Integer)
    assert col.server_default is not None
    # server_default 是 sa.DefaultClause；其 arg 應為 "1"
    assert "1" in str(col.server_default.arg)


def test_pending_order_status_enum() -> None:
    """PendingOrder.status 應為 String 並有 CHECK constraint。"""
    col = _col(PendingOrder, "status")
    # short_enum() 是 native_enum=False，內部是 VARCHAR + CHECK constraint
    # 此處檢查 type 為 Enum 或 String（兩者都 OK）
    type_name = type(col.type).__name__
    assert type_name in ("Enum", "String"), f"status type unexpected: {type_name}"

    # CHECK constraint 存在
    check_names = [
        c.name
        for c in PendingOrder.__table__.constraints
        if c.__class__.__name__ == "CheckConstraint"
    ]
    assert any("status" in (n or "") for n in check_names), (
        f"PendingOrder 缺 status CHECK constraint，現有：{check_names}"
    )


def test_stock_price_composite_pk() -> None:
    """StockPrice 主鍵應為 (symbol, date) 複合鍵。"""
    pk_cols = [c.name for c in StockPrice.__table__.primary_key.columns]
    assert pk_cols == ["symbol", "date"], f"預期 ['symbol', 'date']，實為 {pk_cols}"


def test_notification_log_jsonb_payload() -> None:
    """NotificationLog.payload 應為 JSONB。"""
    col = _col(NotificationLog, "payload")
    assert isinstance(col.type, JSONB), f"payload 應為 JSONB，實為 {type(col.type)}"
    assert col.nullable is False


def test_user_watchlist_unique_constraint() -> None:
    """UserWatchlist 應有 UNIQUE(user_id, symbol, market)。"""
    uq = [
        c for c in UserWatchlist.__table__.constraints if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert uq, "UserWatchlist 缺 UniqueConstraint"
    col_sets = [tuple(sorted(c.name for c in u.columns)) for u in uq]
    assert (
        "market",
        "symbol",
        "user_id",
    ) in col_sets, f"預期 UNIQUE(user_id, symbol, market)，現有 {col_sets}"


def test_llm_usage_cost_decimal_precision() -> None:
    """LLMUsage.cost_usd 應為 Numeric(12, 6) — 足夠表達小金額 + 大累積。"""
    col = _col(LLMUsage, "cost_usd")
    assert isinstance(col.type, Numeric)
    assert col.type.precision == 12
    assert col.type.scale == 6


def test_idempotency_key_ttl_calculated() -> None:
    """IdempotencyKey.calc_default_expires_at() 應回未來 24h 內。"""
    assert IDEMPOTENCY_TTL_HOURS == 24
    now = datetime.now(UTC)
    expires = IdempotencyKey.calc_default_expires_at()
    delta = expires - now
    # 預設 23.99 ~ 24.01 小時間
    assert 23.9 < delta.total_seconds() / 3600 < 24.1, (
        f"TTL 不對：{delta.total_seconds() / 3600} hours"
    )


def test_celery_dead_letter_resolved_default_false() -> None:
    """CeleryDeadLetter.resolved 預設應為 false。"""
    col = _col(CeleryDeadLetter, "resolved")
    assert isinstance(col.type, Boolean)
    assert col.server_default is not None
    assert "false" in str(col.server_default.arg).lower()


def test_user_email_unique_constraint() -> None:
    """User.email 應 unique（PLAN 19.1 認證授權）。"""
    cols = User.__table__.columns
    assert "email" in cols
    assert cols["email"].unique or any(
        c.__class__.__name__ == "UniqueConstraint" and "email" in [col.name for col in c.columns]
        for c in User.__table__.constraints
    )


def test_decimal_precision_user_settings() -> None:
    """確保 ORM 對應 Python Decimal（不是 float）。"""
    # 用 LLMMonthlyQuota.budget_usd 驗證
    from app.models import LLMMonthlyQuota

    col = LLMMonthlyQuota.__table__.columns["budget_usd"]
    assert isinstance(col.type, Numeric)
    # 跑 .python_type 應為 Decimal
    assert col.type.python_type is Decimal


def test_audit_log_table_has_correct_pk() -> None:
    """AuditLog 應為 (id, timestamp) 複合 PK（hypertable 要求）。"""
    pk_cols = [c.name for c in AuditLog.__table__.primary_key.columns]
    assert pk_cols == ["id", "timestamp"], f"預期 ['id', 'timestamp']，實為 {pk_cols}"


def test_datetime_columns_are_timezone_aware() -> None:
    """所有 timestamp 欄位應該帶 timezone（PLAN 15.5 UTC 儲存）。"""
    sample_columns = [
        (User, "created_at"),
        (AnalysisReport, "created_at"),
        (PendingOrder, "expires_at"),
        (AuditLog, "timestamp"),
        (NotificationLog, "sent_at"),
    ]
    for model_cls, col_name in sample_columns:
        col = _col(model_cls, col_name)
        assert isinstance(col.type, DateTime), (
            f"{model_cls.__name__}.{col_name} 應為 DateTime，實為 {type(col.type)}"
        )
        assert col.type.timezone is True, f"{model_cls.__name__}.{col_name} 應 timezone=True"
