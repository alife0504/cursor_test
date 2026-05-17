import { describe, expect, test } from "vitest";

import { buildFlowNodes } from "@/components/analysis-detail/buildFlowNodes";
import type { AnalysisDetail, DebateMessage } from "@/lib/api-types";

const baseAnalysis: AnalysisDetail = {
  id: "a-1",
  user_id: "u-1",
  symbol: "2330",
  market: "TWSE",
  status: "running",
  total_tokens: 0,
  total_cost_usd: "0",
  version: 1,
  created_at: "2026-05-17T00:00:00Z",
};

describe("buildFlowNodes", () => {
  test("空 analysis 回空陣列", () => {
    const nodes = buildFlowNodes({ analysis: null, events: [] });
    expect(nodes).toEqual([]);
  });

  test("running 狀態:全部 pending(無 events)", () => {
    const nodes = buildFlowNodes({
      analysis: baseAnalysis,
      analystTypes: ["market"],
      events: [],
    });
    const market = nodes.find((n) => n.id === "analyst:market");
    expect(market?.state).toBe("pending");
  });

  test("started + analyst_completed → 該 analyst 為 completed", () => {
    const nodes = buildFlowNodes({
      analysis: baseAnalysis,
      analystTypes: ["market", "news"],
      events: [
        { type: "started" },
        { type: "analyst_completed", payload: { name: "market" } },
      ],
    });
    const market = nodes.find((n) => n.id === "analyst:market");
    const news = nodes.find((n) => n.id === "analyst:news");
    expect(market?.state).toBe("completed");
    expect(news?.state).toBe("running");
  });

  test("status=completed:全部標 completed", () => {
    const nodes = buildFlowNodes({
      analysis: { ...baseAnalysis, status: "completed" },
      analystTypes: ["market"],
      events: [],
    });
    nodes.forEach((n) => {
      expect(n.state).toBe("completed");
    });
  });

  test("status=failed:全部標 failed", () => {
    const nodes = buildFlowNodes({
      analysis: { ...baseAnalysis, status: "failed" },
      analystTypes: ["market"],
      events: [],
    });
    nodes.forEach((n) => {
      expect(n.state).toBe("failed");
    });
  });

  test("debateMessages 推導出 debate node 並標 completed", () => {
    const debate: DebateMessage[] = [
      {
        id: "d-1",
        analysis_id: "a-1",
        round_num: 1,
        role: "bull",
        content: { text: "bull text" },
        created_at: "2026-05-17T01:00:00Z",
      },
      {
        id: "d-2",
        analysis_id: "a-1",
        round_num: 1,
        role: "bear",
        content: { text: "bear text" },
        created_at: "2026-05-17T01:01:00Z",
      },
    ];
    const nodes = buildFlowNodes({
      analysis: baseAnalysis,
      analystTypes: ["market"],
      debateMessages: debate,
      events: [],
    });
    const bull = nodes.find((n) => n.id === "bull:round_1");
    const bear = nodes.find((n) => n.id === "bear:round_1");
    expect(bull?.state).toBe("completed");
    expect(bear?.state).toBe("completed");
  });

  test("synthesis_completed event 標 manager 為 completed", () => {
    const nodes = buildFlowNodes({
      analysis: baseAnalysis,
      analystTypes: ["market"],
      events: [
        { type: "started" },
        { type: "synthesis_completed" },
      ],
    });
    const manager = nodes.find((n) => n.id === "manager");
    expect(manager?.state).toBe("completed");
  });

  test("永遠包含 manager 節點", () => {
    const nodes = buildFlowNodes({
      analysis: baseAnalysis,
      analystTypes: ["news"],
      events: [],
    });
    expect(nodes.find((n) => n.id === "manager")).toBeTruthy();
  });
});
