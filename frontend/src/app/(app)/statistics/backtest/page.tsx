"use client";

import { Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { ChartContainer } from "@/components/common/ChartContainer";
import { LineChart } from "@/components/common/LineChart";
import { PageHeader } from "@/components/common/PageHeader";
import { StockPicker } from "@/components/common/StockPicker";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useBacktest } from "@/hooks/useStatistics";

// Phase 17 § I（v1.1）：真實回測
//   - 標的 + 策略 + 期間 → 後端 PIT 回測引擎（歷史日 K），附 Buy&Hold 基準
//   - 指標：總報酬/年化/夏普/最大回撤/勝率/交易次數

const STRATEGIES = [
  { value: "buy_and_hold", label: "Buy & Hold（買進持有）" },
  { value: "sma_cross", label: "SMA 交叉（5/20）" },
  { value: "macd_crossover", label: "MACD 交叉（12/26/9）" },
  { value: "rsi_mean_reversion", label: "RSI 均值回歸（14）" },
];

const PERIODS = [
  { value: "1m", label: "1 個月" },
  { value: "3m", label: "3 個月" },
  { value: "6m", label: "6 個月" },
  { value: "all", label: "全部（本地資料）" },
];

const pctText = (v: number) => `${(v * 100).toFixed(2)}%`;
const money = (v: number) => `$${Math.round(v).toLocaleString()}`;

export default function StatisticsBacktestPage() {
  const [symbol, setSymbol] = useState<string>("TAIEX");
  const [symbolName, setSymbolName] = useState<string>("加權指數");
  const [strategy, setStrategy] = useState<string>("sma_cross");
  const [period, setPeriod] = useState<string>("3m");

  const { data, isLoading, isError } = useBacktest(symbol, strategy, period);
  const noData =
    data?.error === "no_data" ||
    data?.error === "unknown_strategy" ||
    data?.error === "insufficient_data";

  const m = data?.metrics;
  const bm = data?.benchmark_metrics;

  // 合併策略/基準權益（同日期序列）
  // 基準其實是「同一標的 Buy&Hold（全程續抱）」，非大盤指數；用「續抱」命名避免誤導。
  const equityData = useMemo(() => {
    if (!data?.curve) return [];
    return data.curve.map((p, i) => ({
      date: p.date,
      策略: p.equity,
      續抱: data.benchmark_curve[i]?.equity ?? null,
    }));
  }, [data]);

  const drawdownData = useMemo(
    () => (data?.curve ?? []).map((p) => ({ date: p.date, 回撤: p.drawdown })),
    [data],
  );

  const cards = m
    ? [
        {
          label: "總報酬",
          value: pctText(m.total_return),
          tone: m.total_return >= 0 ? "text-bull" : "text-bear",
          sub: bm ? `續抱 ${pctText(bm.total_return)}` : undefined,
        },
        {
          label: "年化報酬",
          value: pctText(m.annualized_return),
          tone: m.annualized_return >= 0 ? "text-bull" : "text-bear",
        },
        {
          label: "夏普值",
          value: m.sharpe.toFixed(2),
          tone: m.sharpe >= 0 ? "text-bull" : "text-bear",
        },
        {
          label: "最大回撤",
          value: pctText(m.max_drawdown),
          tone: "text-bear",
        },
        {
          label: "勝率",
          value: pctText(m.win_rate),
          tone: "",
          sub: `${m.num_trades} 筆交易`,
        },
        {
          label: "期末資金",
          value: money(
            (data?.initial_capital ?? 1_000_000) * (1 + m.total_return),
          ),
          tone: "",
        },
      ]
    : [];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        icon={Sparkles}
        title="回測結果"
        description="標的 + 策略 + 期間 → 歷史日 K 真實回測（PIT，含 Buy&Hold 基準）"
      />

      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <p className="mb-1 text-xs text-muted-foreground">標的</p>
          <StockPicker
            value={`${symbol} ${symbolName}`}
            onSelect={(s) => {
              setSymbol(s.symbol);
              setSymbolName(s.name ?? "");
            }}
            triggerLabel={`${symbol}${symbolName ? ` ${symbolName}` : ""}`}
          />
        </div>
        <div>
          <p className="mb-1 text-xs text-muted-foreground">策略</p>
          <Select value={strategy} onValueChange={(v) => v && setStrategy(v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STRATEGIES.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <p className="mb-1 text-xs text-muted-foreground">期間</p>
          <Select value={period} onValueChange={(v) => v && setPeriod(v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PERIODS.map((p) => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {data?.start_date && !noData ? (
        <p className="text-xs text-muted-foreground">
          回測區間 {data.start_date} ~ {data.end_date}（{data.trading_days}{" "}
          個交易日）；初始資金 {money(data.initial_capital)}。策略在無訊號時持現金（報酬 0）。
        </p>
      ) : null}

      {isLoading ? (
        <div className="rounded-lg border p-8 text-center text-sm text-muted-foreground">
          回測計算中…
        </div>
      ) : isError ? (
        <div className="rounded-lg border p-8 text-center text-sm text-bear">
          回測失敗，請稍後再試
        </div>
      ) : noData ? (
        <div className="rounded-lg border p-8 text-center text-sm text-muted-foreground">
          「{symbol}」在本地無足夠日 K 資料可回測，請換標的或縮短期間
        </div>
      ) : (
        <>
          <section className="grid gap-3 grid-cols-2 lg:grid-cols-6">
            {cards.map((c) => (
              <div
                key={c.label}
                className="rounded-lg border bg-card p-3 card-hover"
              >
                <p className="text-xs text-muted-foreground">{c.label}</p>
                <p className={`num text-xl font-bold ${c.tone}`}>{c.value}</p>
                {c.sub ? (
                  <p className="text-xs text-muted-foreground">{c.sub}</p>
                ) : null}
              </div>
            ))}
          </section>

          <ChartContainer
            title="權益曲線（策略 vs Buy&Hold 同標的續抱）"
            height={300}
          >
            <LineChart
              data={equityData}
              xKey="date"
              series={[
                { dataKey: "策略", name: "策略", color: "#3b82f6" },
                {
                  dataKey: "續抱",
                  name: "Buy&Hold（同標的續抱）",
                  color: "#94a3b8",
                },
              ]}
              xTickFormatter={(v) => v.slice(5)}
              yTickFormatter={(v) => `${Math.round(v / 10000)}萬`}
            />
          </ChartContainer>

          <ChartContainer title="回撤 Drawdown (%)" height={220}>
            <LineChart
              data={drawdownData}
              xKey="date"
              showLegend={false}
              series={[
                { dataKey: "回撤", name: "回撤 %", color: "#ef4444", area: true },
              ]}
              xTickFormatter={(v) => v.slice(5)}
              yTickFormatter={(v) => `${v.toFixed(0)}%`}
            />
          </ChartContainer>
        </>
      )}
    </div>
  );
}
