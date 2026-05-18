"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/common/EmptyState";
import type { DebateMessage } from "@/lib/api-types";
import { cn } from "@/lib/utils";

interface DebateTimelineProps {
  messages: DebateMessage[];
}

// Phase 16 § E + § G:Bull / Bear 辯論
//   - 並排:Bull 左、Bear 右
//   - 每輪一塊
//   - Manager final synthesis 單獨一塊
function renderContent(content: unknown): string {
  if (typeof content === "string") return content;
  if (!content) return "";
  if (typeof content === "object" && "text" in (content as Record<string, unknown>)) {
    const t = (content as Record<string, unknown>).text;
    if (typeof t === "string") return t;
  }
  return JSON.stringify(content, null, 2);
}

export function DebateTimeline({ messages }: DebateTimelineProps) {
  if (!messages.length) {
    return (
      <EmptyState
        title="尚無辯論訊息"
        description="若 debate_rounds 為 0 或分析尚未進行到該階段,這裡會是空的"
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
    <div className="flex flex-col gap-4">
      {rounds.map((r) => {
        const msgs = grouped.get(r) ?? [];
        const bull = msgs.find((m) => m.role === "bull");
        const bear = msgs.find((m) => m.role === "bear");
        const manager = msgs.find((m) => m.role === "manager");
        return (
          <div key={r} className="space-y-2">
            <h3 className="text-sm font-semibold">第 {r} 輪</h3>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Card className={cn("border-emerald-300")}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-emerald-700">
                    🐂 Bull
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="whitespace-pre-wrap text-xs text-foreground/90">
                    {bull ? renderContent(bull.content) : "(尚無)"}
                  </pre>
                </CardContent>
              </Card>
              <Card className={cn("border-rose-300")}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-rose-700">
                    🐻 Bear
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="whitespace-pre-wrap text-xs text-foreground/90">
                    {bear ? renderContent(bear.content) : "(尚無)"}
                  </pre>
                </CardContent>
              </Card>
            </div>
            {manager ? (
              <Card className="border-amber-300">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-amber-700">
                    🧑‍⚖️ Manager(第 {r} 輪結論)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="whitespace-pre-wrap text-xs text-foreground/90">
                    {renderContent(manager.content)}
                  </pre>
                </CardContent>
              </Card>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
