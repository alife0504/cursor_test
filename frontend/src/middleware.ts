import { NextRequest, NextResponse } from "next/server";

// Phase 15 § H:路由保護
// 規則:
//   - 未登入(沒登入 cookie)→ 導到 /login
//   - 已登入但停留 auth 頁(login / forgot-password / reset-password) → 導到 /dashboard
//
// 注意:
//   - backend 把 refresh_token cookie 設在 path=/api/v1/auth(縮小攻擊面),
//     middleware 訪問 /dashboard 等路徑時讀不到。所以改看 csrf_token cookie:
//     它由 backend 與 refresh_token 同步寫入(login)/清除(logout),path=/,
//     middleware 拿得到 → 等價於登入狀態判斷。
//   - csrf_token 仍由 backend 設定,前端只是讀其存在性,不解析內容,
//     不影響 CSRF 防護(POST/PUT/DELETE 仍要求 X-CSRF-Token header)。
const AUTH_ROUTES = ["/login", "/forgot-password", "/reset-password"];
const PUBLIC_ROUTES = ["/healthz"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (PUBLIC_ROUTES.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // 雙重判斷:csrf_token(主) + refresh_token(若可見)
  const hasSession =
    !!req.cookies.get("csrf_token")?.value ||
    !!req.cookies.get("refresh_token")?.value;
  const isAuthRoute = AUTH_ROUTES.some((p) => pathname.startsWith(p));

  if (!hasSession && !isAuthRoute) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    if (pathname !== "/") {
      url.searchParams.set("next", pathname);
    }
    return NextResponse.redirect(url);
  }

  if (hasSession && isAuthRoute) {
    const url = req.nextUrl.clone();
    url.pathname = "/dashboard";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // 排除 _next 內部資源 / favicon / API rewrites / 靜態檔
    "/((?!_next/static|_next/image|favicon.ico|api/|robots.txt|sitemap.xml).*)",
  ],
};
