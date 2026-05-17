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
  channel: "line" | "telegram";
  message: string;
}

export function useSendTestNotification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: SendTestNotificationVars) => {
      const res = await api.post<ApiEnvelope<NotificationLog>>(
        "/notifications/test",
        vars,
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
