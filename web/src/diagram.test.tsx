import { afterEach, describe, expect, it } from "vitest";
import TeamPanel, { TeamTalk, nodeState } from "./components/TeamPanel";
import { emptyTeam, teamReducer } from "./sse";
import { mockApi, mockSpeed, EXAMPLE_TEXT } from "./mock";
import { render, flush, click, type Mounted } from "./test-utils";
import type { PlanEvent } from "./types";

const fold = (evs: PlanEvent[]) => evs.reduce(teamReducer, emptyTeam);
const start = (agent: string): PlanEvent => ({ type: "agent_start", agent, label: agent });
const done = (agent: string): PlanEvent => ({ type: "agent_done", agent, finding: { headline: "h", details: [], numbers: {} }, tokens: { input: 1, cached: 0, output: 1 }, cost_usd: 0.0001 });
const hand = (from: string, to: string, message: string): PlanEvent => ({ type: "handoff", from, to, message });

describe("team diagram state", () => {
  it("is idle until agent_start, working after it, done after agent_done", () => {
    expect(nodeState(emptyTeam, "tax")).toBe("idle");
    const s1 = fold([start("tax")]);
    expect(nodeState(s1, "tax")).toBe("working");
    expect(nodeState(s1, "markets")).toBe("idle");
    expect(nodeState(teamReducer(s1, done("tax")), "tax")).toBe("done");
  });

  it("counts intake as done, since it ran before the team started", () => {
    expect(nodeState(emptyTeam, "intake")).toBe("done");
    expect(nodeState(emptyTeam, "intake", false)).toBe("idle");
  });

  it("a handoff goes in the log and does not start or change any adviser", () => {
    const s = fold([start("longevity"), hand("adviser", "tax", "Work out what you keep.")]);
    expect(s.handoffs).toEqual([{ id: 1, from: "adviser", to: "tax", message: "Work out what you keep." }]);
    expect(s.agents.map((a) => a.agent)).toEqual(["longevity"]);
    expect(nodeState(s, "tax")).toBe("idle");
  });

  it("keeps handoffs in order with running ids", () => {
    const s = fold([hand("adviser", "tax", "a"), hand("tax", "markets", "b"), hand("markets", "adviser", "c")]);
    expect(s.handoffs.map((h) => [h.id, h.from, h.to])).toEqual([[1, "adviser", "tax"], [2, "tax", "markets"], [3, "markets", "adviser"]]);
  });

  it("remembers the newest tool call, with a count", () => {
    const s = fold([{ type: "tool", agent: "tax", tool: "tax", summary: "one" }, { type: "tool", agent: "markets", tool: "simulate", summary: "two" }]);
    expect(s.lastTool).toEqual({ agent: "markets", summary: "two", seq: 2 });
  });

  it("the whole mock stream logs handoffs and ends with every adviser done", async () => {
    mockSpeed.factor = 0;
    const r = await mockApi.intake(EXAMPLE_TEXT, null);
    const r2 = await mockApi.intake("About $1.4 million", r.profile);
    let s = emptyTeam;
    await mockApi.plan(r2.profile, (e) => { s = teamReducer(s, e); });
    expect(s.handoffs.length).toBeGreaterThan(8);
    expect(s.handoffs[0]).toMatchObject({ from: "adviser" });
    expect(s.handoffs[s.handoffs.length - 1]).toMatchObject({ to: "adviser" });
    for (const a of ["longevity", "family", "tax", "research", "markets", "adviser"]) expect(nodeState(s, a)).toBe("done");
  });
});

describe("team diagram and Team talk", () => {
  let m: Mounted | null = null;
  afterEach(() => { m?.unmount(); m = null; });

  it("draws seven portraits with states from the stream", async () => {
    const team = fold([start("tax"), start("markets"), done("markets")]);
    m = await render(<TeamPanel team={team} status="" />);
    const states = Object.fromEntries(Array.from(m.el.querySelectorAll(".node")).map((n) => [n.getAttribute("data-agent"), n.getAttribute("data-state")]));
    expect(states).toEqual({ intake: "done", longevity: "idle", markets: "done", family: "idle", tax: "working", research: "idle", adviser: "idle" });
    expect(m.el.querySelectorAll("svg.portrait")).toHaveLength(7);
    expect(m.el.querySelectorAll(".node-check")).toHaveLength(2);
    expect(Array.from(m.el.querySelectorAll(".badge")).map((b) => b.textContent)).toEqual(["Lead adviser", "Intake", "Longevity", "Markets", "Family", "Tax", "Research"]);
  });

  it("a What If sends the advisers it reruns back to work", async () => {
    const team = fold([start("markets"), done("markets"), start("tax"), done("tax")]);
    m = await render(<TeamPanel team={team} status="" rerun={["markets", "adviser"]} />);
    const st = (a: string) => m!.el.querySelector(`.node-${a}`)!.getAttribute("data-state");
    expect(st("markets")).toBe("working");
    expect(st("adviser")).toBe("working");
    expect(st("tax")).toBe("done");
  });

  it("shows a tool call as it happens, and opens an adviser's finding on click", async () => {
    const team = fold([start("tax"), hand("adviser", "tax", "go"), { type: "tool", agent: "tax", tool: "tax", summary: "Tax: CT rates" }, done("tax")]);
    m = await render(<TeamPanel team={team} status="" />);
    await flush();
    expect(m.el.querySelector("[data-testid=node-tool]")?.textContent).toContain("Tax: CT rates");
    expect(m.el.querySelector(".finding")).toBeNull();
    await click(m.el.querySelector(".node-tax"));
    expect(m.el.querySelector(".detail-box .finding-h")?.textContent).toBe("h");
    await click(m.el.querySelector(".node-tax"));
    expect(m.el.querySelector(".detail-box")).toBeNull();
  });

  it("the Team talk log lists each message with who spoke to whom, newest marked", async () => {
    const team = fold([hand("adviser", "tax", "Work out what you keep."), hand("tax", "markets", "You keep 84 cents.")]);
    m = await render(<TeamTalk handoffs={team.handoffs} />);
    const rows = Array.from(m.el.querySelectorAll(".talk-row"));
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain("Lead adviser");
    expect(rows[0].textContent).toContain("Work out what you keep.");
    expect(rows[1].textContent).toContain("Tax");
    expect(rows[1].className).toContain("newest");
    expect(rows[0].className).not.toContain("newest");
  });

  it("says so when nothing has been said yet", async () => {
    m = await render(<TeamTalk handoffs={[]} />);
    expect(m.el.textContent).toContain("pass notes");
  });
});
