"use client";

import { Check, Search } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { useStocks } from "@/hooks/useStocks";
import type { StockSummary } from "@/lib/api-types";
import { cn } from "@/lib/utils";

interface StockPickerProps {
  value?: string | null;
  onSelect: (stock: StockSummary) => void;
  placeholder?: string;
  /** 已選股票的顯示字串（如 "2330 台積電"）；用來在非搜尋狀態回填輸入框。 */
  triggerLabel?: string;
  className?: string;
  /** 預設 false：全部市場；true 時只搜 TW。 */
  twOnly?: boolean;
  /** true 時禁用（灰階、不可輸入）；用於與自動選股互斥。 */
  disabled?: boolean;
}

function useDebounced<T>(value: T, ms = 200): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

// 股票搜尋器 — inline combobox。
//   - 直接在原地輸入（不再點按鈕彈出獨立小浮層）；輸入框 w-full 對齊容器外框。
//   - 打字 → debounce 200ms 對 /api/v1/stocks?q= 搜尋，結果在輸入框正下方展開。
//   - 鍵盤：↑/↓ 移動、Enter 選取、Esc 收起；點輸入框外自動收起。
//   - 共用元件：watchlist 加入、analysis/new 步驟 1 都會用。
export function StockPicker({
  value,
  onSelect,
  placeholder = "搜尋股票代號或名稱",
  triggerLabel,
  className,
  twOnly = false,
  disabled = false,
}: StockPickerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listboxId = useId();

  const [text, setText] = useState(triggerLabel ?? value ?? "");
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);

  const debounced = useDebounced(text, 200);
  // 已選定（text 等於回填 label）時不再搜尋，避免選完又跳出清單。
  const isSearching =
    open && debounced.trim().length > 0 && debounced !== triggerLabel;

  const { data, isFetching } = useStocks(
    { q: debounced, market: twOnly ? "TW" : undefined, limit: 20 },
    isSearching,
  );
  const items = useMemo(() => data?.items ?? [], [data]);

  // 父層更新已選股票（如深連結 ?symbol=）→ 非聚焦狀態時回填顯示。
  useEffect(() => {
    if (triggerLabel && document.activeElement !== inputRef.current) {
      setText(triggerLabel);
    }
  }, [triggerLabel]);

  // 清單來源變動 → highlight 歸零。
  useEffect(() => {
    setHighlight(0);
  }, [debounced]);

  // 點輸入框外 → 收起清單。
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const choose = (it: StockSummary) => {
    onSelect(it);
    // 清空搜尋字；受控用法（有 triggerLabel）會由上方 effect 回填顯示選取結果，
    // 未受控用法（如 compare 連續加入）則維持空白，方便接著加下一檔。
    setText("");
    setOpen(false);
    inputRef.current?.blur();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setHighlight((h) => Math.min(h + 1, Math.max(items.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      if (isSearching && items[highlight]) {
        e.preventDefault();
        choose(items[highlight]);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={containerRef} className={cn("relative w-full", className)}>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={isSearching}
          aria-controls={listboxId}
          aria-autocomplete="list"
          autoComplete="off"
          disabled={disabled}
          value={text}
          placeholder={placeholder}
          onChange={(e) => {
            setText(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          className={cn(
            "h-10 w-full rounded-lg border border-input bg-background py-2 pr-3 pl-9 text-sm",
            "placeholder:text-muted-foreground outline-none",
            "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50",
            "disabled:cursor-not-allowed disabled:opacity-60",
          )}
        />
      </div>

      {isSearching ? (
        <div
          id={listboxId}
          role="listbox"
          className="absolute z-50 mt-1 max-h-64 w-full overflow-auto rounded-lg bg-popover p-1 text-popover-foreground shadow-md ring-1 ring-foreground/10"
        >
          {isFetching && items.length === 0 ? (
            <div className="px-3 py-2 text-sm text-muted-foreground">搜尋中…</div>
          ) : items.length === 0 ? (
            <div className="px-3 py-2 text-sm text-muted-foreground">
              找不到符合的股票
            </div>
          ) : (
            items.map((it, idx) => (
              <button
                type="button"
                key={`${it.market}:${it.symbol}`}
                role="option"
                aria-selected={value === it.symbol}
                // 用 mousedown：先於 input 的 blur，避免 click 被取消。
                onMouseDown={(e) => {
                  e.preventDefault();
                  choose(it);
                }}
                onMouseEnter={() => setHighlight(idx)}
                className={cn(
                  "flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left",
                  idx === highlight ? "bg-muted text-foreground" : "",
                )}
              >
                <span className="flex min-w-0 flex-col">
                  <span className="text-sm font-medium">
                    {it.symbol}{" "}
                    <span className="text-xs text-muted-foreground">
                      ({it.market})
                    </span>
                  </span>
                  <span className="line-clamp-1 text-xs text-muted-foreground">
                    {it.name}
                  </span>
                </span>
                {value === it.symbol ? (
                  <Check className="h-4 w-4 shrink-0 text-primary" />
                ) : null}
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
