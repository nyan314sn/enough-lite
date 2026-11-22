import type { Finding, Plan, PlanEvent, Tokens } from "./types";

/** Split a Server-Sent Events buffer into whole events. Returns the parsed events and the unfinished tail to keep for the next chunk.
 *  Frames end with a blank line; each frame's `data:` lines are joined; `event:`, `id:` and comment lines are ignored. */
export function parseSSE(buffer: string): { events: PlanEvent[]; rest: string } {
  const text = buffer.replace(/\r\n?/g, "\n");
  const frames = text.split("\n\n");
  const rest = frames.pop() ?? "";
  const events: PlanEvent[] = [];
  for (const frame of frames) {
    const data = frame.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).replace(/^ /, "")).join("\n");
    if (!data) continue;
    try {
      const ev = JSON.parse(data);
      if (ev && typeof ev.type === "string") events.push(ev as PlanEvent);
    } catch {
      events.push({ type: "error", message: "The server sent something we could not read." });
    }
  }
  return { events, rest };
}

export interface AgentCard {
  agent: string;
  label: string;
  status: "working" | "done";
  tools: { tool: string; summary: string }[];
  finding?: Finding;
  tokens?: Tokens;
  cost_usd?: number;
}

export interface Handoff { id: number; from: string; to: string; message: string }

export interface TeamState {
  /** Every handoff so far, in order: the "Team talk" log and the diagram's travelling dots. */
  handoffs: Handoff[];
  /** The newest tool call; "seq" counts tool calls so the diagram can show each one briefly. */
  lastTool: { agent: string; summary: string; seq: number } | null;
  agents: AgentCard[];
  cost: { total_tokens: number; total_usd: number; budget_usd: number | null };
  plan: Plan | null;
  error: string | null;
  done: boolean;
}

export const emptyTeam: TeamState = { handoffs: [], lastTool: null, agents: [], cost: { total_tokens: 0, total_usd: 0, budget_usd: null }, plan: null, error: null, done: false };

function upsert(agents: AgentCard[], agent: string, change: (a: AgentCard) => AgentCard): AgentCard[] {
  const i = agents.findIndex((a) => a.agent === agent);
  if (i < 0) return [...agents, change({ agent, label: agent, status: "working", tools: [] })];
  const next = agents.slice();
  next[i] = change(agents[i]);
  return next;
}

/** Fold one stream event into the screen's state. Tool or done events for an agent we have not seen still make a card. */
export function teamReducer(s: TeamState, e: PlanEvent): TeamState {
  switch (e.type) {
    case "agent_start":
      return { ...s, agents: upsert(s.agents, e.agent, (a) => ({ ...a, label: e.label || a.label, status: "working" })) };
    case "handoff":
      return { ...s, handoffs: [...s.handoffs, { id: s.handoffs.length + 1, from: e.from, to: e.to, message: e.message }] };
    case "tool":
      return { ...s, lastTool: { agent: e.agent, summary: e.summary, seq: (s.lastTool?.seq ?? 0) + 1 }, agents: upsert(s.agents, e.agent, (a) => ({ ...a, tools: [...a.tools, { tool: e.tool, summary: e.summary }] })) };
    case "agent_done":
      return { ...s, agents: upsert(s.agents, e.agent, (a) => ({ ...a, status: "done", finding: e.finding, tokens: e.tokens, cost_usd: e.cost_usd })) };
    case "plan":
      return { ...s, plan: e.plan };
    case "cost":
      return { ...s, cost: { total_tokens: e.total_tokens, total_usd: e.total_usd, budget_usd: e.budget_usd ?? s.cost.budget_usd } };
    case "error":
      return { ...s, error: e.message || "Something went wrong.", done: true };
    case "done":
      return { ...s, done: true, error: s.error ?? (s.plan ? null : "The team finished without a plan. Please try again.") };
    default:
      return s;
  }
}
