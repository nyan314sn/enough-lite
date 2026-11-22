import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import App from "./App";
import IntakeScreen from "./components/IntakeScreen";
import LivePanel from "./components/LivePanel";
import { chartSummary } from "./components/SavingsChart";
import { TeamTalk } from "./components/TeamPanel";
import PlanCard from "./components/PlanCard";
import { scrollBehavior } from "./format";
import { examplePlan, mockApi, mockSpeed } from "./mock";
import { byText, click, flush, render, until, type Mounted } from "./test-utils";
import type { Api, Field, IntakeResponse, Profile } from "./types";

for (const name of ["localStorage", "sessionStorage"]) {
  const mem = new Map<string, string>();
  Object.defineProperty(globalThis, name, { configurable: true, value: { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => void mem.set(k, v), removeItem: (k: string) => void mem.delete(k), clear: () => mem.clear() } });
}
let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; vi.unstubAllGlobals(); });

const profile: Profile = { age: 45, retire_age: 62, pay_per_year: 380000 };
const fields: Field[] = [
  { key: "age", label: "Your age", value: 45, display: "45", source: "you said", section: "Household" },
  { key: "debts", label: "Debts", value: [], display: "None given", source: "default", section: "Home & debts" },
];
const sections = [{ section: "Household", status: "added" as const }, { section: "Home & debts", status: "default" as const }];
const intakeReply: IntakeResponse = {
  profile: { age: 45, retire_age: 62, pay_per_year: 380000, spending_per_year: 165000 },
  fields: [{ key: "age", label: "Your age", value: 45, source: "you said", section: "Household" }, { key: "retire_age", label: "Retire at", value: 62, source: "you said", section: "Work & pay" }],
  missing: [], question: null, reply: "Got it.",
};

describe("Keyboard and screen reader", () => {
  it("section toggles hold no other controls, and their buttons sit beside them", async () => {
    m = await render(<LivePanel profile={profile} fields={fields} missing={[]} sections={sections} onReset={() => {}} onEdit={() => {}} onBuild={() => {}} canBuild={false} />);
    const toggles = Array.from(m.el.querySelectorAll("button.group-toggle"));
    expect(toggles).toHaveLength(2);
    for (const t of toggles) {
      expect(t.querySelector("button, a, input")).toBeNull();
      expect(t.getAttribute("aria-controls")).toBeTruthy();
    }
    expect(m.el.querySelector("summary")).toBeNull();
    expect(m.el.querySelector("[data-section='Household'] .group-h > button.reset")).toBeTruthy();
    await click(toggles[1]);
    expect(toggles[1].getAttribute("aria-expanded")).toBe("true");
    expect(document.getElementById(toggles[1].getAttribute("aria-controls")!)?.hidden).toBe(false);
  });

  it("Esc closes a figure's editor and the keyboard goes back to its pen", async () => {
    mockSpeed.factor = 0;
    const api = { ...mockApi, intake: vi.fn(async () => intakeReply) } as Api;
    m = await render(<App api={api} />);
    await click(byText(m.el, ".quick button", "Use an example"));
    await until(() => m!.el.querySelector(".side button[aria-label='Change Retire at']"));
    const pen = m.el.querySelector(".side button[aria-label='Change Retire at']") as HTMLButtonElement;
    await click(pen);
    const input = m.el.querySelector(".side .editor input") as HTMLInputElement;
    expect(input).toBeTruthy();
    input.focus();
    await act(async () => { input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); });
    expect(m.el.querySelector(".side .editor")).toBeNull();
    expect(document.activeElement).toBe(pen);
  });

  it("the phone sheet closes on Esc from anywhere and returns the keyboard to 'Your numbers'", async () => {
    const api = { ...mockApi, intake: vi.fn(async () => intakeReply) } as Api;
    m = await render(<IntakeScreen api={api} onBuild={() => {}} />);
    await click(byText(m.el, ".quick button", "Use an example"));
    await flush();
    const opener = m.el.querySelector("button.sheet-open") as HTMLButtonElement;
    expect(opener.getAttribute("aria-haspopup")).toBe("dialog");
    await click(opener);
    expect(m.el.querySelector("[role=dialog]")).toBeTruthy();
    expect(document.activeElement?.closest("[role=dialog]")).toBeTruthy();
    // Tab from the last control wraps to the first, so focus never leaves the sheet
    const dlg = m.el.querySelector("[role=dialog]") as HTMLElement;
    const items = Array.from(dlg.querySelectorAll<HTMLButtonElement>("button")).filter((b) => !b.disabled && !b.closest("[hidden]"));
    items[items.length - 1].focus();
    await act(async () => { document.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true })); });
    expect(document.activeElement).toBe(items[0]);
    (document.activeElement as HTMLElement).blur();
    await act(async () => { document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); });
    expect(m.el.querySelector("[role=dialog]")).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it("Esc inside an editor in the sheet closes only the editor, not the sheet", async () => {
    const api = { ...mockApi, intake: vi.fn(async () => intakeReply) } as Api;
    m = await render(<IntakeScreen api={api} onBuild={() => {}} />);
    await click(byText(m.el, ".quick button", "Use an example"));
    await flush();
    await click(m.el.querySelector("button.sheet-open"));
    const dlg = m.el.querySelector("[role=dialog]")!;
    await click(dlg.querySelector("button[aria-label='Change Retire at']"));
    const input = dlg.querySelector(".editor input") as HTMLInputElement;
    input.focus();
    await act(async () => { input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); });
    expect(m.el.querySelector(".editor")).toBeNull();
    expect(m.el.querySelector("[role=dialog]")).toBeTruthy();
  });

  it("Team talk is a labelled, focusable log around a real list", async () => {
    m = await render(<TeamTalk handoffs={[{ id: 1, from: "adviser", to: "tax", message: "go" }, { id: 2, from: "tax", to: "adviser", message: "done" }]} />);
    const log = m.el.querySelector("[role=log]") as HTMLElement;
    expect(log.getAttribute("aria-label")).toBe("Team talk");
    expect(log.tabIndex).toBe(0);
    const ol = log.querySelector("ol")!;
    expect(ol.hasAttribute("role")).toBe(false);
    expect(ol.querySelectorAll(":scope > li")).toHaveLength(2);
  });

  it("the chat log is a labelled, focusable log", async () => {
    m = await render(<IntakeScreen api={mockApi} onBuild={() => {}} />);
    const log = m.el.querySelector(".log") as HTMLElement;
    expect(log.getAttribute("role")).toBe("log");
    expect(log.getAttribute("aria-label")).toBe("Conversation");
    expect(log.tabIndex).toBe(0);
  });
});

describe("Charts, headings and motion", () => {
  it("the savings chart is described in words: start, retirement, peak, end and range", () => {
    const s = chartSummary("Savings by age", { ages: [45, 62, 90], median: [100000, 2000000, 500000], low: [100000, 900000, 0], high: [100000, 3000000, 1200000] } as never, 62);
    expect(s).toContain("Savings by age.");
    expect(s).toContain("$100,000 at age 45");
    expect(s).toContain("$2,000,000 at retirement, age 62");
    expect(s).toContain("highest $2,000,000 at age 62");
    expect(s).toContain("Range at age 90: $0 to $1,200,000");
  });

  it("a What If keeps the heading order h2 then h3, and its household picture is not read twice", async () => {
    const base = examplePlan(profile);
    m = await render(<PlanCard plan={base} retireAge={60} scenario={{ name: "Retire at 60", baseline: base, change: "Retire at 60 instead of 62." }} />);
    expect(m.el.querySelector("h4")).toBeNull();
    expect(m.el.querySelector("h2")).toBeTruthy();
    expect(m.el.querySelectorAll("h3").length).toBeGreaterThan(0);
    const live = await render(<LivePanel profile={{ ...profile, partner_age: 43 }} fields={fields} missing={[]} onEdit={() => {}} onBuild={() => {}} canBuild={false} />);
    expect(live.el.querySelector("svg.household-svg")?.getAttribute("aria-hidden")).toBe("true");
    expect(live.el.querySelector(".household-caption")?.textContent).toMatch(/You \(45\)/);
    live.unmount();
  });

  it("scrolls smoothly, but not when the system asks for reduced motion", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} }));
    expect(scrollBehavior()).toBe("smooth");
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: /reduce/.test(q), media: q, addEventListener() {}, removeEventListener() {} }));
    expect(scrollBehavior()).toBe("auto");
  });
});
