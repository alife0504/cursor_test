"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface CursorPaginationProps {
  /** 目前頁面的下一頁 cursor;null 表示沒有下一頁 */
  nextCursor: string | null;
  hasMore: boolean;
  onNext: () => void;
  onPrev?: () => void;
  /** 是否可回上一頁;若不維護 stack,可設為 false */
  canGoBack?: boolean;
  className?: string;
}

// 後端統一使用 cursor pagination(PLAN § response_envelope/pagination),前端對應元件
export function Pagination({
  hasMore,
  onNext,
  onPrev,
  canGoBack = false,
  className,
}: CursorPaginationProps) {
  return (
    <div className={cn("flex items-center justify-end gap-2", className)}>
      {canGoBack && onPrev && (
        <Button variant="outline" size="sm" onClick={onPrev}>
          <ChevronLeft className="mr-1 h-4 w-4" />
          上一頁
        </Button>
      )}
      <Button
        variant="outline"
        size="sm"
        onClick={onNext}
        disabled={!hasMore}
      >
        下一頁
        <ChevronRight className="ml-1 h-4 w-4" />
      </Button>
    </div>
  );
}
