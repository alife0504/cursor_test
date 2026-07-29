"use client";

import { TrendingUp } from "lucide-react";
import { useState } from "react";

import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { IndexCard } from "@/components/market/IndexCard";
import { IntradayChart } from "@/components/market/IntradayChart";
import { MarketBreadthCard } from "@/components/market/MarketBreadthCard";
import { MarketSwitcher } from "@/components/market/MarketSwitcher";
import { MoversTable } from "@/components/market/MoversTable";
import { SectorHeatmap } from "@/components/market/SectorHeatmap";
import {
  nearMonthFutures,
  useHeatmap,
  useIntraday,
  useMarketOverview,
  useRealtimeForeign,
  useRealtimeFutures,
  useRealtimeIndex,
  useRealtimeOverview,
  useRealtimeStock,
} from "@/hooks/useMarket";
import type { IndexQuote, RealtimeSnapshot } from "@/lib/api-types";

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

// 台指期近月契約挑選邏輯移至 hooks/useMarket 的 nearMonthFutures（與儀表板共用）

/** as_of（UTC iso）→「延遲 · HH:MM」台北時間；海外 yfinance 延遲 ~15 分。 */
function delayLabel(asOf?: string | null): string {
  if (!asOf) return "延遲報價";
  const d = new Date(asOf);
  if (Number.isNaN(d.getTime())) return "延遲報價";
  const hm = d.toLocaleTimeString("zh-TW", {
    timeZone: "Asia/Taipei",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  return `延遲 · ${hm}`;
}

/**
 * 組出指數卡片。
 * TW → 8 張：加權 / 台指全 / 道瓊期貨 / 那斯達克期貨 / 費半 / 韓國 / 日經 / 台積電。
 *   台股 3 張（加權/台指全/台積電）真 5 秒即時；海外 5 張 yfinance 延遲（卡片標「延遲·時間」）。
 * US → 盤後 indices（維持原樣）。
 */
function buildIndexCards(
  market: "TW" | "US",
  eod: IndexQuote[],
  rtIndex?: RealtimeSnapshot,
  rtFutures?: RealtimeSnapshot,
  rtForeign?: RealtimeSnapshot,
  rtTsmc?: RealtimeSnapshot,
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

  // 台股指數（加權）：即時覆蓋盤後
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

  // 台指全（近月期貨）
  const fut = nearMonthFutures(rtFutures);
  const futuresCard: IndexCardData = fut?.price != null
    ? { name: "台指全", value: fut.price, change: fut.change ?? null, changePct: fut.change_rate ?? null, subtitle: liveLabel(rtFutures?.as_of) }
    : { name: "台指全", value: null, change: null, changePct: null, subtitle: unavailableLabel(rtFutures) };

  // 海外指數（yfinance 延遲）：以 yfinance 代碼取值
  const fBy = new Map((rtForeign?.quotes ?? []).map((q) => [q.symbol, q]));
  const foreignCard = (symbol: string, fallbackName: string): IndexCardData => {
    const q = fBy.get(symbol);
    if (q && q.price != null) {
      return {
        name: q.name ?? fallbackName,
        value: q.price,
        change: q.change ?? null,
        changePct: q.change_rate ?? null,
        subtitle: delayLabel(rtForeign?.as_of),
      };
    }
    return { name: fallbackName, value: null, change: null, changePct: null, subtitle: "延遲報價" };
  };

  // 台積電（即時個股）
  const tsmc = (rtTsmc?.quotes ?? []).find((q) => q.symbol === "2330");
  const tsmcCard: IndexCardData = tsmc?.price != null
    ? { name: "台積電", value: tsmc.price, change: tsmc.change ?? null, changePct: tsmc.change_rate ?? null, subtitle: liveLabel(rtTsmc?.as_of) }
    : { name: "台積電", value: null, change: null, changePct: null, subtitle: unavailableLabel(rtTsmc) };

  return [
    indexCard("TAIEX", "加權指數"),
    futuresCard,
    foreignCard("YM=F", "道瓊期貨"),
    foreignCard("NQ=F", "那斯達克期貨"),
    foreignCard("^SOX", "費城半導體"),
    foreignCard("^KS11", "韓國 KOSPI"),
    foreignCard("^N225", "日經 225"),
    tsmcCard,
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
  // 海外指數（延遲）、台積電（即時個股）、板塊熱力圖 —— 僅 TW
  const rtForeign = useRealtimeForeign(isTW);
  const rtTsmc = useRealtimeStock(["2330"], isTW);
  const heatmap = useHeatmap(isTW);
  // 盤中即時走勢（加權指數 5 秒序列 / 台指全逐筆）—— 放在漲跌家數分佈右側
  const intradayTaiex = useIntraday("TAIEX", isTW);
  const intradayTxf = useIntraday("TXF", isTW);

  const indexes = buildIndexCards(
    market,
    data?.indices ?? [],
    rtIndex.data,
    rtFutures.data,
    rtForeign.data,
    rtTsmc.data,
  );

  // 盤中有即時大盤就用即時值，否則用盤後
  const rt = rtOverview.data ?? null;
  const adv = rt?.advance_count ?? (data?.advance_count as number | undefined) ?? 0;
  const dec = rt?.decline_count ?? (data?.decline_count as number | undefined) ?? 0;
  const unc = rt?.unchanged_count ?? (data?.unchanged_count as number | undefined) ?? 0;
  const limitUp =
    (rt?.limit_up_count as number | undefined) ??
    (data?.limit_up_count as number | undefined) ??
    0;
  const limitDown =
    (rt?.limit_down_count as number | undefined) ??
    (data?.limit_down_count as number | undefined) ??
    0;
  const totalVolumeRaw = rt?.total_volume ?? data?.total_volume ?? null;
  const totalVolume =
    totalVolumeRaw != null && totalVolumeRaw !== "" ? Number(totalVolumeRaw) : null;
  const breadthLive = rt != null;

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
      {/* 8 張指數卡 4×2（台股即時＋海外延遲） */}
      <section
        className={
          isTW
            ? "grid gap-3 grid-cols-2 lg:grid-cols-4"
            : "grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
        }
      >
        {isLoading && indexes.every((i) => i.value == null) ? (
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

      {/* 漲跌家數分佈（左）＋ 加權指數／台指全即時走勢圖（右，佔較大空間、非等寬） */}
      <section className="grid gap-3 lg:grid-cols-3">
        <MarketBreadthCard
          adv={adv}
          dec={dec}
          unc={unc}
          limitUp={limitUp}
          limitDown={limitDown}
          totalVolume={totalVolume}
          live={breadthLive}
        />
        {isTW ? (
          <div className="grid gap-3 lg:col-span-2 xl:grid-cols-2">
            <IntradayChart name="加權指數" data={intradayTaiex.data} isLoading={intradayTaiex.isLoading} />
            <IntradayChart name="台指全" data={intradayTxf.data} isLoading={intradayTxf.isLoading} />
          </div>
        ) : null}
      </section>

      {/* 市場板塊圖：獨立一整行、不被壓縮（僅 TW） */}
      {isTW ? <SectorHeatmap data={heatmap.data} isLoading={heatmap.isLoading} /> : null}

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
