"use client";

import { Scale, TrendingDown, TrendingUp } from "lucide-react";

import { ReportMarkdown } from "@/components/analysis-detail/ReportMarkdown";
import { EmptyState } from "@/components/common/EmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DebateMessage } from "@/lib/api-types";
import { cn } from "@/lib/utils";

interface DebateTimelineProps {
  messages: DebateMessage[];
}

// 把 content 規範化成 markdown 字串
function renderContent(content: unknown): string {
  if (typeof content === "string") return content;
  if (!content) return "";
  if (typeof content === "object" && "text" in (content as Record<string, unknown>)) {
    const t = (content as Record<string, unknown>).text;
    if (typeof t === "string") return t;
  }
  // dict / array → 用 markdown code block 包，仍可閱讀
  return "```json\n" + JSON.stringify(content, null, 2) + "\n```";
}

export function DebateTimeline({ messages }: DebateTimelineProps) {
  if (!messages.length) {
    return (
      <EmptyState
        title="尚無辯論訊息"
        description="若 debate_rounds 為 0 或分析尚未進行到該階段，這裡會是空的"
      />
    );
  }

  // group by round_num
  const grouped = new Map<number, DebateMessage[]>();
  for (const m of messages) {
    if (!grouped.has(m.round_num)) grouped.set(m.round_num, []);
    grouped.get(m.round_num)!.push(m);
  }
  const rounds = Array.from(grouped.keys()).sort((a, b) => a - b);

  return (
    <div className="relative flex flex-col gap-6">
      {/* 左側時間軸 */}
      <div
        aria-hidden
        className="pointer-events-none absolute bottom-0 left-3 top-0 w-px bg-border sm:left-4"
      />
      {rounds.map((r) => {
        const msgs = grouped.get(r) ?? [];
        const bull = msgs.find((m) => m.role === "bull");
        const bear = msgs.find((m) => m.role === "bear");
        const manager = msgs.find((m) => m.role === "manager");
        return (
          <div key={r} className="relative pl-10 sm:pl-12">
            <div
              className={cn(
                "absolute left-0 top-0 flex h-7 w-7 items-center justify-center rounded-full ring-4 ring-background",
                "bg-primary text-primary-foreground text-xs font-bold sm:h-8 sm:w-8",
              )}
            >
              {r}
            </div>
            <h3 className="mb-3 text-sm font-semibold">第 {r} 輪辯論</h3>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Card
                data-role="bull"
                className="border-bull/40 bg-bull-muted/30"
              >
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-sm text-bull">
                    <TrendingUp className="h-4 w-4" /> Bull · 看多
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-sm">
                  {bull ? (
                    <ReportMarkdown source={renderContent(bull.content)} />
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      （尚無）
                    </span>
                  )}
                </CardContent>
              </Card>
              <Card
                data-role="bear"
                className="border-bear/40 bg-bear-muted/30"
              >
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-sm text-bear">
                    <TrendingDown className="h-4 w-4" /> Bear · 看空
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-sm">
                  {bear ? (
                    <ReportMarkdown source={renderContent(bear.content)} />
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      （尚無）
                    </span>
                  )}
                </CardContent>
              </Card>
            </div>
            {manager ? (
              <Card
                data-role="manager"
                className="mt-3 border-warning/40 bg-warning/5"
              >
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-sm text-warning">
                    <Scale className="h-4 w-4" /> Manager · 第 {r} 輪結論
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-sm">
                  <ReportMarkdown source={renderContent(manager.content)} />
                </CardContent>
              </Card>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
