"use client";

import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type RowData,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

// 讓每個 column 可透過 meta.align 指定對齊（代號/名稱 left、數字 right）。
declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData extends RowData, TValue> {
    align?: "left" | "right" | "center";
  }
}

function alignClass(align?: "left" | "right" | "center"): string {
  if (align === "right") return "text-right tabular-nums";
  if (align === "center") return "text-center";
  return "text-left";
}

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  isLoading?: boolean;
  emptyText?: string;
  className?: string;
}

// Phase 15 § R:基本 DataTable
//   - 包 @tanstack/react-table
//   - 支援排序(client-side)
//   - 真實 cursor pagination 由父層用 <Pagination /> 控制
export function DataTable<TData, TValue>({
  columns,
  data,
  isLoading = false,
  emptyText = "目前沒有資料",
  className,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (isLoading) {
    return <LoadingSkeleton rows={5} />;
  }

  if (!data.length) {
    return <EmptyState title={emptyText} />;
  }

  return (
    <div className={cn("rounded-md border", className)}>
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((hg) => (
            <TableRow key={hg.id}>
              {hg.headers.map((header) => (
                <TableHead
                  key={header.id}
                  className={alignClass(header.column.columnDef.meta?.align)}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <TableCell
                  key={cell.id}
                  className={alignClass(cell.column.columnDef.meta?.align)}
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
