"use client";

import { Copy, Download, Loader2, RefreshCcw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { DateFormat } from "@/components/common/DateFormat";
import { MarketBadge } from "@/components/common/MarketBadge";
import { SignalBadge } from "@/components/common/SignalBadge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { AnalysisDetail } from "@/lib/api-types";

interface AnalysisHeaderProps {
  analysis: AnalysisDetail;
  wsStatus?: string;
  onRefresh?: () => void;
}

type Fmt = "pdf" | "md" | "xlsx";

export function AnalysisHeader({
  analysis,
  wsStatus,
  onRefresh,
}: AnalysisHeaderProps) {
  const canExport = analysis.status === "completed";
  const [downloading, setDownloading] = useState<Fmt | null>(null);

  const openExport = async (fmt: Fmt) => {
    if (!canExport) {
      toast.error("分析尚未完成，暫時無法匯出");
      return;
    }
    if (typeof window === "undefined") return;
    setDownloading(fmt);
    // 用帶 access token 的 axios 取檔再本地下載。原本 <a> 原生導航走不到 axios interceptor、
    // 不帶 Authorization header，後端 get_current_user 收不到 token → 永遠 401（三種格式全失效）。
    try {
      const res = await api.get(`/exports/${analysis.id}`, {
        params: { format: fmt },
        responseType: "blob",
      });
      const blob = res.data as Blob;
      // 檔名優先取後端 Content-Disposition，否則以標的組出
      const disp = String(res.headers?.["content-disposition"] || "");
      const match = disp.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
      const filename = match
        ? decodeURIComponent(match[1])
        : `${analysis.symbol}_analysis.${fmt}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      toast.error("匯出失敗，請稍後再試");
    } finally {
      setDownloading((cur) => (cur === fmt ? null : cur));
    }
  };

  const copyShareLink = async () => {
    if (typeof window === "undefined") return;
    const url = window.location.href;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("已複製分享連結");
    } catch {
      toast.error("無法複製連結（請手動複製網址列）");
    }
  };

  return (
    <header className="flex flex-col gap-3 border-b pb-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-mono text-2xl font-bold tracking-tight">
            {analysis.symbol}
          </h1>
          <MarketBadge market={analysis.market} />
          <SignalBadge signal={analysis.signal} status={analysis.status} />
          {analysis.llm_model ? (
            <span className="rounded-md bg-muted px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              {analysis.llm_model}
            </span>
          ) : null}
        </div>
        <p className="text-xs text-muted-foreground">
          建立於 <DateFormat value={analysis.created_at} mode="datetime" />
          {analysis.completed_at ? (
            <>
              ・完成於{" "}
              <DateFormat value={analysis.completed_at} mode="datetime" />
            </>
          ) : null}
          {wsStatus ? (
            <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-info/10 px-1.5 py-0.5 text-info">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-info" />
              WS · {wsStatus}
            </span>
          ) : null}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {onRefresh ? (
          <Button variant="outline" size="sm" onClick={onRefresh}>
            <RefreshCcw className="mr-1 h-3 w-3" /> 重新整理
          </Button>
        ) : null}
        <Button variant="ghost" size="sm" onClick={copyShareLink}>
          <Copy className="mr-1 h-3 w-3" /> 分享連結
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => openExport("md")}
          disabled={!canExport || downloading === "md"}
        >
          {downloading === "md" ? (
            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          ) : (
            <Download className="mr-1 h-3 w-3" />
          )}
          MD
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => openExport("xlsx")}
          disabled={!canExport || downloading === "xlsx"}
        >
          {downloading === "xlsx" ? (
            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          ) : (
            <Download className="mr-1 h-3 w-3" />
          )}
          XLSX
        </Button>
        <Button
          size="sm"
          onClick={() => openExport("pdf")}
          disabled={!canExport || downloading === "pdf"}
        >
          {downloading === "pdf" ? (
            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          ) : (
            <Download className="mr-1 h-3 w-3" />
          )}
          PDF
        </Button>
      </div>
    </header>
  );
}
