import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { ErrorState } from "@/components/common/ErrorState";

describe("<ErrorState />", () => {
  test("預設 title 顯示「載入失敗」", () => {
    render(<ErrorState />);
    expect(screen.getByText("載入失敗")).toBeInTheDocument();
  });

  test("提供 onRetry 顯示重試按鈕並可點擊", async () => {
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);
    const btn = screen.getByRole("button", { name: /重試/ });
    await userEvent.click(btn);
    expect(onRetry).toHaveBeenCalledOnce();
  });

  test("variant=inline 用 role=alert 且結構不同", () => {
    const { container } = render(
      <ErrorState variant="inline" title="X" description="Y" />,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(container.textContent).toContain("X");
    expect(container.textContent).toContain("Y");
  });

  test("沒 onRetry 則無重試按鈕", () => {
    render(<ErrorState />);
    expect(
      screen.queryByRole("button", { name: /重試/ }),
    ).not.toBeInTheDocument();
  });
});
