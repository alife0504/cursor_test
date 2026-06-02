"use client";

import { CandlestickChart, Moon, Sun, TrendingUp } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { t } from "@/i18n/messages";

// Auth 系列頁面通用 layout：左側品牌 hero（>= lg）+ 右側 card；mobile 直立。
// 右上角 ThemeToggle，允許登入前切換主題。
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <div className="relative grid min-h-screen grid-cols-1 lg:grid-cols-2">
      {/* 右上角主題切換（mobile / 兩欄都可見） */}
      <div className="absolute right-4 top-4 z-10">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label={t("topbar.theme.toggle")}
        >
          {mounted && theme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* 左欄：品牌 hero（lg+ 顯示） */}
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-primary p-10 text-primary-foreground lg:flex">
        <div className="absolute inset-0 bg-hero-mesh opacity-60" />
        <div className="relative z-10 flex items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-foreground/15 backdrop-blur">
            <CandlestickChart className="h-5 w-5" />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-lg font-semibold">{t("app.title")}</span>
            <span className="text-[10px] uppercase tracking-wider opacity-70">
              Secure Edition
            </span>
          </div>
        </div>

        <div className="relative z-10 space-y-4">
          <h2 className="text-3xl font-bold leading-tight">
            多 Agent AI<br />
            投資分析平台
          </h2>
          <p className="max-w-md text-sm leading-relaxed text-primary-foreground/80">
            台股主、美股輔。技術面、基本面、新聞面、籌碼面四種 Analyst
            跨市場辯論，Manager 綜合決策；完整 audit hash chain 與手動核准下單。
          </p>
          <ul className="space-y-2 text-sm">
            <li className="flex items-start gap-2 text-primary-foreground/90">
              <TrendingUp className="mt-0.5 h-4 w-4 text-bull-foreground/80" />
              <span>4 種 Analyst 自動跑指標 / 財報 / 新聞</span>
            </li>
            <li className="flex items-start gap-2 text-primary-foreground/90">
              <TrendingUp className="mt-0.5 h-4 w-4 text-bull-foreground/80" />
              <span>Bull / Bear 多輪辯論 + Manager 結論</span>
            </li>
            <li className="flex items-start gap-2 text-primary-foreground/90">
              <TrendingUp className="mt-0.5 h-4 w-4 text-bull-foreground/80" />
              <span>PDF / MD / XLSX 匯出 + LINE / Telegram 通知</span>
            </li>
          </ul>
        </div>

        <p className="relative z-10 text-[11px] text-primary-foreground/50">
          v1.0 · Self-hosted · 改造自 TauricResearch/TradingAgents v0.2.4
        </p>
      </aside>

      {/* 右欄：登入 / 註冊 表單 */}
      <main className="relative flex min-h-screen flex-col items-center justify-center bg-muted/30 px-4 py-12">
        {/* Mobile：頂部小品牌 */}
        <div className="mb-6 flex flex-col items-center gap-2 lg:hidden">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-glow">
            <CandlestickChart className="h-6 w-6" />
          </div>
          <div className="text-center">
            <h1 className="text-xl font-bold tracking-tight">
              {t("app.title")}
            </h1>
            <p className="text-sm text-muted-foreground">{t("app.tagline")}</p>
          </div>
        </div>
        <div className="w-full max-w-md animate-fade-in">{children}</div>
      </main>
    </div>
  );
}
