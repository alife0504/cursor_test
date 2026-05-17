"use client";

import "@xyflow/react/dist/style.css";

import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeTypes,
} from "@xyflow/react";
import { useMemo } from "react";

import { cn } from "@/lib/utils";

// Phase 16 § K:AgentFlowGraph
//   - 動態節點:analyst x N + bull/bear x debate_rounds + manager
//   - 狀態:pending(灰) / running(黃 animate) / completed(綠) / failed(紅)
//   - 重複事件用 Map by node id 去重(由父層保證 nodes prop 已去重)
//   - 簡易 left→right layout(每層垂直分散)

export type FlowNodeState = "pending" | "running" | "completed" | "failed";

export interface FlowNodeInput {
  id: string;
  label: string;
  sub?: string; // 副標(如:Round 1)
  group: "analyst" | "bull" | "bear" | "manager";
  state: FlowNodeState;
  // 容忍 ReactFlow 的 Record<string, unknown> 約束
  [k: string]: unknown;
}

const STATE_STYLE: Record<FlowNodeState, string> = {
  pending: "border-slate-300 bg-slate-50 text-slate-700",
  running:
    "border-amber-400 bg-amber-50 text-amber-900 animate-pulse shadow-md shadow-amber-200/50",
  completed: "border-emerald-400 bg-emerald-50 text-emerald-900",
  failed: "border-rose-400 bg-rose-50 text-rose-900",
};

const GROUP_LABEL: Record<FlowNodeInput["group"], string> = {
  analyst: "Analyst",
  bull: "Bull",
  bear: "Bear",
  manager: "Manager",
};

function FlowNodeView({ data }: { data: FlowNodeInput }) {
  return (
    <div
      data-testid={`flow-node-${data.id}`}
      data-state={data.state}
      className={cn(
        "min-w-[160px] rounded-md border-2 px-3 py-2 text-xs shadow-sm",
        STATE_STYLE[data.state],
      )}
      title={`${GROUP_LABEL[data.group]} · ${data.state}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-muted-foreground" />
      <div className="font-medium">{data.label}</div>
      {data.sub ? (
        <div className="text-[10px] text-muted-foreground">{data.sub}</div>
      ) : null}
      <div className="mt-1 inline-flex rounded bg-background/60 px-1 text-[10px] uppercase">
        {data.state}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-muted-foreground" />
    </div>
  );
}

const nodeTypes: NodeTypes = {
  flow: FlowNodeView as unknown as NodeTypes["flow"],
};

interface AgentFlowGraphProps {
  nodes: FlowNodeInput[];
  /** 每個 column 的索引;同 column 內節點垂直排;由 layout 函數推導 */
  className?: string;
}

interface LayoutGroup {
  column: number;
  rows: FlowNodeInput[];
}

function layoutGroups(nodes: FlowNodeInput[]): LayoutGroup[] {
  // 1. analyst 全部放 col 0
  // 2. debate 每輪 bull/bear 放 col 1, 2, 3...(bull/bear 同 column)
  // 3. manager 最後一 column
  const analystNodes = nodes.filter((n) => n.group === "analyst");
  const debateNodes = nodes.filter((n) => n.group === "bull" || n.group === "bear");
  const managerNodes = nodes.filter((n) => n.group === "manager");

  // group debate by round number(由 id 後綴 :round_N 或 sub 推導)
  const roundMap = new Map<number, FlowNodeInput[]>();
  for (const n of debateNodes) {
    const m = /round[_-]?(\d+)/i.exec(n.id) ?? /round[_-]?(\d+)/i.exec(n.sub ?? "");
    const round = m ? Number(m[1]) : 1;
    if (!roundMap.has(round)) roundMap.set(round, []);
    roundMap.get(round)!.push(n);
  }

  const groups: LayoutGroup[] = [];
  if (analystNodes.length) groups.push({ column: 0, rows: analystNodes });
  let col = 1;
  const sortedRounds = Array.from(roundMap.keys()).sort((a, b) => a - b);
  for (const round of sortedRounds) {
    groups.push({ column: col, rows: roundMap.get(round) ?? [] });
    col += 1;
  }
  if (managerNodes.length) groups.push({ column: col, rows: managerNodes });
  return groups;
}

export function AgentFlowGraph({ nodes, className }: AgentFlowGraphProps) {
  const { rfNodes, rfEdges } = useMemo(() => {
    // de-dup by id（PLAN trap:同事件重複到 → state 用 Map）
    const seen = new Map<string, FlowNodeInput>();
    for (const n of nodes) seen.set(n.id, n);
    const dedup = Array.from(seen.values());

    const groups = layoutGroups(dedup);
    const X_GAP = 220;
    const Y_GAP = 92;
    const Y_BASE = 20;

    const rfNodes: Node[] = [];
    const nodeIdToPos: Record<string, { x: number; y: number; column: number }> =
      {};

    for (const g of groups) {
      g.rows.forEach((n, i) => {
        const x = g.column * X_GAP;
        const y = Y_BASE + i * Y_GAP;
        rfNodes.push({
          id: n.id,
          type: "flow",
          position: { x, y },
          data: n,
          draggable: false,
        });
        nodeIdToPos[n.id] = { x, y, column: g.column };
      });
    }

    // edges:相鄰 column 之間全連
    const rfEdges: Edge[] = [];
    for (let i = 0; i < groups.length - 1; i += 1) {
      const from = groups[i];
      const to = groups[i + 1];
      for (const a of from.rows) {
        for (const b of to.rows) {
          rfEdges.push({
            id: `e-${a.id}-${b.id}`,
            source: a.id,
            target: b.id,
            type: "smoothstep",
            markerEnd: { type: MarkerType.ArrowClosed },
            style: { stroke: "#94a3b8" },
          });
        }
      }
    }

    return { rfNodes, rfEdges };
  }, [nodes]);

  return (
    <div
      className={cn("h-[360px] w-full rounded-md border bg-muted/20", className)}
      data-testid="agent-flow-graph"
    >
      <ReactFlowProvider>
        <ReactFlow
          nodes={rfNodes}
          edges={rfEdges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
