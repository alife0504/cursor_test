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

// /auth/login 本身就是「登入動作」,401 表示密碼錯誤,不要去 refresh
// /auth/refresh / /auth/logout 也不要(避免無窮迴圈)
const AUTH_PATHS_NO_REFRESH = ["/auth/login", "/auth/refresh", "/auth/logout"];

// 共用 in-flight refresh promise(mutex)——
// 多查詢頁面 token 過期時會同時噴 N 個 401。若每個都各自打 /auth/refresh,
// 後端 refresh token 是「單次輪替」,只有第一個成功、其餘拿到已輪替 token → 失敗 → logout。
// 用一個共用 promise 讓並發 401 共用同一次 refresh,徹底消除 refresh 風暴。
let refreshPromise: Promise<string> | null = null;

/**
 * 共用的 access token 刷新（mutex）。
 * AuthBootstrap 與 response interceptor 都應呼叫此函式，
 * 確保同一時間只有一個 /auth/refresh 在飛，避免 refresh token 輪替競態 / 重用偵測誤判。
 */
export function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = api
      .post("/auth/refresh", {}, { _isRefreshCall: true } as RetryConfig)
      .then((refresh) => {
        const newToken =
          (refresh.data as LoginEnvelope)?.data?.access_token ?? null;
        if (!newToken) throw new Error("refresh missing access_token");
        useAuthStore.getState().setAccessToken(newToken);
        return newToken;
      })
      .finally(() => {
        // 不論成功或失敗都釋放,讓下一輪過期可重新 refresh
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryConfig | undefined;

    // 不嘗試 refresh:沒 config / 已經 retry / refresh call 本身 / login/logout 動作
    if (!original || original._retry || original._isRefreshCall) {
      throw error;
    }
    if (error.response?.status !== 401) {
      throw error;
    }
    if (
      original.url &&
      AUTH_PATHS_NO_REFRESH.some((p) => original.url!.includes(p))
    ) {
      throw error;
    }

    original._retry = true;
    try {
      // 並發 401 共用同一個 refresh,避免 refresh token 輪替競態
      const newToken = await refreshAccessToken();
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
