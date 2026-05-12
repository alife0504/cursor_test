"""SQLAlchemy ORM models — Phase 4 baseline。

匯入順序遵循依賴關係：
  base → user → stock → 其他

import 此 module 會註冊所有 model 到 `Base.metadata`，方便 Alembic autogenerate。
"""

from __future__ import annotations

from app.models.analysis import (
    ANALYSIS_STATUS_VALUES,
    SIGNAL_VALUES,
    AnalysisReport,
    DebateMessage,
)
from app.models.audit import AuditLog
from app.models.base import Base, CreatedAtMixin, TimestampedMixin, metadata
from app.models.dlq import CeleryDeadLetter
from app.models.financials import STATEMENT_TYPE_VALUES, FinancialStatement
from app.models.idempotency import IDEMPOTENCY_TTL_HOURS, IdempotencyKey
from app.models.news import SENTIMENT_VALUES, Announcement, NewsMetadata
from app.models.notification import (
    NOTIFICATION_CHANNEL_VALUES,
    NOTIFICATION_STATUS_VALUES,
    NotificationLog,
    NotificationSetting,
)
from app.models.order import (
    ORDER_SIDE_VALUES,
    ORDER_STATUS_VALUES,
    PendingOrder,
    PortfolioPosition,
    TradeHistory,
)
from app.models.price import StockPrice
from app.models.quota import LLMMonthlyQuota, LLMUsage
from app.models.stock import MARKET_VALUES, StockInfo, StockList
from app.models.tw_specific import InstitutionalTrading, MarginTrading, MonthlyRevenue
from app.models.user import PasswordResetToken, User, UserRole, UserSession
from app.models.watchlist import UserWatchlist

__all__ = [
    "ANALYSIS_STATUS_VALUES",
    "IDEMPOTENCY_TTL_HOURS",
    "MARKET_VALUES",
    "NOTIFICATION_CHANNEL_VALUES",
    "NOTIFICATION_STATUS_VALUES",
    "ORDER_SIDE_VALUES",
    "ORDER_STATUS_VALUES",
    "SENTIMENT_VALUES",
    "SIGNAL_VALUES",
    "STATEMENT_TYPE_VALUES",
    "AnalysisReport",
    "Announcement",
    "AuditLog",
    "Base",
    "CeleryDeadLetter",
    "CreatedAtMixin",
    "DebateMessage",
    "FinancialStatement",
    "IdempotencyKey",
    "InstitutionalTrading",
    "LLMMonthlyQuota",
    "LLMUsage",
    "MarginTrading",
    "MonthlyRevenue",
    "NewsMetadata",
    "NotificationLog",
    "NotificationSetting",
    "PasswordResetToken",
    "PendingOrder",
    "PortfolioPosition",
    "StockInfo",
    "StockList",
    "StockPrice",
    "TimestampedMixin",
    "TradeHistory",
    "User",
    "UserRole",
    "UserSession",
    "UserWatchlist",
    "metadata",
]
