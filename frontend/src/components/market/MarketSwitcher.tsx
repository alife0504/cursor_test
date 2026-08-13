"use client";

import { useTransition } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Phase 17 § B:TW / US 切換
//   - PLAN 已知陷阱:跨市場切換閃爍 → useTransition

interface MarketSwitcherProps {
  value: "TW" | "US";
  onChange: (m: "TW" | "US") => void;
  className?: string;
}

export function MarketSwitcher({ value, onChange, className }: MarketSwitcherProps) {
  const [isPending, startTransition] = useTransition();
  const handle = (m: "TW" | "US") => () =>
    startTransition(() => onChange(m));
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1 rounded-md border bg-card p-1",
        isPending && "opacity-70",
        className,
      )}
      role="tablist"
    >
      {(["TW", "US"] as const).map((m) => (
        <Button
          key={m}
          role="tab"
          aria-selected={value === m}
          variant={value === m ? "default" : "ghost"}
          size="sm"
          onClick={handle(m)}
        >
          {m === "TW" ? "台股" : "美股"}
        </Button>
      ))}
    </div>
  );
}
