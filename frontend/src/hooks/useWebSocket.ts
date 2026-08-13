"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";

// Phase 15 § S:WebSocket 認證用 Subprotocol + 一次性 Ticket
//   - 先 POST /auth/ws-ticket 取 60s ticket
//   - 建 WS 時 subprotocols = ["tradingagents.v1", `ticket.${ticket}`]
//   - 後端 ws_router 會驗 ticket 並回應同樣的 subprotocol
//
// 連線韌性:
//   - onclose / 連線失敗 → 指數退避自動重連（每次重新取 ticket；一次性不可重用）
//   - 後端每 30s 送 {"event":"heartbeat"} 保活 → 前端直接忽略,不進 events
//   - events 僅保留最近 MAX_EVENTS 筆,避免長分析無上限累積
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

// WS 不走 Next rewrites（HTTP proxy 不保證 upgrade），直連後端。
// 未設 NEXT_PUBLIC_WS_URL 時用瀏覽器當前 hostname + 後端預設 port 8000 推導,
// 讓「非本機瀏覽（區網/容器對外）」也能連上,而不是烤死 localhost。
function resolveWsBase(): string {
  if (process.env.NEXT_PUBLIC_WS_URL) return process.env.NEXT_PUBLIC_WS_URL;
  if (typeof window !== "undefined") {
    const isHttps = window.location.protocol === "https:";
    const proto = isHttps ? "wss" : "ws";
    // https（prod，通常在 nginx 後、以 path 反代 /api/v1/ws）→ 同源、不帶 :8000（否則連
    // wss://host:8000，該 port 對外未開 → 連線被拒、即時進度凍住）。
    // http（dev，後端直接發佈 8000）→ 帶 :8000。
    return isHttps
      ? `${proto}://${window.location.host}`
      : `${proto}://${window.location.hostname}:8000`;
  }
  return "ws://localhost:8000";
}

const MAX_EVENTS = 500;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_BASE_DELAY_MS = 1_000;
const RECONNECT_MAX_DELAY_MS = 15_000;

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
  // 使用者主動 close() 後不再自動重連
  const manuallyClosedRef = useRef(false);

  useEffect(() => {
    if (!enabled || !analysisId) return;

    let cancelled = false;
    let attempt = 0;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    manuallyClosedRef.current = false;

    const scheduleReconnect = () => {
      if (cancelled || manuallyClosedRef.current) return;
      if (attempt >= MAX_RECONNECT_ATTEMPTS) return; // 放棄:5s 輪詢兜底
      attempt += 1;
      const delay = Math.min(
        RECONNECT_BASE_DELAY_MS * 2 ** (attempt - 1),
        RECONNECT_MAX_DELAY_MS,
      );
      retryTimer = setTimeout(() => void connect(), delay);
    };

    const connect = async () => {
      if (cancelled || manuallyClosedRef.current) return;
      setStatus("connecting");
      try {
        // ticket 一次性 + 60s TTL → 每次(重)連都要重新取
        const res = await api.post<WSTicketResponse>("/auth/ws-ticket");
        const ticket = res.data?.data?.ticket;
        if (!ticket) throw new Error("ws-ticket missing");

        if (cancelled || manuallyClosedRef.current) return;

        const url = `${resolveWsBase()}/api/v1/ws/analysis/${analysisId}`;
        const ws = new WebSocket(url, [
          "tradingagents.v1",
          `ticket.${ticket}`,
        ]);
        wsRef.current = ws;

        ws.onopen = () => {
          if (cancelled) return;
          attempt = 0; // 連上就重置退避計數
          setStatus("open");
        };
        ws.onmessage = (e) => {
          try {
            // 後端 streaming.py 送的是 { event, data, ts }；統一正規化成
            // { type, payload, ts } 讓 buildFlowNodes / 詳情頁的 e.type / e.payload 真的讀得到。
            const raw = JSON.parse(e.data) as Record<string, unknown>;
            const type = (raw.type ?? raw.event ?? "unknown") as string;
            if (type === "heartbeat") return; // 保活訊息,不進 events
            const normalized: WSEvent<T> = {
              type,
              payload: (raw.payload ?? raw.data) as T,
              ts: raw.ts as string | undefined,
              trace_id: raw.trace_id as string | undefined,
            };
            setEvents((prev) => [...prev.slice(-(MAX_EVENTS - 1)), normalized]);
          } catch {
            // 收到非 JSON event,當作 raw text 包起來
            setEvents((prev) => [
              ...prev.slice(-(MAX_EVENTS - 1)),
              { type: "raw", payload: e.data as T },
            ]);
          }
        };
        ws.onerror = () => {
          if (!cancelled) setStatus("error");
        };
        ws.onclose = () => {
          if (cancelled) return;
          setStatus("closed");
          scheduleReconnect();
        };
      } catch (err) {
        if (cancelled) return;
        setStatus("error");
        // ticket 取得失敗（後端重啟中等）也走重連退避
        scheduleReconnect();
        // eslint-disable-next-line no-console
        console.error("[useAnalysisWS] ticket/connect failed", err);
      }
    };

    void connect();

    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
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
    manuallyClosedRef.current = true;
    wsRef.current?.close();
  };

  return { events, status, send, close };
}
