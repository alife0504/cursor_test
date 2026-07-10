"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api, type ApiEnvelope } from "@/lib/api";
import type {
  NotificationLog,
  NotificationSettings,
  NotificationSettingsUpdate,
} from "@/lib/api-types";

// Phase 17 § N:通知設定 hooks
//   - GET /notifications/settings
//   - PUT /notifications/settings(部分欄位 = patch)
//   - POST /notifications/test
//   - GET /notifications/logs(cursor pagination)

export function useNotificationSettings(enabled = true) {
  return useQuery({
    queryKey: ["notifications", "settings"],
    enabled,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<NotificationSettings>>(
        "/notifications/settings",
      );
      return res.data.data;
    },
  });
}

export function useUpdateNotificationSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (patch: NotificationSettingsUpdate) => {
      const res = await api.put<ApiEnvelope<NotificationSettings>>(
        "/notifications/settings",
        patch,
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications", "settings"] });
    },
  });
}

export interface SendTestNotificationVars {
  channel: "discord" | "telegram";
  message: string;
  /** 是否僅寫測試紀錄不真正外送；預設 false＝實際發送（測試鈕本意就是驗證 webhook 可用） */
  dry_run?: boolean;
}

export function useSendTestNotification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: SendTestNotificationVars) => {
      // 後端 dry_run 預設 True（只寫 log 不外送）→ 測試永遠驗不到 webhook。
      // 明確帶 dry_run:false 讓「測試」真的送出到 Discord/Telegram。
      const res = await api.post<ApiEnvelope<NotificationLog>>(
        "/notifications/test",
        { dry_run: false, ...vars },
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications", "logs"] });
    },
  });
}

export interface UseNotificationLogsParams {
  cursor?: string | null;
  limit?: number;
  enabled?: boolean;
}

export function useNotificationLogs(params: UseNotificationLogsParams = {}) {
  const { cursor, limit = 50, enabled = true } = params;
  return useQuery({
    queryKey: ["notifications", "logs", { cursor, limit }],
    enabled,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<NotificationLog[]>>(
        "/notifications/logs",
        { params: { cursor: cursor || undefined, limit } },
      );
      return {
        items: res.data.data ?? [],
        nextCursor: res.data.pagination?.next_cursor ?? null,
        hasMore: res.data.pagination?.has_more ?? false,
      };
    },
  });
}
