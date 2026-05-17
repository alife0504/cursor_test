"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

export type AnalystType = "market" | "fundamental" | "news" | "sentiment";

export interface AnalystOption {
  id: AnalystType;
  label: string;
  description: string;
  twOnly?: boolean;
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
    label: "News(新聞 / 公告)",
    description: "近期新聞分群與摘要",
  },
  {
    id: "sentiment",
    label: "Sentiment(情緒)",
    description: "PTT / 論壇情緒;僅支援台股",
    twOnly: true,
  },
];

interface AnalystChooserProps {
  value: AnalystType[];
  onChange: (next: AnalystType[]) => void;
  market: "TW" | "US";
}

// Phase 16 § D 步驟 2:選 analyst(多選)
//   - US 不顯示 sentiment(後端會擋,前端先過濾)
export function AnalystChooser({ value, onChange, market }: AnalystChooserProps) {
  const visible = OPTIONS.filter((o) => !(o.twOnly && market === "US"));
  const toggle = (id: AnalystType) => {
    if (value.includes(id)) {
      onChange(value.filter((v) => v !== id));
    } else {
      onChange([...value, id]);
    }
  };
  return (
    <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
      {visible.map((o) => {
        const checked = value.includes(o.id);
        return (
          <label
            key={o.id}
            htmlFor={`analyst-${o.id}`}
            className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 transition-colors ${
              checked ? "border-primary bg-primary/5" : "hover:bg-muted/40"
            }`}
          >
            <Checkbox
              id={`analyst-${o.id}`}
              checked={checked}
              onCheckedChange={() => toggle(o.id)}
            />
            <div className="flex flex-col">
              <Label
                htmlFor={`analyst-${o.id}`}
                className="cursor-pointer font-medium"
              >
                {o.label}
              </Label>
              <span className="text-xs text-muted-foreground">
                {o.description}
              </span>
            </div>
          </label>
        );
      })}
    </div>
  );
}

export { OPTIONS as ANALYST_OPTIONS };
