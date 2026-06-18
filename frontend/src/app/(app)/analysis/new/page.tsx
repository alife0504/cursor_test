"use client";

import { ChevronDown } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  AnalystChooser,
  ANALYST_OPTIONS,
  type AnalystType,
} from "@/components/analysis-new/AnalystChooser";
import { PageHeader } from "@/components/common/PageHeader";
import { StockPicker } from "@/components/common/StockPicker";
import { QuotaProgress } from "@/components/dashboard/QuotaProgress";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useCreateAnalysis } from "@/hooks/useAnalysis";
import { useLlmProviders } from "@/hooks/useLlmProviders";
import type { StockSummary } from "@/lib/api-types";
import { LLM_MODELS, estimateCostUsd } from "@/lib/llm-models";
import { cn } from "@/lib/utils";
import { uuidv4 } from "@/lib/uuid";

// 新增分析頁
//   - 選股 → 選 analyst → 每個 agent 各自選模型 → 辯論/風險輪數 → 送出
//   - 模型：預設模型 + 每個選到的 analyst 可覆寫 + 辯論/決策模型；組成 agent_models 送後端
//   - 右側為 sticky 摘要面板（配額 / 預估 / 送出）

// 辯論與決策階段的 agent role（共用一個「決策模型」）
const DECISION_ROLES = [
  "bull",
  "bear",
  "manager",
  "trader",
  "aggressive",
  "conservative",
  "neutral",
  "risk_manager",
];

const ANALYST_LABEL: Record<string, string> = Object.fromEntries(
  ANALYST_OPTIONS.map((o) => [o.id, o.label]),
);

export default function NewAnalysisPage() {
  return (
    <Suspense
      fallback={<div className="text-sm text-muted-foreground">載入中...</div>}
    >
      <NewAnalysisInner />
    </Suspense>
  );
}

/** 原生 <select>（取代 base-ui Select：保證可選、不會被裁切） */
function NativeSelect({
  value,
  onChange,
  options,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string; disabled?: boolean }[];
  className?: string;
}) {
  return (
    <div className={cn("relative", className)}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 w-full appearance-none rounded-lg border border-input bg-background py-1.5 pr-8 pl-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
    </div>
  );
}

type ModelOption = { value: string; label: string; disabled?: boolean };

/** 一列「標籤 → 模型下拉」，模型設定卡共用 */
function ModelSelectRow({
  label,
  value,
  onChange,
  hint,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  hint?: string;
  options: ModelOption[];
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="truncate text-sm">{label}</div>
        {hint ? (
          <div className="truncate text-xs text-muted-foreground">{hint}</div>
        ) : null}
      </div>
      <NativeSelect
        className="w-44 shrink-0"
        value={value}
        onChange={onChange}
        options={options}
      />
    </div>
  );
}

function NewAnalysisInner() {
  const router = useRouter();
  const search = useSearchParams();
  const initialSymbol = search.get("symbol");
  const [picked, setPicked] = useState<StockSummary | null>(
    initialSymbol
      ? { symbol: initialSymbol, market: "TW", name: "", is_active: true }
      : null,
  );
  const [analysts, setAnalysts] = useState<AnalystType[]>([
    "market",
    "fundamental",
  ]);
  // 模型：預設 + 每 analyst 覆寫 + 決策階段
  const [defaultModel, setDefaultModel] = useState<string>(LLM_MODELS[0].id);
  const [analystModels, setAnalystModels] = useState<Record<string, string>>(
    {},
  );
  const [decisionModel, setDecisionModel] = useState<string>(LLM_MODELS[0].id);
  const [debateRounds, setDebateRounds] = useState<number>(1);
  const [riskRounds, setRiskRounds] = useState<number>(0);
  const [idemKey, setIdemKey] = useState<string>(() => uuidv4());
  const create = useCreateAnalysis();

  // 依後端「實際有金鑰的 provider」標示/禁用模型選項（避免靜默降級誤導）
  const { data: llmInfo } = useLlmProviders();
  const availableProviders = llmInfo?.available_providers;
  const modelOptions = useMemo<ModelOption[]>(
    () =>
      LLM_MODELS.map((m) => {
        const unavailable =
          !!availableProviders && !availableProviders.includes(m.provider);
        return {
          value: m.id,
          label: unavailable ? `${m.label}(需金鑰)` : m.label,
          disabled: unavailable,
        };
      }),
    [availableProviders],
  );

  useEffect(() => {
    setIdemKey(uuidv4());
  }, [picked?.symbol]);

  const market: "TW" | "US" = useMemo(() => {
    const m = (picked?.market || "TW").toUpperCase();
    if (m === "NYSE" || m === "NASDAQ" || m === "AMEX" || m === "US")
      return "US";
    return "TW";
  }, [picked?.market]);

  useEffect(() => {
    if (market === "US" && analysts.includes("sentiment")) {
      setAnalysts((a) => a.filter((x) => x !== "sentiment"));
    }
  }, [market, analysts]);

  const estimated = estimateCostUsd(
    defaultModel,
    analysts.length,
    debateRounds,
    riskRounds,
  );
  const estimatedSeconds =
    60 + analysts.length * 30 + debateRounds * 30 + riskRounds * 90;

  const canSubmit =
    !!picked && analysts.length > 0 && debateRounds >= 0 && !create.isPending;

  const buildAgentModels = (): Record<string, string> => {
    const out: Record<string, string> = {};
    analysts.forEach((a) => {
      out[a] = analystModels[a] || defaultModel;
    });
    DECISION_ROLES.forEach((r) => {
      out[r] = decisionModel;
    });
    return out;
  };

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
          llm_model: defaultModel,
          agent_models: buildAgentModels(),
          debate_rounds: debateRounds,
          risk_rounds: riskRounds,
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
      setIdemKey(uuidv4());
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="新增分析"
        description="選股 → 選 analyst → 每個 agent 各自選模型 → 辯論 / 風險輪數 → 送出"
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3 lg:items-start">
        <div className="flex flex-col gap-4 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">1. 選擇股票</CardTitle>
              <CardDescription>從股票池搜尋(支援代號或名稱)</CardDescription>
            </CardHeader>
            <CardContent>
              <StockPicker
                value={picked?.symbol ?? null}
                triggerLabel={
                  picked
                    ? `${picked.symbol} ${picked.name || ""}`.trim()
                    : undefined
                }
                onSelect={setPicked}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                2. 選擇 Analyst(可多選)
              </CardTitle>
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
              <CardTitle className="text-base">
                3. 模型設定(每個 agent 可不同)
              </CardTitle>
              <CardDescription>
                未個別設定者使用「預設模型」;非 Google 模型需有對應 API key
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <ModelSelectRow
                label="預設模型"
                hint="沒特別指定的 agent 都用這個"
                value={defaultModel}
                onChange={setDefaultModel}
                options={modelOptions}
              />
              <div className="h-px bg-border" />
              <div className="text-xs font-medium text-muted-foreground">
                各分析師
              </div>
              {analysts.length === 0 ? (
                <div className="text-xs text-muted-foreground">
                  先在上方選 analyst
                </div>
              ) : (
                analysts.map((a) => (
                  <ModelSelectRow
                    key={a}
                    label={ANALYST_LABEL[a] ?? a}
                    value={analystModels[a] ?? defaultModel}
                    onChange={(v) =>
                      setAnalystModels((m) => ({ ...m, [a]: v }))
                    }
                    options={modelOptions}
                  />
                ))
              )}
              <div className="h-px bg-border" />
              <ModelSelectRow
                label="辯論與決策"
                hint="Bull / Bear / 研究經理 / Trader / 風險團隊"
                value={decisionModel}
                onChange={setDecisionModel}
                options={modelOptions}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">4. 辯論與風險設定</CardTitle>
              <CardDescription>輪數越多越深入,但成本與時間越高</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium">
                    Bull / Bear 辯論輪數
                  </label>
                  <NativeSelect
                    value={String(debateRounds)}
                    onChange={(v) => setDebateRounds(Number(v))}
                    options={[
                      { value: "0", label: "0(跳過辯論)" },
                      { value: "1", label: "1 輪(預設)" },
                      { value: "2", label: "2 輪" },
                      { value: "3", label: "3 輪" },
                    ]}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium">
                    風險辯論團隊(完整架構)
                  </label>
                  <NativeSelect
                    value={String(riskRounds)}
                    onChange={(v) => setRiskRounds(Number(v))}
                    options={[
                      { value: "0", label: "0(關閉，預設)" },
                      { value: "1", label: "1 輪" },
                      { value: "2", label: "2 輪" },
                      { value: "3", label: "3 輪" },
                    ]}
                  />
                </div>
              </div>
              {riskRounds > 0 ? (
                <p className="mt-3 text-xs text-muted-foreground">
                  啟用後加掛 Trader → 積極/保守/中立風險辯論 → 風險經理 →
                  接地查核;判斷更深，但成本與時間約增 1.8~2.5 倍
                </p>
              ) : null}
            </CardContent>
          </Card>
        </div>

        <aside className="flex flex-col gap-4 lg:sticky lg:top-4 lg:h-fit">
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
    </div>
  );
}
