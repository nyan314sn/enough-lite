import { afterEach, describe, expect, it, vi } from "vitest";
import AskBox, { ideas, pointless, suggestions } from "./components/AskBox";
import PlanCard, { withoutRepeat } from "./components/PlanCard";
import TeamPanel, { wholeRowsHeight } from "./components/TeamPanel";
import { examplePlan, mockApi } from "./mock";
import { emptyTeam } from "./sse";
import { click, flush, render, type Mounted } from "./test-utils";
import type { Api } from "./types";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const point = { title: "Retire at 67", result: "basics paid in 100 of 100", whatif_text: "Retire at 67", paid_of_100: 100, count_on_per_year: 24000 };

describe("Round 2 UI: starting points", () => {
  it("lists each starting point (no button), and cuts the repeat from action 1", async () => {
    const base = examplePlan({ age: 45, retire_age: 62 });
    const plan = { ...base, starting_points: [point], actions: [{ title: "Make your basics safe first", why: "On your numbers they are not safe. Starting points: retire at 67 (x)." }, ...base.actions.slice(1)] };
    m = await render(<PlanCard plan={plan} retireAge={62} />);
    expect(m.el.querySelector(".starting-points button")).toBeNull();
    expect(m.el.querySelector(".starting-points")?.textContent).toContain("Retire at 67");
    expect(m.el.querySelector(".actions")?.textContent).not.toContain("Starting points:");
    expect(withoutRepeat("A. Starting points: b.", true)).toBe("A.");
    expect(withoutRepeat("A. Starting points: b.", false)).toContain("Starting points");
  });
  it("runs a request from outside as a What If", async () => {
    const plan = examplePlan({ age: 45, retire_age: 62 });
    const ask = vi.fn(async () => ({ kind: "answer" as const, text: "ok", citations: [] }));
    const api = { ...mockApi, ask } as Api;
    const el = (r: { id: number; q: string } | null) => <AskBox api={api} profile={{ age: 45, retire_age: 62 }} plan={plan} onCost={() => {}} request={r} />;
    m = await render(el(null));
    await m.root.render(el({ id: 1, q: "Retire at 67" })); await flush();
    expect(ask).toHaveBeenCalledTimes(1);
    expect((ask.mock.calls[0] as unknown[])[0]).toBe("Retire at 67");
  });
});

describe("Round 2 UI: chips that make no sense", () => {
  it("offers no retire age to someone retired or older, and no child over 50", () => {
    expect(suggestions(null, 66, true).some((s) => /Retire at/.test(s))).toBe(false);
    expect(suggestions(null, 71).some((s) => /Retire at/.test(s))).toBe(false);
    expect(suggestions(65, 66).some((s) => /Retire at/.test(s))).toBe(false);
    expect(suggestions(62, 45).some((s) => /Retire at/.test(s))).toBe(true);
    expect(suggestions(62, 52)).not.toContain("Another child");
  });
  it("drops lever chips with a past retire age", () => {
    const plan = { ...examplePlan({ age: 66, retire_age: 62 }), already_retired: true, levers: [
      { key: "a", title: "Retire at 62", why: "", whatif_text: "What if I retire at 62" },
      { key: "b", title: "Spend less", why: "", whatif_text: "Spend $5,000 a year less" },
    ] };
    expect(ideas({ age: 66, retire_age: 62 }, plan).map((x) => x.label)).toEqual(["Spend less"]);
    expect(pointless("What if I retire at 70", 66, false)).toBe(false);
    expect(pointless("What if I retire at 60", 66, false)).toBe(true);
    expect(pointless("Another child", 55, false)).toBe(true);
  });
  it("says so, without asking the server, when a retiree types a retire age", async () => {
    const plan = { ...examplePlan({ age: 71, retire_age: 65 }), already_retired: true };
    const ask = vi.fn();
    m = await render(<AskBox api={{ ...mockApi, ask } as unknown as Api} profile={{ age: 71, retire_age: 65 }} plan={plan} onCost={() => {}} request={{ id: 1, q: "Retire at 60" }} />);
    await flush();
    expect(ask).not.toHaveBeenCalled();
    expect(m.el.querySelector(".turn-a")?.textContent).toMatch(/already retired/);
  });
});

describe("Round 2 UI: team talk and adviser detail", () => {
  it("fits the log to whole rows, newest last", () => {
    expect(wholeRowsHeight([0, 40, 80], 120, 200)).toBeNull();
    expect(wholeRowsHeight([0, 70, 140, 210], 280, 200)).toEqual({ height: 140, scrollTo: 140 });
    expect(wholeRowsHeight([0, 300], 600, 200)).toEqual({ height: 300, scrollTo: 300 });
  });
  it("shows an adviser's finding in plain words: no tool lines, no tokens", async () => {
    const team = { ...emptyTeam, agents: [{ agent: "markets", status: "done" as const, tools: [{ tool: "t", summary: "Tested 21 strategies" }], finding: { headline: "Your money lasts.", details: ["It holds in 90 of 100 tests."], numbers: {} }, tokens: { input: 1000, cached: 0, output: 50 }, cost_usd: 0.002 }], cost: { total_tokens: 5000, total_usd: 0.01, budget_usd: 0.05 } };
    m = await render(<TeamPanel team={team as never} status="Done." />);
    await click(m.el.querySelector("[data-agent=markets]"));
    const t = m.el.querySelector(".detail-box")?.textContent ?? "";
    expect(t).toContain("Your money lasts.");
    expect(t).not.toMatch(/Tested 21|token/i);
    expect(m.el.querySelector(".tools")).toBeNull();
    m.el.querySelector("[data-testid=cost-block]")?.remove();   // the cost block shows tokens on purpose (owner request)
    expect(m.el.textContent).not.toMatch(/tokens/);
  });
});

describe("Round 2 UI: assumptions", () => {
  it("shows four lines and puts the rest behind More assumptions", async () => {
    const plan = { ...examplePlan({ age: 45, retire_age: 62 }), assumptions: ["a1", "a2", "a3", "a4", "a5", "a6"] };
    m = await render(<PlanCard plan={plan} retireAge={62} />);
    const d = m.el.querySelector("[data-testid=plan-assumptions]")!;
    expect(d.querySelectorAll(":scope > ul > li").length).toBe(4);
    expect(d.querySelector(".more-assumptions summary")?.textContent).toContain("More assumptions");
    expect(d.querySelectorAll(".more-assumptions li").length).toBe(2);
  });
});
