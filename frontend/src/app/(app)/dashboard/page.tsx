import {
  Activity,
  AlertCircle,
  ListChecks,
  Star,
  TrendingUp,
} from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
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

// Dashboard：4-col KPI 牆 + 大盤趨勢 + 今日預警 + 最近分析 + 自選股 + 快速行動
export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="儀表板"
        description={
          <span>
            今日 <span className="text-foreground">{TodayString()}</span>
            ：訊號、市場概況、待辦
          </span>
        }
      />

      {/* 1. 頂部 KPI 牆 */}
      <KpiRow />

      {/* 2. 快速行動 */}
      <QuickActions />

      {/* 3. 大盤趨勢 + 今日預警 雙欄 */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2 card-hover">
          <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <TrendingUp className="h-4 w-4 text-primary" /> 大盤趨勢
              </CardTitle>
              <CardDescription>加權指數 / 漲跌家數 / 7-90 日</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <MarketIndexMiniChart />
          </CardContent>
        </Card>

        <Card className="card-hover">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertCircle className="h-4 w-4 text-warning" /> 今日重點
            </CardTitle>
            <CardDescription>近 24 小時通知 / 警示</CardDescription>
          </CardHeader>
          <CardContent>
            <TodayAlerts limit={5} />
          </CardContent>
        </Card>
      </section>

      {/* 4. 最近分析 / 待核准訂單 */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="card-hover">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="h-4 w-4 text-info" /> 最近分析
            </CardTitle>
            <CardDescription>最後 5 筆</CardDescription>
          </CardHeader>
          <CardContent>
            <RecentAnalyses limit={5} />
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
