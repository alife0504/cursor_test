import {
  Activity,
  ListChecks,
  Star,
  TrendingUp,
} from "lucide-react";

import { MarketIndexMiniChart } from "@/components/dashboard/MarketIndexMiniChart";
import { PendingOrders } from "@/components/dashboard/PendingOrders";
import { QuotaProgress } from "@/components/dashboard/QuotaProgress";
import { RecentAnalyses } from "@/components/dashboard/RecentAnalyses";
import { WatchlistMiniCards } from "@/components/dashboard/WatchlistMiniCards";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

// Phase 16 § B:儀表板主頁
//   - 5 個 section 各自 React Query parallel fetch
//   - 每個 section 自管 loading / empty / error
export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">儀表板</h1>
        <p className="text-sm text-muted-foreground">
          今日重點訊號、待辦、市場摘要
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="h-4 w-4" /> 大盤指數
            </CardTitle>
            <CardDescription>台股加權與漲跌家數</CardDescription>
          </CardHeader>
          <CardContent>
            <MarketIndexMiniChart />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="h-4 w-4" /> LLM 月用量
            </CardTitle>
            <CardDescription>含全部 analyst / debate / report</CardDescription>
          </CardHeader>
          <CardContent>
            <QuotaProgress />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <ListChecks className="h-4 w-4" /> 待核准訂單
            </CardTitle>
            <CardDescription>分析完成後自動產生</CardDescription>
          </CardHeader>
          <CardContent>
            <PendingOrders limit={5} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Star className="h-4 w-4" /> 自選股
          </CardTitle>
          <CardDescription>點擊任一檔開始新分析</CardDescription>
        </CardHeader>
        <CardContent>
          <WatchlistMiniCards limit={6} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Activity className="h-4 w-4" /> 最近分析
          </CardTitle>
          <CardDescription>最後 5 筆</CardDescription>
        </CardHeader>
        <CardContent>
          <RecentAnalyses limit={5} />
        </CardContent>
      </Card>
    </div>
  );
}
