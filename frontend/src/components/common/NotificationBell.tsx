"use client";

import { useQuery } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { api, type ApiEnvelope } from "@/lib/api";
import type { NotificationLog } from "@/lib/api-types";
import { useAuthStore } from "@/store/auth";
import { cn } from "@/lib/utils";

/**
 * Topbar 通知 bell：30 秒一次輪詢「最近 5 筆 notification log」做 unread dot。
 * 沒有後端 unread state 也 OK — 我們把「過去 1 小時內 status=success 的訊息」當「有新事件」。
 * 點擊跳 /notifications。
 *
 * 沒登入時不 fetch；fetch 失敗靜默（不影響其他 UI）。
 */
export function NotificationBell() {
  const router = useRouter();
  const accessToken = useAuthStore((s) => s.accessToken);
  const { data } = useQuery({
    queryKey: ["notifications", "bell", "recent"],
    enabled: !!accessToken,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
    queryFn: async () => {
      try {
        const res = await api.get<ApiEnvelope<NotificationLog[]>>(
          "/notifications/logs",
          { params: { limit: 5 } },
        );
        return res.data.data ?? [];
      } catch {
        return [] as NotificationLog[];
      }
    },
  });

  const oneHourAgo = Date.now() - 60 * 60 * 1000;
  const hasRecent = (data ?? []).some((d) => {
    if (!d?.sent_at) return false;
    const t = new Date(d.sent_at).getTime();
    return Number.isFinite(t) && t > oneHourAgo;
  });

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={hasRecent ? "通知（有新訊息）" : "通知"}
      onClick={() => router.push("/notifications")}
      className="relative"
    >
      <Bell className="h-4 w-4" />
      {hasRecent ? (
        <span
          className={cn(
            "absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-bull ring-2 ring-background",
            "animate-pulse",
          )}
          aria-hidden
        />
      ) : null}
    </Button>
  );
}
