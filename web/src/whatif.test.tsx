import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import AskBox from "./components/AskBox";
import PlanCard from "./components/PlanCard";
import TeamScreen from "./components/TeamScreen";
import { changes, changeLine, shortName } from "./components/WhatIf";
import { examplePlan, mockApi, mockSpeed } from "./mock";
import { byText, click, flush, render, until, type Mounted } from "./test-utils";
import type { Api, AskResponse, Plan, Profile } from "./types";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const profile: Profile = { age: 45, partner_age: 43, retire_age: 62, children: [{ age: 13, college: true }, { age: 10, college: true }, { age: 6, college: true }], pets: [{ kind: "dog", count: 2 }] };
const before = examplePlan(profile);
const after = { ...examplePlan({ ...profile, retire_age: 60 }), actions: [...before.actions.slice(0, 2), { title: "Build a cash bridge to 62", why: "Covers the early years." }] };

describe("What If tab: the full plan view with markers against the baseline", () => {
  it("lists the old and new figures, marks only what changed, says what changed", async () => {
    const rows = changes(before, after);
    expect(rows.find((r) => r.label === "Needs paid")).toMatchObject({ before: 96, after: 88 });
    m = await render(<PlanCard plan={after} retireAge={60} scenario={{ name: "Retire at 60", baseline: before, change: changeLine("Retire at 60", before, 62, 60), text: "Retiring at 60 means fewer years of saving.", citations: [{ title: "SSA rules", url: "https://ssa.gov/x" }] }} />);
    expect(m.el.querySelector("#plan-h")?.textContent).toMatch(/^What if: Retire at 60/);
    expect(m.el.querySelector("[data-testid=wi-change] .wi-line")?.textContent).toBe("What changed: Retire at 60 instead of 62");
    expect(m.el.querySelector(".wi-why .wi-text")?.textContent).toBe("Retiring at 60 means fewer years of saving.");   // the reply once, under Why
    expect(m.el.querySelector("[data-testid=wi-sources] a")?.textContent).toBe("SSA rules");
    // the same plan view as the baseline: headline, needs, wants, wishes, three things to do, family moments, charts
    for (const sel of [".row-needs", ".row-wants", ".lad-bar", ".actions", ".moments"]) expect(m.el.querySelector(sel), sel).toBeTruthy();
    expect(m.el.querySelector("[data-testid=vs-paid]")?.textContent).toMatch(/▼ 8 fewer of 100.*vs baseline/);
    expect(m.el.querySelector("[data-testid=vs-paid] .sr-only")?.textContent).toMatch(/worse/);   // words, not colour alone
    const newOnes = Array.from(m.el.querySelectorAll(".actions li.new, .moments li.new")).map((l) => l.textContent);
    expect(newOnes).toEqual(["1Build a cash bridge to 62new", "2041: you retire at 60; your wife is 58new"].map((t) => expect.stringContaining(t.replace(/^1/, ""))));
    expect(m.el.querySelector(".median-before")).toBeTruthy();
  });

  it("the baseline view has no markers", async () => {
    m = await render(<PlanCard plan={before} retireAge={62} />);
    expect(m.el.querySelector(".vs")).toBeNull();
    expect(m.el.querySelector("#plan-h")?.textContent).toMatch(/^Baseline plan/);
  });

  it("names a tab by the change, short", () => {
    expect(shortName("What if I retire at 64?")).toBe("Retire at 64");
    expect(shortName("Spend $75k")).toBe("Spend $75k");
    expect(shortName("What if I spend $32,000 a year", "Set your spending goal nearer the safe level")).toBe("Spend $32k");
    expect(shortName("What if I spend $500 less a month")).toBe("Spend $500 less");
    expect(shortName("What if I save to the full 401(k) match", "Save enough to get the full employer match")).toBe("Full 401(k) match");
    expect(shortName("What if I hold three months of spending in cash", "Build an emergency fund of three months")).toBe("3-month cash fund");
    expect(shortName("Markets fall 30%")).toBe("Markets fall 30%");
    expect(shortName("What if I have 5 dogs")).toBe("5 dogs");
    expect(shortName("Get a dog")).toBe("Get a dog");
    expect(shortName("Another child")).toBe("Another child");
    const odd = shortName("What if we move to a much cheaper state and also change jobs");
    expect(odd.length).toBeLessThanOrEqual(22);
    expect(odd).toMatch(/…$/);
    expect(changeLine("Spend $75k", before, 62, null)).toBe("Spend $75k");
    expect(changeLine("What if I spend $32,000 a year", { ...before, analysis: { how_sure: { goal_per_year: 40000 } } as never }, 62, null)).toBe("Spending goal $32,000 instead of $40,000");
  });
});

describe("Ask box", () => {
  const reply = (r: Partial<AskResponse>) => vi.fn(async () => ({ kind: "answer", text: "", citations: [], ...r }) as AskResponse);

  it("a What If is handed up to the plan area, with its cost added", async () => {
    const ask = reply({ kind: "whatif", text: "Retiring at 60 means fewer years of saving.", plan: after, cost_usd: 0.0004 });
    const onCost = vi.fn(), onWhatIf = vi.fn(() => 7), onAsking = vi.fn();
    m = await render(<AskBox api={{ ...mockApi, ask } as Api} profile={profile} plan={before} onCost={onCost} onWhatIf={onWhatIf} onAsking={onAsking} />);
    await click(byText(m.el, ".quick button", "Retire at 60"));
    await flush();
    expect(ask).toHaveBeenCalledWith("Retire at 60", profile, before, null);
    expect(onWhatIf).toHaveBeenCalledWith(expect.objectContaining({ q: "Retire at 60", plan: after, retireAfter: 60, cost_usd: 0.0004 }));
    expect(onAsking.mock.calls[0][0]).toEqual(expect.arrayContaining(["longevity", "markets", "adviser"]));
    expect(onAsking).toHaveBeenLastCalledWith([]);
    expect(m.el.textContent).not.toMatch(/fewer years of saving/);   // a What If is not repeated in the chat log
    expect(onCost).toHaveBeenCalledWith(0.0004, undefined);
  });

  it("offers the four suggestions as chips", async () => {
    m = await render(<AskBox api={mockApi} profile={profile} plan={before} onCost={() => {}} />);
    expect(Array.from(m.el.querySelectorAll(".quick:not(.ideas) button")).map((b) => b.textContent)).toEqual(["Retire at 60", "Another child", "Get a dog", "Markets fall 30%"]);
  });

  it("an answer shows its sources as links", async () => {
    const ask = reply({ text: "Up to $24,500.", citations: [{ title: "IRS 401(k) limits", url: "https://www.irs.gov/x" }] });
    m = await render(<AskBox api={{ ...mockApi, ask } as Api} profile={profile} plan={before} onCost={() => {}} />);
    await type(m, "How much can I put in a 401(k)?");
    await flush();
    const link = m.el.querySelector(".cites a") as HTMLAnchorElement;
    expect(link.textContent).toBe("IRS 401(k) limits");
    expect(link.href).toBe("https://www.irs.gov/x");
    expect(m.el.querySelector("[data-testid=whatif]")).toBeNull();
  });

  it("a refusal is said plainly", async () => {
    const ask = reply({ kind: "refused", text: "Moving money to qualify for Medicaid can break the law." });
    m = await render(<AskBox api={{ ...mockApi, ask } as Api} profile={profile} plan={before} onCost={() => {}} />);
    await click(byText(m.el, ".quick button", "Get a dog"));
    await flush();
    const r = m.el.querySelector(".refused")!;
    expect(r.textContent).toMatch(/We can't help with that\..*break the law/);
  });
});

async function type(mm: Mounted, text: string) {
  const input = mm.el.querySelector("#ask-input") as HTMLInputElement;
  await act(async () => {
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    set.call(input, text);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => { (mm.el.querySelector(".ask form") as HTMLFormElement).requestSubmit(); });
}

describe("Plan screen: scenario tabs", () => {
  // each What If gets its own plan (a different count of basics paid), cost and words
  const paidOf = (q: string) => 60 + (q.length % 30);
  const planFor = (q: string): Plan => (q.includes("60") ? after : { ...after, needs: { ...after.needs, paid_of_100: paidOf(q) }, wants: { ...after.wants, per_year: 50000 + q.length * 100 } });
  const mk = () => {
    const ask = vi.fn(async (q: string, _p?: Profile, _pl?: Plan, _pc?: unknown) => ({ kind: "whatif", text: "Here is " + q, citations: [], plan: planFor(q), tokens: { input: 1200, cached: 300, output: 80 }, cost_usd: 0.0004 + q.length / 1e6 }) as AskResponse);
    return { ask, api: { ...mockApi, ask } as Api };
  };
  async function open(a: Api, p: Partial<Parameters<typeof TeamScreen>[0]> = {}) {
    mockSpeed.factor = 0;
    m = await render(<TeamScreen api={a} profile={profile} model="Claude Haiku 5.5" onBack={() => {}} {...p} />);
    await until(() => m!.el.querySelector(".plan"));
  }
  const tabs = () => Array.from(m!.el.querySelectorAll<HTMLElement>("[role=tab]"));
  const sel = () => tabs().filter((t) => t.getAttribute("aria-selected") === "true").map((t) => t.textContent?.trim());
  const chip = (t: string) => byText(m!.el, ".quick button", t);
  const asked = async (t: string, n: number) => { await click(chip(t)); await until(() => tabs().length === n + 1); };

  it("shows a placeholder while the advisers work, then the plan with the team on the right", async () => {
    mockSpeed.factor = 0.2;
    m = await render(<TeamScreen api={mockApi} profile={profile} model="x" onBack={() => {}} />);
    expect(m.el.querySelector(".placeholder")?.textContent).toMatch(/Your advisers are working/);
    expect(m.el.querySelector(".plan")).toBeNull();
    await until(() => m!.el.querySelector(".plan"));
    expect(m.el.querySelector(".placeholder")).toBeNull();
    expect(m.el.querySelector(".plan-screen > .team-panel")).toBeTruthy();
    expect(m.el.querySelectorAll("input, textarea")).toHaveLength(1);
  }, 20000);

  it("starts with the Baseline tab, selected, and a '+ What if…' button; there is no baseline-swap button", async () => {
    await open(mk().api);
    expect(tabs().map((t) => t.textContent)).toEqual(["Baseline"]);
    expect(sel()).toEqual(["Baseline"]);
    expect(m!.el.querySelector("[role=tablist]")).toBeTruthy();
    expect(byText(m!.el, "button", "+ What if…")).toBeTruthy();
    expect(m!.el.querySelector(".scen-compare")).toBeNull();   // nothing to compare yet
    await asked("Retire at 60", 1);
    expect(m!.el.textContent).not.toMatch(/make this my baseline/i);
    expect(m!.el.textContent).not.toMatch(/Back to baseline plan/);
    expect(m!.el.querySelector(".summary-bar")).toBeNull();
  });

  it("makes one tab per What If, each with the full plan, and the new tab is selected", async () => {
    await open(mk().api);
    await asked("Retire at 60", 1);
    await asked("Another child", 2);
    expect(tabs().map((t) => t.textContent?.replace("✓", "").trim())).toEqual(["Baseline", "Retire at 60", "Another child"]);
    expect(sel()[0]).toContain("Another child");
    expect(m!.el.querySelector("#plan-h")?.textContent).toContain("What if: Another child");
    expect(m!.el.querySelector(".plan .ladder")).toBeTruthy();
    expect(m!.el.querySelector(".plan [data-testid=wi-change]")?.textContent).toMatch(/Another child/);
    expect(m!.el.querySelectorAll("[role=tab][aria-controls=scenario-panel]")).toHaveLength(3);
    expect(m!.el.querySelector("[role=tabpanel]#scenario-panel")).toBeTruthy();
  });

  it("builds each What If from the baseline, even while another What If is selected", async () => {
    const { ask, api } = mk();
    await open(api);
    await asked("Retire at 60", 1);
    await asked("Another child", 2);
    await asked("Get a dog", 3);
    const base = ask.mock.calls[0][2];
    expect(ask).toHaveBeenCalledTimes(3);
    for (const c of ask.mock.calls) {
      expect(c[1]).toBe(profile);           // the baseline answers
      expect(c[2]).toBe(base);              // the one baseline plan, never a What If's plan
      expect(c[3]).toBeNull();
    }
    expect(base).not.toBe(after);
    expect(base!.needs.paid_of_100).toBe(96);
  });

  it("switching tabs swaps the plan and the team panel; the session total stays", async () => {
    await open(mk().api);
    await asked("Retire at 60", 1);
    await asked("Another child", 2);
    const panel = () => m!.el.querySelector("[data-testid=team-panel]")!;
    expect(m!.el.querySelector(".wi-why .wi-text")?.textContent).toBe("Here is Another child");
    expect(m!.el.querySelector(".turns")).toBeNull();   // nothing piles up under the plan
    expect(panel().querySelector("[data-testid=scenario-said]")?.textContent).not.toContain("Here is");
    expect(panel().querySelector("[data-testid=cost-scenario]")?.textContent).toMatch(/What If “Another child” alone/);
    expect(panel().querySelector("[data-testid=cost-input]")?.textContent).toBe("1,200");
    expect(panel().querySelector("[data-testid=cost-run]")?.textContent).toMatch(/^\$0\.0004/);
    expect(panel().querySelector(".team-status")?.textContent).toMatch(/Showing the What If “Another child”/);
    await click(tabs()[1]);
    expect(sel()).toEqual(["Retire at 60"]);
    expect(m!.el.querySelector("#plan-h")?.textContent).toContain("Retire at 60");
    expect(m!.el.querySelector(".wi-why .wi-text")?.textContent).toBe("Here is Retire at 60");
    expect(panel().querySelector("[data-testid=cost-session]")).toBeTruthy();
    await click(tabs()[0]);
    expect(m!.el.querySelector("#plan-h")?.textContent).toMatch(/^Baseline plan/);
    expect(m!.el.querySelector(".vs")).toBeNull();
    expect(panel().querySelector("[data-testid=scenario-said]")).toBeNull();
    expect(panel().querySelector("[data-testid=cost-scenario]")).toBeNull();
    expect(panel().querySelector(".talk h3")?.textContent).toBe("Team talk");
    expect(panel().querySelector("[data-testid=cost-session]")).toBeTruthy();
    // an adviser's finding on a What If tab is labelled as the baseline run
    await click(tabs()[2]);
    await click(panel().querySelector("[data-agent=markets]"));
    expect(panel().querySelector(".detail-box:not(.scen-said)")?.textContent).toMatch(/baseline run/);
    expect(panel().querySelector(".talk h3")?.textContent).toBe("Team talk, baseline run");
  });

  it("arrow keys move between tabs", async () => {
    await open(mk().api);
    await asked("Retire at 60", 1);
    await click(tabs()[0]);
    expect(tabs().map((t) => t.tabIndex)).toEqual([0, -1]);
    await act(async () => { tabs()[0].dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })); });
    expect(sel()[0]).toContain("Retire at 60");
    expect(document.activeElement).toBe(tabs()[1]);
    await act(async () => { tabs()[1].dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })); });
    expect(sel()).toEqual(["Baseline"]);   // wraps round
    await act(async () => { tabs()[0].dispatchEvent(new KeyboardEvent("keydown", { key: "End", bubbles: true })); });
    expect(sel()[0]).toContain("Retire at 60");
  });

  it("the ✕ removes a What If and moves focus to the tab beside it", async () => {
    await open(mk().api);
    await asked("Retire at 60", 1);
    await asked("Another child", 2);
    expect(Array.from(m!.el.querySelectorAll(".scen-x")).map((b) => b.getAttribute("aria-label"))).toEqual(["Remove What If: Retire at 60", "Remove What If: Another child"]);
    await click(m!.el.querySelector(".scen-x[aria-label*='Another child']"));   // the selected one
    expect(tabs().map((t) => t.textContent?.replace("✓", "").trim())).toEqual(["Baseline", "Retire at 60"]);
    expect(sel()[0]).toContain("Retire at 60");
    expect(document.activeElement).toBe(tabs()[1]);
    await click(m!.el.querySelector(".scen-x"));
    expect(tabs().map((t) => t.textContent)).toEqual(["Baseline"]);
    expect(sel()).toEqual(["Baseline"]);
    expect(document.activeElement).toBe(tabs()[0]);
    expect(m!.el.querySelector("#plan-h")?.textContent).toMatch(/^Baseline plan/);
  });

  it("removing a tab that is not selected keeps the selection", async () => {
    await open(mk().api);
    await asked("Retire at 60", 1);
    await asked("Another child", 2);
    await click(m!.el.querySelector(".scen-x[aria-label*='Retire at 60']"));
    expect(tabs()).toHaveLength(2);
    expect(sel()[0]).toContain("Another child");
    expect(document.activeElement).toBe(tabs()[1]);
  });

  it("holds five What Ifs at most: the chat says to remove one first, for chips and for typed words", async () => {
    const { ask, api } = mk();
    await open(api);
    await asked("Retire at 60", 1);
    await asked("Another child", 2);
    await asked("Get a dog", 3);
    await asked("Markets fall 30%", 4);
    await type(m!, "Spend $75k");
    await until(() => tabs().length === 6);
    expect(m!.el.querySelector("[data-testid=whatif-full]")).toBeNull();
    expect(ask).toHaveBeenCalledTimes(5);
    expect(m!.el.querySelector("#scen-full")?.textContent).toMatch(/You have 5 What Ifs/);
    // a chip: nothing is sent
    await click(chip("Retire at 60"));
    await flush();
    expect(ask).toHaveBeenCalledTimes(5);
    expect(tabs()).toHaveLength(6);
    expect(m!.el.querySelector("[data-testid=whatif-full]")?.textContent).toBe("You have 5 What Ifs open. Remove one first (the ✕ on its tab), then ask again.");
    // typed words that turn out to be a What If are not added either
    await type(m!, "Spend $50k");
    await flush(5);
    expect(tabs()).toHaveLength(6);
    expect(m!.el.querySelectorAll("[data-testid=whatif-full]")).toHaveLength(2);
    expect(m!.el.textContent).not.toMatch(/Show this What If.*Show this What If.*Show this What If.*Show this What If.*Show this What If.*Show this What If/s);
    // after a removal there is room again
    await click(m!.el.querySelector(".scen-x"));
    await click(chip("Retire at 60"));
    await until(() => tabs().length === 6);
    expect(ask).toHaveBeenCalledTimes(7);
  });

  it("Compare: all tabs side by side, the baseline first, and picking a tab goes back to its plan", async () => {
    await open(mk().api);
    await asked("Retire at 60", 1);
    await asked("Another child", 2);
    const cmp = byText(m!.el, "button", "Compare")!;
    expect(cmp.getAttribute("aria-pressed")).toBe("false");
    await click(cmp);
    expect(cmp.getAttribute("aria-pressed")).toBe("true");
    const view = m!.el.querySelector("[data-testid=compare-view]")!;
    expect(view).toBeTruthy();
    expect(m!.el.querySelector(".plan")).toBeNull();
    expect(sel()).toEqual([]);   // no tab is selected while comparing
    const heads = Array.from(view.querySelectorAll("thead th")).map((t) => t.textContent);
    expect(heads).toEqual(["Measure", "Baseline", "Retire at 60", "Another child"]);
    const rowOf = (label: string) => Array.from(view.querySelectorAll("tbody tr")).find((r) => r.textContent?.startsWith(label))!;
    expect(rowOf("Needs paid").children[1].textContent).toMatch(/^96 of 100/);
    expect(rowOf("Needs paid").children[2].textContent).toMatch(/88 of 100.*▼ 8 fewer/);
    expect(rowOf("Count on").children).toHaveLength(4);
    expect(view.textContent).not.toMatch(/make this my baseline/i);
    await click(byText(view, ".cmp-open", "Retire at 60"));
    expect(m!.el.querySelector("[data-testid=compare-view]")).toBeNull();
    expect(sel()[0]).toContain("Retire at 60");
    expect(m!.el.querySelector("#plan-h")?.textContent).toContain("Retire at 60");
  });

  it("a change that rebuilds the baseline clears the tabs and says so", async () => {
    const fixedProfile = { ...profile, pay_per_year: 210000 };
    const fixedPlan = { ...before, wants: { ...before.wants, per_year: 98765 } };
    const ask = vi.fn(async (q: string) => (/pay/.test(q)
      ? { kind: "change", status: "applied", text: "Done.", citations: [], profile: fixedProfile, plan: fixedPlan }
      : { kind: "whatif", text: "Here is " + q, citations: [], plan: after }) as AskResponse);
    await open({ ...mockApi, ask } as Api);
    await asked("Retire at 60", 1);
    await type(m!, "my pay is 210k");
    await until(() => tabs().length === 1);
    expect(m!.el.querySelector("#plan-h")?.textContent).toMatch(/^Baseline plan/);
    expect(m!.el.textContent).toContain("98,765");
    expect(m!.el.querySelector("[data-testid=scen-cleared]")?.textContent).toMatch(/What Ifs were cleared/);
  });

  it("tells the person that rebuilding a stale plan clears the What Ifs", async () => {
    const { api } = mk();
    await open(api);
    await asked("Retire at 60", 1);
    expect(m!.el.querySelector("[data-testid=scen-stale]")).toBeNull();
    await act(async () => { m!.root.render(<TeamScreen api={api} profile={profile} model="Claude Haiku 5.5" onBack={() => {}} stale />); });
    expect(m!.el.querySelector("[data-testid=scen-stale]")?.textContent).toMatch(/Rebuilding the plan clears these What Ifs/);
  });

  it("'+ What if…' focuses the chat box", async () => {
    await open(mk().api);
    await click(byText(m!.el, "button", "+ What if…"));
    expect(document.activeElement).toBe(m!.el.querySelector("#ask-input"));
  });

  it("sends the advisers it reruns back to work while a What If is on its way", async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => { release = r; });
    const ask = vi.fn(async (q: string) => { await gate; return { kind: "whatif", text: "Here is " + q, citations: [], plan: after } as AskResponse; });
    await open({ ...mockApi, ask } as Api);
    const st = (a: string) => m!.el.querySelector(`.team-panel .node-${a}`)!.getAttribute("data-state");
    expect(st("markets")).toBe("done");
    await click(chip("Markets fall 30%"));
    expect(st("markets")).toBe("working");
    expect(st("adviser")).toBe("working");
    expect(st("research")).toBe("done");
    release();
    await until(() => tabs().length === 2);
    expect(st("markets")).toBe("done");
  });

  it("a What If with no tokens in its reply says so, and the session total stays", async () => {
    const ask = vi.fn(async (q: string) => ({ kind: "whatif", text: "Here is " + q, citations: [], plan: after }) as AskResponse);
    await open({ ...mockApi, ask } as Api);
    await asked("Retire at 60", 1);
    const panel = m!.el.querySelector("[data-testid=team-panel]")!;
    expect(panel.querySelector("[data-testid=cost-scenario]")?.textContent).toMatch(/did not report tokens or cost/);
    expect(panel.querySelector("[data-testid=cost-run]")?.textContent).toBe("—");
    expect(panel.querySelector("[data-testid=cost-session]")).toBeTruthy();
  });
});
