"use client";

import { Check, Search } from "lucide-react";
import { useState } from "react";

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useStocks } from "@/hooks/useStocks";
import type { StockSummary } from "@/lib/api-types";
import { cn } from "@/lib/utils";

interface StockPickerProps {
  value?: string | null;
  onSelect: (stock: StockSummary) => void;
  placeholder?: string;
  triggerLabel?: string;
  className?: string;
  /** 預設 false:全部市場;true 時只搜 TW */
  twOnly?: boolean;
}

// Phase 16 § C-D:cmdk 股票搜尋器
//   - 對 /api/v1/stocks?q= 搜尋
//   - 共用元件:watchlist 加入、analysis/new 步驟 1 都會用
export function StockPicker({
  value,
  onSelect,
  placeholder = "搜尋股票代號或名稱",
  triggerLabel,
  className,
  twOnly = false,
}: StockPickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const { data, isFetching } = useStocks(
    { q: query, market: twOnly ? "TW" : undefined, limit: 20 },
    query.trim().length > 0,
  );
  const items = data?.items ?? [];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <button
            type="button"
            className={cn(
              "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm text-left",
              "ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring",
              className,
            )}
          >
            <span className="flex items-center gap-2 truncate text-muted-foreground">
              <Search className="h-4 w-4" />
              {triggerLabel || value || placeholder}
            </span>
          </button>
        }
      />
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder={placeholder}
            value={query}
            onValueChange={setQuery}
          />
          <CommandList>
            {!isFetching && items.length === 0 ? (
              <CommandEmpty>
                {query.trim() ? "找不到符合的股票" : "輸入關鍵字搜尋"}
              </CommandEmpty>
            ) : null}
            <CommandGroup>
              {items.map((it) => (
                <CommandItem
                  key={`${it.market}:${it.symbol}`}
                  value={`${it.symbol}:${it.name}`}
                  onSelect={() => {
                    onSelect(it);
                    setOpen(false);
                    setQuery("");
                  }}
                  className="flex items-center justify-between gap-2"
                >
                  <div className="flex flex-col">
                    <span className="font-medium">
                      {it.symbol}{" "}
                      <span className="text-xs text-muted-foreground">
                        ({it.market})
                      </span>
                    </span>
                    <span className="text-xs text-muted-foreground line-clamp-1">
                      {it.name}
                    </span>
                  </div>
                  {value === it.symbol ? (
                    <Check className="h-4 w-4 text-primary" />
                  ) : null}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
