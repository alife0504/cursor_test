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
import {
  useMarketOverview,
  useRealtimeFutures,
  useRealtimeIndex,
  useRealtimeOverview,
} from "@/hooks/useMarket";
import type {
  IndexQuote,
  RealtimeQuote,
  RealtimeSnapshot,
} from "@/lib/api-types";

interface IndexCardData {
  name: string;
  value: string | number | null;
  /** 漲跌點數（對前一交易日收盤）。即時來源給 change，盤後來源給 change。 */
  change: string | number | null;
  changePct: string | number | null;
  subtitle: string | null;
}

/** as_of "2026-07-16 13:25:01.123" → "即時 · 13:25:01"；取不到時回「即時」。 */
function liveLabel(asOf?: string | null): string {
  const t = asOf && asOf.length >= 19 ? asOf.slice(11, 19) : null;
  return t ? `即時 · ${t}` : "即時";
}

/** 即時不可用時的小標，依 reason 給人看得懂的說明。 */
function unavailableLabel(snap?: RealtimeSnapshot): string {
  switch (snap?.reason) {
    case "disabled":
      return "即時未啟用";
    case "tier_insufficient":
      return "需 Sponsor";
    case "quota_exceeded":
      return "配額用盡";
    case "empty":
      return "非交易時段";
    default:
      return "收盤";
  }
}

/** 台指期近月：data_id=TXF 回多個月份契約 + R1/R2 連續合約。
 *
 *  首選 `TXFR1`＝官方「近月連續合約」，結算日會自動換到新契約、零維護（R2=次近月）；
 *  取不到才退回「當日累計成交量最大者」（近月一定量最大）。
 *  ⚠️ 不可用 `volume` 挑：那是該筆撮合量，實測每個契約都是 1，等於挑到回傳順序第一筆
 *  （常是總量 1、時間停在數小時前的死遠月契約）。累計量要看 `total_volume`。 */
function nearMonthFutures(snap?: RealtimeSnapshot): RealtimeQuote | null {
  if (!snap?.available || !snap.quotes?.length) return null;
  const r1 = snap.quotes.find((q) => q.symbol === "TXFR1");
  if (r1) return r1;
  return snap.quotes.reduce((best, q) =>
    (q.total_volume ?? 0) > (best.total_volume ?? 0) ? q : best,
  );
}

/**
 * 組出指數卡片：TW → 加權 / 櫃買 / 台指期（盤中即時覆蓋盤後值）；其他市場 → 盤後 indices。
 * 即時取不到（收盤 / 未開通 / 非交易時段）時自動退回盤後值，並在小標註明狀態。
 */
function buildIndexCards(
  market: "TW" | "US",
  eod: IndexQuote[],
  rtIndex?: RealtimeSnapshot,
  rtFutures?: RealtimeSnapshot,
): IndexCardData[] {
  if (market !== "TW") {
    return eod.map((q) => ({
      name: q.name,
      value: q.close ?? null,
      change: q.change ?? null,
      changePct: q.change_pct ?? null,
      subtitle: "收盤",
    }));
  }

  const eodBy = new Map(eod.map((q) => [q.symbol, q]));
  const rtBy = new Map(
    rtIndex?.available ? (rtIndex.quotes ?? []).map((q) => [q.symbol, q]) : [],
  );

  const indexCard = (symbol: string, name: string): IndexCardData => {
    const rt = rtBy.get(symbol);
    if (rt && rt.price != null) {
      return {
        name,
        value: rt.price,
        change: rt.change ?? null,
        changePct: rt.change_rate ?? null,
        subtitle: liveLabel(rtIndex?.as_of),
      };
    }
    const q = eodBy.get(symbol);
    return {
      name,
      value: q?.close ?? null,
      change: q?.change ?? null,
      changePct: q?.change_pct ?? null,
      subtitle: q?.close != null ? "收盤" : unavailableLabel(rtIndex),
    };
  };

  const fut = nearMonthFutures(rtFutures);
  const futuresCard: IndexCardData =
    fut && fut.price != null
      ? {
          name: "台指全",
          value: fut.price,
          change: fut.change ?? null,
          changePct: fut.change_rate ?? null,
          subtitle: liveLabel(rtFutures?.as_of),
        }
      : {
          name: "台指全",
          value: null,
          change: null,
          changePct: null,
          subtitle: unavailableLabel(rtFutures),
        };

  return [
    indexCard("TAIEX", "加權指數"),
    indexCard("TPEX", "櫃買指數"),
    futuresCard,
  ];
}

// 市場總覽
//   - TW：加權、櫃買、台指全（台指全全日即時、加權/櫃買盤中即時，每 5 秒更新）；US：S&P / NASDAQ / Dow（盤後）
//   - 漲跌家數 pie（紅漲綠跌）
//   - 漲幅 / 跌幅 / 成交量榜
export default function MarketOverviewPage() {
  const [market, setMarket] = useState<"TW" | "US">("TW");
  const { data, isLoading, error, refetch } = useMarketOverview(market);
  // 加權/櫃買盤中即時（收盤停輪詢）；台指全全日即時。僅 TW 啟用。
  const isTW = market === "TW";
  const rtIndex = useRealtimeIndex(isTW);
  // 台指全：日盤(08:45–13:45) + 夜盤(15:00–翌日05:00) 全時段即時，由 isTwFuturesOpen 判斷。
  // 不可用 allDay=true —— 那會短路成 24×7 恆真，週末凌晨也每 5 秒空打一次上游（期交所
  // 根本沒開盤、資料不會變），純燒配額並提高被 ip ban 的風險。
  const rtFutures = useRealtimeFutures(["TXF"], isTW, false);
  // 即時漲跌家數 / 總量（盤中；不可用時退回盤後 useMarketOverview）
  const rtOverview = useRealtimeOverview(isTW);

  const indexes = buildIndexCards(market, data?.indices ?? [], rtIndex.data, rtFutures.data);

  // 盤中有即時大盤就用即時值，否則用盤後
  const rt = rtOverview.data ?? null;
  const adv = rt?.advance_count ?? (data?.advance_count as number | undefined) ?? 0;
  const dec = rt?.decline_count ?? (data?.decline_count as number | undefined) ?? 0;
  const unc = rt?.unchanged_count ?? (data?.unchanged_count as number | undefined) ?? 0;
  const totalVolume = rt?.total_volume ?? data?.total_volume ?? null;
  const breadthLive = rt != null;
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
              value={i.value}
              change={i.change}
              changePct={i.changePct}
              subtitle={i.subtitle}
            />
          ))
        )}
      </section>

      <section className="grid gap-3 lg:grid-cols-2">
        <ChartContainer title="漲跌家數分佈" height={260}>
          <PieChart data={pieData} />
        </ChartContainer>
        <div className="rounded-lg border bg-card p-4">
          <h3 className="mb-2 flex items-center gap-2 text-sm font-medium">
            市場摘要
            {breadthLive ? (
              <span className="num text-[10px] font-normal text-bull/80">即時</span>
            ) : null}
          </h3>
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
              <dd className="num font-medium">{totalVolume ?? "—"}</dd>
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
