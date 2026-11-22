import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import App from "./App";
import { mockApi, mockSpeed } from "./mock";
import { byText, click, flush, render, until, type Mounted } from "./test-utils";
import type { Api, IntakeResponse } from "./types";

for (const name of ["localStorage", "sessionStorage"]) {
  const mem = new Map<string, string>();
  Object.defineProperty(globalThis, name, { configurable: true, value: { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => void mem.set(k, v), removeItem: (k: string) => void mem.delete(k), clear: () => mem.clear() } });
}

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const split = { pretax: 450000, roth: 75000, taxable: 150000, cash: 75000 };
const first: IntakeResponse = {
  profile: { age: 45, state: "CT", retire_age: 62, pay_per_year: 380000, savings: split, spending_per_year: 165000, risk: "balanced" },
  fields: [
    { key: "age", label: "Your age", value: 45, source: "you said", section: "Household" },
    { key: "pay_per_year", label: "Your pay", value: 380000, source: "estimate", section: "Work & pay" },
    { key: "savings", label: "Savings", value: split, source: "assumed", note: "You gave the total. I assumed a split.", section: "Saving" },
    { key: "risk", label: "Risk", value: "balanced", source: "assumed", section: "Goals" },
  ],
  missing: [], question: null, reply: "Got it.",
};

function setup() {
  mockSpeed.factor = 0;
  // Like the real server: the profile it is sent comes back, and what the person changed is marked "you said".
  const intake = vi.fn(async (_t: string, p: unknown) => {
    const profile = (p as Record<string, unknown>) ?? first.profile;
    const fields = first.fields.map((f) => (JSON.stringify(profile[f.key]) !== JSON.stringify(first.profile[f.key]) ? { ...f, value: profile[f.key], source: "you said", note: null } : f));
    return { ...first, profile, fields } as IntakeResponse;
  });
  const api = { ...mockApi, intake } as Api;
  return { api, intake };
}
const q = (sel: string) => m!.el.querySelector(sel);
const qa = (sel: string) => Array.from(m!.el.querySelectorAll(sel));
const pen = (label: string) => q(`.side button[aria-label='Change ${label}']`);
async function type(input: HTMLInputElement | null, v: string) {
  await act(async () => {
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    set.call(input, v);
    input!.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
async function open() {
  const { api, intake } = setup();
  m = await render(<App api={api} />);
  await click(byText(m.el, ".quick button", "Use an example"));
  await until(() => pen("Savings"));
  return { intake };
}
const amounts = () => qa(".side .editor .split-field input").map((i) => (i as HTMLInputElement).value);

describe("The savings split editor", () => {
  it("opens with the current split and a live total", async () => {
    await open();
    await click(pen("Savings"));
    expect(amounts()).toEqual(["450000", "75000", "150000", "75000"]);
    expect(q(".side .split-total")?.textContent).toContain("$750,000");
    await type(q(".side .editor input[name=cash]") as HTMLInputElement, "100k");
    expect(q(".side .split-total")?.textContent).toContain("$775,000");
  });

  it("a preset keeps the total and fills the four amounts", async () => {
    await open();
    await click(pen("Savings"));
    await click(byText(m!.el, ".side .editor button", "Even split"));
    expect(amounts()).toEqual(["187500", "187500", "187500", "187500"]);
    await click(byText(m!.el, ".side .editor button", "Mostly bank"));
    expect(amounts().map(Number).reduce((a, b) => a + b, 0)).toBe(750000);
    expect(Number(amounts()[3])).toBe(525000);
  });

  it("Save updates the figure, marks it 'you said', and tells the chat", async () => {
    const { intake } = await open();
    await click(pen("Savings"));
    await type(q(".side .editor input[name=pretax]") as HTMLInputElement, "400k");
    await type(q(".side .editor input[name=roth]") as HTMLInputElement, "100k");
    await click(byText(m!.el, ".side .editor button", "Save"));
    await flush();
    expect(q(".side .editor")).toBeNull();
    const row = q(".side .field[data-key=savings]")!;
    expect(row.textContent).toContain("you said");
    expect(row.textContent).not.toContain("Assumed: check this");
    expect(row.textContent).toContain("$400k pre-tax");
    const last = intake.mock.calls[intake.mock.calls.length - 1];
    expect(last[0]).toMatch(/^Updated your savings: \$400k pre-tax, \$100k Roth/);
    expect((last[1] as { savings: { pretax: number } }).savings.pretax).toBe(400000);
    expect(byText(m!.el, ".bubble-you", "Updated your savings")).toBeTruthy();
  });

  it("Cancel closes it and changes nothing", async () => {
    const { intake } = await open();
    const calls = intake.mock.calls.length;
    await click(pen("Savings"));
    await type(q(".side .editor input[name=pretax]") as HTMLInputElement, "1");
    await click(byText(m!.el, ".side .editor button", "Cancel"));
    expect(q(".side .editor")).toBeNull();
    expect(q(".side .field[data-key=savings]")!.textContent).toContain("$450k pre-tax");
    expect(intake.mock.calls.length).toBe(calls);
  });

  it("only one editor is open at a time", async () => {
    await open();
    await click(pen("Savings"));
    expect(qa(".side .editor").length).toBe(1);
    await click(pen("Your pay"));
    expect(qa(".side .editor").length).toBe(1);
    expect(q(".side .field[data-key=pay_per_year] .editor")).toBeTruthy();
    expect(q(".side .field[data-key=savings] .editor")).toBeNull();
  });

  it("assumed figures carry a 'check this' tag; estimates do not", async () => {
    await open();
    expect(q(".side .field[data-key=savings] .check-tag")?.textContent).toBe("Assumed: check this");
    expect(q(".side .field[data-key=pay_per_year] .check-tag")).toBeNull();
  });

  it("choice and money editors save too", async () => {
    const { intake } = await open();
    await click(pen("Risk"));
    await click(byText(m!.el, ".side .editor button", "Growth"));
    await flush();
    expect(q(".side .field[data-key=risk]")!.textContent).toContain("you said");
    await click(pen("Your pay"));
    await type(q(".side .editor input") as HTMLInputElement, "400k");
    await click(byText(m!.el, ".side .editor button", "Save"));
    await flush();
    expect(q(".side .field[data-key=pay_per_year]")!.textContent).toContain("$400,000");
    expect(intake.mock.calls[intake.mock.calls.length - 1][0]).toContain("Updated your pay");
  });
});

describe("An edit makes the plan out of date", () => {
  it("shows 'Rebuild plan' after the plan is built and an answer changes", async () => {
    await open();
    await click(byText(m!.el, ".side button", "Build my plan"));
    await click(byText(m!.el, ".side button", "Looks right"));
    await until(() => q(".plan"));
    expect(q(".stale")).toBeNull();
    await click(byText(m!.el, "button", "Change my answers"));
    await click(pen("Savings"));
    await click(byText(m!.el, ".side .editor button", "Mostly bank"));
    await click(byText(m!.el, ".side .editor button", "Save"));
    await flush();
    await click(byText(m!.el, "button", "Your plan"));
    expect(q(".stale")?.textContent).toMatch(/Your answers changed/);
    expect(byText(m!.el, ".stale button", "Rebuild plan")).toBeTruthy();
  }, 20000);
});
