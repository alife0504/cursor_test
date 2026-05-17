/**
 * @vitest-environment jsdom
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { useApproveOrder, useRejectOrder } from "@/hooks/useOrders";
import { api } from "@/lib/api";

let mock: MockAdapter;
beforeEach(() => {
  mock = new MockAdapter(api);
});
afterEach(() => mock.restore());

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function W({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("useApproveOrder", () => {
  test("POST /orders/{id}/approve", async () => {
    mock.onPost("/orders/o-1/approve").reply(200, {
      data: {
        id: "o-1",
        user_id: "u-1",
        symbol: "2330",
        market: "TWSE",
        side: "BUY",
        qty: 100,
        status: "APPROVED",
        version: 2,
        created_at: "2026-05-17T00:00:00Z",
      },
    });
    const { result } = renderHook(() => useApproveOrder(), {
      wrapper: makeWrapper(),
    });
    const order = await result.current.mutateAsync({
      id: "o-1",
      notes: "ok",
      expectedVersion: 1,
    });
    expect(order.status).toBe("APPROVED");
  });

  test("409 拋出 error(並發 race)", async () => {
    mock.onPost("/orders/o-1/approve").reply(409, {
      error: { code: "conflict", message_zh: "已被其他人處理" },
    });
    const { result } = renderHook(() => useApproveOrder(), {
      wrapper: makeWrapper(),
    });
    await expect(
      result.current.mutateAsync({ id: "o-1", expectedVersion: 1 }),
    ).rejects.toBeTruthy();
  });
});

describe("useRejectOrder", () => {
  test("帶 reason 必要參數", async () => {
    let sentBody: Record<string, unknown> | undefined;
    mock.onPost("/orders/o-1/reject").reply((cfg) => {
      sentBody = JSON.parse(cfg.data as string);
      return [
        200,
        {
          data: {
            id: "o-1",
            user_id: "u-1",
            symbol: "2330",
            market: "TWSE",
            side: "BUY",
            qty: 100,
            status: "REJECTED",
            version: 2,
            created_at: "2026-05-17T00:00:00Z",
          },
        },
      ];
    });
    const { result } = renderHook(() => useRejectOrder(), {
      wrapper: makeWrapper(),
    });
    const order = await result.current.mutateAsync({
      id: "o-1",
      reason: "信心不足",
    });
    expect(order.status).toBe("REJECTED");
    expect(sentBody?.reason).toBe("信心不足");
  });
});
