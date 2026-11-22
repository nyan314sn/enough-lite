import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "./App";
import PlanCard from "./components/PlanCard";
import TeamScreen from "./components/TeamScreen";
import CompareTable from "./components/CompareTable";
import CostBlock, { addAsk, noAsk, runTotals } from "./components/CostBlock";
import { ROSTER } from "./components/TeamPanel";
import { HOW_KEY } from "./components/HowItWorks";
import { emptyTeam } from "./sse";
import { basicsLevel, planLevel, yearlyGap } from "./shortfall";
import { examplePlan, mockApi, mockSpeed } from "./mock";
import { byText, click, flush, render, until, type Mounted } from "./test-utils";
import type { Plan, Profile } from "./types";

// The four UI requests: How it works, "baseline plan", loud shortfalls, and the cost of this plan.

for (const name of ["localStorage", "sessionStorage"]) {
  const mem = new Map<string, string>();
  Object.defineProperty(globalThis, name, { configurable: true, value: { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => void mem.set(k, v), removeItem: (k: string) => void mem.delete(k), clear: () => mem.clear() } });
}
window.scrollTo = (() => {}) as typeof window.scrollTo;
let m: Mounted | null = null;
beforeEach(() => { try { localStorage.removeItem(HOW_KEY); } catch { /* none */ } });
afterEach(() => { m?.unmount(); m = null; });

const profile: Profile = { age: 45, partner_age: 43, retire_age: 62, children: [{ age: 13, college: true }], pets: [] };
const base = examplePlan(profile);
/** The parts of the analysis that the plan card reads, with the goal and what you can count on. */
const analysisOf = (goal: number, count: number, paid: number) => ({ paths: 100, seed: 1, plan_count_on_per_year: count, plan_basics_paid_of_100: paid,
  how_sure: { levels: [], curve_spend: [], curve_lasts_of_100: [], goal_per_year: goal, goal_lasts_of_100: 50, count_on_per_year: count, basics_per_year: 60000, basics_paid_of_100: paid, line: "Chances, not promises." },
  stresses: { rows: [], line: "" }, levers: { rows: [], line: "" }, sources: { ages: [], spending: [], series: [], surplus: [], line: "", goal_per_year: goal } }) as unknown as Plan["analysis"];
/** A plan that falls short: basics paid in 70 of 100, goal $230,000 against $117,500 to count on. */
const shortPlan = (over: Partial<Plan> = {}): Plan => ({
  ...base, verdict: "falls_short", needs: { ...base.needs, paid_of_100: 70 }, wants: { ...base.wants, per_year: 117500 },
  analysis: analysisOf(230000, 117500, 70), ...over,
});

describe("1. How it works", () => {
  it("shows once for a first-time visitor on page 1, names every adviser, and folds to one line after Got it", async () => {
    mockSpeed.factor = 0;
    m = await render(<App api={mockApi} mock admin={false} />);
    const how = m.el.querySelector("[data-testid=how-it-works]");
    expect(how).toBeTruthy();
    for (const r of ROSTER) expect(how!.textContent).toContain(r.name);
    expect(how!.textContent).toMatch(/calculations, not from the AI/);
    expect(how!.textContent).toMatch(/What if/);
    await click(byText(m.el, "button", "Got it"));
    expect(m.el.querySelector("[data-testid=how-it-works]")).toBeNull();
    expect(m.el.querySelector("[data-testid=how-collapsed]")?.textContent).toMatch(/team of 7 AI advisers/);   // folded, not gone
    expect(localStorage.getItem(HOW_KEY)).toBe("1");
    m.unmount();
    m = await render(<App api={mockApi} mock admin={false} />);
    expect(m.el.querySelector("[data-testid=how-it-works]")).toBeNull();   // remembered
    expect(m.el.querySelector("[data-testid=how-collapsed]")).toBeTruthy();
    await click(byText(m.el, "button", "Show details"));
    expect(m.el.querySelector("[data-testid=how-it-works]")).toBeTruthy();   // opens again from the folded line
  });

  it("lives on page 1 only: no header button, the folded line opens it, and page 2 shows neither", async () => {
    localStorage.setItem(HOW_KEY, "1");
    mockSpeed.factor = 0;
    m = await render(<App api={mockApi} mock admin={false} />);
    expect(m.el.querySelector("button.how-link")).toBeNull();
    await click(byText(m.el, "button", "Show details"));
    expect(m.el.querySelector("[data-testid=how-it-works]")).toBeTruthy();
    await click(byText(m.el, "button", "Got it"));
    await click(byText(m.el, ".quick button", "Use an example"));
    await flush();
    await click(byText(m.el, ".quick button", "About $1.4 million"));
    await flush();
    await click(byText(m.el, ".side button", "Build my plan"));
    await click(byText(m.el, ".side button", "Looks right"));
    await until(() => m!.el.querySelector(".plan"));
    expect(m.el.querySelector("[data-testid=how-it-works]")).toBeNull();
    expect(m.el.querySelector("[data-testid=how-collapsed]")).toBeNull();
  }, 20000);
});

describe("2. Baseline plan", () => {
  it("the plan heading and the Compare table say baseline", async () => {
    m = await render(<PlanCard plan={base} retireAge={62} />);
    expect(m.el.querySelector("#plan-h")?.textContent).toMatch(/^Baseline plan/);
    expect(m.el.textContent).not.toMatch(/Your plan\b/);
    m.unmount();
    m = await render(<CompareTable cols={[{ key: "base", label: "Baseline", plan: base }, { key: "1", label: "Retire at 60", plan: base }]} onOpen={() => {}} />);
    const heads = Array.from(m.el.querySelectorAll(".compare thead th")).map((t) => t.textContent);
    expect(heads[1]).toBe("Baseline");   // the baseline column comes first
    expect(heads).not.toContain("Your plan");
    expect(byText(m.el, "button", "Back to baseline plan")).toBeFalsy();
    m.unmount();
    m = await render(<PlanCard plan={base} retireAge={60} scenario={{ name: "Retire at 60", baseline: base, change: "Retire at 60 instead of 62." }} />);
    expect(m.el.querySelector("#plan-h")?.textContent).toMatch(/^What if: Retire at 60/);
    expect(m.el.querySelector("[data-testid=vs-count]")?.textContent).toMatch(/same as baseline/);
    expect(m.el.querySelector(".legend")?.textContent ?? "").not.toMatch(/Before/);
  });
});

describe("3. Shortfalls are loud", () => {
  it("levels: red below 90 of 100, amber from 90 to 99, calm at 100; the verdict decides for the plan", () => {
    expect([basicsLevel(70), basicsLevel(90), basicsLevel(99), basicsLevel(100)]).toEqual(["short", "close", "close", "ok"]);
    expect(planLevel(shortPlan())).toBe("short");
    expect(planLevel({ ...base, verdict: "below_goal", needs: { ...base.needs, paid_of_100: 100 } })).toBe("short");
    expect(planLevel({ ...base, verdict: "close", needs: { ...base.needs, paid_of_100: 100 } })).toBe("close");
    expect(planLevel({ ...base, verdict: "works", needs: { ...base.needs, paid_of_100: 95 } })).toBe("ok");
    expect(yearlyGap(shortPlan())).toBe(112500);
  });

  it("a plan that falls short shows a big 'Short $112,500 a year' with an icon, and the Needs card turns red", async () => {
    m = await render(<PlanCard plan={shortPlan()} retireAge={62} />);
    const b = m.el.querySelector("[data-testid=shortfall]")!;
    expect(b.getAttribute("data-level")).toBe("short");
    expect(b.querySelector("[data-testid=shortfall-big]")?.textContent).toBe("Short $112,500 a year");
    expect(b.querySelector(".shortfall-icon")?.getAttribute("aria-hidden")).toBe("true");
    expect(b.textContent).toMatch(/70 of 100/);
    expect(m.el.querySelector(".nww-needs")?.className).toMatch(/risk/);
    expect(m.el.querySelector(".nww-needs .lvl")?.textContent).toMatch(/Short/);   // words, not colour alone
  });

  it("close is amber, and a plan that works shows no shortfall block", async () => {
    m = await render(<PlanCard plan={shortPlan({ verdict: "close", needs: { ...base.needs, paid_of_100: 95 } })} />);
    expect(m.el.querySelector("[data-testid=shortfall]")?.getAttribute("data-level")).toBe("close");
    expect(m.el.querySelector(".nww-needs")?.className).toMatch(/close/);
    m.unmount();
    m = await render(<PlanCard plan={{ ...base, verdict: "works", needs: { ...base.needs, paid_of_100: 100 } }} />);
    expect(m.el.querySelector("[data-testid=shortfall]")).toBeNull();
    expect(m.el.querySelector(".nww-needs")?.className).toMatch(/safe/);
  });

  it("the Compare table marks a short result and shows the yearly gap; the What If tab marks it against the baseline", async () => {
    const ok: Plan = { ...base, verdict: "works", needs: { ...base.needs, paid_of_100: 100 }, analysis: analysisOf(100000, 150000, 100) };
    m = await render(<CompareTable cols={[{ key: "base", label: "Baseline", plan: ok }, { key: "1", label: "Retire at 50", plan: shortPlan() }]} onOpen={() => {}} />);
    const paid = Array.from(m.el.querySelectorAll(".compare tbody tr")).find((t) => t.textContent?.includes("Basics paid"))!;
    expect(paid.querySelector("td:last-child")?.className).toMatch(/cell-short/);
    expect(paid.textContent).toMatch(/Short/);
    const gap = m.el.querySelector("[data-testid=gap-row]")!;
    expect(gap.textContent).toMatch(/None/);
    expect(gap.textContent).toMatch(/Short \$112,500/);
    m.unmount();
    m = await render(<PlanCard plan={shortPlan()} retireAge={50} scenario={{ name: "Retire at 50", baseline: ok, change: "Retire at 50 instead of 62." }} />);
    expect(m.el.querySelector("[data-testid=shortfall-big]")?.textContent).toBe("Short $112,500 a year");
    expect(m.el.querySelector("[data-testid=vs-gap]")?.textContent).toMatch(/▲ \$112,500 more short/);
    expect(m.el.querySelector("[data-testid=vs-paid]")?.textContent).toMatch(/▼ 30 fewer of 100/);
    expect(m.el.querySelector("[data-testid=vs-count]")?.textContent).toMatch(/▼ \$40,500 less a year/);
  });
});

describe("4. Token costs", () => {
  const agent = (name: string, input: number, cached: number, output: number, usd: number) => ({ agent: name, label: name, status: "done" as const, tools: [], tokens: { input, cached, output }, cost_usd: usd });
  const team = { ...emptyTeam, done: true, agents: [agent("tax", 1000, 200, 50, 0.001), agent("markets", 2000, 500, 80, 0.002)], cost: { total_tokens: 3830, total_usd: 0.003, budget_usd: 0.05 } };

  it("adds up the tokens and dollars of the run, and folds in a follow-up answer", () => {
    expect(runTotals(team)).toMatchObject({ input: 3000, cached: 700, output: 130 });
    const a = addAsk(addAsk(noAsk, 0.0004, { input: 100, cached: 50, output: 20 }), 0.0001, 30);
    expect(a.calls).toBe(2);
    expect(a).toMatchObject({ input: 130, cached: 50, output: 20 });
    expect(a.usd).toBeCloseTo(0.0005, 8);
  });

  it("shows input, cached, output, the run cost and the session total; the per-adviser table is behind an expander", async () => {
    m = await render(<CostBlock team={team} ask={noAsk} session={{ total_usd: 0.0123, total_tokens: 9999 }} />);
    const q = (id: string) => m!.el.querySelector(`[data-testid=${id}]`)?.textContent;
    expect(q("cost-input")).toBe("3,000");
    expect(q("cost-cached")).toBe("700");
    expect(q("cost-output")).toBe("130");
    expect(q("cost-run")).toBe("$0.0030");
    expect(q("cost-session")).toMatch(/\$0\.012/);
    const d = m.el.querySelector("details.cost-detail") as HTMLDetailsElement;
    expect(d.open).toBe(false);
    expect(m.el.querySelectorAll("[data-testid=cost-table] tbody tr")).toHaveLength(2);
  });

  it("is on page 2 under Team talk, fills in from the stream, and takes the session total from /api/costs", async () => {
    mockSpeed.factor = 0;
    m = await render(<TeamScreen api={mockApi} profile={profile} model="m" onBack={() => {}} />);
    await until(() => m!.el.querySelector(".plan"));
    await flush(5);
    const panel = m.el.querySelector("[data-testid=team-panel]")!;
    const talk = panel.querySelector(".talk")!, cost = panel.querySelector("[data-testid=cost-block]")!;
    expect(talk.compareDocumentPosition(cost) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(Number((cost.querySelector("[data-testid=cost-input]")?.textContent ?? "0").replace(/,/g, ""))).toBeGreaterThan(0);
    expect(cost.querySelector("[data-testid=cost-run]")?.textContent).toMatch(/^\$0\.\d+$/);
    await until(() => /\$0\.\d+/.test(cost.querySelector("[data-testid=cost-session]")?.textContent ?? ""));
    // a What If adds a follow-up line
    await click(byText(m.el, ".quick button", "Retire at 60"));
    await until(() => m!.el.querySelector("[data-testid=cost-ask]"));
    expect(m.el.querySelector("[data-testid=cost-ask]")?.textContent).toMatch(/Questions and What Ifs \(1\)/);
  }, 20000);
});
