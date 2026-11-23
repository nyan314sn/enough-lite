import { afterEach, describe, expect, it, vi } from "vitest";
import TeamScreen from "./components/TeamScreen";
import { askStream, realApi } from "./api";
import { examplePlan, mockApi } from "./mock";
import { byText, click, flush, render, until, type Mounted } from "./test-utils";
import type { Api, AskResponse, PlanEvent, Profile } from "./types";

// A What If streams its team's work to the panel, the same way the baseline plan does: real events, not a made-up animation.

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; vi.restoreAllMocks(); });

const profile: Profile = { age: 49, retire_age: 62, children: [], pets: [] };
const base = examplePlan(profile);
const after = examplePlan({ ...profile, retire_age: 64 });
const tk = (n: number) => ({ input: n, cached: 0, output: n / 10 });

/** The baseline's stream: two notes, every adviser done, the plan. */
const basePlan = vi.fn(async (_p: Profile, on: (e: PlanEvent) => void) => {
  on({ type: "handoff", from: "adviser", to: "tax", message: "Baseline note to tax" });
  on({ type: "handoff", from: "tax", to: "adviser", message: "Baseline note back" });
  for (const a of ["longevity", "family", "tax", "research", "markets", "adviser"]) {
    on({ type: "agent_start", agent: a, label: a });
    on({ type: "agent_done", agent: a, finding: { headline: `Baseline ${a}`, details: [], numbers: {} }, tokens: tk(100), cost_usd: 0.001 });
  }
  on({ type: "plan", plan: base });
  on({ type: "done" });
});

/** A What If whose stream the test moves on step by step. */
function steppedAsk() {
  const gates: (() => void)[] = [];
  const wait = () => new Promise<void>((r) => gates.push(r));
  const result: AskResponse = { kind: "whatif", text: "If you retire at 64, you can count on more.", citations: [], plan: after, tokens: tk(500), cost_usd: 0.0042 };
  const ask = vi.fn(async (_q: string, _p: Profile, _pl: unknown, _pc: unknown, on?: (e: PlanEvent) => void) => {
    on?.({ type: "whatif_start", question: "Retire at 64", agents: ["adviser", "markets", "tax"], estimate: "about 10 to 20 seconds" });
    on?.({ type: "cost", total_tokens: 0, total_usd: 0, budget_usd: 0.1 });
    on?.({ type: "handoff", from: "adviser", to: "markets", message: "What If note: test retiring at 64" });
    on?.({ type: "agent_start", agent: "markets", label: "Markets" });
    on?.({ type: "tool", agent: "markets", tool: "simulate", summary: "Ran 1,000 market tests" });
    await wait();
    on?.({ type: "agent_done", agent: "markets", finding: { headline: "What If markets finding", details: [], numbers: {} }, tokens: tk(300), cost_usd: 0.002 });
    on?.({ type: "handoff", from: "markets", to: "adviser", message: "What If note: goal lasts in 80 of 100" });
    on?.({ type: "agent_start", agent: "adviser", label: "Lead adviser" });
    await wait();
    on?.({ type: "agent_done", agent: "adviser", finding: { headline: "What If lead finding", details: [], numbers: {} }, tokens: tk(200), cost_usd: 0.0022 });
    on?.({ type: "plan", plan: after });
    on?.({ type: "done" });
    return result;
  });
  const step = async () => { await until(() => gates.length > 0); gates.shift()!(); await flush(); };
  return { ask, step };
}

const q = (s: string) => m!.el.querySelector(s);
const nodeState = (a: string) => q(`.team-panel [data-agent=${a}]`)?.getAttribute("data-state");

describe("A streamed What If in the team panel", () => {
  it("shows the run's real progress, its notes and costs, then opens the tab", async () => {
    const { ask, step } = steppedAsk();
    m = await render(<TeamScreen api={{ ...mockApi, plan: basePlan, ask } as unknown as Api} profile={profile} model="x" onBack={() => {}} />);
    await until(() => q(".plan"));
    expect(nodeState("markets")).toBe("done");

    await click(byText(m.el, ".ask .chip", /Retire at 6\d/));
    await until(() => q("[data-testid=run-wait]"));
    // the ask asked for a stream
    expect(typeof ask.mock.calls[0][4]).toBe("function");
    // status: what is being worked on, and the measured time from the server
    expect(q(".team-status")?.textContent).toMatch(/^Working on: Retire at 6\d$/);
    expect(q("[data-testid=run-wait]")?.textContent).toMatch(/^Re-running your plan with: Retire at 6\d — about 10 to 20 seconds\./);
    // the advisers follow this run: markets works; the rest have not started in it
    expect(nodeState("markets")).toBe("working");
    expect(nodeState("adviser")).toBe("idle");
    expect(nodeState("family")).toBe("idle");
    expect(nodeState("intake")).toBe("done");
    expect(q("[data-testid=node-tool]")?.textContent).toContain("Ran 1,000 market tests");
    // Team talk: this run's notes, open, under "This What If"; the baseline's notes folded below
    const run = q("[data-testid=talk-run]")!;
    expect(run.querySelector(".h-mini")?.textContent).toBe("This What If");
    expect(run.querySelector("details")).toBeNull();
    expect(run.textContent).toContain("What If note: test retiring at 64");
    expect(run.textContent).not.toContain("Baseline note");
    const folded = Array.from(m.el.querySelectorAll(".team-panel details.talk-fold")).find((d) => d.textContent?.includes("baseline run"))!;
    expect(folded).toBeTruthy();
    expect((folded as HTMLDetailsElement).open).toBe(false);
    expect(folded.textContent).toContain("Baseline note to tax");
    // the hand-off line animates for this run's note
    expect(q(".rline.active")).toBeTruthy();
    // token costs: this run's so far, not the baseline's
    expect(q("[data-testid=cost-block] dt")?.parentElement?.parentElement?.textContent).toContain("This What If");
    expect(q("[data-testid=cost-input]")?.textContent).toBe("0");

    await step();
    expect(nodeState("markets")).toBe("done");
    expect(nodeState("adviser")).toBe("working");
    expect(q("[data-testid=talk-run]")?.textContent).toContain("goal lasts in 80 of 100");
    expect(q("[data-testid=cost-input]")?.textContent).toBe("300");
    // reading an adviser shows its work in this run
    await click(q(".team-panel [data-agent=markets]"));
    expect(q(".detail-box")?.textContent).toContain("What If markets finding");
    expect(q(".detail-box")?.textContent).toContain("this What If");

    await step();
    await until(() => m!.el.querySelectorAll("[role=tab]").length === 2);
    // done: the tab opened, the panel keeps this What If's run with its own costs
    expect(q("[data-testid=run-wait]")).toBeNull();
    expect(q(".team-status")?.textContent).toMatch(/^Showing the What If “Retire at 6\d”\. Select an adviser to read their work on it\.$/);
    expect(nodeState("adviser")).toBe("done");
    expect(q("[data-testid=talk-run]")?.textContent).toContain("What If note");
    expect(q("[data-testid=cost-input]")?.textContent).toBe("500");
    expect(q("[data-testid=cost-run]")?.textContent).toMatch(/0\.42¢|\$0\.0042|0\.4/);
    expect(q("[data-testid=scenario-said]")).toBeNull();

    // back on the baseline tab, the panel shows the baseline run again
    await click(m.el.querySelectorAll("[role=tab]")[0]);
    expect(q("[data-testid=talk-run]")).toBeNull();
    expect(nodeState("markets")).toBe("done");
    expect(q(".team-status")?.textContent).toBe("Done. Select an adviser to read their work.");
  });

  it("an answer that is not a What If sends no events and leaves the panel on the baseline", async () => {
    const ask = vi.fn(async () => ({ kind: "answer", text: "The limit is $24,500.", citations: [] }) as AskResponse);
    m = await render(<TeamScreen api={{ ...mockApi, plan: basePlan, ask } as unknown as Api} profile={profile} model="x" onBack={() => {}} />);
    await until(() => q(".plan"));
    const input = q("#ask-input") as HTMLInputElement;
    const { act } = await import("react");
    await act(async () => {
      const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
      set.call(input, "What is the 401(k) limit?");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => { (input.form as HTMLFormElement).requestSubmit(); });
    await until(() => m!.el.textContent?.includes("The limit is $24,500."));
    expect(q("[data-testid=run-wait]")).toBeNull();
    expect(q("[data-testid=talk-run]")).toBeNull();
    expect(m.el.querySelectorAll("[role=tab]").length).toBe(1);
  });
});

/** A server stream, as fetch hands it over. */
function sse(events: unknown[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  const text = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
  return new ReadableStream({ start(c) { c.enqueue(enc.encode(text.slice(0, 37))); c.enqueue(enc.encode(text.slice(37))); c.close(); } });
}

describe("askStream and api.ask", () => {
  const result = { kind: "whatif", text: "ok", citations: [], plan: after } as AskResponse;

  it("passes the team's events on and returns the answer", async () => {
    const seen: string[] = [];
    const r = await askStream(sse([{ type: "whatif_start", question: "q", agents: [], estimate: "about 10 to 20 seconds" }, { type: "agent_start", agent: "markets", label: "Markets" },
      { type: "result", result }, { type: "done" }]), (e) => seen.push(e.type));
    expect(r).toEqual(result);
    expect(seen).toEqual(["whatif_start", "agent_start", "done"]);
  });

  it("rejects with the server's plain message when the run fails", async () => {
    await expect(askStream(sse([{ type: "whatif_start", question: "q", agents: [], estimate: "" }, { type: "error", message: "The What If could not be finished. Please try again." }, { type: "done" }]), () => {}))
      .rejects.toThrow("could not be finished");
  });

  it("asks for a stream only when it is given a listener, and reads plain JSON when the server answers with it", async () => {
    const fetchMock = vi.fn(async (_u: string, init: RequestInit) => {
      const h = init.headers as Record<string, string>;
      if (h.Accept === "text/event-stream") return new Response(JSON.stringify({ kind: "refused", text: "No.", citations: [] }), { headers: { "content-type": "application/json" } });
      return new Response(JSON.stringify({ kind: "answer", text: "Yes.", citations: [] }), { headers: { "content-type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    const on = vi.fn();
    expect((await realApi.ask("x", profile, base, null, on)).kind).toBe("refused");
    expect(on).not.toHaveBeenCalled();
    expect((await realApi.ask("x", profile, base, null)).kind).toBe("answer");
    fetchMock.mockImplementationOnce(async () => new Response(sse([{ type: "agent_start", agent: "tax", label: "Tax" }, { type: "result", result }, { type: "done" }]), { headers: { "content-type": "text/event-stream" } }));
    expect(await realApi.ask("x", profile, base, null, on)).toEqual(result);
    expect(on).toHaveBeenCalledWith({ type: "agent_start", agent: "tax", label: "Tax" });
    vi.unstubAllGlobals();
  });
});
