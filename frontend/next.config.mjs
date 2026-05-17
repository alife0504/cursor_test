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

  // Phase 15:基礎安全標頭(prod 應再加 nonce-based CSP,目前 dev/prod 共用一份)
  async headers() {
    const isProd = process.env.NODE_ENV === "production";
    const csp = [
      "default-src 'self'",
      `script-src 'self' 'unsafe-inline'${isProd ? "" : " 'unsafe-eval'"}`,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https:",
      "font-src 'self' data:",
      "connect-src 'self' http: https: ws: wss:",
      "frame-ancestors 'none'",
    ].join("; ");
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Content-Security-Policy", value: csp },
        ],
      },
    ];
  },
};

export default nextConfig;
