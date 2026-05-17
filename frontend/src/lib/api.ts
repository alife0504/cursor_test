"use client";

import axios, {
  type AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from "axios";

import { getCookie } from "@/lib/cookies";
import { useAuthStore } from "@/store/auth";

// Phase 15 § E:axios 實例
// - 預設 baseURL 是 /api/v1(相對路徑),走 next.config rewrites Proxy 到 backend
// - withCredentials=true 才能帶 refresh / csrf cookie
// - request interceptor 自動帶 access token + CSRF header
// - response interceptor 401 自動 refresh + 重試(僅一次,避免無限迴圈)

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1";

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  timeout: 30_000,
});

const MUTATING_METHODS = /^(post|put|patch|delete)$/i;

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  if (config.method && MUTATING_METHODS.test(config.method)) {
    const csrf = getCookie("csrf_token");
    if (csrf) {
      config.headers["X-CSRF-Token"] = csrf;
    }
  }
  return config;
});

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
  _isRefreshCall?: boolean;
}

interface LoginEnvelope {
  data?: { access_token?: string };
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryConfig | undefined;

    // 不嘗試 refresh:沒 config / 已經 retry / refresh call 本身失敗
    if (!original || original._retry || original._isRefreshCall) {
      throw error;
    }
    if (error.response?.status !== 401) {
      throw error;
    }

    original._retry = true;
    try {
      const refresh = await api.post(
        "/auth/refresh",
        {},
        { _isRefreshCall: true } as RetryConfig,
      );
      const newToken =
        (refresh.data as LoginEnvelope)?.data?.access_token ?? null;
      if (!newToken) throw new Error("refresh missing access_token");

      useAuthStore.getState().setAccessToken(newToken);
      original.headers.Authorization = `Bearer ${newToken}`;
      return api(original);
    } catch (refreshErr) {
      useAuthStore.getState().logout();
      if (typeof window !== "undefined") {
        const next = encodeURIComponent(
          window.location.pathname + window.location.search,
        );
        window.location.href = `/login?next=${next}`;
      }
      throw refreshErr;
    }
  },
);

// 後端統一的 envelope: { data, meta, pagination? }
export interface ApiEnvelope<T> {
  data: T;
  meta?: {
    trace_id?: string;
    version?: string;
    timestamp?: string;
  };
  pagination?: {
    next_cursor?: string | null;
    limit?: number;
    has_more?: boolean;
  };
}
