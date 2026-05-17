"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";

// Phase 15 § S:WebSocket 認證用 Subprotocol + 一次性 Ticket
//   - 先 POST /auth/ws-ticket 取 60s ticket
//   - 建 WS 時 subprotocols = ["tradingagents.v1", `ticket.${ticket}`]
//   - 後端 ws_router 會驗 ticket 並回應同樣的 subprotocol
//
// 用法:
//   const { events, status, send } = useAnalysisWS(analysisId, enabled);

export interface WSEvent<T = unknown> {
  type: string;
  payload?: T;
  ts?: string;
  trace_id?: string;
}

export type WSStatus = "idle" | "connecting" | "open" | "closed" | "error";

interface UseAnalysisWSResult<T> {
  events: WSEvent<T>[];
  status: WSStatus;
  send: (data: unknown) => void;
  close: () => void;
}

const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

interface WSTicketResponse {
  data?: { ticket?: string };
}

export function useAnalysisWS<T = unknown>(
  analysisId: string,
  enabled = true,
): UseAnalysisWSResult<T> {
  const [events, setEvents] = useState<WSEvent<T>[]>([]);
  const [status, setStatus] = useState<WSStatus>("idle");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled || !analysisId) return;

    let cancelled = false;
    setStatus("connecting");

    (async () => {
      try {
        const res = await api.post<WSTicketResponse>("/auth/ws-ticket");
        const ticket = res.data?.data?.ticket;
        if (!ticket) throw new Error("ws-ticket missing");

        if (cancelled) return;

        const url = `${WS_BASE_URL}/api/v1/ws/analysis/${analysisId}`;
        const ws = new WebSocket(url, [
          "tradingagents.v1",
          `ticket.${ticket}`,
        ]);
        wsRef.current = ws;

        ws.onopen = () => {
          if (!cancelled) setStatus("open");
        };
        ws.onmessage = (e) => {
          try {
            const parsed = JSON.parse(e.data) as WSEvent<T>;
            setEvents((prev) => [...prev, parsed]);
          } catch {
            // 收到非 JSON event,當作 raw text 包起來
            setEvents((prev) => [...prev, { type: "raw", payload: e.data as T }]);
          }
        };
        ws.onerror = () => {
          if (!cancelled) setStatus("error");
        };
        ws.onclose = () => {
          if (!cancelled) setStatus("closed");
        };
      } catch (err) {
        if (!cancelled) setStatus("error");
        // 不再 throw,UI 自己看 status 判斷
        // eslint-disable-next-line no-console
        console.error("[useAnalysisWS] ticket/connect failed", err);
      }
    })();

    return () => {
      cancelled = true;
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [analysisId, enabled]);

  const send = (data: unknown) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(typeof data === "string" ? data : JSON.stringify(data));
    }
  };

  const close = () => {
    wsRef.current?.close();
  };

  return { events, status, send, close };
}
