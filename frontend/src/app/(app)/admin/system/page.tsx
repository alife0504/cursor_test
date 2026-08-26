"use client";

import {
  Activity,
  Cog,
  Cpu,
  Database,
  HardDrive,
  Layers,
  ListChecks,
} from "lucide-react";

import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSystemInfo, useSystemStats } from "@/hooks/useSystem";

// Phase 17 § O（v1.1）：系統監控
//   - KPI 全為「即時真值」：GET /admin/system/stats（今日用量 / 佇列 / DB 大小）
//   - 完整時序走勢（延遲/可用性歷史）需 Prometheus 抓取 /metrics + Grafana（尚未部署）→ 不放假圖

const fmtBytes = (b: number) => {
  if (b >= 1e9) return `${(b / 1e9).toFixed(2)} GB`;
  if (b >= 1e6) return `${(b / 1e6).toFixed(1)} MB`;
  if (b >= 1e3) return `${(b / 1e3).toFixed(0)} KB`;
  return `${b} B`;
};

export default function AdminSystemPage() {
  const info = useSystemInfo();
  const stats = useSystemStats();
  const s = stats.data;

  const cards = s
    ? [
        {
          icon: ListChecks,
          title: "今日分析數",
          value: String(s.analyses_today),
          hint: "今日建立",
        },
        {
          icon: Activity,
          title: "進行中分析",
          value: String(s.analyses_running),
          hint: "status = running",
        },
        {
          icon: Cpu,
          title: "今日 LLM 成本",
          value: `$${s.llm_cost_today_usd.toFixed(4)}`,
          hint: "llm_usage 合計",
        },
        {
          icon: Layers,
          title: "今日 Tokens",
          value: s.llm_tokens_today.toLocaleString(),
          hint: "prompt + completion",
        },
        {
          icon: Database,
          title: "Celery 佇列",
          value: s.celery_queue_len === null ? "—" : String(s.celery_queue_len),
          hint: "待處理任務數",
        },
        {
          icon: HardDrive,
          title: "資料庫大小",
          value: fmtBytes(s.db_size_bytes),
          hint: "pg_database_size",
        },
      ]
    : [];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        icon={Cog}
        title="系統監控"
        description="即時系統統計（每 15 秒更新）；歷史走勢需 v1.1 Prometheus/Grafana"
      />

      {stats.isLoading || info.isLoading ? (
        <LoadingSkeleton rows={4} />
      ) : stats.isError ? (
        <div className="rounded-lg border p-8 text-center text-sm text-bear">
          無法取得系統統計（需 admin 權限）
        </div>
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
                  <dt className="text-muted-foreground">資料更新</dt>
                  <dd className="font-mono tabular-nums">
                    {s?.as_of?.slice(0, 19).replace("T", " ") ?? "-"}
                  </dd>
                </div>
              </dl>
            </section>
          ) : null}

          <p className="text-xs text-muted-foreground">
            以上為即時真值。延遲、可用性、磁碟 I/O 等「歷史走勢圖」需 Prometheus
            抓取後端 <code>/metrics</code>（已提供）＋ Grafana 視覺化；本專案尚未部署此
            ops 層（P19/P20），故不以假資料呈現走勢。
          </p>
        </>
      )}
    </div>
  );
}
