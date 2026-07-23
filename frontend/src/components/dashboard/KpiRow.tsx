"use client";

import {
  Activity,
  CheckSquare,
  LayoutGrid,
  TrendingUp,
} from "lucide-react";
import { useRouter } from "next/navigation";

import { ErrorState } from "@/components/common/ErrorState";
import { KpiCard } from "@/components/common/KpiCard";
import { KpiSkeleton } from "@/components/common/LoadingSkeleton";
import {
  nearMonthFutures,
  useMarketOverview,
  useRealtimeFutures,
  useRealtimeIndex,
} from "@/hooks/useMarket";
import { useOrders } from "@/hooks/useOrders";
import { useMyQuota } from "@/hooks/useQuota";
import { useOhlcv } from "@/hooks/useStocks";

function isoDate(daysAgo: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - daysAgo);
  return d.toISOString().slice(0, 10);
}

/**
 * 從 OHLCV 取最近 N 個 close，給 sparkline 用。
 */
function closeSeries(
  points: ReturnType<typeof useOhlcv>["data"] | undefined,
  take = 14,
): number[] {
  if (!points || points.length === 0) return [];
  return points
    .slice(-take)
    .map((p) => Number(p.close))
    .filter((n) => Number.isFinite(n));
}

/**
 * 大盤指數值來源策略：
 *  - 優先採用後端 market.overview 的 indices 報價（close/change_pct，從 stock_prices 算）。
 *  - 缺報價時從指數 OHLCV 序列推導：close = 最後一筆、漲跌% = 最後兩筆當日變化。
 *    這讓 dashboard 在有指數 OHLCV（真實回填）時即能顯示，不再全是「—」。
 */
function deriveIndexValue(
  backendClose: unknown,
  backendChange: unknown,
  series: number[],
): { close: string | null; change: number | string | null } {
  if (backendClose !== null && backendClose !== undefined && backendClose !== "") {
    return {
      close: String(backendClose),
      change: (backendChange ?? null) as number | string | null,
    };
  }
  if (series.length === 0) return { close: null, change: null };
  const last = series[series.length - 1];
  const prev = series.length >= 2 ? series[series.length - 2] : null;
  return {
    close: last.toLocaleString("en-US", { maximumFractionDigits: 2 }),
    change: prev && prev !== 0 ? ((last - prev) / prev) * 100 : null,
  };
}

/**
 * Dashboard 頂部 4-col KPI 牆：
 *   加權指數 + sparkline / 櫃買 + sparkline / LLM 配額 + bar / 待核准訂單
 */
export function KpiRow() {
  const router = useRouter();
  const start = isoDate(30);
  const end = isoDate(0);

  const market = useMarketOverview("TW");
  // 盤中即時大盤（每 5 秒；收盤後自動停止輪詢）
  const realtime = useRealtimeIndex();
  // 台指全（TXF 近月）：日盤 08:45–13:45 ＋夜盤 15:00–翌日 05:00 全時段即時
  const rtFutures = useRealtimeFutures(["TXF"], true, false);
  const quota = useMyQuota();
  const orders = useOrders({ status: "PENDING", limit: 1 });

  // 嘗試取大盤 OHLCV 給 sparkline（後端可能未 seed → graceful fallback）
  const twseOhlcv = useOhlcv({ symbol: "TAIEX", start, end });

  const isLoading = market.isLoading || quota.isLoading;

  if (isLoading) {
    return <KpiSkeleton count={4} />;
  }

  if (market.error && quota.error) {
    return (
      <ErrorState
        title="儀表板資料載入失敗"
        description="後端可能未啟動或資料尚未 seed"
        onRetry={() => {
          market.refetch();
          quota.refetch();
          orders.refetch();
        }}
        error={market.error ?? quota.error}
      />
    );
  }

  // 後端 /market/overview 回 indices（複數陣列 IndexQuote[]）；攤平成 deriveIndexValue
  // 需要的 {twse_*}。原本讀單數 market.data?.index 恆為 null（欄位名打錯）→
  // 後端從 stock_prices 算好的指數報價從未被採用、只能靠 OHLCV 序列墊底。
  const indices = market.data?.indices ?? [];
  const findQuote = (sym: string) => indices.find((q) => q.symbol === sym);
  const taiexQ = findQuote("TAIEX");
  const idxObj: Record<string, unknown> = {
    twse_close: taiexQ?.close ?? null,
    twse_change_pct: taiexQ?.change_pct ?? null,
  };

  const twseSpark = closeSeries(twseOhlcv.data);

  // 後端有報價就用，否則從指數 OHLCV 序列推導（修正 v1.0.1「永遠是 —」的接線缺口）
  const twse = deriveIndexValue(
    idxObj?.twse_close ?? idxObj?.close,
    idxObj?.twse_change_pct ?? idxObj?.change_pct,
    twseSpark,
  );

  // 盤中有即時報價就蓋掉盤後值（每 5 秒更新）；未開通/收盤/取不到時自動退回盤後值。
  const rtQuotes = realtime.data?.available ? (realtime.data.quotes ?? []) : [];
  const rtOf = (sym: string) => rtQuotes.find((q) => q.symbol === sym);
  const merge = (
    eod: { close: string | null; change: number | string | null },
    sym: string,
  ) => {
    const rt = rtOf(sym);
    if (rt?.price == null) return { ...eod, live: false };
    return {
      close: Number(rt.price).toLocaleString("en-US", { maximumFractionDigits: 2 }),
      // delta 語意是「漲跌%」，故用 change_rate 而非 change（點數）
      change: rt.change_rate != null ? Number(rt.change_rate) : eod.change,
      live: true,
    };
  };

  const twseV = merge(twse, "TAIEX");
  const twseClose = twseV.close;
  const twseChange = twseV.change;

  // 台指全（TXF 近月連續合約）。期貨無盤後 OHLCV 序列，故無 sparkline、也無退回值：
  // 取不到即顯示「—」並在小標說明狀態。
  const futQuote = nearMonthFutures(rtFutures.data);
  const futClose =
    futQuote?.price != null
      ? Number(futQuote.price).toLocaleString("en-US", {
          maximumFractionDigits: 2,
        })
      : null;
  const futChange =
    futQuote?.change_rate != null ? Number(futQuote.change_rate) : null;
  const futAt = rtFutures.data?.as_of?.slice(11, 19) ?? null;

  // 即時時間標記（只取 HH:MM:SS）
  const liveAt = realtime.data?.as_of?.slice(11, 19) ?? null;
  const liveSubtitle = (live: boolean, fallback: string) =>
    live && liveAt ? `即時 · ${liveAt}` : fallback;

  const used = quota.data?.used_usd ?? "0";
  const limit = quota.data?.limit_usd ?? "0";
  const pct = quota.data?.percentage ?? 0;
  const pendingCount = (orders.data?.items ?? []).length;
  const hasMorePending = orders.data?.hasMore ?? false;

  return (
    <section
      aria-label="今日重點"
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
    >
      <KpiCard
        title="加權指數"
        value={twseClose !== null ? String(twseClose) : "—"}
        delta={twseChange}
        deltaMode="raw"
        spark={twseSpark}
        icon={TrendingUp}
        subtitle={
          twseClose !== null
            ? liveSubtitle(twseV.live, "近 14 日走勢")
            : "指數資料待接入"
        }
        accent={
          twseChange !== null && Number(twseChange) > 0
            ? "bull"
            : twseChange !== null && Number(twseChange) < 0
              ? "bear"
              : undefined
        }
        onClick={() => router.push("/market/overview")}
        footer="前往市場總覽 →"
      />
      <KpiCard
        title="台指全"
        value={futClose !== null ? String(futClose) : "—"}
        delta={futChange}
        deltaMode="raw"
        icon={TrendingUp}
        subtitle={
          futClose !== null && futAt
            ? `即時 · ${futAt}`
            : "非交易時段 / 即時未開通"
        }
        accent={
          futChange !== null && futChange > 0
            ? "bull"
            : futChange !== null && futChange < 0
              ? "bear"
              : undefined
        }
        onClick={() => router.push("/market/overview")}
        footer="前往市場總覽 →"
      />
      <KpiCard
        title="本月 LLM 配額"
        value={`US$${Number(used).toFixed(2)}`}
        subtitle={`上限 US$${Number(limit).toFixed(2)} · ${pct.toFixed(1)}%`}
        icon={Activity}
        accent={pct >= 100 ? "bear" : pct >= 80 ? "warning" : "info"}
        onClick={() => router.push("/analysis/history")}
        footer={
          pct >= 100
            ? "已用完，新分析將被擋"
            : pct >= 80
              ? "已接近上限"
              : `剩餘 US$${(Number(limit) - Number(used)).toFixed(2)}`
        }
      />
      <KpiCard
        title="待核准訂單"
        value={`${pendingCount}${hasMorePending ? "+" : ""}`}
        deltaSuffix="筆"
        icon={CheckSquare}
        accent={pendingCount > 0 ? "warning" : "primary"}
        onClick={() => router.push("/portfolio/orders")}
        subtitle={
          pendingCount > 0
            ? "請及時審視並核准"
            : "目前沒有待處理訂單"
        }
        footer={
          <span className="inline-flex items-center gap-1">
            <LayoutGrid className="h-3 w-3" /> 前往核准 →
          </span>
        }
      />
    </section>
  );
}
