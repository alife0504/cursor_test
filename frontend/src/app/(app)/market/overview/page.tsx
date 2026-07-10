"use client";

import { TrendingUp } from "lucide-react";
import { useState } from "react";

import { ChartContainer } from "@/components/common/ChartContainer";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { PieChart } from "@/components/common/PieChart";
import { IndexCard } from "@/components/market/IndexCard";
import { MarketSwitcher } from "@/components/market/MarketSwitcher";
import { MoversTable } from "@/components/market/MoversTable";
import { useMarketOverview } from "@/hooks/useMarket";

// 市場總覽
//   - TW：加權、櫃買；US：S&P / NASDAQ / Dow
//   - 漲跌家數 pie（紅漲綠跌）
//   - 漲幅 / 跌幅 / 成交量榜
export default function MarketOverviewPage() {
  const [market, setMarket] = useState<"TW" | "US">("TW");
  const { data, isLoading, error, refetch } = useMarketOverview(market);

  // 後端 indices 是 IndexQuote[]（已依 market 回對應指數）；直接 map，欄位名以後端為準。
  const indexes = (data?.indices ?? []).map((q) => ({
    name: q.name,
    value: q.close ?? null,
    changePct: q.change_pct ?? null,
  }));

  const adv = (data?.advance_count as number | undefined) ?? 0;
  const dec = (data?.decline_count as number | undefined) ?? 0;
  const unc = (data?.unchanged_count as number | undefined) ?? 0;
  // 紅漲綠跌 token：bull/bear hsl
  const pieData = [
    { name: "上漲", value: adv, fill: "hsl(var(--bull))" },
    { name: "下跌", value: dec, fill: "hsl(var(--bear))" },
    { name: "平盤", value: unc, fill: "hsl(var(--flat))" },
  ];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        icon={TrendingUp}
        title="市場總覽"
        description="大盤指數、漲跌家數、漲跌幅 / 成交量榜"
        actions={<MarketSwitcher value={market} onChange={setMarket} />}
      />

      {error && !data ? (
        // 載入失敗時給明確錯誤 + 重試，而非靜默顯示 0 家數/空 pie（誤導成「今日零波動」）
        <ErrorState
          title="市場總覽載入失敗"
          description="請稍後再試，或確認後端服務是否正常。"
          error={error}
          onRetry={() => {
            void refetch();
          }}
        />
      ) : (
        <>
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading ? (
          <LoadingSkeleton rows={3} />
        ) : (
          indexes.map((i) => (
            <IndexCard
              key={i.name}
              name={i.name}
              value={i.value as string | number | null}
              changePct={i.changePct as string | number | null}
            />
          ))
        )}
      </section>

      <section className="grid gap-3 lg:grid-cols-2">
        <ChartContainer title="漲跌家數分佈" height={260}>
          <PieChart data={pieData} />
        </ChartContainer>
        <div className="rounded-lg border bg-card p-4">
          <h3 className="mb-2 text-sm font-medium">市場摘要</h3>
          <dl className="space-y-1.5 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">上漲家數</dt>
              <dd className="num font-medium text-bull">{adv}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">下跌家數</dt>
              <dd className="num font-medium text-bear">{dec}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">平盤家數</dt>
              <dd className="num font-medium text-flat">{unc}</dd>
            </div>
            <div className="flex justify-between border-t pt-1.5">
              <dt className="text-muted-foreground">總成交量</dt>
              <dd className="num font-medium">{data?.total_volume ?? "—"}</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="grid gap-3 lg:grid-cols-3">
        <div className="space-y-2">
          <h3 className="text-sm font-medium">漲幅榜</h3>
          <MoversTable type="gainers" market={market} />
        </div>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">跌幅榜</h3>
          <MoversTable type="losers" market={market} />
        </div>
        <div className="space-y-2">
          <h3 className="text-sm font-medium">成交量榜</h3>
          <MoversTable type="volume" market={market} />
        </div>
      </section>
        </>
      )}
    </div>
  );
}
