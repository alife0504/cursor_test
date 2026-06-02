"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { AgentFlowGraph } from "@/components/AgentFlowGraph";
import { AnalysisHeader } from "@/components/analysis-detail/AnalysisHeader";
import { AnalystResultCard } from "@/components/analysis-detail/AnalystResultCard";
import { DebateTimeline } from "@/components/analysis-detail/DebateTimeline";
import { ReportMarkdown } from "@/components/analysis-detail/ReportMarkdown";
import { SignalOverview } from "@/components/analysis-detail/SignalOverview";
import { buildFlowNodes } from "@/components/analysis-detail/buildFlowNodes";
import { ErrorState } from "@/components/common/ErrorState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { StatusStepper } from "@/components/common/StatusStepper";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAnalysisDebate, useAnalysisDetail } from "@/hooks/useAnalysis";
import { useAnalysisWS } from "@/hooks/useWebSocket";

const DEFAULT_ANALYSTS = ["market", "fundamental", "news", "sentiment"];

// 分析詳情頁：
//   - StatusStepper（5 階段視覺化）
//   - SignalOverview（信心圓環 + risk/reward 數線）
//   - AgentFlowGraph（節點圖 + MiniMap）
//   - Tabs：Overview / Analysts / Debate / Report
//   - status=queued/running：WS 串流 + 每 5s 輪詢 detail；done → 停
export default function AnalysisDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const search = useSearchParams();
  const defaultTab = search.get("tab") || "overview";

  const qc = useQueryClient();
  const { data: analysis, isLoading, error, refetch } = useAnalysisDetail(id);

  const running =
    !!analysis &&
    (analysis.status === "queued" || analysis.status === "running");

  // running 時 5s 輪詢一次
  useAnalysisDetail(id, running ? 5000 : false);

  const { events, status: wsStatus } = useAnalysisWS(id, running);
  const { data: debate = [] } = useAnalysisDebate(id);

  // 後端可能未提供 analyst_types / debate_rounds，使用合理 default
  const analystTypes = useMemo(() => {
    const explicit = analysis?.analyst_types;
    if (explicit && explicit.length > 0) return explicit;
    return DEFAULT_ANALYSTS;
  }, [analysis?.analyst_types]);

  const flowNodes = useMemo(
    () =>
      buildFlowNodes({
        analysis: analysis ?? null,
        analystTypes,
        debateRounds: analysis?.debate_rounds ?? undefined,
        debateMessages: debate,
        events,
      }),
    [analysis, analystTypes, debate, events],
  );

  // StatusStepper 推斷
  const managerDone =
    debate.some((m) => m.role === "manager") ||
    events.some(
      (e) => e.type === "synthesis_completed" || e.type === "completed",
    );

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["analysis", id] });
    qc.invalidateQueries({ queryKey: ["analysis", id, "debate"] });
  };

  if (isLoading) {
    return <LoadingSkeleton rows={6} />;
  }
  if (error || !analysis) {
    return (
      <ErrorState
        title="無法載入分析"
        description="該分析可能不存在或你無權檢視"
        onRetry={refetch}
        error={error}
      />
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <AnalysisHeader
        analysis={analysis}
        wsStatus={running ? wsStatus : undefined}
        onRefresh={refresh}
      />

      <StatusStepper
        status={analysis.status}
        debateCount={debate.length}
        managerDone={managerDone}
      />

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-5">
        <div className="xl:col-span-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Agent Flow</CardTitle>
            </CardHeader>
            <CardContent>
              <AgentFlowGraph nodes={flowNodes} />
            </CardContent>
          </Card>
        </div>
        <div className="xl:col-span-2">
          <SignalOverview analysis={analysis} />
        </div>
      </section>

      <Tabs defaultValue={defaultTab} className="w-full">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="analysts">Analysts</TabsTrigger>
          <TabsTrigger value="debate">Debate</TabsTrigger>
          <TabsTrigger value="report">Report</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-3">
          {analysis.error_msg ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base text-destructive">
                  錯誤訊息
                </CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="overflow-x-auto rounded-md border bg-destructive/5 p-3 text-xs text-destructive">
                  {analysis.error_msg}
                </pre>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">綜合報告概要</CardTitle>
              </CardHeader>
              <CardContent>
                {analysis.report_md ? (
                  <ReportMarkdown
                    source={analysis.report_md.slice(0, 600)}
                  />
                ) : (
                  <p className="text-sm text-muted-foreground">
                    分析尚在進行 — 請切換到 Analysts 或 Debate 頁觀察進度
                  </p>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent
          value="analysts"
          className="grid gap-3 md:grid-cols-2"
        >
          {analystTypes.map((t) => {
            const out = analysis.analyst_outputs?.[t] ?? null;
            const done = flowNodes
              .filter((n) => n.id === `analyst:${t}`)
              .some(
                (n) => n.state === "completed" || n.state === "failed",
              );
            return (
              <AnalystResultCard
                key={t}
                type={t}
                output={out}
                done={done}
              />
            );
          })}
        </TabsContent>

        <TabsContent value="debate">
          <DebateTimeline messages={debate} />
        </TabsContent>

        <TabsContent value="report">
          <Card>
            <CardContent className="pt-6">
              <ReportMarkdown source={analysis.report_md} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
