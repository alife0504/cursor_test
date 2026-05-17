import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { SignalBadge } from "@/components/common/SignalBadge";

describe("<SignalBadge />", () => {
  test("completed + BUY 顯示 BUY", () => {
    render(<SignalBadge signal="BUY" status="completed" />);
    expect(screen.getByText("BUY")).toBeInTheDocument();
  });

  test("completed + SELL 顯示 SELL", () => {
    render(<SignalBadge signal="SELL" status="completed" />);
    expect(screen.getByText("SELL")).toBeInTheDocument();
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
