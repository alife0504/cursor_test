"use client";

import { Activity, Clock, Cpu, Database, HardDrive, ListChecks } from "lucide-react";
import { useMemo } from "react";

import { BarChart } from "@/components/common/BarChart";
import { ChartContainer } from "@/components/common/ChartContainer";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { MockBanner } from "@/components/common/MockBanner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSystemInfo, useSystemMetrics } from "@/hooks/useSystem";

// Phase 17 § O:系統監控
//   - 卡片:API 可用性、平均延遲、今日分析次數、今日 LLM 成本、磁碟使用、佇列長度
//   - 圖:過去 24h metrics 走勢(v1.0 mock,v1.1 接 prometheus)
//   - PLAN 已知陷阱:/admin/system/metrics 目前只回 endpoint 指引,圖用 mock

// 24h mock 序列(每小時一個點)
function buildMock24h(base: number, jitter: number) {
  return Array.from({ length: 24 }, (_, i) => ({
    hour: `${i.toString().padStart(2, "0")}:00`,
    value: Math.max(0, base + (Math.random() - 0.5) * jitter * 2),
  }));
}

export default function AdminSystemPage() {
  const info = useSystemInfo();
  const metrics = useSystemMetrics();

  // v1.0 mock series — health_check 會 grep "Mock"
  const latencySeries = useMemo(() => buildMock24h(180, 60), []);
  const queueSeries = useMemo(() => buildMock24h(8, 6), []);

  const cards = [
    {
      icon: Activity,
      title: "API 可用性",
      value: "99.9%",
      hint: "近 24h",
    },
    {
      icon: Clock,
      title: "平均延遲",
      value: "180 ms",
      hint: "p50 latency",
    },
    {
      icon: ListChecks,
      title: "今日分析",
      value: "12",
      hint: "completed",
    },
    {
      icon: Cpu,
      title: "今日 LLM 成本",
      value: "$0.42",
      hint: "USD",
    },
    {
      icon: HardDrive,
      title: "磁碟使用",
      value: "42%",
      hint: "data partition",
    },
    {
      icon: Database,
      title: "佇列長度",
      value: "0",
      hint: "celery default",
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">系統監控</h1>
        <p className="text-sm text-muted-foreground">
          API 可用性、延遲、磁碟、佇列等關鍵指標(/metrics 摘要)
        </p>
      </div>

      <MockBanner
        title="本頁圖表為 Mock - v1.1 將接 Prometheus / Grafana"
        trackingRef="運維整合 P19/P20"
      />

      {metrics.isLoading || info.isLoading ? (
        <LoadingSkeleton rows={4} />
      ) : (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
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
                    <p className="text-2xl font-bold tabular-nums">{c.value}</p>
                    <p className="text-xs text-muted-foreground">{c.hint}</p>
                  </CardContent>
                </Card>
              );
            })}
          </section>

          <section className="grid gap-3 lg:grid-cols-2">
            <ChartContainer title="平均延遲走勢(24h, mock)">
              <BarChart
                data={latencySeries}
                xKey="hour"
                series={[{ dataKey: "value", name: "延遲 (ms)", fill: "#3b82f6" }]}
                showLegend={false}
              />
            </ChartContainer>
            <ChartContainer title="Celery 佇列長度(24h, mock)">
              <BarChart
                data={queueSeries}
                xKey="hour"
                series={[{ dataKey: "value", name: "queue len", fill: "#8b5cf6" }]}
                showLegend={false}
              />
            </ChartContainer>
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
        </>
      )}
    </div>
  );
}
