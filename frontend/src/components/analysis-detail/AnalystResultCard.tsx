"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface AnalystResultCardProps {
  type: string; // market / fundamental / news / sentiment
  content?: unknown;
}

// Phase 16 § E:Analyst 結果卡片(可展開)
//   - 後端 detail 不一定回 analyst raw output;此卡先顯示 type + 完成標記
//   - 真實 raw output 由 detail.report_md 全文呈現;之後 P17 補
export function AnalystResultCard({ type, content }: AnalystResultCardProps) {
  const [open, setOpen] = useState(false);
  const has = content !== null && content !== undefined;
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm">
          {type.charAt(0).toUpperCase() + type.slice(1)} Analyst
        </CardTitle>
        {has ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setOpen((o) => !o)}
            className="h-7"
          >
            {open ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
        ) : null}
      </CardHeader>
      <CardContent>
        {has ? (
          open ? (
            <pre className="overflow-x-auto rounded-md bg-muted/40 p-2 text-xs">
              {typeof content === "string"
                ? content
                : JSON.stringify(content, null, 2)}
            </pre>
          ) : (
            <p className="text-xs text-muted-foreground">已完成,點箭頭展開</p>
          )
        ) : (
          <p className="text-xs text-muted-foreground">尚未完成</p>
        )}
      </CardContent>
    </Card>
  );
}
