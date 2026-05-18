/**
 * @vitest-environment jsdom
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// 先 mock api,再 import 受測模組
vi.mock("@/lib/api", () => {
  return {
    api: {
      post: vi.fn(),
    },
  };
});

import { api } from "@/lib/api";
import { useAnalysisWS } from "@/hooks/useWebSocket";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  readyState = 0;
  url: string;
  protocols: string | string[] | undefined;
  onopen: ((this: WebSocket, ev: Event) => unknown) | null = null;
  onmessage: ((this: WebSocket, ev: MessageEvent) => unknown) | null = null;
  onerror: ((this: WebSocket, ev: Event) => unknown) | null = null;
  onclose: ((this: WebSocket, ev: CloseEvent) => unknown) | null = null;
  sent: string[] = [];

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    this.protocols = protocols;
    MockWebSocket.instances.push(this);
    queueMicrotask(() => {
      this.readyState = 1;
      this.onopen?.call(this as unknown as WebSocket, new Event("open"));
    });
  }

  send(d: string) {
    this.sent.push(d);
  }

  close() {
    this.readyState = 3;
    this.onclose?.call(
      this as unknown as WebSocket,
      new CloseEvent("close"),
    );
  }
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("useAnalysisWS", () => {
  test("enabled=false 時不取 ticket、不連線", () => {
    renderHook(() => useAnalysisWS("aid-1", false));
    expect(api.post).not.toHaveBeenCalled();
    expect(MockWebSocket.instances).toHaveLength(0);
  });

  test("成功取 ticket 後建立 WS 連線並 open", async () => {
    (api.post as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: { data: { ticket: "tkt-xyz" } },
    });

    const { result } = renderHook(() => useAnalysisWS("aid-42", true));

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    const ws = MockWebSocket.instances[0];
    expect(ws.url).toContain("/api/v1/ws/analysis/aid-42");
    expect(ws.protocols).toEqual(["tradingagents.v1", "ticket.tkt-xyz"]);

    await waitFor(() => {
      expect(result.current.status).toBe("open");
    });
  });

  test("收到 message 累積到 events", async () => {
    (api.post as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: { data: { ticket: "tkt-1" } },
    });

    const { result } = renderHook(() => useAnalysisWS("aid-9", true));

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.onmessage?.call(
        ws as unknown as WebSocket,
        new MessageEvent("message", {
          data: JSON.stringify({ type: "tick", payload: { v: 1 } }),
        }),
      );
    });

    await waitFor(() => {
      expect(result.current.events).toHaveLength(1);
    });
    expect(result.current.events[0]).toMatchObject({ type: "tick" });
  });

  test("取 ticket 失敗 status 變 error", async () => {
    (api.post as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("boom"),
    );

    const { result } = renderHook(() => useAnalysisWS("aid-99", true));

    await waitFor(() => {
      expect(result.current.status).toBe("error");
    });
  });
});
