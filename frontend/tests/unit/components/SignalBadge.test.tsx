import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { SignalBadge } from "@/components/common/SignalBadge";

describe("<SignalBadge />", () => {
  test("completed + BUY 顯示「買進」且 data-tone=buy", () => {
    const { container } = render(
      <SignalBadge signal="BUY" status="completed" />,
    );
    expect(screen.getByText(/買進/)).toBeInTheDocument();
    expect(container.querySelector('[data-tone="buy"]')).toBeTruthy();
  });

  test("completed + SELL 顯示「賣出」且 data-tone=sell", () => {
    const { container } = render(
      <SignalBadge signal="SELL" status="completed" />,
    );
    expect(screen.getByText(/賣出/)).toBeInTheDocument();
    expect(container.querySelector('[data-tone="sell"]')).toBeTruthy();
  });

  test("completed + HOLD 顯示「持有」", () => {
    render(<SignalBadge signal="HOLD" status="completed" />);
    expect(screen.getByText(/持有/)).toBeInTheDocument();
  });

  test("running 顯示中文「分析中」", () => {
    render(<SignalBadge status="running" />);
    expect(screen.getByText("分析中")).toBeInTheDocument();
  });

  test("queued 顯示中文「排隊中」", () => {
    render(<SignalBadge status="queued" />);
    expect(screen.getByText("排隊中")).toBeInTheDocument();
  });

  test("failed 顯示中文「失敗」", () => {
    render(<SignalBadge status="failed" />);
    expect(screen.getByText("失敗")).toBeInTheDocument();
  });

  test("缺資訊回 dash", () => {
    render(<SignalBadge />);
    expect(screen.getByText("-")).toBeInTheDocument();
  });

  test("有 signal 但未 completed 仍顯示狀態", () => {
    render(<SignalBadge signal="BUY" status="running" />);
    expect(screen.getByText("分析中")).toBeInTheDocument();
  });
});
