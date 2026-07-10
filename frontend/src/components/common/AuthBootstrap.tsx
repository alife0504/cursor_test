"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, refreshAccessToken, type ApiEnvelope } from "@/lib/api";
import { useAuthStore, type AuthUser } from "@/store/auth";

// (app) layout 進入時:
//   - 確保有 access token（沒有就用 refresh cookie 靜默換）
//   - **每次 mount 都重新抓 /me**：取得最新的 must_change_password / onboarding_completed 旗標。
//     若只在無 user 時抓，改密/onboarding 完成後 store 內是登入當下的陳舊旗標，守衛會把使用者
//     彈回改密頁造成死鎖。
export function AuthBootstrap() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const pathname = usePathname();
  const router = useRouter();
  // 守衛只在「本次 mount 重新抓到的新 /me」就緒後才動作，避免用陳舊旗標誤導向。
  const [meFresh, setMeFresh] = useState(false);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        if (!accessToken) {
          // 沒 token → 用 refresh cookie 換一個（走共用 mutex，與 interceptor 不互相競態）
          await refreshAccessToken();
        }
        const r = await api.get<ApiEnvelope<AuthUser>>("/auth/me");
        const me = r.data?.data;
        if (me && !cancelled) setUser(me);
      } catch {
        // 失敗:interceptor 已經會處理 redirect
      } finally {
        if (!cancelled) setMeFresh(true);
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 強制改密 / onboarding 守衛：middleware 只看 cookie 存在、後端不擋，之前可直接輸網址繞過。
  // 僅在最新 /me 就緒後依旗標強制導向，封鎖內頁。
  useEffect(() => {
    if (!meFresh || !user) return;
    if (user.must_change_password && pathname !== "/onboarding/change-password") {
      router.replace("/onboarding/change-password");
    } else if (
      user.onboarding_completed === false &&
      !pathname.startsWith("/onboarding")
    ) {
      router.replace("/onboarding");
    }
  }, [meFresh, user, pathname, router]);

  return null;
}
