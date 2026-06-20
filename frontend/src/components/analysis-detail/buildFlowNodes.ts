import type { FlowNodeInput, FlowNodeState } from "@/components/AgentFlowGraph";
import type { AnalysisDetail, DebateMessage } from "@/lib/api-types";
import type { WSEvent } from "@/hooks/useWebSocket";

// Phase 16:把 analysis_detail + ws events + debate 訊息 → AgentFlowGraph nodes
//
// 節點 id 約定:
//   analyst:    analyst:<type>     例 analyst:market
//   debate(b):  bull:round_N
//   debate(b):  bear:round_N
//   manager:    manager
//
// 後端 streaming event 約定(PLAN 14 / agents/streaming.py)：
//   後端送 { event, data, ts }；useWebSocket hook 已正規化成 { type, payload, ts }。
//   analyst_completed: data.node = analyst 名（market/...）
//   debate_argument:   data.role = bull/bear、data.round = 輪數
//   （本檔仍相容舊欄位 name / round_num）

export interface BuildArgs {
  analysis: AnalysisDetail | null | undefined;
  analystTypes?: string[]; // 從原始建立參數推導(目前 backend detail 沒回,先用 fallback)
  debateRounds?: number;
  debateMessages?: DebateMessage[];
  events: WSEvent[];
}

export function buildFlowNodes({
  analysis,
  analystTypes,
  debateRounds,
  debateMessages,
  events,
}: BuildArgs): FlowNodeInput[] {
  if (!analysis) return [];

  // 推導 analyst types:優先用傳入的 hint;否則用後端可能的欄位(目前無),最後 default
  const analysts = analystTypes && analystTypes.length
    ? analystTypes
    : ["market", "fundamental", "news"];

  // 推導 debate rounds:debateMessages 中最大 round_num,或外部 hint
  const inferredRounds = debateMessages?.length
    ? Math.max(...debateMessages.map((m) => m.round_num))
    : 0;
  const rounds = Math.max(debateRounds ?? 0, inferredRounds);

  // 從 events 推導每個節點的狀態
  const analystDone = new Set<string>();
  const debateDone = new Set<string>(); // e.g. "bull:1"
  let managerDone = false;
  let failed = false;
  // 即使 WS 事件漏接 / 斷線，status=running 也讓節點顯示「running」而非凍在 pending
  let started = analysis.status === "running";

  for (const ev of events) {
    if (ev.type === "started") started = true;
    if (ev.type === "analyst_completed") {
      // 後端 data 以 node 帶 analyst 名（相容舊 name 欄位）
      const payload = ev.payload as { node?: string; name?: string } | undefined;
      const name = payload?.node ?? payload?.name;
      if (name) analystDone.add(name);
    }
    if (ev.type === "debate_argument") {
      // 後端 data 以 round 帶輪數（相容舊 round_num 欄位）
      const payload = ev.payload as
        | { round?: number; round_num?: number; role?: string }
        | undefined;
      const round = payload?.round ?? payload?.round_num;
      if (payload?.role && round) {
        debateDone.add(`${payload.role}:${round}`);
      }
    }
    if (ev.type === "synthesis_completed" || ev.type === "completed") {
      managerDone = true;
    }
    if (ev.type === "failed") failed = true;
  }

  // debate messages 也可推完成度(reload 後沒 ws event 時的退路)
  for (const m of debateMessages ?? []) {
    debateDone.add(`${m.role}:${m.round_num}`);
  }

  // 已完成的 analysis(reload 看舊資料時):全部標 completed
  const overallStatus = analysis.status;
  const allDone = overallStatus === "completed";
  const allFailed = overallStatus === "failed" || failed;

  const decideState = (done: boolean): FlowNodeState => {
    if (allFailed) return "failed";
    if (allDone) return "completed";
    if (done) return "completed";
    if (started) return "running";
    return "pending";
  };

  const out: FlowNodeInput[] = [];
  for (const a of analysts) {
    out.push({
      id: `analyst:${a}`,
      label: a.charAt(0).toUpperCase() + a.slice(1),
      sub: "Analyst",
      group: "analyst",
      state: decideState(analystDone.has(a)),
    });
  }
  for (let r = 1; r <= rounds; r += 1) {
    out.push({
      id: `bull:round_${r}`,
      label: "Bull",
      sub: `Round ${r}`,
      group: "bull",
      state: decideState(debateDone.has(`bull:${r}`)),
    });
    out.push({
      id: `bear:round_${r}`,
      label: "Bear",
      sub: `Round ${r}`,
      group: "bear",
      state: decideState(debateDone.has(`bear:${r}`)),
    });
  }
  out.push({
    id: "manager",
    label: "Manager",
    sub: "Final Signal",
    group: "manager",
    state: decideState(managerDone),
  });
  return out;
}
