"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";
import { formatDateTime, formatDate, formatRelative } from "@/lib/format";

type Mode = "datetime" | "date" | "relative";

interface DateFormatProps {
  value: string | null | undefined;
  mode?: Mode;
  timezone?: string;
  className?: string;
  fallback?: string;
}

// Hydration-safe DateFormat:
//   - SSR 與 client 第一次渲染都用 UTC 格式(避免時區 mismatch)
//   - client 端 mount 後切換到使用者時區
export function DateFormat({
  value,
  mode = "datetime",
  timezone,
  className,
  fallback = "-",
}: DateFormatProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const tz =
    timezone ||
    (typeof window !== "undefined"
      ? process.env.NEXT_PUBLIC_DEFAULT_TIMEZONE || "Asia/Taipei"
      : "UTC");

  let text: string;
  if (mode === "relative") {
    text = formatRelative(value, undefined, fallback);
  } else if (mode === "date") {
    text = formatDate(value, mounted ? tz : "UTC", fallback);
  } else {
    text = formatDateTime(
      value,
      mounted ? tz : "UTC",
      "YYYY-MM-DD HH:mm:ss",
      fallback,
    );
  }
  return <span className={cn("tabular-nums", className)}>{text}</span>;
}
