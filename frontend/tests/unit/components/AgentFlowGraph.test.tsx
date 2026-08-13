/**
 * @vitest-environment jsdom
 */
import { render } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import {
  AgentFlowGraph,
  type FlowNodeInput,
} from "@/components/AgentFlowGraph";

// jsdom 沒實作 ResizeObserver / DOMRect.toJSON,ReactFlow 需要 polyfill
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === "undefined") {
    globalThis.ResizeObserver = class {
      observe(): void {}
      unobserve(): void {}
      disconnect(): void {}
    } as unknown as typeof ResizeObserver;
  }
});

import { beforeAll } from "vitest";

describe("<AgentFlowGraph />", () => {
  test("空 nodes 渲染容器", () => {
    const { getByTestId } = render(<AgentFlowGraph nodes={[]} />);
    expect(getByTestId("agent-flow-graph")).toBeInTheDocument();
  });

  test("渲染 analyst + manager 節點", () => {
    const nodes: FlowNodeInput[] = [
      {
        id: "analyst:market",
        label: "Market",
        group: "analyst",
        state: "pending",
      },
      {
        id: "manager",
        label: "Manager",
        group: "manager",
        state: "pending",
      },
    ];
    const { getByTestId } = render(<AgentFlowGraph nodes={nodes} />);
    expect(getByTestId("flow-node-analyst:market")).toBeInTheDocument();
    expect(getByTestId("flow-node-manager")).toBeInTheDocument();
  });

  test("重複 id 的事件不會渲染兩次(去重 by Map)", () => {
    const nodes: FlowNodeInput[] = [
      {
        id: "analyst:market",
        label: "Market(舊)",
        group: "analyst",
        state: "pending",
      },
      {
        id: "analyst:market",
        label: "Market(新)",
        group: "analyst",
        state: "completed",
      },
    ];
    const { getAllByTestId, getByText } = render(
      <AgentFlowGraph nodes={nodes} />,
    );
    expect(getAllByTestId("flow-node-analyst:market")).toHaveLength(1);
    // 後寫入的 state 取勝(Map.set 覆寫)
    expect(getByText("Market(新)")).toBeInTheDocument();
  });

  test("不同 state 套用不同 data-state", () => {
    const nodes: FlowNodeInput[] = [
      {
        id: "a:1",
        label: "Running",
        group: "analyst",
        state: "running",
      },
      {
        id: "a:2",
        label: "Done",
        group: "analyst",
        state: "completed",
      },
      {
        id: "a:3",
        label: "Bad",
        group: "analyst",
        state: "failed",
      },
    ];
    const { getByTestId } = render(<AgentFlowGraph nodes={nodes} />);
    expect(getByTestId("flow-node-a:1").getAttribute("data-state")).toBe(
      "running",
    );
    expect(getByTestId("flow-node-a:2").getAttribute("data-state")).toBe(
      "completed",
    );
    expect(getByTestId("flow-node-a:3").getAttribute("data-state")).toBe(
      "failed",
    );
  });

  test("多輪 debate:bull / bear 都渲染", () => {
    const nodes: FlowNodeInput[] = [
      { id: "analyst:market", label: "M", group: "analyst", state: "completed" },
      { id: "bull:round_1", label: "Bull", group: "bull", state: "completed" },
      { id: "bear:round_1", label: "Bear", group: "bear", state: "completed" },
      { id: "bull:round_2", label: "Bull", group: "bull", state: "running" },
      { id: "bear:round_2", label: "Bear", group: "bear", state: "pending" },
      { id: "manager", label: "Manager", group: "manager", state: "pending" },
    ];
    const { getByTestId } = render(<AgentFlowGraph nodes={nodes} />);
    expect(getByTestId("flow-node-bull:round_1")).toBeInTheDocument();
    expect(getByTestId("flow-node-bull:round_2")).toBeInTheDocument();
    expect(getByTestId("flow-node-bear:round_1")).toBeInTheDocument();
    expect(getByTestId("flow-node-manager")).toBeInTheDocument();
  });
});

// 防止 lint 報 unused
const _silence = vi.fn();
_silence();
