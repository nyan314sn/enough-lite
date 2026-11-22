import { describe, expect, it } from "vitest";
import { emptyTeam, parseSSE, teamReducer } from "./sse";
import { readStream } from "./api";
import { mockApi, mockSpeed, EXAMPLE_TEXT } from "./mock";
import type { PlanEvent } from "./types";

const frame = (e: object) => `data: ${JSON.stringify(e)}\n\n`;

describe("parseSSE", () => {
  it("parses whole frames and keeps the unfinished tail", () => {
    const buf = frame({ type: "agent_start", agent: "tax", label: "Tax" }) + 'data: {"type":"tool","agent":"ta';
    const { events, rest } = parseSSE(buf);
    expect(events).toEqual([{ type: "agent_start", agent: "tax", label: "Tax" }]);
    expect(rest).toBe('data: {"type":"tool","agent":"ta');
  });

  it("handles CRLF, event: and comment lines, and multi-line data", () => {
    const buf = ': keep-alive\r\n\r\nevent: message\r\ndata: {"type":\r\ndata: "done"}\r\n\r\n';
    expect(parseSSE(buf).events).toEqual([{ type: "done" }]);
  });

  it("turns a garbled frame into an error event instead of throwing", () => {
    expect(parseSSE("data: {not json\n\n").events[0].type).toBe("error");
  });
});

describe("readStream", () => {
  it("reassembles events split across network chunks and adds done if the server forgot", async () => {
    const text = frame({ type: "agent_start", agent: "markets", label: "Markets" }) + frame({ type: "tool", agent: "markets", tool: "simulate", summary: "Simulation: 2,000 paths" });
    const enc = new TextEncoder();
    const cuts = [0, 7, 30, 61, 90, text.length];
    const body = new ReadableStream<Uint8Array>({
      start(c) { for (let i = 1; i < cuts.length; i++) c.enqueue(enc.encode(text.slice(cuts[i - 1], cuts[i]))); c.close(); },
    });
    const got: PlanEvent[] = [];
    await readStream(body, (e) => got.push(e));
    expect(got.map((e) => e.type)).toEqual(["agent_start", "tool", "done"]);
    expect(got[1]).toMatchObject({ summary: "Simulation: 2,000 paths" });
  });
});

describe("teamReducer", () => {
  it("builds a card per agent with its tool calls, finding, tokens and cost", () => {
    let s = emptyTeam;
    const evs: PlanEvent[] = [
      { type: "agent_start", agent: "longevity", label: "Longevity" },
      { type: "tool", agent: "longevity", tool: "life_table", summary: "Life table: planning to age 95" },
      { type: "agent_done", agent: "longevity", finding: { headline: "Plan to age 95.", details: [], numbers: { horizon_age: 95 } }, tokens: { input: 1000, cached: 200, output: 100 }, cost_usd: 0.00013 },
      { type: "cost", total_tokens: 1100, total_usd: 0.00013, budget_usd: 0.05 },
    ];
    for (const e of evs) s = teamReducer(s, e);
    expect(s.agents).toHaveLength(1);
    expect(s.agents[0]).toMatchObject({ label: "Longevity", status: "done", tools: [{ summary: "Life table: planning to age 95" }], cost_usd: 0.00013 });
    expect(s.cost).toEqual({ total_tokens: 1100, total_usd: 0.00013, budget_usd: 0.05 });
    expect(s.done).toBe(false);
  });

  it("makes a card for a tool event that arrives before its agent_start", () => {
    const s = teamReducer(emptyTeam, { type: "tool", agent: "tax", tool: "tax", summary: "Tax: CT rates" });
    expect(s.agents[0]).toMatchObject({ agent: "tax", status: "working", tools: [{ summary: "Tax: CT rates" }] });
  });

  it("an error ends the run with the message; done without a plan is an error too", () => {
    expect(teamReducer(emptyTeam, { type: "error", message: "Budget reached" })).toMatchObject({ done: true, error: "Budget reached" });
    expect(teamReducer(emptyTeam, { type: "done" }).error).toMatch(/without a plan/);
  });

  it("replays the whole mock stream into six finished advisers and a plan", async () => {
    mockSpeed.factor = 0;
    const r = await mockApi.intake(EXAMPLE_TEXT, null);
    const r2 = await mockApi.intake("About $1.4 million", r.profile);
    let s = emptyTeam;
    await mockApi.plan(r2.profile, (e) => { s = teamReducer(s, e); });
    expect(s.agents.map((a) => a.label)).toEqual(["Longevity", "Family", "Tax", "Research", "Markets", "Lead adviser"]);
    expect(s.agents.every((a) => a.status === "done" && a.tools.length > 0)).toBe(true);
    expect(s.plan?.actions).toHaveLength(3);
    expect(s.done).toBe(true);
    expect(s.error).toBeNull();
    const sum = s.agents.reduce((t, a) => t + (a.cost_usd ?? 0), 0);
    expect(s.cost.total_usd).toBeCloseTo(sum, 6);
    expect(s.cost.total_usd).toBeLessThan(s.cost.budget_usd ?? 0);
  });
});
