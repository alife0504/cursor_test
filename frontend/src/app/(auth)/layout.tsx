"use client";

import {
  CandlestickChart,
  FileDown,
  LineChart,
  MessagesSquare,
  Moon,
  ShieldCheck,
  Sparkles,
  Sun,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { t } from "@/i18n/messages";

// Auth 版型（v1.0.2 重做）：全幅品牌靛藍漸層 + 置中浮層卡。
//  - 取代舊的生硬 50/50 切半：漸層填滿 16:9、卡片為一個整體單元置中。
//  - 左品牌 hero（lg+）/ 右白色表單卡；mobile 收合為單欄。
//  - 深邃靛藍漸層取代死黑；右上角 ThemeToggle。
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <div className="relative min-h-screen overflow-hidden bg-brand-gradient text-primary-foreground">
      {/* 裝飾光暈 — 讓漸層更有層次、不死板 */}
      <div className="pointer-events-none absolute -left-40 -top-40 h-[32rem] w-[32rem] rounded-full bg-[hsl(217_91%_60%/0.18)] blur-3xl" />
      <div className="pointer-events-none absolute -bottom-48 -right-24 h-[34rem] w-[34rem] rounded-full bg-[hsl(266_60%_55%/0.16)] blur-3xl" />

      {/* 右上角主題切換 */}
      <div className="absolute right-5 top-5 z-20">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label={t("topbar.theme.toggle")}
          className="text-primary-foreground/70 hover:bg-white/10 hover:text-primary-foreground"
        >
          {mounted && theme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* 置中浮層卡 */}
      <div className="relative z-10 flex min-h-screen items-center justify-center p-4 sm:p-8">
        <div className="grid w-full max-w-5xl overflow-hidden rounded-3xl shadow-2xl ring-1 ring-white/10 lg:grid-cols-[1.05fr_0.95fr]">
          {/* 左：品牌 hero（lg+） */}
          <aside className="relative hidden flex-col justify-between gap-10 p-10 lg:flex">
            <div className="flex items-center gap-2.5">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 ring-1 ring-inset ring-white/15 backdrop-blur">
                <CandlestickChart className="h-5 w-5" />
              </div>
              <div className="flex flex-col leading-tight">
                <span className="text-lg font-semibold">{t("app.title")}</span>
                <span className="text-[10px] uppercase tracking-[0.18em] opacity-60">
                  Secure Edition
                </span>
              </div>
            </div>

            <div>
              <span className="mb-5 inline-flex w-fit items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-medium tracking-wide text-primary-foreground/85 ring-1 ring-inset ring-white/15">
                <Sparkles className="h-3.5 w-3.5" /> 台股主 · 美股輔 · 自用級資安
              </span>
              <h2 className="text-balance text-[2.5rem] font-bold leading-[1.12]">
                多 Agent AI
                <br />
                投資分析平台
              </h2>
              <p className="mt-4 max-w-md text-sm leading-relaxed text-primary-foreground/70">
                技術面、基本面、新聞面、籌碼面四種 Analyst 跨市場辯論，Manager
                綜合決策；完整 audit hash chain 與手動核准下單。
              </p>
              <ul className="mt-8 space-y-3.5 text-sm">
                {[
                  { icon: LineChart, text: "4 種 Analyst 自動跑技術 / 財報 / 新聞 / 籌碼" },
                  { icon: MessagesSquare, text: "Bull / Bear 多輪辯論 + Manager 綜合結論" },
                  { icon: ShieldCheck, text: "JWT 輪替 · RBAC · Audit Hash Chain 不可竄改" },
                  { icon: FileDown, text: "PDF / MD / XLSX 匯出 + Discord / Telegram 通知" },
                ].map(({ icon: Icon, text }) => (
                  <li
                    key={text}
                    className="flex items-start gap-3 text-primary-foreground/90"
                  >
                    <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-white/10 ring-1 ring-inset ring-white/15">
                      <Icon className="h-3.5 w-3.5" />
                    </span>
                    <span className="leading-relaxed">{text}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="flex items-center gap-4 text-[11px] text-primary-foreground/50">
              <span>v1.0 · Self-hosted</span>
              <span className="h-3 w-px bg-white/15" />
              <span>改造自 TauricResearch/TradingAgents</span>
            </div>
          </aside>

          {/* 右：表單卡（白底，與深色左欄形成對照但同框呼應） */}
          <main className="flex flex-col justify-center bg-card p-8 text-foreground sm:p-10">
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
            <div className="mx-auto w-full max-w-sm animate-fade-in">
              {children}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
