import { afterEach, describe, expect, it } from "vitest";
import { act } from "react";
import App from "./App";
import AdminScreen from "./components/AdminScreen";
import { ADMIN_BEFORE_KEY, adminFromUrl, adminSession, markAdminSession, buildExport, compare, diffRow, pool, summarize, type Metrics } from "./admin";
import { examplePlan, mockApi, mockSpeed } from "./mock";
import { byText, click, flush, render, until, type Mounted } from "./test-utils";
import type { Api, Plan, Profile, Sample } from "./types";

// jsdom here has no web storage (opaque origin), so give the test a small one.
for (const name of ["localStorage", "sessionStorage"]) {
  const mem = new Map<string, string>();
  Object.defineProperty(globalThis, name, { configurable: true, value: { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => void mem.set(k, v), removeItem: (k: string) => void mem.delete(k), clear: () => mem.clear() } });
}

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; localStorage.clear(); });

const mk = (id: string, tier: Sample["tier"], name: string, profile: Profile): Sample => ({
  id, tier, name, description: `About ${name}.`, profile,
  intake: { profile, fields: [{ key: "age", label: "Your age", value: profile.age, source: "you said", section: "Household" }], missing: [], question: null, reply: "Loaded." },
});
const SAMPLES: Sample[] = [
  mk("a", "comfortable", "Doctor couple", { age: 45, partner_age: 43, state: "CT", retire_age: 62, pay_per_year: 310000, savings: { pretax: 900000 }, spending_now_per_year: 200000 }),
  mk("b", "comfortable", "Retired couple", { age: 71, partner_age: 68, state: "NC", retire_age: 71, pay_per_year: 0, savings: { pretax: 1100000 }, spending_now_per_year: 85000 }),
  mk("c", "average", "Single, 66", { age: 66, state: "FL", retire_age: 69, pay_per_year: 130000, savings: { pretax: 700000 }, spending_now_per_year: 83000 }),
  mk("d", "average", "Young couple", { age: 34, partner_age: 33, state: "TX", retire_age: 65, pay_per_year: 130000, savings: { pretax: 80000 }, spending_now_per_year: 96000 }),
  mk("e", "struggling", "Single parent", { age: 34, state: "GA", retire_age: 66, pay_per_year: 52000, savings: { cash: 10500 }, spending_now_per_year: 46000 }),
  mk("f", "struggling", "Retiree on Social Security", { age: 68, state: "WV", retire_age: 68, pay_per_year: 0, savings: { cash: 3000 }, spending_now_per_year: 20000 }),
];

/** An api whose plans we control: `countOn` is what each plan says you can count on. */
function fake(countOn: { v: number }, tracker = { now: 0, max: 0 }): Api {
  return {
    ...mockApi,
    samples: async () => SAMPLES,
    async plan(profile, onEvent) {
      tracker.now++; tracker.max = Math.max(tracker.max, tracker.now);
      await new Promise((r) => setTimeout(r, 5));
      const plan: Plan = examplePlan(profile);
      plan.wants = { ...plan.wants, per_year: countOn.v };
      plan.verdict = countOn.v >= 100000 ? "works" : "below_goal";
      onEvent({ type: "plan", plan });
      onEvent({ type: "done" });
      tracker.now--;
    },
  };
}
const q = (sel: string) => m!.el.querySelector(sel);
const noop = () => {};
/** The browser Back button from a household: the address returns to /admin and a popstate fires. */
async function back() {
  window.history.replaceState({}, "", "/admin");
  await act(async () => { window.dispatchEvent(new PopStateEvent("popstate")); });
  window.history.replaceState({}, "", "/");
}
const idle = () => !byText(m!.el, "button", "Running");

describe("admin gating", () => {
  it("is on only at the path /admin; ?admin does nothing", () => {
    expect(adminFromUrl("")).toBe(false);
    expect(adminFromUrl("/")).toBe(false);
    expect(adminFromUrl("/?admin")).toBe(false);
    expect(adminFromUrl("/admin")).toBe(true);
    expect(adminFromUrl("/admin/")).toBe(true);
    expect(adminFromUrl("/administrator")).toBe(false);
    // the default reads the address: this page is not /admin
    expect(adminFromUrl()).toBe(false);
  });

  it("an admin session sets the flag that api.ts reads for the test header", () => {
    sessionStorage.clear();
    expect(adminSession()).toBe(false);
    markAdminSession();
    expect(adminSession()).toBe(true);
    sessionStorage.clear();
  });

  it("opening the app at /admin marks the session; opening it elsewhere does not", async () => {
    sessionStorage.clear();
    m = await render(<App api={mockApi} admin={false} />);
    expect(adminSession()).toBe(false);
    m.unmount();
    m = await render(<App api={{ ...mockApi, samples: async () => SAMPLES }} admin />);
    expect(adminSession()).toBe(true);
  });

  it("nobody sees an Admin button, in any mode", async () => {
    mockSpeed.factor = 0;
    m = await render(<App api={fake({ v: 120000 })} admin />);
    await until(() => q(".adm-table"));
    expect(q(".admin-link")).toBeNull();
    await click(byText(m.el, "button", "Open in app"));
    expect(q(".admin-link")).toBeNull();
    expect(byText(m.el, "header button", "Admin")).toBeUndefined();
  });

  it("the Model comparison section shows the table, the winner in words, the recommendation and the caveats", async () => {
    m = await render(<AdminScreen api={fake({ v: 1 })} onOpen={noop} onBuild={noop} />);
    await until(() => q("[data-testid=model-compare] table"));
    const sec = q("[data-testid=model-compare]")!;
    expect(sec.querySelector("h3")?.textContent).toContain("Model comparison");
    expect(Array.from(sec.querySelectorAll("thead th")).map((h) => h.textContent)).toEqual(["Metric", "Claude Haiku 5.5", "gpt-6-luna", "n", "Winner"]);
    expect(sec.querySelectorAll("tbody tr")).toHaveLength(2);
    expect(sec.querySelector(".adm-win")?.textContent).toContain("Winner: Haiku");   // words, not colour alone
    expect(sec.querySelector("tbody tr:last-child .adm-win")?.textContent).toContain("Tie");
    expect(sec.querySelector("[data-testid=model-rec]")?.textContent).toContain("Use Claude Haiku 5.5 as the default.");
    expect(sec.textContent).toContain("2026-11-22");
    expect(sec.textContent).toContain("$2.60");
    expect(sec.querySelector("details summary")?.textContent).toBe("Caveats");
  });

  it("the Model comparison section has an empty state when the endpoint has nothing", async () => {
    m = await render(<AdminScreen api={{ ...fake({ v: 1 }), modelCompare: async () => { throw new Error("No model comparison has been saved yet."); } }} onOpen={noop} onBuild={noop} />);
    await until(() => q(".adm-table"));
    await until(() => q("[data-testid=model-compare]")?.textContent?.includes("No comparison run yet."));
    expect(q("[data-testid=model-compare] table")).toBeNull();
  });

  it("a normal user sees no Admin link and no admin screen, and never asks for the samples", async () => {
    mockSpeed.factor = 0;
    let asked = 0;
    m = await render(<App api={{ ...mockApi, samples: async () => { asked++; return SAMPLES; } }} admin={false} />);
    expect(byText(m.el, "button", "Admin")).toBeUndefined();
    expect(q(".adm")).toBeNull();
    expect(asked).toBe(0);
  });

  it("at /admin the list is the first screen, and the browser's Back returns to it from a household", async () => {
    mockSpeed.factor = 0;
    m = await render(<App api={fake({ v: 120000 })} admin />);
    await until(() => q(".adm-table"));
    expect(q(".adm")?.closest("[hidden]")).toBeNull();
    expect(q(".steps")).toBeNull();
    await click(byText(m.el, "button", "Open in app"));
    expect(q(".adm")?.closest("[hidden]")).not.toBeNull();
    await back();   // Back, with the address at /admin
    expect(q(".adm")?.closest("[hidden]")).toBeNull();
  });
});

describe("admin screen", () => {
  it("lists households by tier with their figures and two buttons each", async () => {
    m = await render(<AdminScreen api={fake({ v: 1 })} onOpen={noop} onBuild={noop} />);
    await until(() => q(".adm-table"));
    const heads = Array.from(m.el.querySelectorAll("h3.adm-h")).map((h) => h.textContent);
    expect(heads[0]).toMatch(/Comfortable/); expect(heads[1]).toMatch(/Average/); expect(heads[2]).toMatch(/Struggling/);
    const doctor = byText(m.el, "tr", "Doctor couple")!;
    expect(doctor.textContent).toMatch(/45 and 43/);
    expect(doctor.textContent).toContain("$310,000");
    expect(doctor.textContent).toContain("$900,000");
    expect(doctor.textContent).toContain("$200,000");
    expect(doctor.textContent).toContain("CT");
    expect(doctor.querySelectorAll("button").length).toBe(2);
    expect(m.el.querySelectorAll(".adm-tier tbody tr").length).toBe(SAMPLES.length);
    expect(Array.from(m.el.querySelectorAll("table")).every((t) => t.querySelector("caption") && t.querySelector("th[scope=col]"))).toBe(true);
  });

  it("Open in app and Build plan hand the household on", async () => {
    const got: string[] = [];
    m = await render(<AdminScreen api={fake({ v: 1 })} onOpen={(s) => got.push("open " + s.id)} onBuild={(s) => got.push("build " + s.id)} />);
    await until(() => q(".adm-table"));
    const row = byText(m.el, "tr", "Single parent")!;
    await click(byText(row, "button", "Open in app"));
    await click(byText(row, "button", "Build plan"));
    expect(got).toEqual(["open e", "build e"]);
  });

  it("Open in app puts the figures on page 1; Build plan goes to the plan", async () => {
    mockSpeed.factor = 0;
    m = await render(<App api={fake({ v: 120000 })} admin />);
    await until(() => q(".adm-table"));
    await click(byText(byText(m.el, "tr", "Single, 66")!, "button", "Open in app"));
    await until(() => byText(m!.el, ".side button", "Build my plan"));
    expect((byText(m.el, ".side button", "Build my plan") as HTMLButtonElement).disabled).toBe(false);
    expect(q(".side")?.textContent).toContain("66");
    await back();
    await click(byText(byText(m.el, "tr", "Young couple")!, "button", "Build plan"));
    await until(() => q(".plan"));
  }, 20000);

  it("Start over empties page 1 completely, also for a household opened from admin, and drops the plan and its tabs", async () => {
    mockSpeed.factor = 0;
    m = await render(<App api={fake({ v: 120000 })} admin />);
    await until(() => q(".adm-table"));
    await click(byText(byText(m.el, "tr", "Single, 66")!, "button", "Open in app"));
    await until(() => q(".side [data-key]"));
    expect(m.el.querySelectorAll(".side [data-key]").length).toBeGreaterThan(0);
    await click(byText(m.el, "button", "Start over"));
    await click(byText(m.el, "button", "Yes, clear"));
    await flush();
    expect(m.el.querySelectorAll(".side [data-key]")).toHaveLength(0);
    expect(m.el.querySelectorAll(".bubble-you")).toHaveLength(0);
    expect(m.el.querySelectorAll(".bubble-us")).toHaveLength(1);
    // the same after Build plan, from the plan page with a What If tab open
    await act(async () => { window.history.replaceState({}, "", "/admin"); window.dispatchEvent(new PopStateEvent("popstate")); window.history.replaceState({}, "", "/"); });
    await click(byText(byText(m.el, "tr", "Young couple")!, "button", "Build plan"));
    await until(() => q(".plan"));
    expect(q("[role=tablist]")).toBeTruthy();
    await click(byText(m.el, "button", "Start over"));
    await click(byText(m.el, "button", "Yes, clear"));
    await flush();
    expect(q(".plan-screen")).toBeNull();
    expect(q("[role=tab]")).toBeNull();
    expect(m.el.querySelectorAll(".side [data-key]")).toHaveLength(0);
    expect(m.el.querySelectorAll(".bubble-us")).toHaveLength(1);
  }, 20000);

  it("the footer says only that this is not financial advice", async () => {
    m = await render(<App api={mockApi} admin={false} />);
    const f = m.el.querySelector("footer")!.textContent ?? "";
    expect(f).toMatch(/Not financial advice/);
    expect(f).not.toMatch(/Yale|MGT|teaching/i);
  });

  it("Run all builds every plan, at most 3 at once, and fills the table", async () => {
    const t = { now: 0, max: 0 };
    m = await render(<AdminScreen api={fake({ v: 120000 }, t)} onOpen={noop} onBuild={noop} />);
    await until(() => q(".adm-table"));
    expect(q(".adm-res-table")).toBeNull();
    await click(byText(m.el, "button", "Run all"));
    await until(() => /6 of 6 plans finished/.test(m!.el.textContent ?? "") && idle());
    expect(t.max).toBe(3);
    const rows = m.el.querySelectorAll(".adm-res-table tbody tr");
    expect(rows.length).toBe(6);
    expect(rows[0].textContent).toMatch(/Comfortable.*Doctor couple.*Works.*\$120,000/);
    expect(byText(m.el, "button", "Download results")?.hasAttribute("disabled")).toBe(false);
  }, 20000);

  it("Save as before, change, run again: Before and After side by side with the changes marked", async () => {
    const v = { v: 120000 };
    m = await render(<AdminScreen api={fake(v)} onOpen={noop} onBuild={noop} />);
    await until(() => q(".adm-table"));
    await click(byText(m.el, "button", "Run all"));
    await until(() => /6 of 6/.test(m!.el.textContent ?? "") && idle());
    expect(q(".adm-pair")).toBeNull();                      // nothing to compare with yet
    await click(byText(m.el, "button", "Save as before"));
    const saved = JSON.parse(localStorage.getItem(ADMIN_BEFORE_KEY)!);
    expect(Object.keys(saved.results).length).toBe(6);
    expect(typeof saved.savedAt).toBe("string");
    v.v = 90000;                                            // after: less to count on, verdict worse
    await click(byText(m.el, "button", "Run all"));
    await until(() => q(".adm-pair") && idle());
    expect(q(".adm-res-table td.adm-pair.adm-worse")).toBeTruthy();
    const row = byText(m.el, ".adm-res-table tr", "Doctor couple")!;
    expect(row.textContent).toContain("Before");
    expect(row.textContent).toContain("$120,000");
    expect(row.textContent).toContain("$90,000");
    expect(row.textContent).toMatch(/▼/);
    expect(row.querySelector(".sr-only")?.textContent).toMatch(/worse/);
    v.v = 150000;                                           // and better
    await click(byText(m.el, "button", "Run all"));
    await until(() => q(".adm-pair.adm-better") && idle());
    expect(byText(m.el, ".adm-res-table tr", "Doctor couple")!.textContent).toMatch(/▲/);
  }, 30000);
});

describe("admin helpers", () => {
  const mm = (over: Partial<Metrics> = {}): Metrics => ({ verdict: "works", basics_of_100: 95, count_on: 100000, gap: 0, savings_at_retire: 1_000_000, ...over });

  it("compares with the right direction of good", () => {
    expect(compare(100, 120)).toMatchObject({ dir: "up", good: true });
    expect(compare(100, 80)).toMatchObject({ dir: "down", good: false });
    expect(compare(100, 80, true)).toMatchObject({ dir: "down", good: true });
    expect(compare(100, 100.2, false, 1).dir).toBe("same");
    expect(compare(null, 5).dir).toBe("same");
  });

  it("diffRow marks a worse verdict and a bigger gap as worse", () => {
    const d = diffRow(mm(), mm({ verdict: "close", gap: 12000, count_on: 100200 }));
    expect(d.verdict).toMatchObject({ dir: "down", good: false });
    expect(d.gap).toMatchObject({ dir: "up", good: false });
    expect(d.count_on.dir).toBe("same");                    // inside the $500 tolerance
    expect(d.basics.dir).toBe("same");
  });

  it("summarize reads the plan's main figures", () => {
    const p = Object.assign(examplePlan({ age: 45, retire_age: 62, savings: { pretax: 900000 } }), { verdict: "close" });
    const s = summarize(p, 62);
    expect(s.verdict).toBe("close");
    expect(s.basics_of_100).toBe(p.needs.paid_of_100);
    expect(s.count_on).toBe(p.wants.per_year);
    expect(s.savings_at_retire).toBe(p.chart.median[p.chart.ages.indexOf(62)]);
  });

  it("the download holds after and before for every household", () => {
    const out = buildExport(SAMPLES, { a: mm() }, { savedAt: "2026-11-22T10:00:00.000Z", results: { a: mm({ count_on: 1 }) } }, new Date("2026-11-22T11:00:00Z"));
    expect(out.households.length).toBe(6);
    expect(out.households[0]).toMatchObject({ id: "a", tier: "comfortable", after: { count_on: 100000 }, before: { count_on: 1 } });
    expect(out.households[1].after).toBeNull();
    expect(out.before_saved_at).toBe("2026-11-22T10:00:00.000Z");
  });

  it("pool never runs more than the limit at once", async () => {
    let now = 0, max = 0;
    await pool([1, 2, 3, 4, 5, 6, 7], 3, async () => { now++; max = Math.max(max, now); await new Promise((r) => setTimeout(r, 2)); now--; });
    expect(max).toBe(3);
  });
});
