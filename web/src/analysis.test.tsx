import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import AnalysisSection, { mergeSources, sourcesReadout, sureSentence, topChoices, topRisks } from "./components/AnalysisSection";
import CostsChart, { costsReadout } from "./components/CostsChart";
import { render, type Mounted } from "./test-utils";
import type { Analysis, AnalysisRow } from "./types";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const analysis: Analysis = {
  paths: 2000, seed: 409, plan_count_on_per_year: 31900, plan_basics_paid_of_100: 99,
  how_sure: {
    levels: [{ of_100: 50, per_year: 39600 }, { of_100: 75, per_year: 34900 }, { of_100: 90, per_year: 31900 }, { of_100: 95, per_year: 30500 }],
    curve_spend: [0, 10000, 20000, 30000, 40000, 50000], curve_lasts_of_100: [100, 100, 100, 93, 48, 10],
    goal_per_year: 40000, goal_lasts_of_100: 48, count_on_per_year: 31900, basics_per_year: 28900, basics_paid_of_100: 99,
    line: "In half of the scenarios you could spend $39,600 a year.",
  },
  stresses: { line: "", rows: [] },
  levers: { line: "", rows: [] },
  sources: {
    ages: [64, 65, 66, 67], spending: [46000, 40000, 40000, 40000], surplus: [0, 0, 0, 2000], goal_per_year: 40000,
    line: "Pay covers your spending until you retire.",
    series: [
      { key: "pay", label: "Pay", values: [46000, 0, 0, 0] },
      { key: "ss_you", label: "Social Security", values: [0, 0, 29500, 42000] },
      { key: "savings", label: "From savings", values: [0, 40000, 10500, 0] },
    ],
  },
};
const press = (el: Element, k: string) => act(async () => { el.dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true })); });

const row = (key: string, title: string, c: number, b: number, cc: number, bc: number, extra: Partial<AnalysisRow> = {}): AnalysisRow =>
  ({ key, title, count_on_per_year: c, basics_paid_of_100: b, count_on_change: cc, basics_change: bc, ...extra });
const many: Analysis = {
  ...analysis,
  stresses: { line: "", rows: [
    row("bad_decade", "A poor first decade", 31200, 98, -700, -1), row("inflation", "Higher inflation", 30000, 97, -1900, -2),
    row("long_you", "Living to 100", 26000, 80, -5900, -19, { label: "You live to 100", sentence: "Your $31,000 a year still lasts in most paths. In the worst 1 in 10, savings run out at 93, and you would cut about $6,000 a year for 7 years. Basics stay paid in 80 of 100 paths." }), row("long_partner", "Your partner lives to 100", 27000, 85, -4900, -14),
    row("early_death", "The first death comes 10 years early", 33000, 99, 1100, 0, { note: "Spending falls as well." }),
  ] },
  levers: { line: "", rows: [
    row("retire", "Retire 1 year later, at 67", 33600, 100, 1700, 1, { ask: "What if I retire at 67" }),
    row("claim", "Claim Social Security at 70", 33000, 100, 1100, 0, { ask: "What if I claim Social Security at 70" }),
    row("match", "Take the full match", 32300, 99, 400, 0), row("debt", "Pay off the card", 32200, 99, 300, 6, { ask: "What if I pay off my credit card" }),
    row("save", "Save $100 a month more", 31900, 99, 0, 0), row("spend_now", "Spend less", 32800, 99, 900, 0),
  ] },
};
const text = (el: Element | null) => (el?.textContent ?? "");
const words = (s: string) => s.trim().split(/\s+/).filter(Boolean).length;

describe("The analysis", () => {
  it("is a closed expander: one sentence, two small tables, one chart", async () => {
    m = await render(<AnalysisSection analysis={many} onTry={() => {}} />);
    const d = m.el.querySelector("[data-testid=plan-analysis]") as HTMLDetailsElement;
    expect(d.tagName).toBe("DETAILS");
    expect(d.open).toBe(false);
    expect(d.querySelector("summary")?.textContent).toBe("The analysis");
    expect(Array.from(d.querySelectorAll("h4")).map((h) => h.textContent)).toEqual(["How sure is it?", "What could go wrong?", "What each choice is worth", "Where the money comes from"]);
    expect(d.querySelectorAll("table").length).toBe(1);
    expect(d.querySelectorAll("svg[role=img]").length).toBe(1);
    expect(d.querySelector(".table-view")).toBeNull();
    // about 150 words of visible text apart from the table and labels (the three sentences included)
    const clone = d.cloneNode(true) as HTMLElement;
    clone.querySelectorAll("table, h4, summary, .an-legend, .sr-only, svg").forEach((e) => e.remove());
    expect(words(clone.textContent ?? "")).toBeLessThanOrEqual(160);
  });
  it("renders nothing without an analysis", async () => {
    m = await render(<AnalysisSection analysis={null} />);
    expect(m.el.querySelector("[data-testid=plan-analysis]")).toBeNull();
  });
  it("how sure is one sentence with the plan's own figures, and no chart", async () => {
    m = await render(<AnalysisSection analysis={analysis} />);
    const p = m.el.querySelector("[data-testid=an-sure]")!;
    expect(p.textContent).toBe("Spending $34,900 a year lasts in 75 of 100 market paths; $30,500 lasts in 95.");
    expect(sureSentence(analysis.how_sure)).toBe(p.textContent);
    expect(m.el.querySelector("[data-testid=sure-chart]")).toBeNull();
    expect(sureSentence({ ...analysis.how_sure, levels: [{ of_100: 75, per_year: 0 }, { of_100: 95, per_year: 0 }] })).toBe(analysis.how_sure.line);
  });
  it("risks: at most 3 sentences, worst first, only those that hurt, each starting with the risk in bold", async () => {
    expect(topRisks(many.stresses.rows).map((r) => r.key)).toEqual(["long_you", "long_partner", "inflation"]);
    m = await render(<AnalysisSection analysis={many} />);
    const items = m.el.querySelectorAll("[data-testid=an-stresses] li");
    expect(items.length).toBe(3);
    expect(m.el.querySelector("[data-testid=an-stresses]")?.tagName).toBe("UL");
    expect(items[0].querySelector("strong")?.textContent).toBe("You live to 100.");
    expect(text(items[0])).toContain("Your $31,000 a year still lasts in most paths");
    expect(m.el.querySelectorAll("[data-at-risk=true]").length).toBe(0);
    expect(m.el.textContent).not.toContain("Spending drops to 75%");   // the early-death sentence shows only when that row is in the top 3
  });
  it("risks: when basics stay paid in every path for all shown, that is said once after the list", async () => {
    const s = (k: string, c: number) => row(k, k, c, 100, -1000, 0, { label: k, sentence: "Your $31,000 a year still lasts in most paths." });
    const a = { ...many, stresses: { line: "", top: ["a", "b", "c"], rows: [s("a", 1), s("b", 2), s("c", 3)] } };
    m = await render(<AnalysisSection analysis={a} />);
    expect(m.el.querySelector("[data-testid=an-basics-all]")?.textContent).toBe("In all three, your basics stay paid in every path.");
    expect(m.el.querySelector("[data-testid=an-stresses]")?.textContent).not.toContain("basics");
    m.unmount();
    m = await render(<AnalysisSection analysis={many} />);
    expect(m.el.querySelector("[data-testid=an-basics-all]")).toBeNull();   // some differ: said per sentence
  });
  it("risks: amber marks a risk to the basics, and the server's top list sets what shows", async () => {
    const bad = row("long_you", "Living to 100", 20000, 70, -9000, -28, { label: "You live to 100", basics_at_risk: true, sentence: "Your basics would go unpaid in 30 of 100 market paths." });
    const early = row("early_death", "The first death comes 10 years early", 33000, 99, -500, 0, { label: "The first death comes 10 years early", sentence: "The plan still works. Spending drops to 75% for the one left." });
    const a = { ...many, stresses: { line: "", top: ["long_you", "early_death"], rows: [bad, early, ...many.stresses.rows.slice(0, 1)] } };
    m = await render(<AnalysisSection analysis={a} />);
    const items = m.el.querySelectorAll("[data-testid=an-stresses] li");
    expect(items.length).toBe(2);
    expect(items[0].getAttribute("data-at-risk")).toBe("true");
    expect(items[0].className).toContain("an-risk-warn");
    expect(items[1].getAttribute("data-at-risk")).toBeNull();
    expect(text(items[1])).toContain("Spending drops to 75% for the one left.");
  });
  it("risks: a plan that already falls short gets one sentence, not the table", async () => {
    m = await render(<AnalysisSection analysis={{ ...many, plan_basics_paid_of_100: 62 }} />);
    expect(m.el.querySelector("[data-testid=an-stresses]")).toBeNull();
    expect(m.el.querySelector("[data-testid=an-short]")?.textContent).toContain("62 of 100");
  });
  it("choices: hidden below the threshold, at most 3 rows, best first", async () => {
    expect(topChoices(many.levers.rows).map((r) => r.key)).toEqual(["retire", "claim", "spend_now"].sort((a, b) => many.levers.rows.find((r) => r.key === b)!.count_on_change - many.levers.rows.find((r) => r.key === a)!.count_on_change));
    expect(topChoices([row("a", "A", 1, 1, 499, 4), row("b", "B", 1, 1, 0, 0)])).toEqual([]);
    expect(topChoices([row("a", "A", 1, 1, 100, 5)]).length).toBe(1);
    m = await render(<AnalysisSection analysis={many} onTry={() => {}} />);
    expect(m.el.querySelectorAll("[data-testid=an-levers] tbody tr").length).toBe(3);
    expect(text(m.el.querySelector("[data-testid=an-levers]"))).toContain("+$1,700");
    m.unmount();
    m = await render(<AnalysisSection analysis={{ ...many, levers: { line: "", rows: [row("save", "Save $100 a month more", 31900, 99, 0, 0)] } }} onTry={() => {}} />);
    expect(m.el.querySelector("[data-testid=an-levers]")).toBeNull();
    expect(m.el.textContent).not.toContain("What each choice is worth");
  });
  it("choices: Try this runs a What If", async () => {
    const onTry = vi.fn();
    m = await render(<AnalysisSection analysis={many} onTry={onTry} />);
    const b = m.el.querySelector("[data-testid=an-levers] tbody tr button") as HTMLButtonElement;
    expect(b.textContent).toContain("Try this");
    await act(async () => { b.click(); });
    expect(onTry).toHaveBeenCalledWith("What if I retire at 67");
  });
  it("sources chart: four series, the readout lists each part and they add up", async () => {
    const wide: Analysis["sources"] = { ...analysis.sources, series: [
      { key: "pay", label: "Pay", values: [46000, 0, 0, 0] },
      { key: "ss_you", label: "Social Security, you", values: [0, 0, 20000, 30000] }, { key: "ss_partner", label: "Social Security, your partner", values: [0, 0, 9500, 12000] },
      { key: "pension", label: "Pensions", values: [0, 0, 0, 0] }, { key: "annuity", label: "Annuity", values: [0, 0, 0, 0] },
      { key: "savings", label: "From savings", values: [0, 40000, 10500, 0] },
    ] };
    expect(mergeSources(wide).series.map((s) => s.key)).toEqual(["pay", "ss", "pension", "savings"]);
    m = await render(<AnalysisSection analysis={{ ...analysis, sources: wide }} />);
    const svg = m.el.querySelector("[data-testid=sources-chart]")!;
    expect(svg.getAttribute("tabindex")).toBe("0");
    await press(svg, "Home"); await press(svg, "ArrowRight"); await press(svg, "ArrowRight");
    const tip = m.el.querySelector("[data-testid=sources-tip]")!.textContent!;
    expect(tip).toContain("Age 66");
    expect(tip).toMatch(/Social Security\s?\$29,500/);
    expect(tip).toMatch(/From savings\s?\$10,500/);
    const merged = mergeSources(wide);
    for (let i = 0; i < merged.ages.length; i++) {
      const r = sourcesReadout(merged, i);
      expect(r.parts.reduce((t, p) => t + p.value, 0)).toBe(r.spending + r.surplus);
    }
    expect(sourcesReadout(merged, 3).text).toContain("Saved: $2,000");
    await press(svg, "Escape");
    expect(m.el.querySelector("[data-testid=sources-tip]")).toBeNull();
  });
});

describe("Costs chart parts", () => {
  const costs = {
    ages: [60, 61], total: [90000, 80000], basics: [50000, 50000], events: [{ age: 60, label: "You retire at 60", year: 2026 }],
    parts: [{ key: "basics", label: "Basics: home, food, transport, care", values: [50000, 50000] },
            { key: "health_cover", label: "Health cover before Medicare", values: [12000, 12000] },
            { key: "other", label: "Other spending", values: [28000, 18000] }],
  };
  it("the readout lists the parts, which add up to the total", async () => {
    const r = costsReadout(costs, 0);
    expect(r.parts.reduce((t, p) => t + p.value, 0)).toBe(r.total);
    expect(r.text).toContain("Health cover before Medicare: $12,000");
    m = await render(<CostsChart costs={costs} retireAge={60} />);
    const svg = m.el.querySelector("svg")!;
    await press(svg, "ArrowRight");
    const tip = m.el.querySelector("[data-testid=costs-tip]")!.textContent!;
    expect(tip).toMatch(/Health cover before Medicare\s?\$12,000/);
    expect(tip).toMatch(/Other spending\s?\$28,000/);
  });
});

describe("The analysis, risks grouped", () => {
  it("one lead line, then a short line per risk, then the shared basics line; full sentences when verdicts differ", async () => {
    const h = (k: string, label: string, short: string) => row(k, label, 1, 100, -1000, 0, { label, kind: "holds", short, sentence: "Full sentence." });
    const a = { ...many, stresses: { line: "", top: ["a", "b", "c"], lead: "Your $111,000 a year holds up in most market paths under each of these. In the worst 1 in 10:", rows: [
      h("a", "Prices rise faster for 10 years", "savings run out at 93; you would cut about $40,000 a year for 5 years."),
      h("b", "Stocks do badly for 10 years", "savings run out at 93; you would cut about $37,000 a year for 5 years."),
      h("c", "Your partner lives to 100", "savings run out at 98; you would cut about $39,000 a year for 5 years.")] } };
    m = await render(<AnalysisSection analysis={a} />);
    expect(m.el.querySelector("[data-testid=an-lead]")?.textContent).toContain("holds up in most market paths under each of these");
    const items = m.el.querySelectorAll("[data-testid=an-stresses] li");
    expect(items.length).toBe(3);
    expect(items[0].textContent).toBe("Prices rise faster for 10 years: savings run out at 93; you would cut about $40,000 a year for 5 years.");
    expect(items[0].querySelector("strong")?.textContent).toBe("Prices rise faster for 10 years:");
    expect(m.el.textContent?.split("$111,000").length).toBe(2);   // the plan's figure is said once
    expect(m.el.querySelector("[data-testid=an-basics-all]")?.textContent).toBe("In all three, your basics stay paid in every path.");
    m.unmount();
    m = await render(<AnalysisSection analysis={{ ...a, stresses: { ...a.stresses, lead: "" } }} />);   // differing verdicts: no lead, full sentences
    expect(m.el.querySelector("[data-testid=an-lead]")).toBeNull();
    expect(text(m.el.querySelectorAll("[data-testid=an-stresses] li")[0])).toContain("Full sentence.");
  });
});
