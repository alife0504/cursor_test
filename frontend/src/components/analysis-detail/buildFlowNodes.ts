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
// 後端 streaming event 約定(PLAN 14 / agents/streaming.py):
//   type: started / analyst_completed / debate_argument / synthesis_completed / completed / failed
//   payload 視 type 不同;analyst_completed: { name }
//   debate_argument: { round_num, role }

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
  let started = false;

  for (const ev of events) {
    if (ev.type === "started") started = true;
    if (ev.type === "analyst_completed") {
      const payload = ev.payload as { name?: string } | undefined;
      if (payload?.name) analystDone.add(payload.name);
    }
    if (ev.type === "debate_argument") {
      const payload = ev.payload as
        | { round_num?: number; role?: string }
        | undefined;
      if (payload?.role && payload?.round_num) {
        debateDone.add(`${payload.role}:${payload.round_num}`);
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
