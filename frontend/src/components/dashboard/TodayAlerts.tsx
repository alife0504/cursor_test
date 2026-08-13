"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  Inbox,
  ShieldAlert,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { DateFormat } from "@/components/common/DateFormat";
import { EmptyState } from "@/components/common/EmptyState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { Badge } from "@/components/ui/badge";
import { api, type ApiEnvelope } from "@/lib/api";
import type { NotificationLog } from "@/lib/api-types";
import { cn } from "@/lib/utils";

interface AlertVisual {
  icon: LucideIcon;
  tone: string;
  badge: string;
  label: string;
}

function visualForEvent(event: string, status: string): AlertVisual {
  if (status && status.toLowerCase() === "failed") {
    return {
      icon: XCircle,
      tone: "text-destructive",
      badge: "bg-destructive/10 text-destructive",
      label: "送出失敗",
    };
  }
  switch (event) {
    case "analysis.completed":
      return {
        icon: CheckCircle2,
        tone: "text-success",
        badge: "bg-success/10 text-success",
        label: "分析完成",
      };
    case "analysis.failed":
      return {
        icon: XCircle,
        tone: "text-destructive",
        badge: "bg-destructive/10 text-destructive",
        label: "分析失敗",
      };
    case "order.approved":
      return {
        icon: CheckCircle2,
        tone: "text-bull",
        badge: "bg-bull-muted text-bull",
        label: "訂單核准",
      };
    case "order.rejected":
      return {
        icon: XCircle,
        tone: "text-bear",
        badge: "bg-bear-muted text-bear",
        label: "訂單拒絕",
      };
    case "system.alert":
      return {
        icon: ShieldAlert,
        tone: "text-warning",
        badge: "bg-warning/10 text-warning",
        label: "系統警示",
      };
    default:
      return {
        icon: AlertTriangle,
        tone: "text-muted-foreground",
        badge: "bg-muted text-muted-foreground",
        label: event,
      };
  }
}

function summarizePayload(p: unknown): string {
  if (!p || typeof p !== "object") return "";
  const obj = p as Record<string, unknown>;
  if (typeof obj.message === "string") return obj.message;
  if (typeof obj.symbol === "string") {
    const signal = typeof obj.signal === "string" ? ` · ${obj.signal}` : "";
    return `${obj.symbol}${signal}`;
  }
  if (typeof obj.title === "string") return obj.title;
  return "";
}

/**
 * Dashboard「今日重點」widget。
 * 取最近 5 筆 notification logs，過濾近 24h，依事件 type 著色。
 */
export function TodayAlerts({ limit = 5 }: { limit?: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard", "today-alerts", limit],
    staleTime: 30_000,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<NotificationLog[]>>(
        "/notifications/logs",
        { params: { limit: limit * 2 } },
      );
      return res.data.data ?? [];
    },
  });

  if (isLoading) return <LoadingSkeleton rows={3} />;
  if (error) {
    return (
      <p className="text-xs text-muted-foreground">
        通知服務暫不可用（這不影響主要分析功能）
      </p>
    );
  }

  const dayAgo = Date.now() - 24 * 60 * 60 * 1000;
  const items = (data ?? [])
    .filter((d) => {
      if (!d?.sent_at) return false;
      const t = new Date(d.sent_at).getTime();
      return Number.isFinite(t) && t > dayAgo;
    })
    .slice(0, limit);

  if (items.length === 0) {
    return (
      <EmptyState
        icon={Inbox}
        title="今日尚無新事件"
        description="分析完成、訂單核准與系統警示會出現在這裡"
        variant="inline"
      />
    );
  }

  return (
    <ul className="flex flex-col divide-y">
      {items.map((it) => {
        const v = visualForEvent(it.event_type, it.status);
        const Icon = v.icon;
        const summary = summarizePayload(it.payload);
        return (
          <li key={it.id} className="flex items-center gap-3 py-2.5">
            <div
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full ring-1 ring-border",
                v.badge,
              )}
            >
              <Icon className={cn("h-4 w-4", v.tone)} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className={cn("text-[10px]", v.badge)}>
                  {v.label}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  · <DateFormat value={it.sent_at} mode="relative" />
                </span>
              </div>
              {summary ? (
                <p className="mt-0.5 truncate text-sm">{summary}</p>
              ) : null}
            </div>
          </li>
        );
      })}
      <li className="pt-2 text-right">
        <Link
          href="/notifications"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <Bell className="h-3 w-3" /> 全部通知 →
        </Link>
      </li>
    </ul>
  );
}
