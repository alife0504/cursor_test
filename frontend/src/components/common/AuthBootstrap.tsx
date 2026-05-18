"use client";

import { useEffect } from "react";

import { api, type ApiEnvelope } from "@/lib/api";
import { useAuthStore, type AuthUser } from "@/store/auth";

// (app) layout 進入時:
//   - 若 access token 已有 → 不重複載 /me
//   - 否則靜默 refresh 取得 access token,再拉 /me
// 這樣 hard refresh / 直接訪問 deep link 時也能恢復登入狀態
export function AuthBootstrap() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const setAccessToken = useAuthStore((s) => s.setAccessToken);
  const setUser = useAuthStore((s) => s.setUser);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        if (!accessToken) {
          // 沒 token → 用 refresh cookie 換一個
          const r = await api.post<ApiEnvelope<{ access_token: string }>>(
            "/auth/refresh",
          );
          const token = r.data?.data?.access_token;
          if (token && !cancelled) setAccessToken(token);
        }
        if (!user) {
          const r = await api.get<ApiEnvelope<AuthUser>>("/auth/me");
          const me = r.data?.data;
          if (me && !cancelled) setUser(me);
        }
      } catch {
        // 失敗:interceptor 已經會處理 redirect
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
