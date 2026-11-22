import { afterEach, describe, expect, it } from "vitest";
import App from "./App";
import AgentPortrait, { type AgentKey, portraitAlt } from "./figure/Advisers";
import { mockApi, mockSpeed } from "./mock";
import { byText, click, flush, render, until, type Mounted } from "./test-utils";

// Outcome tests for the UI product rules (docs/PRODUCT_RULES.md): R3 one place to type, R17 ruthless UI, R18 plain words
// on screen, R19 hand-made portraits. Each reads what a person would see in the rendered page.

for (const name of ["localStorage", "sessionStorage"]) {
  const mem = new Map<string, string>();
  Object.defineProperty(globalThis, name, { configurable: true, value: { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => void mem.set(k, v), removeItem: (k: string) => void mem.delete(k), clear: () => mem.clear() } });
}
window.scrollTo = (() => {}) as typeof window.scrollTo;

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const visible = (el: Element) => !el.closest("[hidden]") && !el.closest("details:not([open]) > :not(summary)");
/** Every place a person can type: text boxes, text areas, selects, editable regions. Buttons, checkboxes and hidden inputs are not. */
const TYPING = "textarea, select, [contenteditable='true'], input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=button]):not([type=submit]):not([type=range])";
const typingPlaces = (root: ParentNode) => Array.from(root.querySelectorAll(TYPING)).filter(visible);
const describe_ = (els: Element[]) => els.map((e) => `${e.tagName.toLowerCase()}#${e.id || "?"}.${(e.className || "").toString()}`);

async function atIntake() {
  mockSpeed.factor = 0;
  m = await render(<App api={mockApi} mock />);
  await click(byText(m.el, ".quick button", "Use an example"));
  await flush();
  await click(byText(m.el, ".quick button", "About $1.4 million"));
  await flush();
  return m;
}

describe("R3. One place to type per page", () => {
  it("GAP R3: the first page has one place to type, and still one when a figure's editor is open", async () => {
    await atIntake();
    expect(describe_(typingPlaces(m!.el))).toHaveLength(1);
    const pen = m!.el.querySelector(".side button.pen, .side button[aria-label^='Change']") as HTMLElement | null;
    expect(pen, "no pen button on the panel").toBeTruthy();
    await click(pen);
    await flush();
    expect(m!.el.querySelector(".side .editor"), "the editor did not open").toBeTruthy();
    expect(describe_(typingPlaces(m!.el)), "an open editor adds a second place to type on the same page").toHaveLength(1);
  });

  it("the plan page has one place to type", async () => {
    await atIntake();
    await click(byText(m!.el, ".side button", "Build my plan"));
    await click(byText(m!.el, ".side button", "Looks right"));
    await until(() => m!.el.querySelector(".plan"));
    expect(describe_(typingPlaces(m!.el))).toHaveLength(1);
  }, 20000);
});

const JARGON = ["monte carlo", "percentile", "stochastic", "asset allocation", "withdrawal rate", "sequence of returns", "glide path", "tax-advantaged", "fiduciary", "drawdown", "volatility", "decumulation", "annuitiz", "basis points", "equities", "fixed income", "rebalanc", "standard deviation", "longevity risk", "liquidity", "diversif", "tool output", "the model", "llm", "tokens"];
const HYPE = ["amazing", "incredible", "revolutionary", "unlock", "supercharge", "game-changer", "world-class", "cutting-edge", "seamless", "powerful", "guaranteed", "risk-free"];
/** All the words a person can see: every text node whose parent is shown (not hidden, not inside a closed expander). */
const words = (root: Element) => {
  const out: string[] = [];
  const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const p = n.parentElement;
    if (p && visible(p) && !p.closest(".sr-only") && (n.textContent ?? "").trim()) out.push(n.textContent!.trim());
  }
  return out.join(" ");
};
const found = (text: string, list: string[]) => list.filter((w) => new RegExp(`(^|[^a-z])${w.replace(/[-]/g, "\\-")}`, "i").test(text));

describe("R18. Plain words on screen", () => {
  it("GAP R18: the first page shows no jargon and no hype (header says per million tokens)", async () => {
    await atIntake();
    const text = words(m!.el);
    expect(found(text, [...JARGON, ...HYPE])).toEqual([]);
  });

  it("the plan page shows no jargon and no hype", async () => {
    await atIntake();
    await click(byText(m!.el, ".side button", "Build my plan"));
    await click(byText(m!.el, ".side button", "Looks right"));
    await until(() => m!.el.querySelector(".plan"));
    await flush(5);
    // the owner asked for token counts in "Token costs"; the word is allowed there and nowhere else
    const rest = m!.el.cloneNode(true) as Element;
    rest.querySelector("[data-testid=cost-block]")?.remove();
    const text = words(rest);
    expect(found(text, [...JARGON, ...HYPE])).toEqual([]);
  }, 20000);
});

describe("R17. Show only what drives a decision", () => {
  it("the plan page keeps its detail behind expanders: few visible words, and the assumptions, notes and history closed", async () => {
    await atIntake();
    await click(byText(m!.el, ".side button", "Build my plan"));
    await click(byText(m!.el, ".side button", "Looks right"));
    await until(() => m!.el.querySelector(".plan"));
    await flush(5);
    const plan = m!.el.querySelector(".plan")!;
    const shown = words(plan).split(/\s+/).filter(Boolean).length;
    expect(shown, "the visible plan runs long").toBeLessThan(450);
    const open = Array.from(plan.querySelectorAll("details[open]"));
    expect(open.map((d) => d.querySelector("summary")?.textContent), "an expander starts open").toEqual([]);
    expect(plan.querySelectorAll("details").length).toBeGreaterThanOrEqual(1);
  }, 20000);
});

const KEYS: AgentKey[] = ["adviser", "intake", "longevity", "markets", "family", "tax", "research"];

describe("R19. Human-like, hand-made portraits", () => {
  it("GAP R19: each adviser is an inked, labelled SVG person, and no two are the same drawing", async () => {
    const markup: Record<string, string> = {};
    for (const k of KEYS) {
      const mm = await render(<AgentPortrait agent={k} />);
      const svg = mm.el.querySelector("svg");
      expect(svg, `${k}: no svg`).toBeTruthy();
      expect(svg!.getAttribute("data-draws"), `${k}: no description of who is drawn`).toBeTruthy();
      expect(portraitAlt(k).length, `${k}: no description`).toBeGreaterThan(10);
      expect(svg!.querySelectorAll("path").length, `${k}: too few shapes for a person`).toBeGreaterThanOrEqual(12);
      expect(svg!.querySelectorAll("circle, rect, ellipse").length, `${k}: a perfect circle or rectangle is not hand-made`).toBe(0);
      expect(svg!.querySelector("[class*='fg-skin']"), `${k}: no skin-toned face or hands`).toBeTruthy();
      expect(svg!.querySelector("text"), `${k}: text or an emoji drawn as the portrait`).toBeNull();
      markup[k] = svg!.innerHTML;
      mm.unmount();
    }
    expect(new Set(Object.values(markup)).size).toBe(KEYS.length);
  });
});

import SavingsChart from "./components/SavingsChart";
import CostsChart from "./components/CostsChart";
import TeamPanel from "./components/TeamPanel";
import { examplePlan } from "./mock";
import { emptyTeam } from "./sse";

describe("R17. Every chart has a hover, tap and keyboard readout", () => {
  const plan = examplePlan({ age: 45, partner_age: 43, retire_age: 62 });
  // the mock plan carries no costs_by_age, so the costs chart gets its own data
  const costsData = { ages: [60, 61, 62, 63, 64, 65], total: [100000, 105000, 90000, 90000, 90000, 80000], basics: [70000, 70000, 70000, 70000, 70000, 70000], events: [{ age: 62, label: "Retire", year: 2028 }] };
  for (const [name, ui] of [["savings chart", <SavingsChart chart={plan.chart} retireAge={62} />], ["costs chart", <CostsChart costs={costsData} retireAge={62} />]] as const) {
    it(`GAP R17: the ${name} can be read from the keyboard: focusable, and an arrow key shows a value`, async () => {
      m = await render(ui);
      const svg = m.el.querySelector("svg[role='img'], svg:not([aria-hidden='true'])") as SVGElement | null;
      expect(svg, "no chart svg").toBeTruthy();
      const target = (svg!.closest("[tabindex]") ?? svg) as HTMLElement;
      expect(target.getAttribute("tabindex"), "the chart cannot take focus").not.toBeNull();
      const before = m.el.textContent;
      const { act } = await import("react");
      await act(async () => { target.focus(); target.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })); });
      expect(m.el.textContent).not.toBe(before);
      expect(m.el.querySelector("[role='status'], .tip, .readout, [aria-live]")).toBeTruthy();
    });
  }
});

describe("R17. The savings chart keys", () => {
  it("Home, End and Escape work, and a live region says the age", async () => {
    const plan = examplePlan({ age: 45, partner_age: 43, retire_age: 62 });
    m = await render(<SavingsChart chart={plan.chart} retireAge={62} />);
    const svg = m.el.querySelector("svg") as SVGElement;
    const { act } = await import("react");
    const key = (k: string) => act(async () => { svg.dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true })); });
    const live = () => m!.el.querySelector("[data-testid=savings-live]")!.textContent;
    expect(svg.getAttribute("aria-label")).toMatch(/arrow keys/);
    expect(live()).toBe("");
    await key("End");
    expect(live()).toContain(`Age ${plan.chart.ages[plan.chart.ages.length - 1]}`);
    await key("Home");
    expect(live()).toContain(`Age ${plan.chart.ages[0]}`);
    await key("ArrowRight");
    expect(live()).toContain(`Age ${plan.chart.ages[1]}`);
    await key("Escape");
    expect(live()).toBe("");
    expect(m.el.querySelector(".tip")).toBeNull();
  });
});

describe("R16. The team panel draws lines from the lead adviser to each adviser", () => {
  it("GAP R16: the team panel has a line from the lead adviser to each of the six others", async () => {
    m = await render(<TeamPanel team={emptyTeam} status="Waiting" />);
    const lines = m.el.querySelectorAll("svg.roster-lines path[data-line], svg line, svg path.connector, .connector, [data-connector]");
    expect(lines.length).toBeGreaterThanOrEqual(6);
  });
});
