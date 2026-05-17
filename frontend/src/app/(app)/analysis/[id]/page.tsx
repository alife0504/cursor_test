"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { AgentFlowGraph } from "@/components/AgentFlowGraph";
import { AnalysisHeader } from "@/components/analysis-detail/AnalysisHeader";
import { AnalystResultCard } from "@/components/analysis-detail/AnalystResultCard";
import { DebateTimeline } from "@/components/analysis-detail/DebateTimeline";
import { ReportMarkdown } from "@/components/analysis-detail/ReportMarkdown";
import { buildFlowNodes } from "@/components/analysis-detail/buildFlowNodes";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAnalysisDebate, useAnalysisDetail } from "@/hooks/useAnalysis";
import { useAnalysisWS } from "@/hooks/useWebSocket";

// Phase 16 § E + § G:分析詳情頁(含 AgentFlowGraph + Tabs)
//   - status=queued/running:WS 串流 + 每 5s 輪詢 detail
//   - status=completed/failed:停止輪詢、停止 WS
//   - tabs:Overview / Analysts / Debate / Report
export default function AnalysisDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const search = useSearchParams();
  const defaultTab = search.get("tab") || "overview";

  const qc = useQueryClient();
  const { data: analysis, isLoading, error } = useAnalysisDetail(id);

  const running =
    !!analysis &&
    (analysis.status === "queued" || analysis.status === "running");

  // 動態 polling:running 時 5s 一次,完成後停止
  // 透過 refetchOnMount + manual invalidate;這裡簡化用 useAnalysisDetail 重 enable
  useAnalysisDetail(id, running ? 5000 : false);

  const { events, status: wsStatus } = useAnalysisWS(id, running);
  const { data: debate = [] } = useAnalysisDebate(id);

  const flowNodes = useMemo(
    () =>
      buildFlowNodes({
        analysis: analysis ?? null,
        debateMessages: debate,
        events,
      }),
    [analysis, debate, events],
  );

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["analysis", id] });
    qc.invalidateQueries({ queryKey: ["analysis", id, "debate"] });
  };

  if (isLoading || !analysis) {
    if (error) {
      return (
        <div className="text-sm text-destructive">
          無法載入分析:{(error as Error).message}
        </div>
      );
    }
    return <LoadingSkeleton rows={6} />;
  }

  return (
    <div className="flex flex-col gap-4">
      <AnalysisHeader
        analysis={analysis}
        wsStatus={running ? wsStatus : undefined}
        onRefresh={refresh}
      />

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Agent Flow</CardTitle>
        </CardHeader>
        <CardContent>
          <AgentFlowGraph nodes={flowNodes} />
        </CardContent>
      </Card>

      <Tabs defaultValue={defaultTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="analysts">Analysts</TabsTrigger>
          <TabsTrigger value="debate">Debate</TabsTrigger>
          <TabsTrigger value="report">Report</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Manager Signal</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
              <div>
                <div className="text-xs text-muted-foreground">Signal</div>
                <div className="font-medium">{analysis.signal ?? "-"}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Confidence</div>
                <div className="font-medium tabular-nums">
                  {analysis.confidence ?? "-"}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Target Price</div>
                <div className="font-medium tabular-nums">
                  {analysis.target_price ?? "-"}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Stop / Take</div>
                <div className="font-medium tabular-nums">
                  {analysis.stop_loss ?? "-"} / {analysis.take_profit ?? "-"}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Cost (USD)</div>
                <div className="font-medium tabular-nums">
                  {analysis.total_cost_usd ?? "0"}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Tokens</div>
                <div className="font-medium tabular-nums">
                  {analysis.total_tokens}
                </div>
              </div>
            </CardContent>
          </Card>
          {analysis.error_msg ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base text-destructive">錯誤</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="overflow-x-auto rounded-md bg-rose-50 p-3 text-xs text-rose-900">
                  {analysis.error_msg}
                </pre>
              </CardContent>
            </Card>
          ) : null}
        </TabsContent>

        <TabsContent value="analysts" className="grid gap-3 md:grid-cols-2">
          {/* 後端 detail 未顯露 analyst raw result;先用 type 列出狀態,內容由 report_md 提供 */}
          {["market", "fundamental", "news", "sentiment"].map((t) => (
            <AnalystResultCard key={t} type={t} />
          ))}
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
