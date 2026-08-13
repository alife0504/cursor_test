/**
 * @vitest-environment jsdom
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  useAnalysisDetail,
  useAnalysisList,
  useCreateAnalysis,
} from "@/hooks/useAnalysis";
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

describe("useAnalysisList", () => {
  test("拿 list + pagination", async () => {
    mock.onGet("/analysis").reply(200, {
      data: [
        {
          id: "a-1",
          symbol: "2330",
          market: "TWSE",
          status: "completed",
          signal: "BUY",
          total_tokens: 0,
          total_cost_usd: "0.01",
          version: 1,
          created_at: "2026-05-17T00:00:00Z",
        },
      ],
      pagination: { has_more: true, next_cursor: "cur-1" },
    });
    const { result } = renderHook(() => useAnalysisList(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.hasMore).toBe(true);
    expect(result.current.data?.nextCursor).toBe("cur-1");
  });
});

describe("useAnalysisDetail", () => {
  test("id 為 null 時不 fetch", () => {
    const { result } = renderHook(() => useAnalysisDetail(null), {
      wrapper: makeWrapper(),
    });
    expect(result.current.fetchStatus).toBe("idle");
  });

  test("拿 detail 物件", async () => {
    mock.onGet("/analysis/a-1").reply(200, {
      data: {
        id: "a-1",
        user_id: "u-1",
        symbol: "2330",
        market: "TWSE",
        status: "completed",
        total_tokens: 100,
        total_cost_usd: "0.05",
        version: 1,
        created_at: "2026-05-17T00:00:00Z",
      },
    });
    const { result } = renderHook(() => useAnalysisDetail("a-1"), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe("a-1");
  });
});

describe("useCreateAnalysis", () => {
  test("POST 時帶 Idempotency-Key header", async () => {
    let receivedKey: string | undefined;
    mock.onPost("/analysis").reply((cfg) => {
      receivedKey = (cfg.headers as Record<string, string> | undefined)?.[
        "Idempotency-Key"
      ];
      return [
        201,
        { data: { analysis_id: "a-new", status: "queued", estimated_seconds: 180 } },
      ];
    });
    const { result } = renderHook(() => useCreateAnalysis(), {
      wrapper: makeWrapper(),
    });
    const res = await result.current.mutateAsync({
      body: {
        symbol: "2330",
        analyst_types: ["market"],
        llm_model: "gemini-2.0-flash",
        debate_rounds: 1,
      },
      idempotencyKey: "key-abc",
    });
    expect(res.analysis_id).toBe("a-new");
    expect(receivedKey).toBe("key-abc");
  });

  test("402 (quota exceeded) 會拋", async () => {
    mock.onPost("/analysis").reply(402, {
      error: { code: "quota_exceeded" },
    });
    const { result } = renderHook(() => useCreateAnalysis(), {
      wrapper: makeWrapper(),
    });
    await expect(
      result.current.mutateAsync({
        body: {
          symbol: "2330",
          analyst_types: ["market"],
          llm_model: "gemini-2.0-flash",
          debate_rounds: 1,
        },
        idempotencyKey: "key-abc",
      }),
    ).rejects.toBeTruthy();
  });
});
