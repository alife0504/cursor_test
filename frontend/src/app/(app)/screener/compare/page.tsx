"use client";

import { useQueries } from "@tanstack/react-query";
import { GitCompareArrows, X } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/common/PageHeader";
import { StockPicker } from "@/components/common/StockPicker";
import { Button } from "@/components/ui/button";
import { api, type ApiEnvelope } from "@/lib/api";

// Phase 17 § F（v1.1）：多股比較
//   - 多選最多 5 支；並排真實指標（GET /stocks/{symbol}/metrics → stock_metrics）
//   - 每日 sync_stock_metrics_tw 物化；無資料欄位顯示 -（不硬湊）

interface StockMetricsData {
  symbol: string;
  as_of_date: string | null;
  pe_ratio: number | null;
  pbr: number | null;
  dividend_yield: number | null;
  market_cap: number | null;
  rsi14: number | null;
  eps_growth: number | null;
}

interface Picked {
  symbol: string;
  name: string;
}

const EXAMPLES: Picked[] = [
  { symbol: "2330", name: "台積電" },
  { symbol: "2317", name: "鴻海" },
];

const num = (v: number | null, digits = 2) =>
  v === null || v === undefined ? "-" : v.toFixed(digits);

const marketCap = (v: number | null) => {
  if (v === null || v === undefined) return "-";
  if (v >= 1e12) return `${(v / 1e12).toFixed(2)} 兆`;
  if (v >= 1e8) return `${(v / 1e8).toFixed(0)} 億`;
  return v.toLocaleString();
};

export default function ScreenerComparePage() {
  const [selected, setSelected] = useState<Picked[]>([]);

  const addSymbol = (p: Picked) => {
    if (selected.length >= 5 || selected.some((s) => s.symbol === p.symbol))
      return;
    setSelected([...selected, p]);
  };
  const removeSymbol = (symbol: string) =>
    setSelected(selected.filter((s) => s.symbol !== symbol));

  const results = useQueries({
    queries: selected.map((s) => ({
      queryKey: ["stock", s.symbol, "metrics"],
      queryFn: async () => {
        const res = await api.get<ApiEnvelope<StockMetricsData>>(
          `/stocks/${s.symbol}/metrics`,
        );
        return res.data.data;
      },
    })),
  });

  const statusBySymbol = new Map<
    string,
    { data?: StockMetricsData; isLoading: boolean; isError: boolean }
  >();
  selected.forEach((s, i) =>
    statusBySymbol.set(s.symbol, {
      data: results[i]?.data,
      isLoading: Boolean(results[i]?.isLoading),
      isError: Boolean(results[i]?.isError),
    }),
  );
  const asOf = results.find((r) => r.data?.as_of_date)?.data?.as_of_date ?? null;

  const rows: Array<{ label: string; fmt: (m?: StockMetricsData) => string }> = [
    { label: "本益比 PE", fmt: (m) => num(m?.pe_ratio ?? null) },
    { label: "股價淨值比 PBR", fmt: (m) => num(m?.pbr ?? null) },
    { label: "殖利率 (%)", fmt: (m) => num(m?.dividend_yield ?? null) },
    { label: "EPS 成長 YoY (%)", fmt: (m) => num(m?.eps_growth ?? null) },
    { label: "RSI(14)", fmt: (m) => num(m?.rsi14 ?? null) },
    { label: "市值", fmt: (m) => marketCap(m?.market_cap ?? null) },
  ];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        icon={GitCompareArrows}
        title="多股比較"
        description="並排檢視最多 5 支股票的真實關鍵指標"
      />

      <div className="flex flex-wrap items-center gap-2">
        {selected.length < 5 ? (
          <StockPicker
            onSelect={(s) => addSymbol({ symbol: s.symbol, name: s.name ?? "" })}
            placeholder="加入比較(最多 5 支)"
            className="w-64"
          />
        ) : (
          <span className="text-xs text-muted-foreground">
            已選滿 5 支，移除後可繼續加入
          </span>
        )}
        {selected.map((s) => (
          <div
            key={s.symbol}
            className="inline-flex items-center gap-1 rounded-md border bg-card px-2 py-1 text-sm"
          >
            <span className="font-mono">{s.symbol}</span>
            <span className="text-xs text-muted-foreground">{s.name}</span>
            <Button
              variant="ghost"
              size="icon"
              className="h-5 w-5"
              aria-label={`移除 ${s.symbol}`}
              onClick={() => removeSymbol(s.symbol)}
            >
              <X className="h-3 w-3" />
            </Button>
          </div>
        ))}
      </div>

      {selected.length === 0 ? (
        <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed bg-card/50 p-10 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
            <GitCompareArrows className="h-6 w-6" />
          </div>
          <div>
            <p className="font-medium">尚未加入比較標的</p>
            <p className="mt-1 text-sm text-muted-foreground">
              從上方搜尋加入股票（最多 5 支），或點下列範例快速開始
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            {EXAMPLES.map((m) => (
              <Button
                key={m.symbol}
                variant="outline"
                size="sm"
                onClick={() => addSymbol(m)}
              >
                + {m.symbol} {m.name}
              </Button>
            ))}
          </div>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-left">
                  <th className="p-2">指標</th>
                  {selected.map((s) => (
                    <th key={s.symbol} className="p-2">
                      <div className="font-mono">{s.symbol}</div>
                      <div className="text-xs font-normal text-muted-foreground">
                        {s.name}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.label} className="border-b">
                    <td className="p-2 text-muted-foreground">{row.label}</td>
                    {selected.map((s) => {
                      const st = statusBySymbol.get(s.symbol);
                      return (
                        <td
                          key={s.symbol}
                          className="p-2 font-mono tabular-nums"
                        >
                          {st?.isLoading ? (
                            <span className="text-muted-foreground">…</span>
                          ) : st?.isError ? (
                            <span className="text-xs text-bear">查詢失敗</span>
                          ) : (
                            row.fmt(st?.data)
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {asOf ? (
            <p className="text-xs text-muted-foreground">
              指標資料日：{asOf}（每日更新；PE/市值 as-of 該日，RSI 用最新收盤）
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
