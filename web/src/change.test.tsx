import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import AskBox, { updateNote } from "./components/AskBox";
import TeamScreen from "./components/TeamScreen";
import { examplePlan, mockApi, mockSpeed } from "./mock";
import { byText, click, flush, render, until, type Mounted } from "./test-utils";
import type { Api, AskResponse, Profile } from "./types";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const profile: Profile = { age: 45, retire_age: 62, pay_per_year: 380000 };
const fixedProfile: Profile = { ...profile, pay_per_year: 210000 };
const base = examplePlan(profile);
const fixedPlan = { ...examplePlan(fixedProfile), wants: { per_year: 98765, line: "Rebuilt." } };

const reply = (...rs: Partial<AskResponse>[]) => vi.fn(async () => ({ kind: "answer", text: "", citations: [], ...rs.shift() }) as AskResponse);
async function say(text: string) {
  const input = m!.el.querySelector("#ask-input") as HTMLInputElement;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, text);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => { (m!.el.querySelector(".ask form") as HTMLFormElement).requestSubmit(); });
  await flush();
}

describe("Corrections in the plan chat", () => {
  it("names what changed", () => {
    expect(updateNote(profile, fixedProfile)).toBe("Your pay is now $210,000 a year.");
  });

  it("a proposal comes with confirm chips; the chip is sent as the next question", async () => {
    const pending = { facts: { pay_per_year: 210000 } };
    const ask = reply({ kind: "change", status: "confirm", text: "Set your pay to $210,000 and rebuild?", quick_answers: ["Yes, rebuild", "No"], pending_change: pending }, { kind: "change", status: "applied", text: "Your plan was updated: your pay to $210,000 a year.", profile: fixedProfile, plan: fixedPlan });
    const onChange = vi.fn();
    m = await render(<AskBox api={{ ...mockApi, ask } as Api} profile={profile} plan={base} onCost={() => {}} onChange={onChange} />);
    await say("my pay is wrong, it is 210k");
    expect(m.el.querySelector(".turn-chips")?.textContent).toBe("Yes, rebuildNo");
    expect(onChange).not.toHaveBeenCalled();
    await click(byText(m.el, ".turn-chips button", "Yes, rebuild"));
    await flush();
    expect(ask).toHaveBeenNthCalledWith(1, "my pay is wrong, it is 210k", profile, base, null);
    expect(ask).toHaveBeenLastCalledWith("Yes, rebuild", profile, base, pending);   // the pending change travels back
    expect(onChange).toHaveBeenCalledWith(fixedProfile, fixedPlan);
    expect(m.el.querySelector(".updated-note")?.textContent).toBe("Your pay is now $210,000 a year.");
    expect(m.el.querySelectorAll(".turn-a")).toHaveLength(1);   // the confirmation question only; the update note replaces the second answer
    expect(m.el.querySelector(".turn-chips")).toBeNull();
  });

  it("a clarify reply shows its chips, and a whatif does not replace the baseline", async () => {
    const ask = reply({ kind: "clarify", text: "I am not sure what you mean.", quick_answers: ["Change an answer", "Try a What If", "Explain my plan"] },
      { kind: "whatif", text: "Retiring later helps.", plan: fixedPlan, profile: fixedProfile });
    const onChange = vi.fn();
    m = await render(<AskBox api={{ ...mockApi, ask } as Api} profile={profile} plan={base} onCost={() => {}} onChange={onChange} />);
    await say("this is wrong");
    expect(m.el.querySelector(".turn-a")?.textContent).toBe("I am not sure what you mean.");
    expect(m.el.querySelector(".turn-chips")?.textContent).toBe("Change an answerTry a What IfExplain my plan");
    await say("retire at 64");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("offers ideas as What If chips, built from the person's own numbers", async () => {
    const ask = reply({ kind: "whatif", text: "ok", plan: fixedPlan });
    m = await render(<AskBox api={{ ...mockApi, ask } as Api} profile={{ ...profile, save_rate: 0.1 }} plan={base} onCost={() => {}} />);
    expect(Array.from(m.el.querySelectorAll(".ideas button")).map((b) => b.textContent)).toEqual(["Retire 2 years later", "Save 5% more of pay"]);
    await click(byText(m.el, ".ideas button", "Save 5% more of pay"));
    expect(ask).toHaveBeenCalledWith("Save 15% of my pay", { ...profile, save_rate: 0.1 }, base, null);
  });

  it("follow-up chips show on any answer", async () => {
    const ask = reply({ text: "Which account?", quick_answers: ["401(k)", "IRA"] });
    m = await render(<AskBox api={{ ...mockApi, ask } as Api} profile={profile} plan={base} onCost={() => {}} />);
    await say("limits?");
    expect(Array.from(m.el.querySelectorAll(".turn-chips button")).map((b) => b.textContent)).toEqual(["401(k)", "IRA"]);
  });

  it("a confirmed change replaces the baseline plan, outside the What If history", async () => {
    mockSpeed.factor = 0;
    const ask = reply({ kind: "change", text: "Done.", profile: fixedProfile, plan: fixedPlan });
    const onProfileChange = vi.fn();
    m = await render(<TeamScreen api={{ ...mockApi, ask } as Api} profile={profile} model="m" onBack={() => {}} onProfileChange={onProfileChange} />);
    await until(() => m!.el.querySelector(".plan"));
    await say("my pay is 210k");
    expect(onProfileChange).toHaveBeenCalledWith(fixedProfile);
    expect(m.el.textContent).toContain("98,765");
    expect(m.el.querySelector(".history")).toBeNull();
    expect(m.el.querySelector(".updated-note")).toBeTruthy();
  }, 20000);
});

describe("A typed yes to an offered What If", () => {
  it("names the new tab from the pending change, not from 'yes'", async () => {
    const pending = { whatif: "What if I retire at 65" };
    const ask = reply({ kind: "clarify", status: "confirm", text: "I read that as: retire at 65. Shall I run this What If?", quick_answers: ["What if I retire at 65", "No"], pending_change: pending },
      { kind: "whatif", text: "Retiring at 65 helps.", plan: fixedPlan });
    const onWhatIf = vi.fn(() => 1);
    m = await render(<AskBox api={{ ...mockApi, ask } as Api} profile={profile} plan={base} onCost={() => {}} onWhatIf={onWhatIf} />);
    await say("what about working a bit longer");
    await say("yes");
    expect(ask).toHaveBeenLastCalledWith("yes", profile, base, pending);
    expect(onWhatIf).toHaveBeenCalledWith(expect.objectContaining({ name: "Retire at 65", q: "What if I retire at 65", retireAfter: 65 }));
  });
});
