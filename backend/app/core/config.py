"""應用設定 — Pydantic v2 BaseSettings。

依 PLAN.md 第 6.1 章 pin 版本 + 第 19.4 章 Secret 管理 + 第 14.1 章連線池。

v7.0 設計原則：P3 一次列齊「v1.0 全部會用到」的欄位，避免後續 Phase 回頭修。
實際 P3 還用不到的欄位（如 LLM provider、通知 token）給合理 default 或設為 Optional。
"""

from __future__ import annotations

import base64
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import EmailStr, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 此檔在 backend/app/core/config.py，往上 3 層 = 專案根目錄
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """應用層 / 安全 / DB / Redis / Qdrant / 資料源 / LLM / 通知 / 國際化。"""

    model_config = SettingsConfigDict(
        # 同時嘗試專案根 .env（優先）與 backend/.env（萬一將來分離）
        env_file=(str(_PROJECT_ROOT / ".env"), str(_PROJECT_ROOT / "backend" / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── 應用層 ────────────────────────────────────────────────
    APP_ENV: Literal["dev", "test", "staging", "prod"] = "dev"
    APP_VERSION: str = "0.3.0"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"
    ADMIN_EMAIL: EmailStr = "admin@example.com"  # type: ignore[assignment]
    """系統管理者 + 初始 admin 帳號 email。

    用途：
    - SEC EDGAR User-Agent (P6)
    - seed_users.py 建立的第一個 admin 帳號 (P7)
    - 系統警告通知收件人 (P18)
    """
    ADMIN_INITIAL_PASSWORD: SecretStr = SecretStr("ChangeMeOnFirstLogin!1234")
    """第一次 seed admin 用的初始密碼（onboarding 強制改）。"""

    # ── 安全 ────────────────────────────────────────────────
    SECRET_KEY: str
    """≥ 32 bytes（base64 解碼後），JWT 簽名 + CSRF token。"""
    SECRET_KEY_PREVIOUS: str | None = None
    """雙 key rotation 過渡期用（P8）。平時為 None。"""
    DATA_ENCRYPTION_KEY: str
    """Fernet 加密 LINE/Telegram token（P14/P18）；必須與 SECRET_KEY 不同。"""
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    CSP_PROD_ENABLED: bool = False
    """P18 才設 true（prod CSP nonce-based）。"""

    # ── DB（連線池參數依第 14.1 章） ────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "tradingagents_tw"
    POSTGRES_SUPERUSER_PASSWORD: SecretStr
    """維運用，僅 init / dump / 緊急復原。"""
    TA_MIGRATION_PASSWORD: SecretStr
    """alembic migration 用（CREATEDB + DDL 權限）。"""
    TA_SERVICE_RW_PASSWORD: SecretStr
    """後端業務 CRUD 用（DML only，無 DDL）。"""
    TA_AGENT_RO_PASSWORD: SecretStr
    """LangGraph Agent / Tool 用（read-only，防 prompt injection 注入 SQL）。"""
    POOL_SIZE_RW: int = 20
    POOL_SIZE_RO: int = 30
    STATEMENT_TIMEOUT_MS: int = 30000
    LOCK_TIMEOUT_MS: int = 10000

    # ── Redis ────────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: SecretStr
    POOL_SIZE_REDIS: int = 50

    # ── Qdrant ────────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_API_KEY: SecretStr
    EMBEDDING_DIM: int = 768
    """Gemini text-embedding-004 維度。"""

    # ── 資料源 API key（P5/P6） ──────────────────────────────
    FINMIND_TOKEN: SecretStr | None = None
    ALPHA_VANTAGE_API_KEY: SecretStr | None = None
    FINNHUB_API_KEY: SecretStr | None = None
    # SEC EDGAR / TWSE / TPEX / MOPS / cnyes 無需 API key

    # ── LLM Provider（P12/P14） ──────────────────────────────
    GOOGLE_API_KEY: SecretStr | None = None
    OPENAI_API_KEY: SecretStr | None = None
    ANTHROPIC_API_KEY: SecretStr | None = None
    LLM_DEFAULT_PROVIDER: Literal["google", "openai", "anthropic"] = "google"
    LLM_DEFAULT_MODEL: str = "gemini-2.0-flash"
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_DEFAULT_MODEL: str = "claude-haiku-3-5-20241022"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"
    LLM_MONTHLY_BUDGET_USD_DEFAULT: Decimal = Decimal("50.00")
    """用戶預設月預算（每用戶可個別覆寫）。"""

    # ── 通知（P18） ──────────────────────────────────────────
    LINE_NOTIFY_TOKEN: SecretStr | None = None
    TELEGRAM_BOT_TOKEN: SecretStr | None = None
    TELEGRAM_CHAT_ID: str | None = None

    # ── 國際化 / 時區 ────────────────────────────────────────
    DEFAULT_TIMEZONE: str = "Asia/Taipei"
    DEFAULT_LANG: str = "zh-TW"

    # ── 開發 / 測試專用 ──────────────────────────────────────
    PYTEST_RUNNING: bool = False
    """測試 fixture 設 True 時跳過某些 startup check（如 LLM provider readiness）。"""

    # ── HTTP client 設定（依 14.2 章） ───────────────────────
    HTTP_CONNECT_TIMEOUT_S: float = 10.0
    HTTP_READ_TIMEOUT_S: float = 30.0
    HTTP_TOTAL_TIMEOUT_S: float = 60.0
    HTTP_RETRY_MAX_ATTEMPTS: int = 3
    HTTP_RETRY_MIN_WAIT_S: float = 2.0
    HTTP_RETRY_MAX_WAIT_S: float = 30.0

    # ── Circuit Breaker 設定（依 14.3 章） ───────────────────
    CB_FAILURE_THRESHOLD: int = 5
    CB_OPEN_TIMEOUT_S: int = 600  # 10 分鐘

    # ════════════════ Validators ════════════════

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_min_length(cls, v: str) -> str:
        """SECRET_KEY 必須是 base64 字串，解碼後 ≥ 32 bytes。"""
        if not v:
            raise ValueError("SECRET_KEY 不可為空")
        try:
            decoded = base64.urlsafe_b64decode(v + "=" * (-len(v) % 4))
        except Exception as e:
            raise ValueError(f"SECRET_KEY 必須為 base64 字串：{e}") from e
        if len(decoded) < 32:
            raise ValueError(f"SECRET_KEY 解碼後須 ≥ 32 bytes，目前 {len(decoded)}")
        return v

    @field_validator("DATA_ENCRYPTION_KEY")
    @classmethod
    def data_encryption_key_format(cls, v: str) -> str:
        """DATA_ENCRYPTION_KEY 也必須是 base64 ≥ 32 bytes。"""
        if not v:
            raise ValueError("DATA_ENCRYPTION_KEY 不可為空")
        try:
            decoded = base64.urlsafe_b64decode(v + "=" * (-len(v) % 4))
        except Exception as e:
            raise ValueError(f"DATA_ENCRYPTION_KEY 必須為 base64 字串：{e}") from e
        if len(decoded) < 32:
            raise ValueError(f"DATA_ENCRYPTION_KEY 解碼後須 ≥ 32 bytes，目前 {len(decoded)}")
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str] | object:
        """允許 CORS_ORIGINS 用 JSON 字串或 list 形式設定。"""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json

                return json.loads(v)
            # 逗號分隔
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def cross_field_validations(self) -> Settings:
        """跨欄位驗證。"""
        # SECRET_KEY 與 DATA_ENCRYPTION_KEY 必須不同
        if self.SECRET_KEY == self.DATA_ENCRYPTION_KEY:
            raise ValueError(
                "SECRET_KEY 與 DATA_ENCRYPTION_KEY 必須分離（避免單一 key 洩漏全失守）"
            )

        # LLM_DEFAULT_PROVIDER 對應的 API key 在 prod 必須有值（dev/test 可空）
        if self.APP_ENV == "prod":
            provider_key_map: dict[str, SecretStr | None] = {
                "google": self.GOOGLE_API_KEY,
                "openai": self.OPENAI_API_KEY,
                "anthropic": self.ANTHROPIC_API_KEY,
            }
            if not provider_key_map.get(self.LLM_DEFAULT_PROVIDER):
                raise ValueError(
                    f"prod 環境 LLM_DEFAULT_PROVIDER={self.LLM_DEFAULT_PROVIDER} "
                    f"但對應 API key 為空"
                )

        # prod 環境檢查
        if self.APP_ENV == "prod":
            if any("localhost" in o for o in self.CORS_ORIGINS):
                raise ValueError("prod 環境 CORS_ORIGINS 不可含 localhost")
            if not self.CSP_PROD_ENABLED:
                raise ValueError("prod 環境必須啟用 CSP_PROD_ENABLED")

        return self

    # ════════════════ Helper Properties ════════════════

    @property
    def postgres_dsn(self) -> str:
        """superuser DSN（僅 init/dump 用）。"""
        return (
            f"postgresql+asyncpg://postgres:"
            f"{self.POSTGRES_SUPERUSER_PASSWORD.get_secret_value()}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def postgres_dsn_rw(self) -> str:
        """ta_service_rw DSN（後端業務用）。"""
        return (
            f"postgresql+asyncpg://ta_service_rw:"
            f"{self.TA_SERVICE_RW_PASSWORD.get_secret_value()}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def postgres_dsn_ro(self) -> str:
        """ta_agent_ro DSN（Agent / Tool 用）。"""
        return (
            f"postgresql+asyncpg://ta_agent_ro:"
            f"{self.TA_AGENT_RO_PASSWORD.get_secret_value()}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def postgres_dsn_migration(self) -> str:
        """ta_migration DSN（alembic 用）。"""
        return (
            f"postgresql+asyncpg://ta_migration:"
            f"{self.TA_MIGRATION_PASSWORD.get_secret_value()}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    def redis_url(self, db: int = 0) -> str:
        """Redis URL（指定 db 編號）。"""
        return (
            f"redis://:{self.REDIS_PASSWORD.get_secret_value()}"
            f"@{self.REDIS_HOST}:{self.REDIS_PORT}/{db}"
        )

    @property
    def qdrant_url(self) -> str:
        """Qdrant HTTP URL。"""
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

    @property
    def qdrant_grpc_url(self) -> str:
        """Qdrant gRPC URL。"""
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_GRPC_PORT}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """單例（lru_cache）。整個 process 只 load 一次 .env。"""
    return Settings()  # type: ignore[call-arg]


# 模組層級單例（便於 import）
settings = get_settings()


__all__ = ["Settings", "get_settings", "settings"]
