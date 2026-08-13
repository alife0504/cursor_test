import type { FlowNodeInput, FlowNodeState } from "@/components/AgentFlowGraph";
import type { AnalysisDetail, DebateMessage } from "@/lib/api-types";
import type { WSEvent } from "@/hooks/useWebSocket";

// Phase 16:把 analysis_detail + ws events + debate 訊息 → AgentFlowGraph nodes
//
// 節點 id 約定:
//   analyst:    analyst:<type>     例 analyst:market
//   debate(b):  bull:round_N / bear:round_N
//   manager:    manager
//   風險層（risk_rounds>0）: trader / risk_debate / risk_manager / verifier
//
// 後端 streaming event 約定(PLAN 14 / agents/streaming.py)：
//   後端送 { event, data, ts }；useWebSocket hook 已正規化成 { type, payload, ts }。
//   analyst_completed:    data.node = analyst 名（market/...）
//   debate_argument:      data.role = bull/bear/trader/風險立場、data.round = 輪數
//   synthesis_completed:  data.node = manager / risk_manager / verifier（各自的合成節點）
//   （本檔仍相容舊欄位 name / round_num）

export interface BuildArgs {
  analysis: AnalysisDetail | null | undefined;
  analystTypes?: string[]; // 從原始建立參數推導(目前 backend detail 沒回,先用 fallback)
  debateRounds?: number;
  /** 風險辯論輪數提示（>0 → 顯示風險層節點）；detail 未帶時可為 undefined，改由事件推導 */
  riskRounds?: number;
  debateMessages?: DebateMessage[];
  events: WSEvent[];
}

export function buildFlowNodes({
  analysis,
  analystTypes,
  debateRounds,
  riskRounds,
  debateMessages,
  events,
}: BuildArgs): FlowNodeInput[] {
  if (!analysis) return [];

  // 推導 analyst types:優先用傳入的 hint;否則用後端可能的欄位(目前無),最後 default
  const analysts =
    analystTypes && analystTypes.length
      ? analystTypes
      : ["market", "fundamental", "news"];

  // 推導 debate rounds:debateMessages 中最大 round_num,或外部 hint（排除 manager 訊息）
  const inferredRounds = debateMessages?.length
    ? Math.max(
        0,
        ...debateMessages
          .filter((m) => m.role === "bull" || m.role === "bear")
          .map((m) => m.round_num),
      )
    : 0;
  const rounds = Math.max(debateRounds ?? 0, inferredRounds);

  // 從 events 推導每個節點的狀態
  const analystDone = new Set<string>();
  const debateDone = new Set<string>(); // e.g. "bull:1"
  let managerDone = false; // 只認 synthesis node==='manager'
  let traderDone = false;
  let riskDebateSeen = false;
  let riskManagerDone = false;
  let verifierDone = false;
  let overallDone = false;
  let failed = false;
  // 即使 WS 事件漏接 / 斷線，status=running 也讓節點顯示「running」而非凍在 pending
  let started = analysis.status === "running";

  for (const ev of events) {
    if (ev.type === "started") started = true;
    if (ev.type === "analyst_completed") {
      const payload = ev.payload as { node?: string; name?: string } | undefined;
      const name = payload?.node ?? payload?.name;
      if (name) analystDone.add(name);
    }
    if (ev.type === "debate_argument") {
      const payload = ev.payload as
        | { round?: number; round_num?: number; role?: string }
        | undefined;
      const round = payload?.round ?? payload?.round_num;
      const role = payload?.role;
      if (role === "bull" || role === "bear") {
        if (round) debateDone.add(`${role}:${round}`);
      } else if (role === "trader") {
        traderDone = true;
      } else if (role) {
        // 非 bull/bear/trader 一律視為風險辯論員（積極/保守/中立，stance 標籤可能多樣）
        riskDebateSeen = true;
      }
    }
    if (ev.type === "synthesis_completed") {
      const node = (ev.payload as { node?: string } | undefined)?.node;
      if (node === "manager") managerDone = true;
      else if (node === "risk_manager") riskManagerDone = true;
      else if (node === "verifier") verifierDone = true;
      else managerDone = true; // 舊事件無 node → 退回原行為（至少標 manager）
    }
    if (ev.type === "completed") overallDone = true;
    if (ev.type === "failed") failed = true;
  }

  // debate messages 也可推完成度(reload 後沒 ws event 時的退路)
  for (const m of debateMessages ?? []) {
    if (m.role === "bull" || m.role === "bear") {
      debateDone.add(`${m.role}:${m.round_num}`);
    } else if (m.role === "manager") {
      managerDone = true;
    }
  }

  // 是否顯示風險層：hint>0 或事件/訊息顯示風險層有跑
  const riskActive =
    (riskRounds ?? 0) > 0 ||
    traderDone ||
    riskDebateSeen ||
    riskManagerDone ||
    verifierDone;

  // 已完成的 analysis(reload 看舊資料時):全部標 completed
  const overallStatus = analysis.status;
  const allDone = overallStatus === "completed" || overallDone;
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
    // 風險層啟用時 manager 只是「暫定訊號」，最終由 verifier 決定
    sub: riskActive ? "Investment Plan" : "Final Signal",
    group: "manager",
    state: decideState(managerDone),
  });

  // 風險層節點（trader → 風險辯論 → RiskManager → Verifier）
  if (riskActive) {
    out.push({
      id: "trader",
      label: "Trader",
      sub: "Proposal",
      group: "manager",
      state: decideState(traderDone || riskDebateSeen || riskManagerDone),
    });
    out.push({
      id: "risk_debate",
      label: "Risk Debate",
      sub: "積極/保守/中立",
      group: "bull",
      // 風險辯論在 RiskManager 合成前完成
      state: decideState(riskManagerDone),
    });
    out.push({
      id: "risk_manager",
      label: "Risk Manager",
      sub: "Final Signal",
      group: "manager",
      state: decideState(riskManagerDone),
    });
    out.push({
      id: "verifier",
      label: "Verifier",
      sub: "接地查核",
      group: "manager",
      state: decideState(verifierDone),
    });
  }

  return out;
}
