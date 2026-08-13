import { describe, expect, test } from "vitest";

import {
  formatCurrency,
  formatDate,
  formatDateTime,
  formatNumber,
  formatPercent,
  formatRelative,
} from "@/lib/format";

describe("formatNumber", () => {
  test("整數加千分位", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
  });

  test("decimal 字串保留精度", () => {
    expect(formatNumber("12345.6789", 2)).toBe("12,345.68");
  });

  test("null 回 fallback", () => {
    expect(formatNumber(null)).toBe("-");
    expect(formatNumber(undefined, 0, "N/A")).toBe("N/A");
  });

  test("NaN 字串回 fallback 而不丟錯", () => {
    expect(formatNumber("abc")).toBe("-");
  });

  test("負數", () => {
    expect(formatNumber("-9876.5", 2)).toBe("-9,876.50");
  });
});

describe("formatPercent", () => {
  test("比例 0.0825 → 8.25%", () => {
    expect(formatPercent(0.0825)).toBe("8.25%");
  });

  test("字串 0.1234 → 12.34%", () => {
    expect(formatPercent("0.1234")).toBe("12.34%");
  });

  test("0 → 0.00%", () => {
    expect(formatPercent(0)).toBe("0.00%");
  });

  test("null fallback", () => {
    expect(formatPercent(null)).toBe("-");
  });
});

describe("formatCurrency", () => {
  test("TWD 預設無小數", () => {
    expect(formatCurrency(123456, "TWD")).toBe("NT$123,456");
  });

  test("USD 預設兩位小數", () => {
    expect(formatCurrency("1234.5", "USD")).toBe("US$1,234.50");
  });

  test("decimal override", () => {
    expect(formatCurrency(1000, "TWD", 2)).toBe("NT$1,000.00");
  });

  test("null fallback", () => {
    expect(formatCurrency(null)).toBe("-");
  });
});

describe("formatDateTime / formatDate", () => {
  test("UTC ISO → Asia/Taipei", () => {
    // 2026-05-17T01:23:45Z → Taipei +08:00 = 09:23:45
    expect(formatDateTime("2026-05-17T01:23:45Z", "Asia/Taipei")).toBe(
      "2026-05-17 09:23:45",
    );
  });

  test("date mode 只顯示日期", () => {
    expect(formatDate("2026-05-17T15:00:00Z", "Asia/Taipei")).toBe(
      "2026-05-17",
    );
  });

  test("無效 ISO 回 fallback", () => {
    expect(formatDateTime("not-a-date")).toBe("-");
  });

  test("null 回 fallback", () => {
    expect(formatDate(null)).toBe("-");
  });
});

describe("formatRelative", () => {
  test("剛剛", () => {
    expect(
      formatRelative("2026-05-17T10:00:00Z", "2026-05-17T10:00:30Z"),
    ).toBe("30 秒前");
  });

  test("數分鐘前", () => {
    expect(
      formatRelative("2026-05-17T10:00:00Z", "2026-05-17T10:05:00Z"),
    ).toBe("5 分鐘前");
  });

  test("數小時前", () => {
    expect(
      formatRelative("2026-05-17T08:00:00Z", "2026-05-17T10:00:00Z"),
    ).toBe("2 小時前");
  });

  test("數天前", () => {
    expect(
      formatRelative("2026-05-15T10:00:00Z", "2026-05-17T10:00:00Z"),
    ).toBe("2 天前");
  });

  test("未來時間 fallback", () => {
    expect(
      formatRelative("2026-05-17T11:00:00Z", "2026-05-17T10:00:00Z"),
    ).toBe("-");
  });
});
