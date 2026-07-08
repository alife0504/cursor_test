import {
  Activity,
  AlertCircle,
  ListChecks,
  Sparkles,
  Star,
  TrendingUp,
} from "lucide-react";

import { Illustration } from "@/components/common/Illustration";
import { KpiRow } from "@/components/dashboard/KpiRow";
import { MarketIndexMiniChart } from "@/components/dashboard/MarketIndexMiniChart";
import { PendingOrders } from "@/components/dashboard/PendingOrders";
import { QuickActions } from "@/components/dashboard/QuickActions";
import { RecentAnalyses } from "@/components/dashboard/RecentAnalyses";
import { TodayAlerts } from "@/components/dashboard/TodayAlerts";
import { WatchlistMiniCards } from "@/components/dashboard/WatchlistMiniCards";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

function TodayString() {
  const d = new Date();
  return d.toLocaleDateString("zh-TW", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
}

function Greeting() {
  const h = new Date().getHours();
  if (h < 5) return "夜深了";
  if (h < 11) return "早安";
  if (h < 14) return "午安";
  if (h < 18) return "午後好";
  return "晚安";
}

// Dashboard：4-col KPI 牆 + 大盤趨勢 + 今日預警 + 最近分析 + 自選股 + 快速行動
export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      {/* 品牌 hero 橫幅：時段問候 + 多 Agent 網絡插畫（純顯示，資訊與原頁首等價） */}
      <section className="relative overflow-hidden rounded-2xl bg-brand-gradient px-6 py-6 text-primary-foreground shadow-lift sm:px-8">
        <div className="pointer-events-none absolute -right-12 -top-20 h-64 w-64 rounded-full bg-white/10 blur-3xl" />
        <Illustration
          name="agents"
          className="pointer-events-none absolute inset-y-3 right-4 hidden opacity-90 md:block"
        />
        <div className="relative z-10 md:pr-72">
          <span className="mb-2.5 inline-flex items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-0.5 text-[11px] font-medium tracking-wide text-primary-foreground/85 ring-1 ring-inset ring-white/15">
            <Sparkles className="h-3 w-3" /> 多 Agent AI 投資分析
          </span>
          <h1 className="text-2xl font-bold tracking-tight md:text-[26px]">
            {Greeting()}，歡迎回來
          </h1>
          <p className="mt-1 text-sm text-primary-foreground/70">
            今日 {TodayString()}：訊號、市場概況、待辦一次掌握
          </p>
        </div>
      </section>

      {/* 1. 頂部 KPI 牆 */}
      <KpiRow />

      {/* 2. 快速行動 */}
      <QuickActions />

      {/* 3. 主區：左欄（大盤趨勢 + 最近分析）｜右側欄（今日重點 + 待核准訂單）— 填滿 16:9、左右平衡 */}
      <section className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        {/* 左：主欄（2/3） */}
        <div className="flex flex-col gap-5 xl:col-span-2">
          <Card className="card-hover">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <TrendingUp className="h-4 w-4 text-primary" /> 大盤趨勢
              </CardTitle>
              <CardDescription>加權指數 / 漲跌家數 / 7-90 日</CardDescription>
            </CardHeader>
            <CardContent>
              <MarketIndexMiniChart />
            </CardContent>
          </Card>
          <Card className="card-hover">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <Activity className="h-4 w-4 text-info" /> 最近分析
              </CardTitle>
              <CardDescription>最後 6 筆 AI 分析結果</CardDescription>
            </CardHeader>
            <CardContent>
              <RecentAnalyses limit={6} />
            </CardContent>
          </Card>
        </div>

        {/* 右：側欄（1/3，堆疊填滿） */}
        <div className="flex flex-col gap-5">
          <Card className="card-hover">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <AlertCircle className="h-4 w-4 text-warning" /> 今日重點
              </CardTitle>
              <CardDescription>近 24 小時通知 / 警示</CardDescription>
            </CardHeader>
            <CardContent>
              <TodayAlerts limit={6} />
            </CardContent>
          </Card>
          <Card className="card-hover">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <ListChecks className="h-4 w-4 text-warning" /> 待核准訂單
              </CardTitle>
              <CardDescription>分析完成自動產生</CardDescription>
            </CardHeader>
            <CardContent>
              <PendingOrders limit={5} />
            </CardContent>
          </Card>
        </div>
      </section>

      {/* 5. 自選股 */}
      <Card className="card-hover">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Star className="h-4 w-4 text-bull" /> 自選股
          </CardTitle>
          <CardDescription>點擊任一檔開始新分析</CardDescription>
        </CardHeader>
        <CardContent>
          <WatchlistMiniCards limit={6} />
        </CardContent>
      </Card>
    </div>
  );
}
