import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import IntakeScreen from "./components/IntakeScreen";
import LivePanel from "./components/LivePanel";
import { EXAMPLE_TEXT } from "./examples";
import { mockApi, mockSpeed } from "./mock";
import { byText, click, flush, render, type Mounted } from "./test-utils";
import type { Api, IntakeResponse } from "./types";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const first: IntakeResponse = {
  profile: { age: 45, partner_age: 43, state: "CT", retire_age: 62, pay_per_year: 380000, partner_pay_per_year: 0, children: [{ age: 13, college: true }, { age: 10, college: true }, { age: 6, college: true }], pets: [{ kind: "dog", count: 2 }], spending_per_year: 165000 },
  fields: [
    { key: "age", label: "Your age", value: 45, source: "you said" },
    { key: "pay_per_year", label: "Your pay", value: 380000, source: "estimate", note: "Typical pay for a doctor in Connecticut" },
    { key: "spending_per_year", label: "Spending", value: 165000, source: "estimate" },
  ],
  missing: ["savings"],
  question: { text: "About how much have you saved?", quick_answers: ["About $1 million", "Not sure"] },
  reply: "Got it.",
};
const second: IntakeResponse = { ...first, profile: { ...first.profile, savings: { pretax: 1_000_000 } }, fields: [...first.fields, { key: "savings", label: "Savings", value: { pretax: 1_000_000 }, source: "you said" }], missing: [], question: { text: "That is all we need.", quick_answers: [] } };

function fakeApi(...answers: IntakeResponse[]) {
  const intake = vi.fn(async () => answers.shift()!);
  return { api: { ...mockApi, intake } as Api, intake };
}

describe("quick answers", () => {
  it("the opening example and each quick answer from /api/intake send their text", async () => {
    const { api, intake } = fakeApi(first, second);
    m = await render(<IntakeScreen api={api} onBuild={() => {}} />);
    await click(byText(m.el, ".quick button", "Use an example"));
    await flush();
    expect(intake).toHaveBeenNthCalledWith(1, EXAMPLE_TEXT, null);
    const chips = Array.from(m.el.querySelectorAll(".quick button")).map((b) => b.textContent);
    expect(chips).toEqual(["About $1 million", "Not sure"]);
    await click(byText(m.el, ".quick button", "About $1 million"));
    await flush();
    expect(intake).toHaveBeenNthCalledWith(2, "About $1 million", first.profile);
    expect(byText(m.el, ".bubble-you", "About $1 million")).toBeTruthy();
    expect(byText(m.el, ".bubble-us", "That is all we need.")).toBeTruthy();
  });

  it("shows an error with Try again when the server fails, and keeps the chat", async () => {
    const intake = vi.fn().mockRejectedValueOnce(new Error("We could not reach the server.")).mockResolvedValueOnce(first);
    m = await render(<IntakeScreen api={{ ...mockApi, intake } as Api} onBuild={() => {}} />);
    await click(byText(m.el, ".quick button", "Use an example"));
    await flush();
    expect(m.el.querySelector("[role=alert]")?.textContent).toMatch(/could not reach/);
    await click(byText(m.el, "[role=alert] button", "Try again"));
    await flush();
    expect(intake).toHaveBeenCalledTimes(2);
    expect(m.el.querySelector("[role=alert]")).toBeNull();
    expect(m.el.querySelectorAll(".bubble-you")).toHaveLength(1);
  });
});

describe("live panel", () => {
  it("updates as answers arrive: household, money, sources, still needed, then Build my plan", async () => {
    const { api } = fakeApi(first, second);
    const onBuild = vi.fn();
    m = await render(<IntakeScreen api={api} onBuild={onBuild} />);
    const panel = () => m!.el.querySelector(".side [data-testid=live-panel]")!;
    expect(panel().textContent).toMatch(/appears here as you answer/);
    await click(byText(m.el, ".quick button", "Use an example"));
    await flush();
    expect(panel().querySelector(".household-caption")?.textContent).toBe("You (45), your partner (43), 3 children (13, 10, 6) and 2 dogs");
    expect(panel().querySelectorAll("[data-pet=dog]")).toHaveLength(2);
    const pay = panel().querySelector("[data-key=pay_per_year]")!;
    expect(pay.textContent).toMatch(/\$380,000 a year/);
    expect(pay.querySelector(".tag")?.textContent).toBe("estimate");
    expect(panel().querySelector("[data-key=age] .tag")?.textContent).toBe("you said");
    expect(panel().textContent).toMatch(/Left before tax\$215,000/);
    expect(panel().textContent).toMatch(/Still needed: your savings/);
    const btn = () => byText(m!.el, ".side button", "Build my plan")!;
    expect(btn().getAttribute("aria-disabled")).toBe("true");                 // always there, off until ready
    expect(panel().querySelector(".build-why")?.textContent).toBe("Still needed: your savings.");
    expect(m.el.querySelectorAll("button").length && Array.from(m.el.querySelectorAll("button")).filter((b) => b.textContent === "Build my plan")).toHaveLength(1);
    expect(panel().querySelector(".household-caption")!.compareDocumentPosition(btn()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();   // under the family picture
    await click(btn());
    expect(onBuild).not.toHaveBeenCalled();                                   // a click while off does nothing

    await click(byText(m.el, ".quick button", "About $1 million"));
    await flush();
    expect(panel().querySelector("[data-key=savings]")?.textContent).toMatch(/\$1,000,000/);
    expect(btn().getAttribute("aria-disabled")).toBe("false");
    expect(btn().className).toMatch(/btn-primary/);
    expect(panel().querySelector(".build-why")?.textContent).toBe("Check the figures, then build.");
    expect(panel().querySelector("[role=status][aria-live=polite]")?.textContent).toBe("Ready: you can build your plan.");
    await click(btn());
    expect(onBuild).not.toHaveBeenCalled();                                   // the first press opens the check, it does not build
    const chk = () => panel().querySelector(".check");
    expect(chk()?.querySelector(".check-h")?.textContent).toBe("Before I build, check your figures below. The ones marked estimate are my guesses; change any that are wrong.");
    expect(chk()?.textContent).not.toMatch(/\$|\d/);                          // the note holds no figures
    expect(document.activeElement).toBe(chk()!.querySelector(".check-h"));
    const marked = Array.from(panel().querySelectorAll(".field.is-check"));
    expect(marked.length).toBeGreaterThan(0);                                 // guessed rows are highlighted in the answers panel
    expect(marked.every((li) => /estimate|assumed|typical/.test(li.querySelector(".tag")?.textContent ?? ""))).toBe(true);
    expect(panel().querySelectorAll(".field:not(.is-check) .tag-estimate, .field:not(.is-check) .tag-assumed, .field:not(.is-check) .tag-default")).toHaveLength(0);
    expect(marked.some((li) => li.closest("[hidden]"))).toBe(false);          // groups holding one are open
    await click(byText(m.el, ".side button", "Looks right"));
    expect(onBuild).toHaveBeenCalledWith(second.profile);
    expect(onBuild).toHaveBeenCalledTimes(1);
    await click(btn());                                                       // confirmed once: the next press builds at once
    expect(onBuild).toHaveBeenCalledTimes(2);
    expect(chk()).toBeNull();
    expect(panel().querySelector(".is-check")).toBeNull();                    // no highlight after the build
  });

  it("Escape closes the check and 'Let me change something' closes it without building", async () => {
    const { api } = fakeApi(first, second);
    const onBuild = vi.fn();
    m = await render(<IntakeScreen api={api} onBuild={onBuild} />);
    await click(byText(m.el, ".quick button", "Use an example")); await flush();
    await click(byText(m.el, ".quick button", "About $1 million")); await flush();
    const btn = () => byText(m!.el, ".side button", "Build my plan")!;
    await click(btn());
    expect(m.el.querySelector(".check")).toBeTruthy();
    await act(async () => { m!.el.querySelector(".check .check-h")!.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); });
    expect(m.el.querySelector(".check")).toBeNull();
    expect(m.el.querySelector(".is-check")).toBeNull();                         // Escape removes the highlight
    await click(btn());
    expect(m.el.querySelector(".side .is-check")).toBeTruthy();
    await click(byText(m.el, ".check button", "Let me change something"));
    expect(m.el.querySelector(".check")).toBeNull();
    expect(m.el.querySelector(".side .is-check")).toBeTruthy();                 // the highlight stays until the row is edited
    expect(document.activeElement).toBe(m.el.querySelector(".side .is-check .pen"));
    expect(onBuild).not.toHaveBeenCalled();
  });

  it("✎ puts “Change X to:” into the chat box when the figure has no editor", async () => {
    const { api } = fakeApi({ ...first, fields: [...first.fields, { key: "state", label: "State", value: "CT", source: "you said" }] });
    m = await render(<IntakeScreen api={api} onBuild={() => {}} />);
    await click(byText(m.el, ".quick button", "Use an example"));
    await flush();
    await click(m.el.querySelector(".side [aria-label='Change State']"));
    await act(async () => { await new Promise((r) => requestAnimationFrame(() => r(null))); });
    const box = m.el.querySelector("#chat-input") as HTMLTextAreaElement;
    expect(box.value).toBe("Change State to: ");
    expect(document.activeElement).toBe(box);
  });

  it("draws pets as dogs and cats and a child at each age", async () => {
    m = await render(<LivePanel profile={{ age: 38, children: [{ age: 2, college: false }], pets: [{ kind: "cat", count: 1 }, { kind: "dog", count: 1 }] }}
      fields={[{ key: "age", label: "Your age", value: 38, source: "you said" }]} missing={[]} onEdit={() => {}} onBuild={() => {}} canBuild={false} />);
    expect(m.el.querySelectorAll("[data-pet=cat]")).toHaveLength(1);
    expect(m.el.querySelectorAll("[data-pet=dog]")).toHaveLength(1);
    expect(m.el.querySelector(".household-caption")?.textContent).toBe("You (38), 1 child (2), 1 cat and 1 dog");
  });

  it("works end to end with the mock server (doctor example)", async () => {
    mockSpeed.factor = 0;
    m = await render(<IntakeScreen api={mockApi} onBuild={() => {}} />);
    await click(byText(m.el, ".quick button", "Use an example"));
    await flush();
    await click(byText(m.el, ".quick button", "About $1.4 million"));
    await flush();
    expect(byText(m.el, ".side button", "Build my plan")).toBeTruthy();
    expect(m.el.querySelector(".side [data-key=state]")?.textContent).toMatch(/Connecticut/);
  });
});
