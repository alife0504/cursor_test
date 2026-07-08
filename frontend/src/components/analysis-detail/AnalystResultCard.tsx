"use client";

import {
  ChevronDown,
  ChevronUp,
  Coins,
  Gauge,
  Newspaper,
  Sparkles,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";

import { ReportMarkdown } from "@/components/analysis-detail/ReportMarkdown";
import { SignalBadge } from "@/components/common/SignalBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AnalystOutput } from "@/lib/api-types";
import { cn } from "@/lib/utils";

const ANALYST_META: Record<
  string,
  { label: string; description: string; icon: LucideIcon }
> = {
  market: {
    label: "市場面 Analyst",
    description: "技術指標：RSI / MACD / KD / 均線",
    icon: TrendingUp,
  },
  fundamental: {
    label: "基本面 Analyst",
    description: "財報：EPS / PE / 殖利率 / 成長率",
    icon: Sparkles,
  },
  news: {
    label: "新聞面 Analyst",
    description: "個股新聞 / 公告 + 大盤總經脈絡",
    icon: Newspaper,
  },
  sentiment: {
    label: "情緒面 Analyst",
    description: "新聞情緒聚合：市場情緒溫度 / 熱度 / 動能（TW only）",
    icon: Gauge,
  },
  chip: {
    label: "籌碼面 Analyst",
    description: "三大法人、融資融券、月營收（TW only）",
    icon: Coins,
  },
};

interface AnalystResultCardProps {
  type: string;
  /** 從 analysis.analyst_outputs[type] 取的結構化結果 */
  output?: AnalystOutput | null;
  /** parent 提供「該 analyst 是否已完成」（從 events / debate / status 推導） */
  done?: boolean;
}

function shortenScore(s?: number | string | null): string {
  if (s === null || s === undefined || s === "") return "—";
  const n = Number(s);
  if (!Number.isFinite(n)) return "—";
  // 0-1 → 百分比
  if (n <= 1) return `${(n * 100).toFixed(0)}%`;
  // 0-100
  return `${n.toFixed(0)}%`;
}

export function AnalystResultCard({
  type,
  output,
  done = false,
}: AnalystResultCardProps) {
  const [open, setOpen] = useState(false);
  const meta = ANALYST_META[type] ?? {
    label: `${type} Analyst`,
    description: "",
    icon: Sparkles,
  };
  const Icon = meta.icon;
  const hasOutput = output && Object.keys(output).length > 0;
  const keyPoints = (output?.key_points ?? []).filter(
    (s): s is string => typeof s === "string",
  );
  const signal = output?.signal ? String(output.signal).toUpperCase() : null;
  const reportMd = (output?.report_md as string | null) ?? null;

  return (
    <Card data-analyst={type} className="card-hover">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Icon className="h-3.5 w-3.5" />
          </span>
          <div>
            <CardTitle className="text-sm leading-tight">{meta.label}</CardTitle>
            <p className="text-[10px] text-muted-foreground">
              {meta.description}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {signal ? <SignalBadge signal={signal} status="completed" /> : null}
          {output?.score !== undefined && output?.score !== null ? (
            <Badge variant="outline" className="text-[10px] font-mono">
              信心 {shortenScore(output.score)}
            </Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>
        {hasOutput ? (
          <div className="flex flex-col gap-2">
            {keyPoints.length > 0 ? (
              <ul className="space-y-1.5 text-sm">
                {(open ? keyPoints : keyPoints.slice(0, 3)).map((p, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                    <span>{p}</span>
                  </li>
                ))}
                {keyPoints.length > 3 ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setOpen((o) => !o)}
                    className="mt-1 h-7 text-xs text-muted-foreground"
                  >
                    {open ? (
                      <>
                        <ChevronUp className="mr-1 h-3 w-3" /> 收起
                      </>
                    ) : (
                      <>
                        <ChevronDown className="mr-1 h-3 w-3" /> 還有{" "}
                        {keyPoints.length - 3} 點
                      </>
                    )}
                  </Button>
                ) : null}
              </ul>
            ) : null}

            {reportMd ? (
              <details className="mt-2 rounded-md border bg-muted/20 p-2 [&[open]>summary]:mb-2">
                <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
                  完整報告（Markdown）
                </summary>
                <div className="px-1">
                  <ReportMarkdown source={reportMd} />
                </div>
              </details>
            ) : null}

            {keyPoints.length === 0 && !reportMd ? (
              <p className="text-xs text-muted-foreground">
                該分析師已完成，但未產出結構化要點
              </p>
            ) : null}
          </div>
        ) : (
          <p
            className={cn(
              "text-xs",
              done ? "text-success" : "text-muted-foreground",
            )}
          >
            {done
              ? "已完成（結構化資料尚未取得，請查看完整報告）"
              : "尚未完成"}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
