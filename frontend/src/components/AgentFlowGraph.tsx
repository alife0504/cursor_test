"use client";

import "@xyflow/react/dist/style.css";

import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeTypes,
} from "@xyflow/react";
import {
  CheckCircle2,
  Loader2,
  Sparkles,
  TrendingDown,
  TrendingUp,
  UserCog,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { useMemo } from "react";

import { cn } from "@/lib/utils";

// AgentFlowGraph：動態節點圖（左→右）
//   - analyst x N → debate round x N（bull/bear 同 column）→ manager
//   - 重複事件用 Map by id 去重（父層保證已去重）
//   - 用色彩 token + icon + 動態 stroke 表達狀態

export type FlowNodeState = "pending" | "running" | "completed" | "failed";

export interface FlowNodeInput {
  id: string;
  label: string;
  sub?: string;
  group: "analyst" | "bull" | "bear" | "manager";
  state: FlowNodeState;
  [k: string]: unknown;
}

const STATE_STYLE: Record<FlowNodeState, string> = {
  pending:
    "border-state-pending bg-state-pending-muted text-flat",
  running:
    "border-state-running bg-state-running-muted text-state-running animate-pulse-glow",
  completed:
    "border-state-done bg-state-done-muted text-state-done",
  failed: "border-state-failed bg-state-failed-muted text-state-failed",
};

const STATE_ICON: Record<FlowNodeState, LucideIcon> = {
  pending: Sparkles,
  running: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
};

const GROUP_ICON: Record<FlowNodeInput["group"], LucideIcon> = {
  analyst: Sparkles,
  bull: TrendingUp,
  bear: TrendingDown,
  manager: UserCog,
};

const GROUP_LABEL: Record<FlowNodeInput["group"], string> = {
  analyst: "Analyst",
  bull: "Bull（看多）",
  bear: "Bear（看空）",
  manager: "Manager",
};

const STATE_LABEL: Record<FlowNodeState, string> = {
  pending: "待執行",
  running: "進行中",
  completed: "已完成",
  failed: "失敗",
};

function FlowNodeView({ data }: { data: FlowNodeInput }) {
  const StateIcon = STATE_ICON[data.state];
  const GroupIcon = GROUP_ICON[data.group];
  return (
    <div
      data-testid={`flow-node-${data.id}`}
      data-state={data.state}
      data-group={data.group}
      className={cn(
        "min-w-[180px] rounded-lg border-2 px-3 py-2.5 text-xs shadow-soft transition-shadow",
        STATE_STYLE[data.state],
      )}
      title={`${GROUP_LABEL[data.group]} · ${STATE_LABEL[data.state]}`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-muted-foreground/60"
      />
      <div className="flex items-center gap-1.5">
        <GroupIcon className="h-3.5 w-3.5 opacity-80" />
        <span className="font-semibold">{data.label}</span>
      </div>
      {data.sub ? (
        <div className="mt-0.5 ml-5 text-[10px] text-muted-foreground">
          {data.sub}
        </div>
      ) : null}
      <div className="mt-1.5 ml-5 inline-flex items-center gap-1 rounded-full bg-background/70 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide">
        <StateIcon
          className={cn(
            "h-3 w-3",
            data.state === "running" && "animate-spin",
          )}
        />
        {STATE_LABEL[data.state]}
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-muted-foreground/60"
      />
    </div>
  );
}

const nodeTypes: NodeTypes = {
  flow: FlowNodeView as unknown as NodeTypes["flow"],
};

interface AgentFlowGraphProps {
  nodes: FlowNodeInput[];
  className?: string;
}

interface LayoutGroup {
  column: number;
  rows: FlowNodeInput[];
}

function layoutGroups(nodes: FlowNodeInput[]): LayoutGroup[] {
  const analystNodes = nodes.filter((n) => n.group === "analyst");
  const debateNodes = nodes.filter(
    (n) => n.group === "bull" || n.group === "bear",
  );
  const managerNodes = nodes.filter((n) => n.group === "manager");

  const roundMap = new Map<number, FlowNodeInput[]>();
  for (const n of debateNodes) {
    const m =
      /round[_-]?(\d+)/i.exec(n.id) ?? /round[_-]?(\d+)/i.exec(n.sub ?? "");
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

function edgeStateColor(state: FlowNodeState): string {
  switch (state) {
    case "completed":
      return "hsl(var(--state-done))";
    case "running":
      return "hsl(var(--state-running))";
    case "failed":
      return "hsl(var(--state-failed))";
    default:
      return "hsl(var(--state-pending))";
  }
}

export function AgentFlowGraph({ nodes, className }: AgentFlowGraphProps) {
  const { rfNodes, rfEdges } = useMemo(() => {
    const seen = new Map<string, FlowNodeInput>();
    for (const n of nodes) seen.set(n.id, n);
    const dedup = Array.from(seen.values());

    const groups = layoutGroups(dedup);
    const X_GAP = 260;
    const Y_GAP = 110;
    const Y_BASE = 24;

    const rfNodes: Node[] = [];
    for (const g of groups) {
      g.rows.forEach((n, i) => {
        rfNodes.push({
          id: n.id,
          type: "flow",
          position: { x: g.column * X_GAP, y: Y_BASE + i * Y_GAP },
          data: n,
          draggable: false,
        });
      });
    }

    const rfEdges: Edge[] = [];
    for (let i = 0; i < groups.length - 1; i += 1) {
      const from = groups[i];
      const to = groups[i + 1];
      for (const a of from.rows) {
        for (const b of to.rows) {
          // edge 顏色取決於 source state（done = 綠、running = 橙）
          const stroke = edgeStateColor(a.state);
          const animated = a.state === "running";
          rfEdges.push({
            id: `e-${a.id}-${b.id}`,
            source: a.id,
            target: b.id,
            type: "smoothstep",
            animated,
            markerEnd: { type: MarkerType.ArrowClosed, color: stroke },
            style: { stroke, strokeWidth: 1.5 },
          });
        }
      }
    }

    return { rfNodes, rfEdges };
  }, [nodes]);

  return (
    <div
      className={cn(
        "h-[420px] w-full overflow-hidden rounded-lg border bg-muted/10 sm:h-[480px]",
        className,
      )}
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
          <Background gap={20} className="bg-muted/20" />
          <Controls showInteractive={false} className="!bg-card !border" />
          <MiniMap
            zoomable
            pannable
            position="bottom-right"
            className="!bg-card !border"
            nodeColor={(node) => {
              const data = node.data as FlowNodeInput | undefined;
              if (!data) return "hsl(var(--state-pending))";
              return edgeStateColor(data.state);
            }}
            maskColor="hsl(var(--background) / 0.6)"
          />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
