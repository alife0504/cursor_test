/**
 * @vitest-environment jsdom
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { useScreener } from "@/hooks/useScreener";
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

describe("useScreener", () => {
  test("回傳 items + pagination", async () => {
    mock.onGet("/screener").reply(200, {
      data: [
        { symbol: "2330", name: "台積電", pe: "23.4" },
        { symbol: "2317", name: "鴻海", pe: "11.2" },
      ],
      pagination: { has_more: true, next_cursor: "cursor1" },
    });
    const { result } = renderHook(() => useScreener({ market: "TW" }), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items.length).toBe(2);
    expect(result.current.data?.hasMore).toBe(true);
    expect(result.current.data?.nextCursor).toBe("cursor1");
  });

  test("filter params 正確傳給後端", async () => {
    let lastConfig: { url?: string; params?: Record<string, unknown> } | null = null;
    mock.onGet("/screener").reply((config) => {
      lastConfig = { url: config.url, params: config.params };
      return [200, { data: [] }];
    });
    const { result } = renderHook(
      () =>
        useScreener({
          market: "TW",
          PE_min: 5,
          PE_max: 20,
          dividend_yield_min: 3,
          RSI_min: 30,
        }),
      { wrapper: makeWrapper() },
    );
    await waitFor(() => expect(result.current.isFetched).toBe(true));
    expect(lastConfig).not.toBeNull();
    expect(lastConfig!.params?.PE_min).toBe(5);
    expect(lastConfig!.params?.PE_max).toBe(20);
    expect(lastConfig!.params?.dividend_yield_min).toBe(3);
    expect(lastConfig!.params?.RSI_min).toBe(30);
    expect(lastConfig!.params?.market).toBe("TW");
  });

  test("無 pagination 時預設 hasMore=false", async () => {
    mock.onGet("/screener").reply(200, { data: [] });
    const { result } = renderHook(() => useScreener(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.hasMore).toBe(false);
    expect(result.current.data?.nextCursor).toBeNull();
  });
});
