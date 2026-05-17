/**
 * @vitest-environment jsdom
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  useInstitutional,
  useStockAnnouncements,
  useStockNews,
} from "@/hooks/useNews";
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

describe("useInstitutional", () => {
  test("回傳 date + rows", async () => {
    mock.onGet("/market/institutional").reply(200, {
      data: {
        date: "2025-01-15",
        rows: [
          {
            symbol: "2330",
            date: "2025-01-15",
            foreign_net: "100000",
            trust_net: "50000",
            dealer_net: "10000",
          },
        ],
      },
    });
    const { result } = renderHook(() => useInstitutional(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.date).toBe("2025-01-15");
    expect(result.current.data?.rows.length).toBe(1);
  });
});

describe("useStockNews", () => {
  test("沒給 symbol 時 disabled", async () => {
    const { result } = renderHook(() => useStockNews({ symbol: "" }), {
      wrapper: makeWrapper(),
    });
    // disabled hooks: isFetching=false 一直保持
    expect(result.current.isFetching).toBe(false);
  });

  test("有 symbol 時呼叫 /stocks/<sym>/news", async () => {
    mock.onGet("/stocks/2330/news").reply(200, {
      data: [
        {
          title: "TSMC Q4 beats",
          published_at: "2025-01-10T00:00:00Z",
          source: "Reuters",
          sentiment_label: "very_positive",
        },
      ],
    });
    const { result } = renderHook(() => useStockNews({ symbol: "2330" }), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0].title).toBe("TSMC Q4 beats");
  });
});

describe("useStockAnnouncements", () => {
  test("無 symbol 時 disabled", () => {
    const { result } = renderHook(
      () => useStockAnnouncements({ symbol: "" }),
      { wrapper: makeWrapper() },
    );
    expect(result.current.isFetching).toBe(false);
  });

  test("有 symbol 時呼叫 /stocks/<sym>/announcements", async () => {
    mock.onGet("/stocks/AAPL/announcements").reply(200, {
      data: [
        { title: "Apple files 10-K", type: "10-K", published_at: "2025-01-10T00:00:00Z" },
      ],
    });
    const { result } = renderHook(
      () => useStockAnnouncements({ symbol: "AAPL" }),
      { wrapper: makeWrapper() },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.[0].title).toContain("Apple");
  });
});
