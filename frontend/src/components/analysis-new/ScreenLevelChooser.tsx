"use client";

import { cn } from "@/lib/utils";

export type ScreenLevel = "low" | "mid" | "high";

export interface ScreenLevelOption {
  id: ScreenLevel;
  label: string;
  /** 保留量標籤（右側 badge） */
  keep: string;
  /** 該等級的篩選條件說明（顯示於等級之下） */
  description: string;
}

// 步驟 2：自動選股篩選（未指定個股時啟用）
//   - 「基本」是必備 floor（剔除停牌/低流動性/雞蛋水餃股），永遠先套用、非可選等級。
//   - 低/中/高才是可選等級，各保留約 600/300/150 檔（絕對數）；愈高愈嚴、留得愈少。
//   - 因子只用價量技術面（流動性/均線/RSI/漲幅/量能波動）；漸進疊加。
const OPTIONS: ScreenLevelOption[] = [
  {
    id: "low",
    label: "低級",
    keep: "約 600 檔",
    description:
      "基本 +趨勢：站上季線（60MA）、均線多頭排列程度。依趨勢強弱排序，取前約 600 檔。",
  },
  {
    id: "mid",
    label: "中級",
    keep: "約 300 檔",
    description:
      "低級 +動能：近 20 日相對強度、RSI 落健康區間（避開超買超賣）。趨勢 + 動能綜合取前約 300 檔。",
  },
  {
    id: "high",
    label: "高級",
    keep: "約 150 檔",
    description:
      "中級 +量能 / 波動品質：帶量表態、波動適中（濾掉暴漲暴跌）。綜合評分最嚴，取前約 150 檔。",
  },
];

interface ScreenLevelChooserProps {
  /** 目前選取的等級；null = 未選（此時步驟 1 可選股） */
  value: ScreenLevel | null;
  /** 點已選等級可再取消（回 null）→ 解除與步驟 1 的互斥 */
  onChange: (next: ScreenLevel | null) => void;
  /** 步驟 1 已指定個股時 → 略過本步驟，整組禁用並灰階 */
  disabled?: boolean;
}

export function ScreenLevelChooser({
  value,
  onChange,
  disabled,
}: ScreenLevelChooserProps) {
  return (
    <div
      className="flex flex-col gap-2"
      role="radiogroup"
      aria-label="自動選股篩選強度"
    >
      {OPTIONS.map((o) => {
        const checked = !disabled && value === o.id;
        return (
          <button
            key={o.id}
            type="button"
            role="radio"
            aria-checked={checked}
            disabled={disabled}
            // 點已選 → 取消（null）；否則選取。
            onClick={() => onChange(checked ? null : o.id)}
            className={cn(
              "flex items-start gap-3 rounded-md border p-3 text-left transition-colors",
              disabled
                ? "cursor-not-allowed opacity-60"
                : checked
                  ? "cursor-pointer border-primary bg-primary/5"
                  : "cursor-pointer hover:bg-muted/40",
            )}
          >
            {/* radio 圓點（單選視覺指示） */}
            <span
              className={cn(
                "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border",
                checked ? "border-primary" : "border-input",
              )}
            >
              {checked ? (
                <span className="size-2 rounded-full bg-primary" />
              ) : null}
            </span>
            <div className="flex flex-col">
              <span className="flex items-center gap-2 font-medium">
                {o.label}
                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-normal text-muted-foreground">
                  {o.keep}
                </span>
              </span>
              <span className="text-xs text-muted-foreground">
                {o.description}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

export { OPTIONS as SCREEN_LEVEL_OPTIONS };
