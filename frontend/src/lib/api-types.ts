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
  symbol: string;
  analyst_types: string[];
  llm_model: string;
  debate_rounds: number;
  risk_tolerance?: string | null;
  notes?: string | null;
}

export interface AnalysisCreateResponse {
  analysis_id: UUID;
  status: string;
  estimated_seconds: number;
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

export interface MarketOverview {
  market?: string;
  index?: Record<string, unknown> | null;
  advancers?: number | null;
  decliners?: number | null;
  unchanged?: number | null;
  total_volume?: string | null;
  // 後端 P10 stub:結構彈性,前端容忍未知欄位
  [k: string]: unknown;
}
