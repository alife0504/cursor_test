import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { PriceDelta } from "@/components/common/PriceDelta";

describe("<PriceDelta />", () => {
  test("正值 → data-tone=bull 且加 + 號（台股紅漲）", () => {
    const { container } = render(<PriceDelta value={1.23} />);
    const root = container.querySelector('[data-tone="bull"]');
    expect(root).toBeTruthy();
    expect(screen.getByText(/\+1\.23%/)).toBeInTheDocument();
  });

  test("負值 → data-tone=bear 且加 − 號（台股綠跌）", () => {
    const { container } = render(<PriceDelta value={-0.5} />);
    const root = container.querySelector('[data-tone="bear"]');
    expect(root).toBeTruthy();
    expect(screen.getByText(/−0\.50%/)).toBeInTheDocument();
  });

  test("零 → data-tone=flat", () => {
    const { container } = render(<PriceDelta value={0} />);
    expect(container.querySelector('[data-tone="flat"]')).toBeTruthy();
  });

  test("null → 顯示 dash 且為 flat", () => {
    const { container } = render(<PriceDelta value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(container.querySelector('[data-tone="flat"]')).toBeTruthy();
  });

  test("mode=pct 把 0.01 轉成 1.00%", () => {
    render(<PriceDelta value={0.01} mode="pct" />);
    expect(screen.getByText(/\+1\.00%/)).toBeInTheDocument();
  });

  test("自訂 suffix 取代預設 %", () => {
    render(
      <PriceDelta value={5} mode="abs" suffix=" 點" showIcon={false} />,
    );
    expect(screen.getByText(/\+5 點/)).toBeInTheDocument();
  });
});
