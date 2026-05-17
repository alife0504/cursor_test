/**
 * @vitest-environment jsdom
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  useDLQ,
  useRequeueDLQ,
  useResolveDLQ,
  useSystemInfo,
} from "@/hooks/useSystem";
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

describe("useSystemInfo", () => {
  test("回傳版本 / env", async () => {
    mock.onGet("/admin/system/info").reply(200, {
      data: { version: "1.0.0", env: "dev", started_at: "2025-01-01T00:00:00Z" },
    });
    const { result } = renderHook(() => useSystemInfo(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.version).toBe("1.0.0");
    expect(result.current.data?.env).toBe("dev");
  });
});

describe("useDLQ", () => {
  test("預設拉 resolved=false", async () => {
    let params: Record<string, unknown> | null = null;
    mock.onGet("/admin/pipeline/dlq").reply((config) => {
      params = config.params;
      return [200, { data: [] }];
    });
    renderHook(() => useDLQ(), { wrapper: makeWrapper() });
    await waitFor(() => expect(params).not.toBeNull());
    expect(params!.resolved).toBe("false");
  });

  test("回傳 DLQ 陣列", async () => {
    mock.onGet("/admin/pipeline/dlq").reply(200, {
      data: [
        {
          id: 1,
          failed_at: "2025-01-01T00:00:00Z",
          task_name: "sync_ohlcv",
          retry_count: 3,
          resolved: false,
        },
      ],
    });
    const { result } = renderHook(() => useDLQ(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.length).toBe(1);
    expect(result.current.data?.[0].task_name).toBe("sync_ohlcv");
  });
});

describe("useResolveDLQ", () => {
  test("POST /resolve 帶 notes", async () => {
    let body: Record<string, unknown> | null = null;
    mock.onPost("/admin/pipeline/dlq/42/resolve").reply((config) => {
      body = JSON.parse(config.data);
      return [200, { data: { id: 42, failed_at: "2025-01-01T00:00:00Z", task_name: "x", retry_count: 0, resolved: true } }];
    });
    const { result } = renderHook(() => useResolveDLQ(), {
      wrapper: makeWrapper(),
    });
    await result.current.mutateAsync({ id: 42, notes: "fixed manually" });
    expect(body!.notes).toBe("fixed manually");
  });
});

describe("useRequeueDLQ", () => {
  test("POST /requeue 成功", async () => {
    mock.onPost("/admin/pipeline/dlq/7/requeue").reply(200, {
      data: { id: 7, failed_at: "2025-01-01T00:00:00Z", task_name: "x", retry_count: 0, resolved: false },
    });
    const { result } = renderHook(() => useRequeueDLQ(), {
      wrapper: makeWrapper(),
    });
    const out = await result.current.mutateAsync(7);
    expect(out.id).toBe(7);
  });
});
