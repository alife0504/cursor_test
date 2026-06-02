"use client";

import { ColumnDef } from "@tanstack/react-table";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

import { DataTable } from "@/components/common/DataTable";
import { DateFormat } from "@/components/common/DateFormat";
import { ErrorState } from "@/components/common/ErrorState";
import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuditLogs } from "@/hooks/useAdmin";
import type { AuditLogItem } from "@/lib/api-types";

// Phase 16 § J:審計日誌(僅 ADMIN)
//   - 篩選:actor / action / entity / date range
//   - cursor pagination
//   - 點擊展開 details JSON

interface DetailsRowProps {
  log: AuditLogItem;
  expanded: boolean;
  onToggle: () => void;
}

function ActionCell({ log, expanded, onToggle }: DetailsRowProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="flex items-center gap-1 text-left hover:underline"
    >
      {expanded ? (
        <ChevronDown className="h-3 w-3" />
      ) : (
        <ChevronRight className="h-3 w-3" />
      )}
      <span className="font-mono text-xs">{log.action}</span>
    </button>
  );
}

export default function AuditPage() {
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const [entity, setEntity] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [appliedFilters, setAppliedFilters] = useState<{
    actor?: string;
    action?: string;
    entity?: string;
    from?: string;
    to?: string;
  }>({});
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const cursor = cursorStack[cursorStack.length - 1];
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  const { data, isLoading, error } = useAuditLogs({
    actor: appliedFilters.actor || null,
    action: appliedFilters.action || null,
    entity: appliedFilters.entity || null,
    from: appliedFilters.from || null,
    to: appliedFilters.to || null,
    cursor,
  });
  const items = data?.items ?? [];

  const applyFilter = () => {
    setAppliedFilters({ actor, action, entity, from, to });
    setCursorStack([null]);
  };
  const clearFilter = () => {
    setActor("");
    setAction("");
    setEntity("");
    setFrom("");
    setTo("");
    setAppliedFilters({});
    setCursorStack([null]);
  };

  const columns: ColumnDef<AuditLogItem>[] = [
    {
      accessorKey: "timestamp",
      header: "時間",
      cell: ({ row }) => (
        <DateFormat value={row.original.timestamp} mode="datetime" />
      ),
    },
    {
      accessorKey: "actor_id",
      header: "Actor",
      cell: ({ row }) => (
        <span className="font-mono text-xs">
          {row.original.actor_id?.slice(0, 8) ?? "system"}
        </span>
      ),
    },
    {
      accessorKey: "action",
      header: "Action",
      cell: ({ row }) => (
        <ActionCell
          log={row.original}
          expanded={!!expanded[row.original.id]}
          onToggle={() =>
            setExpanded((s) => ({ ...s, [row.original.id]: !s[row.original.id] }))
          }
        />
      ),
    },
    {
      accessorKey: "entity_type",
      header: "Entity",
      cell: ({ row }) => (
        <span className="text-xs">
          {row.original.entity_type ?? "-"}
          {row.original.entity_id ? (
            <span className="ml-1 font-mono text-muted-foreground">
              {row.original.entity_id.slice(0, 8)}
            </span>
          ) : null}
        </span>
      ),
    },
    {
      accessorKey: "request_id",
      header: "trace_id",
      cell: ({ row }) => (
        <span className="font-mono text-xs text-muted-foreground">
          {row.original.request_id ?? "-"}
        </span>
      ),
    },
  ];

  const detailRows = items.filter((it) => expanded[it.id]);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="審計日誌"
        description="Tamper-evident 紀錄（hash chain）。僅 ADMIN 可看"
      />

      <div className="grid grid-cols-1 gap-2 rounded-md border p-3 md:grid-cols-5">
        <div>
          <Label htmlFor="f-actor">Actor</Label>
          <Input
            id="f-actor"
            value={actor}
            onChange={(e) => setActor(e.target.value)}
            placeholder="user_id 前綴"
          />
        </div>
        <div>
          <Label htmlFor="f-action">Action</Label>
          <Input
            id="f-action"
            value={action}
            onChange={(e) => setAction(e.target.value)}
            placeholder="如 auth.login.success"
          />
        </div>
        <div>
          <Label htmlFor="f-entity">Entity</Label>
          <Input
            id="f-entity"
            value={entity}
            onChange={(e) => setEntity(e.target.value)}
            placeholder="如 user / analysis"
          />
        </div>
        <div>
          <Label htmlFor="f-from">From (UTC)</Label>
          <Input
            id="f-from"
            type="datetime-local"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="f-to">To (UTC)</Label>
          <Input
            id="f-to"
            type="datetime-local"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </div>
        <div className="md:col-span-5 flex items-center justify-end gap-2">
          <Button variant="outline" onClick={clearFilter}>
            清除
          </Button>
          <Button onClick={applyFilter}>套用</Button>
        </div>
      </div>

      {error ? (
        <ErrorState
          title="無法載入審計日誌"
          variant="inline"
          onRetry={() => {
            if (typeof window !== "undefined") window.location.reload();
          }}
          error={error}
        />
      ) : null}

      <DataTable
        columns={columns}
        data={items}
        isLoading={isLoading}
        emptyText="此條件下沒有紀錄"
      />

      {detailRows.length > 0 ? (
        <div className="rounded-md border">
          {detailRows.map((it) => (
            <div key={`detail-${it.id}`} className="border-b p-3 last:border-b-0">
              <div className="mb-1 text-xs text-muted-foreground">
                展開 #{it.id} ({it.action})
              </div>
              <pre className="overflow-x-auto rounded-md bg-muted/40 p-2 text-xs">
                {JSON.stringify(it.details ?? {}, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      ) : null}

      <Pagination
        hasMore={!!data?.hasMore}
        canGoBack={cursorStack.length > 1}
        onPrev={() => setCursorStack((s) => s.slice(0, -1))}
        onNext={() =>
          data?.nextCursor &&
          setCursorStack((s) => [...s, data.nextCursor as string])
        }
      />
    </div>
  );
}
