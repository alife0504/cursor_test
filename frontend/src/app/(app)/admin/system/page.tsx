"use client";

import { Cog, Cpu, ListChecks } from "lucide-react";
import { useMemo } from "react";

import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAnalysisList } from "@/hooks/useAnalysis";
import { useSystemInfo } from "@/hooks/useSystem";

// Phase 17 § O（v1.1）：系統監控
//   - 只顯示真實資料：今日分析數 / 今日 LLM 成本（由 /analysis 即時彙總）+ 系統資訊
//   - 完整運維指標（可用性/延遲/磁碟/佇列走勢）需 Prometheus/Grafana（P19/P20），
//     未接前不放假數字誤導 → 該區塊移除

export default function AdminSystemPage() {
  const info = useSystemInfo();
  const q = useAnalysisList({ limit: 200 }, true);

  const { todayCount, todayCost } = useMemo(() => {
    const items = q.data?.items ?? [];
    const today = new Date().toISOString().slice(0, 10);
    let count = 0;
    let cost = 0;
    for (const it of items) {
      if (it.created_at?.slice(0, 10) === today) {
        count += 1;
        cost += Number(it.total_cost_usd ?? 0);
      }
    }
    return { todayCount: count, todayCost: cost };
  }, [q.data]);

  const cards = [
    {
      icon: ListChecks,
      title: "今日分析數",
      value: String(todayCount),
      hint: "今日建立的分析（近 200 筆內）",
    },
    {
      icon: Cpu,
      title: "今日 LLM 成本",
      value: `$${todayCost.toFixed(4)}`,
      hint: "今日分析 total_cost_usd 合計",
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        icon={Cog}
        title="系統監控"
        description="今日用量與系統資訊（即時運維指標見 v1.1 Prometheus 整合）"
      />

      {q.isLoading || info.isLoading ? (
        <LoadingSkeleton rows={4} />
      ) : (
        <>
          <section className="grid gap-3 sm:grid-cols-2">
            {cards.map((c) => {
              const Icon = c.icon;
              return (
                <Card key={c.title}>
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardTitle className="text-sm text-muted-foreground">
                      {c.title}
                    </CardTitle>
                    <Icon className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <p className="num text-2xl font-bold tabular-nums">
                      {c.value}
                    </p>
                    <p className="text-xs text-muted-foreground">{c.hint}</p>
                  </CardContent>
                </Card>
              );
            })}
          </section>

          {info.data ? (
            <section className="rounded-lg border bg-card p-4">
              <h3 className="mb-3 text-sm font-medium">系統資訊</h3>
              <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-muted-foreground">版本</dt>
                  <dd className="font-mono">{info.data.version}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">環境</dt>
                  <dd className="font-mono">{info.data.env}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">啟動時間</dt>
                  <dd className="font-mono tabular-nums">
                    {info.data.started_at ?? "-"}
                  </dd>
                </div>
              </dl>
            </section>
          ) : null}

          <p className="text-xs text-muted-foreground">
            可用性、延遲、磁碟、佇列走勢等即時運維指標將於 v1.1 接入 Prometheus /
            Grafana（P19/P20）；此頁目前僅呈現可由應用資料直接彙總的真實數字。
          </p>
        </>
      )}
    </div>
  );
}
