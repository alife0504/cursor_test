import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { EmptyState } from "@/components/common/EmptyState";

describe("<EmptyState />", () => {
  test("預設顯示「目前沒有資料」", () => {
    render(<EmptyState />);
    expect(screen.getByText("目前沒有資料")).toBeInTheDocument();
  });

  test("自訂 title / description", () => {
    render(
      <EmptyState title="找不到結果" description="請調整篩選條件" />,
    );
    expect(screen.getByText("找不到結果")).toBeInTheDocument();
    expect(screen.getByText("請調整篩選條件")).toBeInTheDocument();
  });

  test("action 按鈕觸發 callback", async () => {
    const handler = vi.fn();
    render(
      <EmptyState
        action={{ label: "建立第一筆", onClick: handler }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "建立第一筆" }));
    expect(handler).toHaveBeenCalledOnce();
  });
});
