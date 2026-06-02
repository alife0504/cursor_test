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
import { useMarketOverview } from "@/hooks/useMarket";
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
 * Dashboard 頂部 4-col KPI 牆：
 *   加權指數 + sparkline / 櫃買 + sparkline / LLM 配額 + bar / 待核准訂單
 */
export function KpiRow() {
  const router = useRouter();
  const start = isoDate(30);
  const end = isoDate(0);

  const market = useMarketOverview("TW");
  const quota = useMyQuota();
  const orders = useOrders({ status: "PENDING", limit: 1 });

  // 嘗試取大盤 OHLCV 給 sparkline（後端可能未 seed → graceful fallback）
  const twseOhlcv = useOhlcv({ symbol: "TAIEX", start, end });
  const tpexOhlcv = useOhlcv({ symbol: "TPEX", start, end });

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

  const idxObj = (market.data?.index ?? null) as Record<string, unknown> | null;
  const twseClose = (idxObj?.twse_close ?? idxObj?.close ?? null) as
    | string
    | number
    | null;
  const twseChange = (idxObj?.twse_change_pct ?? idxObj?.change_pct ?? null) as
    | string
    | number
    | null;
  const tpexClose = (idxObj?.tpex_close ?? null) as string | number | null;
  const tpexChange = (idxObj?.tpex_change_pct ?? null) as
    | string
    | number
    | null;

  const twseSpark = closeSeries(twseOhlcv.data);
  const tpexSpark = closeSeries(tpexOhlcv.data);

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
        subtitle="近 14 日走勢"
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
        title="櫃買指數"
        value={tpexClose !== null ? String(tpexClose) : "—"}
        delta={tpexChange}
        deltaMode="raw"
        spark={tpexSpark}
        icon={TrendingUp}
        subtitle="近 14 日走勢"
        accent={
          tpexChange !== null && Number(tpexChange) > 0
            ? "bull"
            : tpexChange !== null && Number(tpexChange) < 0
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
