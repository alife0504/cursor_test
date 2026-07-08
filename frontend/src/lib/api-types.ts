// Phase 16:後端 API 回傳的共用型別(envelope 內 data 形狀)。
//
// 設計原則:
//  - 對齊後端 Pydantic schema(backend/app/schemas/*)
//  - Decimal 一律用 string 表示(後端 mode="json" 序列化規則)
//  - DateTime ISO 8601 string

export type UUID = string;

export interface StockSummary {
  symbol: string;
  market: string;
  name: string;
  short_name?: string | null;
  industry?: string | null;
  is_active: boolean;
}

export interface StockDetail extends StockSummary {
  listed_at?: string | null;
  full_name?: string | null;
  sector?: string | null;
  sub_industry?: string | null;
  description?: string | null;
  website?: string | null;
  capital?: string | null;
  employees?: number | null;
  fiscal_year_end?: string | null;
}

export interface OHLCVPoint {
  symbol: string;
  date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  adjusted_close?: string | null;
  volume: number;
  turnover?: string | null;
  source?: string | null;
}

export interface IndicatorPoint {
  date: string;
  rsi?: string | null;
  macd?: string | null;
  macd_signal?: string | null;
  macd_hist?: string | null;
  k?: string | null;
  d?: string | null;
  bb_upper?: string | null;
  bb_middle?: string | null;
  bb_lower?: string | null;
}

export type WatchlistMarket =
  | "TWSE"
  | "TPEX"
  | "NYSE"
  | "NASDAQ"
  | "AMEX"
  | "OTHER";

export interface WatchlistItem {
  id: string;
  user_id: string;
  symbol: string;
  market: string;
  tag?: string | null;
  notes?: string | null;
  sort_order: number;
  created_at: string;
}

export interface WatchlistCreateBody {
  symbol: string;
  market: WatchlistMarket;
  tag?: string | null;
  notes?: string | null;
}

export interface WatchlistUpdateBody {
  tag?: string | null;
  notes?: string | null;
  sort_order?: number | null;
}

export type AnalysisStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type AnalysisSignal = "BUY" | "SELL" | "HOLD" | string;

export interface AnalysisSummary {
  id: UUID;
  symbol: string;
  market: string;
  status: AnalysisStatus | string;
  signal?: AnalysisSignal | null;
  confidence?: string | null;
  llm_model?: string | null;
  total_cost_usd?: string | null;
  created_at: string;
  completed_at?: string | null;
}

/** Analyst raw output 的結構（後端 P14+ 寫入 analysis_reports.analyst_outputs）。 */
export interface AnalystOutput {
  /** 分析師類型：market / fundamental / news / sentiment / chip */
  type?: string;
  /** 信心度 0-1 */
  score?: number | string | null;
  /** 訊號（同 BUY/SELL/HOLD 系列） */
  signal?: string | null;
  /** 關鍵觀察點（依 prompt schema） */
  key_points?: string[] | null;
  /** Markdown 完整報告片段（可選） */
  report_md?: string | null;
  /** 額外結構化資料（指標數值等） */
  metrics?: Record<string, unknown> | null;
  /** 任何其他欄位 — pass-through */
  [k: string]: unknown;
}

export interface AnalysisDetail extends AnalysisSummary {
  user_id: UUID;
  target_price?: string | null;
  stop_loss?: string | null;
  take_profit?: string | null;
  llm_provider?: string | null;
  total_tokens: number;
  total_cost_usd: string;
  report_md?: string | null;
  error_msg?: string | null;
  version: number;
  started_at?: string | null;
  /** Phase 14+：每個 analyst 的結構化輸出（v1.0.1 後端開始顯露） */
  analyst_outputs?: Record<string, AnalystOutput> | null;
  /** 從建立參數帶回，給前端 AgentFlowGraph 建節點用（v1.0.1 後端開始顯露） */
  analyst_types?: string[] | null;
  debate_rounds?: number | null;
  risk_tolerance?: string | null;
}

export interface DebateMessage {
  id: UUID;
  analysis_id: UUID;
  round_num: number;
  role: string;
  content: Record<string, unknown> | unknown[];
  tokens_used?: number | null;
  created_at: string;
}

export interface AnalysisCreateBody {
  // 指定個股（symbol）與自動選股（screen_level）二擇一
  symbol?: string;
  screen_level?: "basic" | "low" | "mid" | "high";
  market?: "TW" | "US";
  analyst_types: string[];
  llm_model: string;
  agent_models?: Record<string, string>;
  debate_rounds: number;
  risk_rounds?: number;
  risk_tolerance?: string | null;
  notes?: string | null;
}

export interface AnalysisCreateResponse {
  analysis_id: UUID;
  status: string;
  estimated_seconds: number;
  // 批次（自動選股）時 count > 1；指定個股為 1
  count?: number;
  analysis_ids?: UUID[];
  screened_symbols?: string[];
  // 篩出的候選總數（可能 > count；實際只建立前 count 檔分析）
  screened_count?: number;
}

export type OrderSide = "BUY" | "SELL" | string;
export type OrderStatus =
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "EXPIRED"
  | "CANCELLED"
  | string;

export interface OrderSummary {
  id: UUID;
  user_id: UUID;
  analysis_id?: UUID | null;
  symbol: string;
  market: string;
  side: OrderSide;
  qty: number;
  target_price?: string | null;
  stop_loss?: string | null;
  take_profit?: string | null;
  status: OrderStatus;
  reviewed_by?: UUID | null;
  reviewed_at?: string | null;
  review_notes?: string | null;
  version: number;
  created_at: string;
  expires_at?: string | null;
}

export type UserRole = "ADMIN" | "ANALYST" | "VIEWER";

export interface AdminUserItem {
  id: string;
  email: string;
  full_name?: string | null;
  role: UserRole;
  preferred_timezone: string;
  preferred_language: string;
  onboarding_completed: boolean;
  must_change_password: boolean;
  is_active: boolean;
  last_login_at?: string | null;
  created_at?: string | null;
}

export interface AuditLogItem {
  id: number;
  timestamp: string;
  actor_id?: string | null;
  action: string;
  entity_type?: string | null;
  entity_id?: string | null;
  details?: Record<string, unknown> | unknown[] | null;
  ip?: string | null;
  request_id?: string | null;
  prev_hash?: string | null;
  entry_hash?: string | null;
}

export interface QuotaMe {
  used_usd: string;
  limit_usd: string;
  allowed: boolean;
  percentage: number;
}

export interface MoverRow {
  symbol: string;
  name?: string | null;
  close?: string | null;
  change_pct?: string | null;
  volume?: number | null;
}

// 對齊 backend/app/schemas/market.py IndexQuote
export interface IndexQuote {
  name: string;
  symbol: string;
  close?: string | null;
  change?: string | null;
  change_pct?: string | null;
  volume?: number | null;
  as_of?: string | null;
}

// 對齊 backend/app/schemas/market.py MarketOverview（欄位名以後端為準）
export interface MarketOverview {
  market?: string;
  as_of?: string;
  indices?: IndexQuote[] | null;
  advance_count?: number | null;
  decline_count?: number | null;
  unchanged_count?: number | null;
  total_volume?: number | string | null;
  // 結構彈性,前端容忍未知欄位
  [k: string]: unknown;
}

// ════════════════ Phase 17 ════════════════
// 三大法人 row（對應 backend/schemas/market.py InstitutionalRow）
export interface InstitutionalRow {
  symbol: string;
  date: string;
  foreign_buy?: string | null;
  foreign_sell?: string | null;
  foreign_net?: string | null;
  trust_buy?: string | null;
  trust_sell?: string | null;
  trust_net?: string | null;
  dealer_buy?: string | null;
  dealer_sell?: string | null;
  dealer_net?: string | null;
}

export interface InstitutionalResponse {
  date: string | null;
  rows: InstitutionalRow[];
}

// Screener row（對應 backend/schemas/screener.py ScreenerRow）
// 對齊 backend/app/schemas/screener.py ScreenerRow（後端欄位 pe_ratio，無 volume）
export interface ScreenerRow {
  symbol: string;
  name?: string | null;
  market?: string | null;
  industry?: string | null;
  close?: string | null;
  pe_ratio?: string | null;
  dividend_yield?: string | null;
  eps_growth?: string | null;
  rsi?: string | null;
  market_cap?: string | null;
}

export interface ScreenerFilters {
  market?: "TW" | "US";
  PE_min?: number | null;
  PE_max?: number | null;
  dividend_yield_min?: number | null;
  eps_growth_min?: number | null;
  RSI_min?: number | null;
  RSI_max?: number | null;
  market_cap_min?: number | null;
  industry?: string | null;
  sort?: string;
  order?: "asc" | "desc";
}

// 個股 news / announcement
export interface NewsItem {
  id?: string;
  symbol?: string | null;
  market?: string | null;
  title: string;
  summary?: string | null;
  source?: string | null;
  url?: string | null;
  author?: string | null;
  published_at: string;
  /** 後端欄位（backend NewsItem.sentiment）：very_positive | positive | neutral | negative | very_negative */
  sentiment?: "very_positive" | "positive" | "neutral" | "negative" | "very_negative" | string | null;
  /** @deprecated 後端實際回 `sentiment`；保留作向後相容 fallback */
  sentiment_label?: string | null;
  sentiment_score?: string | number | null;
}

// 對齊 backend/app/schemas/stocks.py AnnouncementItem（後端無 source 欄位）
export interface AnnouncementItem {
  id?: string;
  symbol?: string | null;
  market?: string | null;
  announcement_type?: string | null;
  title: string;
  url?: string | null;
  published_at: string;
}

// Notifications（對齊 backend/app/schemas/notifications.py）
export type NotificationChannel = "line" | "telegram" | "email" | "webhook";
export type NotificationEvent =
  | "analysis.completed"
  | "analysis.failed"
  | "order.approved"
  | "order.rejected"
  | "system.alert"
  | "test";

export interface NotificationSettings {
  user_id: string;
  discord_webhook_masked?: string | null;
  discord_webhook_set?: boolean;
  telegram_chat_id?: string | null;
  email_enabled: boolean;
  enabled_channels?: string[] | null;
  enabled_events?: string[] | null;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
  updated_at: string;
}

export interface NotificationSettingsUpdate {
  discord_webhook?: string | null;
  telegram_chat_id?: string | null;
  email_enabled?: boolean | null;
  enabled_channels?: string[] | null;
  enabled_events?: string[] | null;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
}

export interface NotificationLog {
  id: number;
  user_id?: string | null;
  channel: string;
  event_type: string;
  payload: Record<string, unknown> | unknown[];
  status: string;
  error_msg?: string | null;
  retry_count: number;
  sent_at: string;
}

// Admin / system
export interface SystemMetricsSummary {
  api_availability?: number | null;
  avg_latency_ms?: number | null;
  analyses_today?: number | null;
  llm_cost_today_usd?: string | number | null;
  disk_usage_pct?: number | null;
  queue_length?: number | null;
  [k: string]: unknown;
}

export interface SystemInfo {
  version: string;
  env: string;
  started_at: string;
  [k: string]: unknown;
}

// DLQ row（對齊 backend/schemas/admin.py DeadLetterOut）
export interface DLQItem {
  id: number;
  failed_at: string;
  task_name: string;
  task_id?: string | null;
  args?: unknown;
  kwargs?: Record<string, unknown> | null;
  exception_type?: string | null;
  exception?: string | null;
  retry_count: number;
  resolved: boolean;
  resolved_at?: string | null;
  resolved_by?: string | null;
  resolution_notes?: string | null;
}

// 對齊 backend/app/schemas/market.py CalendarItem（v1.1 接真實資料用；目前 calendar 頁仍用本地 mock）
export interface CalendarEvent {
  symbol: string;
  market?: string;
  event_type: string;
  event_date: string;
  title: string;
  extra?: Record<string, unknown> | null;
}
