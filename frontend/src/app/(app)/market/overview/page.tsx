"use client";

import { useState } from "react";

import { ChartContainer } from "@/components/common/ChartContainer";
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
  const { data, isLoading } = useMarketOverview(market);

  const idxObj = (data?.index ?? null) as Record<string, unknown> | null;
  const indexes =
    market === "TW"
      ? [
          {
            name: "加權指數",
            value:
              idxObj?.twse_close ?? idxObj?.close ?? idxObj?.value ?? null,
            changePct: idxObj?.twse_change_pct ?? idxObj?.change_pct ?? null,
          },
          {
            name: "櫃買指數",
            value: idxObj?.tpex_close ?? null,
            changePct: idxObj?.tpex_change_pct ?? null,
          },
        ]
      : [
          {
            name: "S&P 500",
            value: idxObj?.sp500_close ?? null,
            changePct: idxObj?.sp500_change_pct ?? null,
          },
          {
            name: "NASDAQ",
            value: idxObj?.nasdaq_close ?? null,
            changePct: idxObj?.nasdaq_change_pct ?? null,
          },
          {
            name: "Dow Jones",
            value: idxObj?.dow_close ?? null,
            changePct: idxObj?.dow_change_pct ?? null,
          },
        ];

  const adv = (data?.advancers as number | undefined) ?? 0;
  const dec = (data?.decliners as number | undefined) ?? 0;
  const unc = (data?.unchanged as number | undefined) ?? 0;
  // 紅漲綠跌 token：bull/bear hsl
  const pieData = [
    { name: "上漲", value: adv, fill: "hsl(var(--bull))" },
    { name: "下跌", value: dec, fill: "hsl(var(--bear))" },
    { name: "平盤", value: unc, fill: "hsl(var(--flat))" },
  ];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="市場總覽"
        description="大盤指數、漲跌家數、漲跌幅 / 成交量榜"
        actions={<MarketSwitcher value={market} onChange={setMarket} />}
      />

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
    </div>
  );
}
