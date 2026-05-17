"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  AnalystChooser,
  type AnalystType,
} from "@/components/analysis-new/AnalystChooser";
import { QuotaProgress } from "@/components/dashboard/QuotaProgress";
import { StockPicker } from "@/components/common/StockPicker";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCreateAnalysis } from "@/hooks/useAnalysis";
import type { StockSummary } from "@/lib/api-types";
import { LLM_MODELS, estimateCostUsd } from "@/lib/llm-models";
import { uuidv4 } from "@/lib/uuid";

// Phase 16 § D:新增分析頁
//   - 步驟 1 選股 → 步驟 2 analyst → 步驟 3 model → 步驟 4 debate rounds
//   - submit 帶 Idempotency-Key,完成跳 /analysis/[id]
//   - quota 顯示在右側 sticky panel
//   - useSearchParams 需要在 Suspense boundary 內(Next 14 dynamic CSR bailout)
export default function NewAnalysisPage() {
  return (
    <Suspense fallback={<div className="text-sm text-muted-foreground">載入中...</div>}>
      <NewAnalysisInner />
    </Suspense>
  );
}

function NewAnalysisInner() {
  const router = useRouter();
  const search = useSearchParams();
  const initialSymbol = search.get("symbol");
  const [picked, setPicked] = useState<StockSummary | null>(
    initialSymbol
      ? {
          symbol: initialSymbol,
          market: "TW",
          name: "",
          is_active: true,
        }
      : null,
  );
  const [analysts, setAnalysts] = useState<AnalystType[]>([
    "market",
    "fundamental",
  ]);
  const [model, setModel] = useState<string>(LLM_MODELS[0].id);
  const [debateRounds, setDebateRounds] = useState<number>(1);
  const [idemKey, setIdemKey] = useState<string>(() => uuidv4());
  const create = useCreateAnalysis();

  // 每次 picked / submit 後 reset key,避免重送被當 idempotent replay
  useEffect(() => {
    setIdemKey(uuidv4());
  }, [picked?.symbol]);

  const market: "TW" | "US" = useMemo(() => {
    const m = (picked?.market || "").toUpperCase();
    if (m === "TW" || m === "TWSE" || m === "TPEX") return "TW";
    return "US";
  }, [picked?.market]);

  // US 不允許 sentiment;若選了就過濾
  useEffect(() => {
    if (market === "US" && analysts.includes("sentiment")) {
      setAnalysts((a) => a.filter((x) => x !== "sentiment"));
    }
  }, [market, analysts]);

  const estimated = estimateCostUsd(model, analysts.length, debateRounds);
  const estimatedSeconds = 60 + analysts.length * 30 + debateRounds * 30;

  const canSubmit =
    !!picked &&
    analysts.length > 0 &&
    debateRounds >= 0 &&
    !create.isPending;

  const submit = async () => {
    if (!picked) return;
    if (!analysts.length) {
      toast.error("請至少選一個 analyst");
      return;
    }
    try {
      const res = await create.mutateAsync({
        body: {
          symbol: picked.symbol,
          analyst_types: analysts,
          llm_model: model,
          debate_rounds: debateRounds,
        },
        idempotencyKey: idemKey,
      });
      toast.success("分析已送出");
      router.push(`/analysis/${res.analysis_id}`);
    } catch (e) {
      const msg = (e as Error).message || "送出失敗";
      if (msg.includes("402") || msg.includes("quota")) {
        toast.error("本月 LLM 配額已用盡,請等下月或聯絡管理員調額");
      } else {
        toast.error(msg);
      }
      // 失敗後也換 key,以免 replay 卡住
      setIdemKey(uuidv4());
    }
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="flex flex-col gap-4 lg:col-span-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">新增分析</h1>
          <p className="text-sm text-muted-foreground">
            選股 → 選 analyst → 選模型 → 選辯論輪數 → 送出
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">1. 選擇股票</CardTitle>
            <CardDescription>從股票池搜尋(支援代號或名稱)</CardDescription>
          </CardHeader>
          <CardContent>
            <StockPicker
              value={picked?.symbol ?? null}
              triggerLabel={
                picked ? `${picked.symbol} ${picked.name || ""}`.trim() : undefined
              }
              onSelect={setPicked}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">2. 選擇 Analyst(可多選)</CardTitle>
            <CardDescription>
              {market === "US"
                ? "美股不支援情緒分析"
                : "至少選一個;選越多 cost 越高"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <AnalystChooser
              value={analysts}
              onChange={setAnalysts}
              market={market}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">3. 選擇 LLM 模型</CardTitle>
            <CardDescription>
              所有 analyst / debate 都用同一個模型
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Select
              value={model}
              onValueChange={(v) => v && setModel(v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LLM_MODELS.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.label} — {m.description}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">4. Bull / Bear 辯論輪數</CardTitle>
            <CardDescription>
              建議 1-2 輪;每多一輪會多 ~30 秒與 cost
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Select
              value={String(debateRounds)}
              onValueChange={(v) => v && setDebateRounds(Number(v))}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="0">0(跳過辯論)</SelectItem>
                <SelectItem value="1">1 輪(預設)</SelectItem>
                <SelectItem value="2">2 輪</SelectItem>
                <SelectItem value="3">3 輪</SelectItem>
              </SelectContent>
            </Select>
          </CardContent>
        </Card>
      </div>

      <aside className="flex flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">本月配額</CardTitle>
          </CardHeader>
          <CardContent>
            <QuotaProgress />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">預估</CardTitle>
            <CardDescription>實際成本以後端 llm_usage 為準</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">預估 cost</span>
              <span className="tabular-nums font-medium">
                US${estimated.low.toFixed(3)} ~ US${estimated.high.toFixed(3)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">預估時間</span>
              <span className="tabular-nums font-medium">
                約 {estimatedSeconds} 秒
              </span>
            </div>
          </CardContent>
        </Card>

        <Button
          size="lg"
          onClick={() => void submit()}
          disabled={!canSubmit}
          className="w-full"
        >
          {create.isPending ? "送出中..." : "送出分析"}
        </Button>
      </aside>
    </div>
  );
}
