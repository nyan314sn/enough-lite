import { afterEach, describe, expect, it, vi } from "vitest";
import App, { DRAFT_KEYS } from "./App";
import { mockApi, mockSpeed } from "./mock";
import { byText, click, flush, render, until, type Mounted } from "./test-utils";
import type { Api, IntakeResponse } from "./types";

// jsdom here has no web storage (opaque origin), so give the test a small one.
for (const name of ["localStorage", "sessionStorage"]) {
  const mem = new Map<string, string>();
  Object.defineProperty(globalThis, name, { configurable: true, value: { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => void mem.set(k, v), removeItem: (k: string) => void mem.delete(k), clear: () => mem.clear() } });
}

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; localStorage.clear(); sessionStorage.clear(); });

const fields = (savings: number | null): IntakeResponse["fields"] => [
  { key: "age", label: "Your age", value: 45, source: "you said", section: "Household" },
  { key: "pay_per_year", label: "Your pay", value: 380000, source: "estimate", section: "Work & pay" },
  ...(savings ? [{ key: "savings", label: "Savings", value: { pretax: savings }, source: "you said", section: "Saving" }] : []),
];
const base = { age: 45, partner_age: 43, state: "CT", retire_age: 62, pay_per_year: 380000, children: [{ age: 13, college: true }], pets: [], spending_per_year: 165000 };
const reply = (savings: number | null): IntakeResponse => ({
  profile: savings ? { ...base, savings: { pretax: savings } } : base, fields: fields(savings), missing: savings ? [] : ["savings"],
  question: { text: savings ? "That is all we need." : "About how much have you saved?", quick_answers: savings ? [] : ["About $1 million"] }, reply: "Got it.",
});

function app(...answers: IntakeResponse[]) {
  mockSpeed.factor = 0;
  const intake = vi.fn(async () => answers.shift()!);
  return { api: { ...mockApi, intake } as Api, intake };
}
const q = (sel: string) => m!.el.querySelector(sel);
async function toPlan(a: Api) {
  m = await render(<App api={a} />);
  await click(byText(m.el, ".quick button", "Use an example"));
  await click(byText(m.el, ".quick button", "About $1 million"));
  await click(byText(m.el, ".side button", "Build my plan"));
  await click(byText(m.el, ".side button", "Looks right"));
  await until(() => q(".plan"));
}

describe("Start over", () => {
  it("asks first, and Keep leaves everything as it is", async () => {
    const { api } = app(reply(null), reply(1_000_000));
    await toPlan(api);
    await click(byText(m!.el, "button", "Start over"));
    expect(q("[role=group][aria-label='Start over']")?.textContent).toMatch(/Clear everything and start again\?/);
    await click(byText(m!.el, "button", "Keep my answers"));
    expect(q(".plan")).toBeTruthy();
    expect(byText(m!.el, "button", "Start over")).toBeTruthy();
  }, 20000);

  it("asks for the check again after Start over", async () => {
    const { api } = app(reply(null), reply(1_000_000), reply(null), reply(1_000_000));
    await toPlan(api);                                                          // confirmed once
    await click(byText(m!.el, "button", "Start over"));
    await click(byText(m!.el, "button", "Yes, clear"));
    await flush();
    await click(byText(m!.el, ".quick button", "Use an example"));
    await click(byText(m!.el, ".quick button", "About $1 million"));
    await click(byText(m!.el, ".side button", "Build my plan"));
    expect(q(".side .check")).toBeTruthy();                                     // the first press after Start over checks again
  }, 20000);

  it("clears the answers, the chat, the plan, the What Ifs and any saved draft", async () => {
    const { api } = app(reply(null), reply(1_000_000));
    const resetSpy = vi.fn(async () => {});
    (api as { reset: () => Promise<void> }).reset = resetSpy;
    DRAFT_KEYS.forEach((k) => { localStorage.setItem(k, "saved"); sessionStorage.setItem(k, "saved"); });
    await toPlan(api);
    await click(byText(m!.el, "button", "Start over"));
    await click(byText(m!.el, "button", "Yes, clear"));
    await flush();
    expect(resetSpy).toHaveBeenCalledTimes(1);                                  // POST /api/reset
    expect(q(".plan-screen")).toBeNull();
    expect(q(".plan")).toBeNull();
    expect(m!.el.querySelectorAll(".bubble-you")).toHaveLength(0);
    expect(m!.el.querySelectorAll(".bubble-us")).toHaveLength(1);
    expect(q(".side [data-key]")).toBeNull();
    expect(q(".quick button")?.textContent).toMatch(/Use an example/);
    DRAFT_KEYS.forEach((k) => { expect(localStorage.getItem(k)).toBeNull(); expect(sessionStorage.getItem(k)).toBeNull(); });
  }, 20000);
});

describe("Reset one section", () => {
  it("clears that section, tells the chat, and marks the plan out of date", async () => {
    const { api, intake } = app(reply(null), reply(1_000_000), reply(null));
    await toPlan(api);
    expect(q(".stale")).toBeNull();
    await click(byText(m!.el, ".step-link", "Change my answers"));
    expect(q(".side [data-key=savings]")).toBeTruthy();
    await click(q(".side [aria-label='Reset Saving']"));
    expect(q(".side [data-key=savings]")).toBeNull();
    expect(q(".side [data-key=age]")).toBeTruthy();                            // other sections stay
    expect(byText(m!.el, ".bubble-us", "Cleared your saving. About how much have you saved?")).toBeTruthy();
    expect(intake).toHaveBeenLastCalledWith("", expect.not.objectContaining({ savings: expect.anything() }), ["Saving"]);   // the server is told, and the section is gone from what we send
    expect(byText(m!.el, ".side .build-why", "savings")).toBeTruthy();
    expect(q(".side .build button")?.getAttribute("aria-disabled")).toBe("true");   // a core answer is missing: no plan yet

    await click(byText(m!.el, ".step-link", "Your plan"));
    expect(q(".plan")).toBeTruthy();                                            // the old plan stays, but not silently
    expect(q(".stale")?.textContent).toMatch(/Your answers changed/);
    expect(byText(m!.el, ".stale button", "Finish your answers")).toBeTruthy();
  }, 20000);
});

describe("An out-of-date plan", () => {
  it("offers Rebuild plan once the answers are complete again, and clears the prompt after the rebuild", async () => {
    const { api } = app(reply(null), reply(1_000_000), reply(null), reply(1_200_000));
    await toPlan(api);
    await click(byText(m!.el, ".step-link", "Change my answers"));
    await click(q(".side [aria-label='Reset Saving']"));
    await click(byText(m!.el, ".quick button", "About $1 million"));          // the reply gives savings again, a new figure
    await click(byText(m!.el, ".step-link", "Your plan"));
    expect(q(".stale")?.textContent).toMatch(/Your answers changed/);
    await click(byText(m!.el, ".stale button", "Rebuild plan"));
    await until(() => q(".plan") && !q(".placeholder"));
    expect(q(".stale")).toBeNull();
  }, 20000);

  it("is not shown when nothing changed", async () => {
    const { api } = app(reply(null), reply(1_000_000));
    await toPlan(api);
    await click(byText(m!.el, ".step-link", "Change my answers"));
    await click(byText(m!.el, ".step-link", "Your plan"));
    expect(q(".stale")).toBeNull();
  }, 20000);
});

describe("Start over and the welcome message", () => {
  it("leaves only the welcome message, even after Change my answers", async () => {
    const { api } = app(reply(null), reply(1_000_000));
    await toPlan(api);
    await click(byText(m!.el, "button", "Change my answers"));
    expect(q(".log")?.textContent).toContain("Your plan is kept");
    await click(byText(m!.el, "button", "Start over"));
    await click(byText(m!.el, "button", "Yes, clear"));
    await flush();
    expect(m!.el.querySelectorAll(".log .bubble").length).toBe(1);
    expect(q(".log")?.textContent).not.toContain("Your plan is kept");
  }, 20000);
});
