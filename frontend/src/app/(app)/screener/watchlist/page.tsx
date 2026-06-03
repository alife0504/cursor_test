"use client";

import { Globe, Layers, Star, TrendingUp } from "lucide-react";
import { useMemo } from "react";

import { KpiCard } from "@/components/common/KpiCard";
import { PageHeader } from "@/components/common/PageHeader";
import { AddWatchlistButton } from "@/components/watchlist/AddWatchlistButton";
import { WatchlistTable } from "@/components/watchlist/WatchlistTable";
import { useWatchlist } from "@/hooks/useWatchlist";

const TW_MARKETS = new Set(["TWSE", "TPEX"]);

// 自選股清單頁 — 頂部摘要 KPI（共用 useWatchlist 快取，不重複抓）
export default function WatchlistPage() {
  const { data } = useWatchlist();
  const items = data ?? [];

  const summary = useMemo(() => {
    const tw = items.filter((i) => TW_MARKETS.has(i.market)).length;
    const tags = new Set(items.map((i) => i.tag).filter(Boolean)).size;
    return { n: items.length, tw, us: items.length - tw, tags };
  }, [items]);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="自選股清單"
        description="管理你關注的股票；後續可從這裡發起分析"
        actions={<AddWatchlistButton />}
      />

      {/* 摘要 KPI 帶 */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          title="自選股檔數"
          value={summary.n}
          subtitle="關注中標的"
          icon={Star}
          accent="primary"
        />
        <KpiCard
          title="台股"
          value={summary.tw}
          subtitle="TWSE / TPEX"
          icon={TrendingUp}
          accent="info"
        />
        <KpiCard
          title="美股"
          value={summary.us}
          subtitle="NYSE / NASDAQ / AMEX"
          icon={Globe}
          accent="info"
        />
        <KpiCard
          title="分組標籤"
          value={summary.tags}
          subtitle="自訂分組數"
          icon={Layers}
          accent="warning"
        />
      </section>

      <WatchlistTable />
    </div>
  );
}
