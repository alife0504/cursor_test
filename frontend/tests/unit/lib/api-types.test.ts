import { describe, expect, test } from "vitest";

import type {
  AdminUserItem,
  AnalysisCreateBody,
  AnalysisSummary,
  AuditLogItem,
  OrderSummary,
  QuotaMe,
  StockSummary,
  WatchlistCreateBody,
} from "@/lib/api-types";

// Phase 16:api-types 是 type-only,測試僅做結構性檢查
describe("api-types 結構", () => {
  test("StockSummary 必要欄位", () => {
    const s: StockSummary = {
      symbol: "2330",
      market: "TWSE",
      name: "台積電",
      is_active: true,
    };
    expect(s.symbol).toBe("2330");
  });

  test("WatchlistCreateBody 接受 OTHER 市場", () => {
    const w: WatchlistCreateBody = {
      symbol: "TEST",
      market: "OTHER",
    };
    expect(w.market).toBe("OTHER");
  });

  test("AnalysisCreateBody analyst_types 為 string[]", () => {
    const a: AnalysisCreateBody = {
      symbol: "2330",
      analyst_types: ["market", "news"],
      llm_model: "gemini-2.0-flash",
      debate_rounds: 1,
    };
    expect(a.analyst_types).toContain("news");
  });

  test("AnalysisSummary 允許 null 訊號", () => {
    const a: AnalysisSummary = {
      id: "a-1",
      symbol: "2330",
      market: "TWSE",
      status: "queued",
      signal: null,
      confidence: null,
      created_at: "2026-05-17T00:00:00Z",
    };
    expect(a.signal).toBeNull();
  });

  test("OrderSummary 必要欄位", () => {
    const o: OrderSummary = {
      id: "o-1",
      user_id: "u-1",
      symbol: "2330",
      market: "TWSE",
      side: "BUY",
      qty: 100,
      status: "PENDING",
      version: 1,
      created_at: "2026-05-17T00:00:00Z",
    };
    expect(o.qty).toBe(100);
  });

  test("AdminUserItem role 為 enum", () => {
    const u: AdminUserItem = {
      id: "u-1",
      email: "a@b.com",
      role: "ADMIN",
      preferred_timezone: "Asia/Taipei",
      preferred_language: "zh-TW",
      onboarding_completed: true,
      must_change_password: false,
      is_active: true,
    };
    expect(u.role).toBe("ADMIN");
  });

  test("AuditLogItem id 為 number", () => {
    const l: AuditLogItem = {
      id: 123,
      timestamp: "2026-05-17T00:00:00Z",
      action: "auth.login",
    };
    expect(typeof l.id).toBe("number");
  });

  test("QuotaMe percentage 為 number", () => {
    const q: QuotaMe = {
      used_usd: "10.00",
      limit_usd: "50.00",
      allowed: true,
      percentage: 20,
    };
    expect(q.percentage).toBe(20);
  });
});
