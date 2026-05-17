/**
 * @vitest-environment jsdom
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  useAddWatchlist,
  useDeleteWatchlist,
  useUpdateWatchlist,
  useWatchlist,
} from "@/hooks/useWatchlist";
import { api } from "@/lib/api";

let mock: MockAdapter;

beforeEach(() => {
  mock = new MockAdapter(api);
});

afterEach(() => {
  mock.restore();
});

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function W({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("useWatchlist", () => {
  test("回傳 list 陣列", async () => {
    mock.onGet("/watchlist").reply(200, {
      data: [
        {
          id: "w-1",
          user_id: "u-1",
          symbol: "2330",
          market: "TWSE",
          sort_order: 0,
          created_at: "2026-05-17T00:00:00Z",
        },
      ],
    });
    const { result } = renderHook(() => useWatchlist(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].symbol).toBe("2330");
  });
});

describe("useAddWatchlist", () => {
  test("成功新增 → 回傳新 item", async () => {
    mock.onPost("/watchlist").reply(201, {
      data: {
        id: "w-2",
        user_id: "u-1",
        symbol: "AAPL",
        market: "NYSE",
        sort_order: 1,
        created_at: "2026-05-17T00:00:00Z",
      },
    });
    const { result } = renderHook(() => useAddWatchlist(), {
      wrapper: makeWrapper(),
    });
    const item = await result.current.mutateAsync({
      symbol: "AAPL",
      market: "NYSE",
    });
    expect(item.symbol).toBe("AAPL");
  });
});

describe("useUpdateWatchlist", () => {
  test("PATCH /watchlist/{id}", async () => {
    mock.onPatch("/watchlist/w-1").reply(200, {
      data: {
        id: "w-1",
        user_id: "u-1",
        symbol: "2330",
        market: "TWSE",
        notes: "new",
        sort_order: 0,
        created_at: "2026-05-17T00:00:00Z",
      },
    });
    const { result } = renderHook(() => useUpdateWatchlist(), {
      wrapper: makeWrapper(),
    });
    const item = await result.current.mutateAsync({
      id: "w-1",
      body: { notes: "new" },
    });
    expect(item.notes).toBe("new");
  });
});

describe("useDeleteWatchlist", () => {
  test("DELETE /watchlist/{id}", async () => {
    mock.onDelete("/watchlist/w-1").reply(200, { data: { ok: true } });
    const { result } = renderHook(() => useDeleteWatchlist(), {
      wrapper: makeWrapper(),
    });
    const id = await result.current.mutateAsync("w-1");
    expect(id).toBe("w-1");
  });
});
