/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,

  // Phase 15:把 /api/v1 Proxy 到 backend,解決 dev 跨 port cookie 共享問題
  // prod 由 nginx 統一,因此 BACKEND_INTERNAL_URL 也可指 nginx 內部位址
  async rewrites() {
    const backendUrl = process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";
    return [
      { source: "/api/v1/:path*", destination: `${backendUrl}/api/v1/:path*` },
    ];
  },

  // Phase 18:安全標頭 + CSP
  // - dev: 寬鬆,允許 unsafe-eval(Next.js HMR / SWC dev mode 必要)
  // - prod: CSP 由 backend SecurityHeadersMiddleware 下 per-request nonce
  //         前端不再下重複的 CSP header,避免雙重設定衝突
  async headers() {
    const isProd = process.env.NODE_ENV === "production";
    const baseHeaders = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      {
        key: "Permissions-Policy",
        value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
      },
    ];
    if (!isProd) {
      const cspDev = [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: https:",
        "font-src 'self' data:",
        "connect-src 'self' http: https: ws: wss:",
        "frame-ancestors 'none'",
      ].join("; ");
      baseHeaders.push({
        key: "Content-Security-Policy",
        value: cspDev,
      });
    }
    return [
      {
        source: "/(.*)",
        headers: baseHeaders,
      },
    ];
  },
};

export default nextConfig;
