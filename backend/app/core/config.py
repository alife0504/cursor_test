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
    APP_VERSION: str = "1.1.0"
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
    """Fernet 加密 Discord webhook / Telegram token（P14/P18）；必須與 SECRET_KEY 不同。"""
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    CSP_PROD_ENABLED: bool = False
    """P18 才設 true（prod CSP nonce-based）。"""
    TRUST_PROXY_HEADERS: bool = False
    """部署在受信任反向代理（nginx 等）後才設 True，才會信任 X-Forwarded-For / X-Real-IP
    取真實 client IP；預設 False（直連）以免任何人偽造標頭繞過限流 / 稽核。"""
    TRUSTED_PROXY_HOPS: int = 1
    """信任的反向代理層數（從應用連線端往回數），用於從 X-Forwarded-For 取對真實 client IP。"""
    EXPOSE_RESET_TOKEN_IN_RESPONSE: bool = False
    """是否在 /auth/password-reset 回應直接回傳明文 reset token（dev_token）。

    預設 False：即使 dev 也不外露——回應含明文 token 等於「免信箱帳號接管原語」，只要能對
    後端發請求並讀回應即可重設任意帳號密碼。僅供自動化測試 / 本機手測時明確 opt-in（設 True），
    且 prod 一律強制不回傳（見 auth_router）。真實寄信由 P18 通知管道負責。"""

    # ── 啟動韌性（避免依賴短暫不可用就把整個 process 殺掉）────────
    STARTUP_PROBE_RETRIES: int = 10
    """啟動時 DB/Redis/Qdrant 探測的重試次數（退避）；用盡才 fail-fast。
    讓容器冷啟排序、筆電休眠喚醒、redis 重啟等短暫抖動不會一啟動就崩潰退出。"""
    STARTUP_PROBE_DELAY_S: float = 2.0
    """啟動探測每次重試的基礎退避秒數（實際 = min(delay×attempt, 10)）。"""

    # ── 自動選股預篩選（v1.1；未指定個股時依等級批次選股）────────
    # 全部是「條件」，刻意設成可調（screening_service 依這些算候選數 / floor）。
    # 「基本」是必備 floor（剔除停牌/低流動性/雞蛋水餃股），永遠先套用；
    # 低/中/高是使用者可選等級，各自保留約 N 檔（絕對數，非比例）。
    SCREEN_COUNT_LOW: int = 600
    """低級等級保留檔數（約 600）。"""
    SCREEN_COUNT_MID: int = 300
    """中級等級保留檔數（約 300）。"""
    SCREEN_COUNT_HIGH: int = 150
    """高級等級保留檔數（約 150）。"""
    SCREEN_POOL_SIZE: int = 1000
    """流動性候選池大小：先取近期日均成交額前 N 檔算指標評分，再取各等級 top。
    需 ≥ SCREEN_COUNT_LOW 才能產出低級的量。"""
    SCREEN_MAX_ANALYSES: int = 30
    """⚠️ 批次實際建立分析的硬上限（保護月配額 / 時間）。
    自動選股雖可篩出低級約 600 檔，但一次對 600 檔各跑完整多 Agent 分析成本/時間巨大、
    可能瞬間爆掉月配額，故只實際建立「篩選排序後前 N 檔」的分析，其餘為候選未分析。
    自用級預設保守；要一次跑更多再調高。"""
    SCREEN_LOOKBACK_DAYS: int = 90
    """算指標往回抓幾天日 K（相對資料最新交易日，非今天）。"""
    SCREEN_MIN_PRICE: float = 5.0
    """價格 floor：低於此收盤價視為雞蛋水餃股剔除（floor 全濾空時自動放寬）。"""
    SCREEN_MIN_AVG_TURNOVER: float = 5_000_000.0
    """流動性 floor：近期日均成交額（元）低於此剔除（floor 全濾空時自動放寬）。"""

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

    # ── FinMind 本地資料庫（盤後 EOD 主源；自架 finmind-platform 的 fm-postgres）──
    # 啟用後 TW OHLCV 盤後資料直接查本地庫（priority=5 最優先），FinMind API 只當即時/備援。
    FINMIND_LOCAL_ENABLED: bool = False
    FINMIND_LOCAL_HOST: str = "host.docker.internal"
    FINMIND_LOCAL_PORT: int = 15432
    FINMIND_LOCAL_DB: str = "finmind"
    FINMIND_LOCAL_USER: str = "postgres"
    FINMIND_LOCAL_PASSWORD: SecretStr | None = None

    # ── tw-hawk / twofc 本地資料湖（DuckDB 檔）——補 FinMind 缺的股東會/財報公布日等 ──
    # 啟用後財報日曆會加上「股東會」事件（twofc_event_calendar，含真實 announced_at）。
    # 讀不到（檔案未掛載/被鎖）時 graceful 跳過，日曆其餘照常。
    TWHAWK_ENABLED: bool = False
    TWHAWK_DUCKDB_PATH: str = "/twhawk/twofc.duckdb"

    # ── FinMind 即時盤 snapshot（盤中即時報價；需 FinMind 付費 Sponsor 等級 token）──
    # taiwan_stock_tick_snapshot / taiwan_futures_snapshot 這兩個端點免費(register)等級無權，
    # 會回 status=400「Your level is register」。預設關閉：開啟前請確認 token 為 Sponsor 等級，
    # 否則每次呼叫都吃配額卻拿不到資料。開啟後 /api/v1/market/realtime/* 才會實際打 API。
    FINMIND_REALTIME_ENABLED: bool = False

    # ── LLM Provider（P12/P14） ──────────────────────────────
    GOOGLE_API_KEY: SecretStr | None = None
    OPENAI_API_KEY: SecretStr | None = None
    ANTHROPIC_API_KEY: SecretStr | None = None
    MINIMAX_API_KEY: SecretStr | None = None
    LLM_DEFAULT_PROVIDER: Literal["google", "openai", "anthropic", "minimax"] = "google"
    LLM_DEFAULT_MODEL: str = "gemini-2.5-flash"
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_DEFAULT_MODEL: str = "claude-haiku-4-5"
    MINIMAX_DEFAULT_MODEL: str = "MiniMax-M3"
    MINIMAX_BASE_URL: str = "https://api.minimax.io/v1"
    """MiniMax OpenAI 相容端點。國際版 api.minimax.io；中國站為 api.minimaxi.com。"""
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"
    LLM_MONTHLY_BUDGET_USD_DEFAULT: Decimal = Decimal("50.00")
    """用戶預設月預算（每用戶可個別覆寫）。"""
    LLM_MAX_RETRIES: int = 2
    """單一 provider 對「暫時性錯誤」（429 / 5xx / timeout）的退避重試次數。
    對齊上游 v0.3.1 llm_max_retries：只有 Google 金鑰時，一次 429 突發不再直接炸掉整輪分析
    （fallback chain 沒別家可轉時尤其重要）。0＝不重試（回舊行為）。"""
    LLM_RETRY_BASE_DELAY_S: float = 0.8
    """暫時性錯誤重試的基礎退避秒數（實際 = base × 2^attempt，指數退避）。"""

    # ── 通知（P18） ──────────────────────────────────────────
    DISCORD_WEBHOOK_URL: SecretStr | None = None
    """系統層級 Discord Webhook（選用；取代已停服的 LINE Notify）。
    使用者個人 webhook 存於 notification_settings.discord_webhook_encrypted。"""
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
                "minimax": self.MINIMAX_API_KEY,
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
