"use client";

import { Download, RefreshCcw } from "lucide-react";
import { toast } from "sonner";

import { DateFormat } from "@/components/common/DateFormat";
import { MarketBadge } from "@/components/common/MarketBadge";
import { SignalBadge } from "@/components/common/SignalBadge";
import { Button } from "@/components/ui/button";
import type { AnalysisDetail } from "@/lib/api-types";
import { API_BASE_URL } from "@/lib/api";

interface AnalysisHeaderProps {
  analysis: AnalysisDetail;
  wsStatus?: string;
  onRefresh?: () => void;
}

// Phase 16 § E:分析詳情 header(代號 + signal + 控制按鈕)
export function AnalysisHeader({
  analysis,
  wsStatus,
  onRefresh,
}: AnalysisHeaderProps) {
  const exportBase = `${API_BASE_URL}/exports/${analysis.id}`;
  const canExport = analysis.status === "completed";

  const openExport = (fmt: "pdf" | "md" | "xlsx") => {
    if (!canExport) {
      toast.error("分析尚未完成,暫時無法匯出");
      return;
    }
    if (typeof window !== "undefined") {
      window.open(`${exportBase}?format=${fmt}`, "_blank");
    }
  };

  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold tracking-tight">
            {analysis.symbol}
          </h1>
          <MarketBadge market={analysis.market} />
          <SignalBadge signal={analysis.signal} status={analysis.status} />
        </div>
        <p className="text-xs text-muted-foreground">
          建立於 <DateFormat value={analysis.created_at} mode="datetime" />
          {analysis.completed_at ? (
            <>
              ;完成於 <DateFormat value={analysis.completed_at} mode="datetime" />
            </>
          ) : null}
          {analysis.llm_model ? (
            <span className="ml-2">· {analysis.llm_model}</span>
          ) : null}
          {wsStatus ? (
            <span className="ml-2">· WS: {wsStatus}</span>
          ) : null}
        </p>
      </div>
      <div className="flex items-center gap-2">
        {onRefresh ? (
          <Button variant="outline" size="sm" onClick={onRefresh}>
            <RefreshCcw className="mr-1 h-3 w-3" /> 重新整理
          </Button>
        ) : null}
        <Button
          size="sm"
          variant="outline"
          onClick={() => openExport("md")}
          disabled={!canExport}
        >
          <Download className="mr-1 h-3 w-3" /> MD
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => openExport("xlsx")}
          disabled={!canExport}
        >
          <Download className="mr-1 h-3 w-3" /> XLSX
        </Button>
        <Button
          size="sm"
          onClick={() => openExport("pdf")}
          disabled={!canExport}
        >
          <Download className="mr-1 h-3 w-3" /> PDF
        </Button>
      </div>
    </div>
  );
}
