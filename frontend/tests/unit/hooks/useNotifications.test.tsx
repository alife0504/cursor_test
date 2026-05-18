/**
 * @vitest-environment jsdom
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import MockAdapter from "axios-mock-adapter";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import {
  useNotificationLogs,
  useNotificationSettings,
  useSendTestNotification,
  useUpdateNotificationSettings,
} from "@/hooks/useNotifications";
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

describe("useNotificationSettings", () => {
  test("回傳設定物件(line_token_masked + enabled_events)", async () => {
    mock.onGet("/notifications/settings").reply(200, {
      data: {
        user_id: "u1",
        line_token_masked: "***abc",
        telegram_chat_id: null,
        email_enabled: false,
        enabled_events: ["analysis.completed"],
        updated_at: "2025-01-01T00:00:00Z",
      },
    });
    const { result } = renderHook(() => useNotificationSettings(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.line_token_masked).toBe("***abc");
    expect(result.current.data?.enabled_events).toContain("analysis.completed");
  });
});

describe("useUpdateNotificationSettings", () => {
  test("PUT body 包含 events 與 telegram_chat_id", async () => {
    let body: Record<string, unknown> | null = null;
    mock.onPut("/notifications/settings").reply((config) => {
      body = JSON.parse(config.data);
      return [200, { data: { user_id: "u1", email_enabled: false, updated_at: "2025-01-01T00:00:00Z" } }];
    });
    const { result } = renderHook(() => useUpdateNotificationSettings(), {
      wrapper: makeWrapper(),
    });
    await result.current.mutateAsync({
      telegram_chat_id: "12345",
      enabled_events: ["test"],
    });
    expect(body).not.toBeNull();
    expect(body!.telegram_chat_id).toBe("12345");
    expect(body!.enabled_events).toEqual(["test"]);
  });
});

describe("useSendTestNotification", () => {
  test("POST channel=line 成功", async () => {
    let body: Record<string, unknown> | null = null;
    mock.onPost("/notifications/test").reply((config) => {
      body = JSON.parse(config.data);
      return [
        200,
        {
          data: {
            id: 1,
            channel: "line",
            event_type: "test",
            payload: {},
            status: "sent",
            retry_count: 0,
            sent_at: "2025-01-01T00:00:00Z",
          },
        },
      ];
    });
    const { result } = renderHook(() => useSendTestNotification(), {
      wrapper: makeWrapper(),
    });
    const out = await result.current.mutateAsync({ channel: "line", message: "x" });
    expect(body!.channel).toBe("line");
    expect(out.status).toBe("sent");
  });
});

describe("useNotificationLogs", () => {
  test("回傳 items + pagination", async () => {
    mock.onGet("/notifications/logs").reply(200, {
      data: [
        {
          id: 1,
          channel: "line",
          event_type: "test",
          payload: {},
          status: "sent",
          retry_count: 0,
          sent_at: "2025-01-01T00:00:00Z",
        },
      ],
      pagination: { has_more: false },
    });
    const { result } = renderHook(() => useNotificationLogs(), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items.length).toBe(1);
    expect(result.current.data?.hasMore).toBe(false);
  });
});
