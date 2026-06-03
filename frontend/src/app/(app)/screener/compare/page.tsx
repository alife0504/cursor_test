"use client";

import { GitCompareArrows, X } from "lucide-react";
import { useState } from "react";

import { MockBanner } from "@/components/common/MockBanner";
import { PageHeader } from "@/components/common/PageHeader";
import { StockPicker } from "@/components/common/StockPicker";
import { Button } from "@/components/ui/button";

// Phase 17 § F:多股比較(mock,v1.1)
//   - 多選最多 5 支
//   - 並排顯示主要指標(現用 mock value;v1.1 改接 /stocks/{symbol} 聚合)
//   - 包含 "Mock - v1.1" 字串

interface MockStockMetric {
  symbol: string;
  name: string;
  pe: string;
  dividend_yield: string;
  eps_growth: string;
  rsi: string;
  market_cap: string;
}

const MOCK_METRICS: Record<string, MockStockMetric> = {
  "2330": {
    symbol: "2330",
    name: "台積電",
    pe: "23.45",
    dividend_yield: "1.85",
    eps_growth: "12.3",
    rsi: "58.2",
    market_cap: "16,800,000,000,000",
  },
  "2317": {
    symbol: "2317",
    name: "鴻海",
    pe: "11.20",
    dividend_yield: "4.50",
    eps_growth: "6.8",
    rsi: "52.4",
    market_cap: "2,300,000,000,000",
  },
};

export default function ScreenerComparePage() {
  const [selected, setSelected] = useState<string[]>([]);

  const addSymbol = (symbol: string) => {
    if (selected.length >= 5 || selected.includes(symbol)) return;
    setSelected([...selected, symbol]);
  };

  const removeSymbol = (symbol: string) => {
    setSelected(selected.filter((s) => s !== symbol));
  };

  const metrics: Array<{ label: string; key: keyof MockStockMetric }> = [
    { label: "PE", key: "pe" },
    { label: "殖利率 (%)", key: "dividend_yield" },
    { label: "EPS 成長 (%)", key: "eps_growth" },
    { label: "RSI", key: "rsi" },
    { label: "市值", key: "market_cap" },
  ];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="多股比較"
        description="並排檢視最多 5 支股票的主要指標"
      />

      <MockBanner trackingRef="GitHub issue: multi-stock-compare" />

      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          {selected.length < 5 ? (
            <StockPicker
              onSelect={(s) => addSymbol(s.symbol)}
              placeholder="加入比較(最多 5 支)"
              className="w-64"
            />
          ) : (
            <span className="text-xs text-muted-foreground">
              已選滿 5 支,移除後可繼續加入
            </span>
          )}
          {selected.map((sym) => (
            <div
              key={sym}
              className="inline-flex items-center gap-1 rounded-md border bg-card px-2 py-1 text-sm"
            >
              <span className="font-mono">{sym}</span>
              <Button
                variant="ghost"
                size="icon"
                className="h-5 w-5"
                aria-label={`移除 ${sym}`}
                onClick={() => removeSymbol(sym)}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          ))}
        </div>
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
            {Object.values(MOCK_METRICS).map((m) => (
              <Button
                key={m.symbol}
                variant="outline"
                size="sm"
                onClick={() => addSymbol(m.symbol)}
              >
                + {m.symbol} {m.name}
              </Button>
            ))}
          </div>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50 text-left">
                <th className="p-2">指標</th>
                {selected.map((sym) => {
                  const m = MOCK_METRICS[sym];
                  return (
                    <th key={sym} className="p-2">
                      <div className="font-mono">{sym}</div>
                      <div className="text-xs font-normal text-muted-foreground">
                        {m?.name ?? "(無 mock 資料)"}
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {metrics.map((row) => (
                <tr key={row.key} className="border-b">
                  <td className="p-2 text-muted-foreground">{row.label}</td>
                  {selected.map((sym) => {
                    const m = MOCK_METRICS[sym];
                    return (
                      <td key={sym} className="p-2 font-mono tabular-nums">
                        {m ? m[row.key] : "-"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
