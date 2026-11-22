import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import AskBox, { ASK_ERROR, suggestions } from "./components/AskBox";
import PlanCard from "./components/PlanCard";
import { actionIsNew } from "./components/WhatIf";
import TeamPanel from "./components/TeamPanel";
import { emptyTeam } from "./sse";
import { examplePlan, mockApi } from "./mock";
import { byText, click, flush, render, type Mounted } from "./test-utils";
import type { Api, AskResponse, Profile } from "./types";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const profile: Profile = { age: 45, retire_age: 62, pay_per_year: 100000 };
const plan = examplePlan(profile);
const reply = (r: Partial<AskResponse>) => vi.fn(async () => ({ kind: "answer", text: "", citations: [], ...r }) as AskResponse);
async function say(text: string) {
  const input = m!.el.querySelector("#ask-input") as HTMLInputElement;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, text);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => { (m!.el.querySelector(".ask form") as HTMLFormElement).requestSubmit(); });
  await flush();
}

describe("What If chips fit the person", () => {
  it("drops retire ages at or below the person's age, and none for a retiree", () => {
    expect(suggestions(62, 45)).toContain("Retire at 60");
    expect(suggestions(66, 61)).toContain("Retire at 68");
    expect(suggestions(66, 61)).not.toContain("Retire at 60");
    expect(suggestions(71, 71).some((s) => s.startsWith("Retire"))).toBe(false);
    expect(suggestions(65, 72).some((s) => s.startsWith("Retire"))).toBe(false);
  });
  it("offers another child only up to about 50", () => {
    expect(suggestions(62, 50)).toContain("Another child");
    expect(suggestions(67, 55)).not.toContain("Another child");
  });
  it("marks a What If already tried", async () => {
    const ask = reply({ kind: "whatif", text: "ok", plan });
    m = await render(<AskBox api={{ ...mockApi, ask } as Api} profile={profile} plan={plan} onCost={() => {}} onWhatIf={() => 1} />);
    await click(byText(m.el, ".chip", "Get a dog"));
    await flush();
    const chip = byText(m.el, ".chip", "Get a dog")!;
    expect(chip.className).toContain("tried");
    expect(chip.textContent).toMatch(/already tried/);
  });
});

describe("A failed question", () => {
  it("keeps the text, shows a plain error with Retry, never the server's words", async () => {
    const ask = vi.fn().mockRejectedValueOnce(new Error("500 Traceback: KeyError in app/ask.py")).mockResolvedValueOnce({ kind: "answer", text: "Fine.", citations: [] });
    m = await render(<AskBox api={{ ...mockApi, ask } as Api} profile={profile} plan={plan} onCost={() => {}} />);
    await say("how much can I put in an IRA");
    expect(m.el.querySelector(".alert")?.textContent).toContain(ASK_ERROR);
    expect(m.el.textContent).not.toMatch(/Traceback|KeyError/);
    expect((m.el.querySelector("#ask-input") as HTMLInputElement).value).toBe("how much can I put in an IRA");
    await click(byText(m.el, ".alert button", "Retry"));
    await flush();
    expect(ask).toHaveBeenCalledTimes(2);
    expect(m.el.querySelector(".alert")).toBeNull();
    expect(m.el.textContent).toContain("Fine.");
  });
});

describe("What Ifs are not in the chat log", () => {
  const whatif = reply({ kind: "whatif", text: "Later is safer.", plan });
  it("a What If goes to its tab: the chat keeps no reply block, no Show button and no sources for it", async () => {
    const onWhatIf = vi.fn(() => 5);
    m = await render(<AskBox api={{ ...mockApi, ask: whatif } as Api} profile={profile} plan={plan} onCost={() => {}} onWhatIf={onWhatIf} onOpen={() => {}} whatifIds={[5]} />);
    await say("Retire at 64");
    expect(onWhatIf).toHaveBeenCalledWith(expect.objectContaining({ q: "Retire at 64", name: "Retire at 64", text: "Later is safer." }));
    expect(m.el.querySelector(".turns")).toBeNull();
    expect(m.el.textContent).not.toContain("Show this What If");
    expect(m.el.textContent).not.toContain("Later is safer.");
  });
});

describe("A stale plan", () => {
  it("does not run a What If; it says the plan is out of date and offers a rebuild", async () => {
    const ask = reply({ kind: "whatif", text: "x", plan });
    const onRebuild = vi.fn();
    m = await render(<AskBox api={{ ...mockApi, ask } as Api} profile={profile} plan={plan} onCost={() => {}} stale onRebuild={onRebuild} />);
    await say("Retire at 64");
    expect(ask).not.toHaveBeenCalled();
    expect(m.el.querySelector(".stale-ask")?.textContent).toMatch(/out of date/);
    await click(byText(m.el, ".stale-ask button", "Rebuild plan"));
    expect(onRebuild).toHaveBeenCalled();
    await click(byText(m.el, ".stale-ask button", "Ask on the old plan"));
    await flush();
    expect(ask).toHaveBeenCalledTimes(1);
  });
});

describe("Change confirmation", () => {
  it("has no source links and plain update text", async () => {
    const fixed = { ...profile, pay_per_year: 150000 };
    const ask = reply({ kind: "change", status: "applied", text: "old words", profile: fixed, plan, citations: [{ title: "IRS", url: "https://irs.gov" }] });
    m = await render(<AskBox api={{ ...mockApi, ask } as Api} profile={profile} plan={plan} onCost={() => {}} onChange={() => {}} />);
    await say("my pay is 150k");
    expect(m.el.querySelector(".updated-note")?.textContent).toBe("Your pay is now $150,000 a year.");
    expect(m.el.querySelector(".cites")).toBeNull();
  });
});

describe("New tags in a What If", () => {
  it("match by lever key and ignore reworded figures", () => {
    const lev = (key: string, title: string) => ({ key, title, why: "" });
    const before = { ...plan, actions: [{ title: "Pay off the card at 24%", why: "" }], levers: [lev("debt", "Pay off the card at 24%")] };
    const after = { ...plan, actions: [{ title: "Pay off the card at 22%", why: "" }, { title: "Take the match", why: "" }], levers: [lev("debt", "Pay off the card at 22%"), lev("match", "Take the match")] };
    const isNew = actionIsNew(before, after);
    expect(isNew("Pay off the card at 22%")).toBe(false);
    expect(isNew("Take the match")).toBe(true);
  });
  it("hides an empty Family moments heading", async () => {
    m = await render(<PlanCard plan={{ ...plan, family_moments: [] }} scenario={{ name: "q", baseline: plan, change: "q" }} />);
    expect(m.el.textContent).not.toContain("Family moments");
  });
});

describe("Adviser detail", () => {
  it("shows no token counts or cost, and says something useful for Intake", async () => {
    const team = { ...emptyTeam, agents: [{ agent: "markets", status: "done" as const, tools: [], finding: { headline: "Tested.", details: [], numbers: {} }, tokens: { input: 1000, cached: 0, output: 50 }, cost_usd: 0.002 }] };
    m = await render(<TeamPanel team={team as never} status="Done." />);
    await click(m.el.querySelector("[data-agent=markets]"));
    expect(m.el.querySelector(".detail-box")?.textContent).not.toMatch(/ out |\$0\.00/);
    await click(m.el.querySelector("[data-agent=intake]"));
    expect(m.el.querySelector(".detail-box")?.textContent).toMatch(/wrote down the facts/);
  });
});
