"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export type AnalystType =
  | "market"
  | "fundamental"
  | "news"
  | "sentiment"
  | "chip";

export interface AnalystOption {
  id: AnalystType;
  label: string;
  description: string;
  twOnly?: boolean;
  /** twOnly 時,美股禁用卡片顯示的原因 */
  twOnlyReason?: string;
}

const OPTIONS: AnalystOption[] = [
  {
    id: "market",
    label: "Market(技術面)",
    description: "RSI / MACD / KD / 布林 / 量價結構",
  },
  {
    id: "fundamental",
    label: "Fundamental(基本面)",
    description: "ROE / EPS / 毛利率 / 估值",
  },
  {
    id: "news",
    label: "News(新聞 / 總經)",
    description: "個股新聞 / 公告 + 大盤總經脈絡",
  },
  {
    id: "sentiment",
    label: "Sentiment(情緒)",
    description: "新聞情緒聚合:市場情緒溫度 / 熱度 / 動能",
    twOnly: true,
    twOnlyReason: "情緒面以台股新聞語氣聚合,僅支援台股",
  },
  {
    id: "chip",
    label: "Chip(籌碼面)",
    description: "三大法人 / 融資融券 / 月營收",
    twOnly: true,
    twOnlyReason: "籌碼面（三大法人 / 融資券）為台股專屬資料",
  },
];

interface AnalystChooserProps {
  value: AnalystType[];
  onChange: (next: AnalystType[]) => void;
  market: "TW" | "US";
}

// Phase 16 § D 步驟 2:選 analyst(多選)
//   - 籌碼面（sentiment）為台股專屬：美股時「顯示但禁用 + 標註原因」，不隱藏（避免選項憑空消失）
export function AnalystChooser({ value, onChange, market }: AnalystChooserProps) {
  const toggle = (id: AnalystType) => {
    if (value.includes(id)) {
      onChange(value.filter((v) => v !== id));
    } else {
      onChange([...value, id]);
    }
  };
  return (
    <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
      {OPTIONS.map((o) => {
        const isDisabled = !!o.twOnly && market === "US";
        const checked = value.includes(o.id) && !isDisabled;
        return (
          <label
            key={o.id}
            htmlFor={`analyst-${o.id}`}
            className={cn(
              "flex items-start gap-3 rounded-md border p-3 transition-colors",
              isDisabled
                ? "cursor-not-allowed border-dashed opacity-60"
                : checked
                  ? "cursor-pointer border-primary bg-primary/5"
                  : "cursor-pointer hover:bg-muted/40",
            )}
          >
            <Checkbox
              id={`analyst-${o.id}`}
              checked={checked}
              disabled={isDisabled}
              onCheckedChange={() => {
                if (!isDisabled) toggle(o.id);
              }}
            />
            <div className="flex flex-col">
              <Label
                htmlFor={`analyst-${o.id}`}
                className={cn(
                  "flex items-center gap-2 font-medium",
                  isDisabled ? "cursor-not-allowed" : "cursor-pointer",
                )}
              >
                {o.label}
                {isDisabled ? (
                  <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-normal text-muted-foreground">
                    美股不支援
                  </span>
                ) : null}
              </Label>
              <span className="text-xs text-muted-foreground">
                {isDisabled
                  ? (o.twOnlyReason ?? "此分析師僅支援台股")
                  : o.description}
              </span>
            </div>
          </label>
        );
      })}
    </div>
  );
}

export { OPTIONS as ANALYST_OPTIONS };
