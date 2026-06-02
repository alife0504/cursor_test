"use client";

import { Target, TrendingDown, TrendingUp } from "lucide-react";
import { useMemo } from "react";

import { PriceDelta } from "@/components/common/PriceDelta";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AnalysisDetail } from "@/lib/api-types";
import { cn } from "@/lib/utils";

interface SignalOverviewProps {
  analysis: AnalysisDetail;
}

function toNum(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/**
 * 圓形信心度（簡單 SVG 環）。
 */
function ConfidenceRing({ pct }: { pct: number }) {
  const clamped = Math.max(0, Math.min(100, pct));
  const size = 64;
  const stroke = 6;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const dash = (clamped / 100) * c;
  const color =
    clamped >= 75
      ? "hsl(var(--success))"
      : clamped >= 50
        ? "hsl(var(--info))"
        : clamped >= 25
          ? "hsl(var(--warning))"
          : "hsl(var(--destructive))";
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className="shrink-0"
    >
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        stroke="hsl(var(--muted))"
        strokeWidth={stroke}
        fill="none"
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        stroke={color}
        strokeWidth={stroke}
        fill="none"
        strokeLinecap="round"
        strokeDasharray={`${dash} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text
        x="50%"
        y="50%"
        textAnchor="middle"
        dominantBaseline="middle"
        className="num"
        style={{ fontSize: 13, fontWeight: 600, fill: color }}
      >
        {Math.round(clamped)}%
      </text>
    </svg>
  );
}

/**
 * Risk/Reward 數線。
 *  - 顯示 target / stop / take 在一條線上的相對位置
 *  - 中央顯示 target；左 stop（綠）、右 take（紅）
 */
function RiskRewardLine({
  target,
  stop,
  take,
  signal,
}: {
  target: number | null;
  stop: number | null;
  take: number | null;
  signal: string | null;
}) {
  // 用 target 當中心，把 stop / take 轉成 ± 百分比
  if (target === null || (!stop && !take)) {
    return (
      <p className="text-xs text-muted-foreground">
        無 stop / take 資訊
      </p>
    );
  }

  const stopPct = stop !== null ? ((stop - target) / target) * 100 : 0;
  const takePct = take !== null ? ((take - target) / target) * 100 : 0;
  const range = Math.max(Math.abs(stopPct), Math.abs(takePct), 5);

  const toX = (pct: number) => 50 + (pct / range) * 45;
  const stopX = toX(stopPct);
  const takeX = toX(takePct);
  const isBuy = signal === "BUY";

  return (
    <div className="relative h-12 w-full">
      <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-muted" />
      {/* zone：stop ~ take */}
      <div
        className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full"
        style={{
          left: `${Math.min(stopX, takeX)}%`,
          right: `${100 - Math.max(stopX, takeX)}%`,
          background:
            "linear-gradient(to right, hsl(var(--bear) / 0.4), hsl(var(--warning) / 0.4), hsl(var(--bull) / 0.4))",
        }}
      />

      {/* stop marker */}
      {stop !== null ? (
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 flex flex-col items-center"
          style={{ left: `${stopX}%` }}
        >
          <span className="mb-0.5 text-[10px] font-medium text-bear">
            停損
          </span>
          <span className="h-3 w-3 rounded-full border-2 border-bear bg-background" />
          <span className="num mt-0.5 text-[10px] text-muted-foreground">
            {stop.toFixed(2)}
          </span>
        </div>
      ) : null}

      {/* target marker */}
      <div
        className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 flex flex-col items-center"
        style={{ left: "50%" }}
      >
        <span className="mb-0.5 text-[10px] font-medium text-foreground">
          目標價
        </span>
        <span
          className={cn(
            "h-3.5 w-3.5 rounded-full border-2 ring-2 ring-background",
            isBuy
              ? "border-bull bg-bull-muted"
              : "border-bear bg-bear-muted",
          )}
        />
        <span className="num mt-0.5 text-[10px] font-medium">
          {target.toFixed(2)}
        </span>
      </div>

      {/* take marker */}
      {take !== null ? (
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 flex flex-col items-center"
          style={{ left: `${takeX}%` }}
        >
          <span className="mb-0.5 text-[10px] font-medium text-bull">
            停利
          </span>
          <span className="h-3 w-3 rounded-full border-2 border-bull bg-background" />
          <span className="num mt-0.5 text-[10px] text-muted-foreground">
            {take.toFixed(2)}
          </span>
        </div>
      ) : null}
    </div>
  );
}

export function SignalOverview({ analysis }: SignalOverviewProps) {
  const target = toNum(analysis.target_price);
  const stop = toNum(analysis.stop_loss);
  const take = toNum(analysis.take_profit);
  const cost = toNum(analysis.total_cost_usd);
  const confidencePct = useMemo(() => {
    const n = toNum(analysis.confidence);
    if (n === null) return null;
    // 後端有時回 0-1，有時 0-100；都正規化到 100
    return n <= 1 ? n * 100 : n;
  }, [analysis.confidence]);

  const stopPct =
    target !== null && stop !== null ? ((stop - target) / target) * 100 : null;
  const takePct =
    target !== null && take !== null ? ((take - target) / target) * 100 : null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Target className="h-4 w-4 text-primary" /> 訊號摘要
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-[auto_1fr]">
          <div className="flex items-center gap-3">
            {confidencePct !== null ? (
              <ConfidenceRing pct={confidencePct} />
            ) : (
              <div className="flex h-16 w-16 items-center justify-center rounded-full border-2 border-dashed border-border text-xs text-muted-foreground">
                N/A
              </div>
            )}
            <div className="space-y-0.5">
              <p className="text-xs text-muted-foreground">綜合信心度</p>
              <p className="num text-2xl font-bold">
                {confidencePct !== null
                  ? `${confidencePct.toFixed(0)}%`
                  : "—"}
              </p>
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-xs text-muted-foreground">訊號</dt>
              <dd className="font-semibold">
                {analysis.signal ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">模型</dt>
              <dd className="font-mono text-xs">
                {analysis.llm_model ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">花費</dt>
              <dd className="num">
                {cost !== null ? `US$${cost.toFixed(3)}` : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Tokens</dt>
              <dd className="num">{analysis.total_tokens ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">停損距</dt>
              <dd>
                <PriceDelta value={stopPct} mode="raw" />
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">停利距</dt>
              <dd>
                <PriceDelta value={takePct} mode="raw" />
              </dd>
            </div>
          </dl>
        </div>

        {target !== null || stop !== null || take !== null ? (
          <div className="rounded-md border bg-muted/20 p-3">
            <RiskRewardLine
              target={target}
              stop={stop}
              take={take}
              signal={analysis.signal ?? null}
            />
            <div className="mt-2 flex justify-between text-[10px] text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <TrendingDown className="h-3 w-3 text-bear" /> 風險區
              </span>
              <span className="inline-flex items-center gap-1">
                <TrendingUp className="h-3 w-3 text-bull" /> 報酬區
              </span>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
