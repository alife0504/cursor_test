import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { MarketBadge } from "@/components/common/MarketBadge";

// Phase 16 對 MarketBadge 的擴充:支援 TWSE/TPEX/NYSE/NASDAQ/AMEX
describe("<MarketBadge /> P16 擴充", () => {
  test("TWSE 歸類為台股", () => {
    render(<MarketBadge market="TWSE" />);
    expect(screen.getByText(/台股/)).toBeInTheDocument();
  });

  test("TPEX 歸類為台股", () => {
    render(<MarketBadge market="TPEX" />);
    expect(screen.getByText(/台股/)).toBeInTheDocument();
  });

  test("NYSE 歸類為美股", () => {
    render(<MarketBadge market="NYSE" />);
    expect(screen.getByText(/美股/)).toBeInTheDocument();
  });

  test("NASDAQ 歸類為美股", () => {
    render(<MarketBadge market="NASDAQ" />);
    expect(screen.getByText(/美股/)).toBeInTheDocument();
  });

  test("OTHER 顯示「其他」", () => {
    render(<MarketBadge market="OTHER" />);
    expect(screen.getByText("其他")).toBeInTheDocument();
  });

  test("不認得的字串退化為「其他」", () => {
    render(<MarketBadge market="JPX" />);
    expect(screen.getByText("其他")).toBeInTheDocument();
  });
});
