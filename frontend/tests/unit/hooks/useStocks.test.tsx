/**
 * @vitest-environment jsdom
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { useStocks } from "@/hooks/useStocks";
import { api } from "@/lib/api";

let mock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(api);
});

afterEach(() => {
  mock.restore();
});

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useStocks", () => {
  test("帶 q 參數會打 /stocks?q=", async () => {
    mock.onGet("/stocks").reply((cfg) => {
      expect(cfg.params).toMatchObject({ q: "2330" });
      return [
        200,
        {
          data: [
            {
              symbol: "2330",
              market: "TWSE",
              name: "台積電",
              is_active: true,
            },
          ],
          pagination: { has_more: false, next_cursor: null },
        },
      ];
    });
    const { result } = renderHook(() => useStocks({ q: "2330" }), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0].symbol).toBe("2330");
  });

  test("enabled=false 不會 fetch", () => {
    const { result } = renderHook(() => useStocks({}, false), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
  });

  test("錯誤狀態", async () => {
    mock.onGet("/stocks").reply(500, { error: "boom" });
    const { result } = renderHook(() => useStocks({ q: "x" }), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
