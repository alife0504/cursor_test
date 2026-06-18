"use client";

import { useMemo, useState } from "react";

import { BarChart } from "@/components/common/BarChart";
import { ChartContainer } from "@/components/common/ChartContainer";
import { MockBanner } from "@/components/common/MockBanner";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// Phase 17 § I:回測結果(mock,v1.1)
//   - 策略選單 + 期間
//   - mock equity curve + drawdown

const STRATEGIES = [
  { value: "buy_and_hold", label: "Buy & Hold" },
  { value: "rsi_mean_reversion", label: "RSI 均值回歸" },
  { value: "macd_crossover", label: "MACD 交叉" },
];

const PERIODS = [
  { value: "1m", label: "1 個月" },
  { value: "3m", label: "3 個月" },
  { value: "6m", label: "6 個月" },
  { value: "1y", label: "1 年" },
];

function buildMockEquityCurve(strategy: string, period: string) {
  // deterministic mock(以 strategy+period 為 seed)
  const combined = strategy + period;
  let seedNum = 0;
  for (let i = 0; i < combined.length; i++) {
    seedNum = (seedNum + combined.charCodeAt(i)) % 100;
  }
  const days =
    period === "1m" ? 22 : period === "3m" ? 66 : period === "6m" ? 132 : 250;
  let v = 1_000_000;
  const arr: Array<{ day: number; equity: number; drawdown: number }> = [];
  let peak = v;
  for (let i = 0; i < days; i++) {
    const noise = ((seedNum + i * 7) % 13) / 100 - 0.06;
    v = v * (1 + noise);
    if (v > peak) peak = v;
    arr.push({
      day: i + 1,
      equity: Math.round(v),
      drawdown: Math.round(((v - peak) / peak) * 10000) / 100,
    });
  }
  return arr;
}

export default function StatisticsBacktestPage() {
  const [strategy, setStrategy] = useState<string>("buy_and_hold");
  const [period, setPeriod] = useState<string>("3m");
  const data = useMemo(() => buildMockEquityCurve(strategy, period), [strategy, period]);

  const finalEquity = data.length > 0 ? data[data.length - 1].equity : 0;
  const maxDD =
    data.length > 0 ? Math.min(...data.map((d) => d.drawdown)) : 0;
  const totalReturn = data.length > 0 ? ((finalEquity - 1_000_000) / 1_000_000) * 100 : 0;

  // 投資人做回測最常看的指標（mock：由 equity curve 推導；v1.1 改由真實回測引擎回傳）
  const dailyReturns = useMemo(() => {
    const rs: number[] = [];
    for (let i = 1; i < data.length; i++) {
      rs.push(data[i].equity / data[i - 1].equity - 1);
    }
    return rs;
  }, [data]);

  const sharpe = useMemo(() => {
    if (dailyReturns.length < 2) return 0;
    const mean = dailyReturns.reduce((a, b) => a + b, 0) / dailyReturns.length;
    const variance =
      dailyReturns.reduce((a, b) => a + (b - mean) ** 2, 0) / (dailyReturns.length - 1);
    const sd = Math.sqrt(variance);
    return sd === 0 ? 0 : (mean / sd) * Math.sqrt(252); // 年化夏普
  }, [dailyReturns]);

  const winRate = useMemo(() => {
    if (dailyReturns.length === 0) return 0;
    return (dailyReturns.filter((r) => r > 0).length / dailyReturns.length) * 100;
  }, [dailyReturns]);

  const annualizedReturn = useMemo(() => {
    const days = data.length;
    if (days === 0 || finalEquity <= 0) return 0;
    return (Math.pow(finalEquity / 1_000_000, 252 / days) - 1) * 100;
  }, [data.length, finalEquity]);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="回測結果"
        description="策略 + 期間 → equity curve / drawdown"
      />

      <MockBanner
        title="Mock 資料 - v1.1 將接真實回測引擎"
        trackingRef="後端待加 backtest service(P 後續)"
      />

      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <p className="mb-1 text-xs text-muted-foreground">策略</p>
          <Select value={strategy} onValueChange={(v) => v && setStrategy(v)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {STRATEGIES.map((s) => (
                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <p className="mb-1 text-xs text-muted-foreground">期間</p>
          <Select value={period} onValueChange={(v) => v && setPeriod(v)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {PERIODS.map((p) => (
                <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-end">
          <Button variant="outline" disabled>
            執行回測(v1.1)
          </Button>
        </div>
      </div>

      <section className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border bg-card p-3 card-hover">
          <p className="text-xs text-muted-foreground">期末資金</p>
          <p className="num text-2xl font-bold">
            ${finalEquity.toLocaleString()}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-3 card-hover">
          <p className="text-xs text-muted-foreground">總報酬</p>
          <p
            className={`num text-2xl font-bold ${totalReturn >= 0 ? "text-bull" : "text-bear"}`}
          >
            {totalReturn.toFixed(2)}%
          </p>
        </div>
        <div className="rounded-lg border bg-card p-3 card-hover">
          <p className="text-xs text-muted-foreground">最大回撤</p>
          <p className="num text-2xl font-bold text-bear">
            {maxDD.toFixed(2)}%
          </p>
        </div>
        <div className="rounded-lg border bg-card p-3 card-hover">
          <p className="text-xs text-muted-foreground">夏普值</p>
          <p className="num text-2xl font-bold">{sharpe.toFixed(2)}</p>
        </div>
        <div className="rounded-lg border bg-card p-3 card-hover">
          <p className="text-xs text-muted-foreground">勝率</p>
          <p className="num text-2xl font-bold">{winRate.toFixed(1)}%</p>
        </div>
        <div className="rounded-lg border bg-card p-3 card-hover">
          <p className="text-xs text-muted-foreground">年化報酬</p>
          <p
            className={`num text-2xl font-bold ${annualizedReturn >= 0 ? "text-bull" : "text-bear"}`}
          >
            {annualizedReturn.toFixed(2)}%
          </p>
        </div>
      </section>

      <ChartContainer title="Equity Curve（mock）">
        <BarChart
          data={data}
          xKey="day"
          series={[
            { dataKey: "equity", name: "equity", fill: "hsl(var(--chart-1))" },
          ]}
          showLegend={false}
        />
      </ChartContainer>

      <ChartContainer title="Drawdown（mock）">
        <BarChart
          data={data}
          xKey="day"
          series={[
            {
              dataKey: "drawdown",
              name: "drawdown %",
              fill: "hsl(var(--bear))",
            },
          ]}
          showLegend={false}
        />
      </ChartContainer>
    </div>
  );
}
