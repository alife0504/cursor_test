import type { Metadata } from "next";
import { Noto_Sans_TC } from "next/font/google";

import { Providers } from "@/lib/providers";
import { cn } from "@/lib/utils";

import "./globals.css";

const notoSansTC = Noto_Sans_TC({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "TradingAgents-TW",
  description: "台股 / 美股 AI 多智能體交易分析",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-TW" suppressHydrationWarning>
      <body
        className={cn(
          notoSansTC.variable,
          "min-h-screen bg-background font-sans antialiased",
        )}
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
