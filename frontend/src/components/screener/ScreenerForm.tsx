"use client";

import { useState, useTransition } from "react";

import { MarketSwitcher } from "@/components/market/MarketSwitcher";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ScreenerFilters } from "@/lib/api-types";

// Phase 17 § E:選股篩選器 form
//   - PLAN 已知陷阱:條件多 → debounce 300ms(這裡用 submit-onlyform,非 onChange 觸發)
//   - 切市場用 useTransition 避免閃爍

interface ScreenerFormProps {
  initial?: ScreenerFilters;
  onSubmit: (f: ScreenerFilters) => void;
}

const LS_KEY = "screener.lastFilters";

export function ScreenerForm({ initial, onSubmit }: ScreenerFormProps) {
  const [, startTransition] = useTransition();
  const [market, setMarket] = useState<"TW" | "US">(initial?.market ?? "TW");
  const [peMin, setPeMin] = useState<string>(initial?.PE_min?.toString() ?? "");
  const [peMax, setPeMax] = useState<string>(initial?.PE_max?.toString() ?? "");
  const [divMin, setDivMin] = useState<string>(
    initial?.dividend_yield_min?.toString() ?? "",
  );
  const [epsMin, setEpsMin] = useState<string>(
    initial?.eps_growth_min?.toString() ?? "",
  );
  const [rsiMin, setRsiMin] = useState<string>(initial?.RSI_min?.toString() ?? "");
  const [rsiMax, setRsiMax] = useState<string>(initial?.RSI_max?.toString() ?? "");
  const [mcapMin, setMcapMin] = useState<string>(
    initial?.market_cap_min?.toString() ?? "",
  );
  const [industry, setIndustry] = useState<string>(initial?.industry ?? "");

  const toNumOrNull = (s: string): number | null =>
    s === "" || Number.isNaN(Number(s)) ? null : Number(s);

  const buildFilters = (): ScreenerFilters => ({
    market,
    PE_min: toNumOrNull(peMin),
    PE_max: toNumOrNull(peMax),
    dividend_yield_min: toNumOrNull(divMin),
    eps_growth_min: toNumOrNull(epsMin),
    RSI_min: toNumOrNull(rsiMin),
    RSI_max: toNumOrNull(rsiMax),
    market_cap_min: toNumOrNull(mcapMin),
    industry: industry || null,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const filters = buildFilters();
    onSubmit(filters);
    // 儲存到 localStorage(v1.1 改接後端)
    try {
      window.localStorage.setItem(LS_KEY, JSON.stringify(filters));
    } catch {
      /* ignore quota / security errors */
    }
  };

  const handleReset = () => {
    setMarket("TW");
    setPeMin("");
    setPeMax("");
    setDivMin("");
    setEpsMin("");
    setRsiMin("");
    setRsiMax("");
    setMcapMin("");
    setIndustry("");
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">篩選條件</h3>
        <MarketSwitcher
          value={market}
          onChange={(m) => startTransition(() => setMarket(m))}
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-1">
          <Label htmlFor="pe-min" className="text-xs">PE 最小</Label>
          <Input id="pe-min" value={peMin} onChange={(e) => setPeMin(e.target.value)} type="number" step="0.01" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="pe-max" className="text-xs">PE 最大</Label>
          <Input id="pe-max" value={peMax} onChange={(e) => setPeMax(e.target.value)} type="number" step="0.01" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="div-min" className="text-xs">殖利率 ≥ (%)</Label>
          <Input id="div-min" value={divMin} onChange={(e) => setDivMin(e.target.value)} type="number" step="0.01" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="eps-min" className="text-xs">EPS 成長 ≥ (%)</Label>
          <Input id="eps-min" value={epsMin} onChange={(e) => setEpsMin(e.target.value)} type="number" step="0.01" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="rsi-min" className="text-xs">RSI 最小</Label>
          <Input id="rsi-min" value={rsiMin} onChange={(e) => setRsiMin(e.target.value)} type="number" step="0.01" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="rsi-max" className="text-xs">RSI 最大</Label>
          <Input id="rsi-max" value={rsiMax} onChange={(e) => setRsiMax(e.target.value)} type="number" step="0.01" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="mcap-min" className="text-xs">市值 ≥</Label>
          <Input id="mcap-min" value={mcapMin} onChange={(e) => setMcapMin(e.target.value)} type="number" step="1" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="industry" className="text-xs">產業</Label>
          <Input id="industry" value={industry} onChange={(e) => setIndustry(e.target.value)} />
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={handleReset}>
          重置
        </Button>
        <Button type="submit">套用篩選</Button>
      </div>
    </form>
  );
}

export function loadLastFilters(): ScreenerFilters | undefined {
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) return undefined;
    return JSON.parse(raw) as ScreenerFilters;
  } catch {
    return undefined;
  }
}
