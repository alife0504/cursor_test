/**
 * @vitest-environment jsdom
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { OrderApprovalDialog } from "@/components/orders/OrderApprovalDialog";
import { api } from "@/lib/api";
import type { OrderSummary } from "@/lib/api-types";

const order: OrderSummary = {
  id: "o-1",
  user_id: "u-1",
  symbol: "2330",
  market: "TWSE",
  side: "BUY",
  qty: 100,
  target_price: "650.00",
  status: "PENDING",
  version: 1,
  created_at: "2026-05-17T00:00:00Z",
};

let mock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(api);
});

afterEach(() => {
  mock.restore();
  vi.restoreAllMocks();
});

function renderWithProviders(ui: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("<OrderApprovalDialog />", () => {
  test("核准模式:未勾選確認框時 button disabled", () => {
    renderWithProviders(
      <OrderApprovalDialog order={order} mode="approve" onClose={() => {}} />,
    );
    const btn = screen.getByRole("button", { name: /確認核准/ });
    expect(btn).toBeDisabled();
  });

  test("核准模式:勾選確認框後 button enabled", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <OrderApprovalDialog order={order} mode="approve" onClose={() => {}} />,
    );
    await user.click(
      screen.getByLabelText(/我已核對/),
    );
    const btn = screen.getByRole("button", { name: /確認核准/ });
    expect(btn).toBeEnabled();
  });

  test("拒絕模式:reason 為空時 button disabled", () => {
    renderWithProviders(
      <OrderApprovalDialog order={order} mode="reject" onClose={() => {}} />,
    );
    const btn = screen.getByRole("button", { name: /確認拒絕/ });
    expect(btn).toBeDisabled();
  });

  test("拒絕模式:填入 reason 後 button enabled", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <OrderApprovalDialog order={order} mode="reject" onClose={() => {}} />,
    );
    await user.type(screen.getByLabelText(/拒絕原因/), "信心不足");
    const btn = screen.getByRole("button", { name: /確認拒絕/ });
    expect(btn).toBeEnabled();
  });

  test("核准成功 → 呼叫 onClose", async () => {
    mock.onPost("/orders/o-1/approve").reply(200, {
      data: { ...order, status: "APPROVED", version: 2 },
    });
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <OrderApprovalDialog order={order} mode="approve" onClose={onClose} />,
    );
    await user.click(screen.getByLabelText(/我已核對/));
    await user.click(screen.getByRole("button", { name: /確認核准/ }));
    // 等 mutation 完成
    await new Promise((r) => setTimeout(r, 50));
    expect(onClose).toHaveBeenCalled();
  });

  test("核准 409 → 仍呼叫 onClose(列表會 refetch 顯示已被處理)", async () => {
    mock.onPost("/orders/o-1/approve").reply(409, {
      error: { code: "conflict" },
    });
    const onClose = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <OrderApprovalDialog order={order} mode="approve" onClose={onClose} />,
    );
    await user.click(screen.getByLabelText(/我已核對/));
    await user.click(screen.getByRole("button", { name: /確認核准/ }));
    await new Promise((r) => setTimeout(r, 50));
    expect(onClose).toHaveBeenCalled();
  });
});
