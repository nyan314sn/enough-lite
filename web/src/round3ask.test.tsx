import { afterEach, describe, expect, it, vi } from "vitest";
import AskBox from "./components/AskBox";
import { examplePlan, mockApi } from "./mock";
import { click, flush, render, type Mounted } from "./test-utils";
import type { Api } from "./types";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

describe("Round 3: a Worth trying chip", () => {
  it("shows its own text as You asked, and adds no second chip for the same What If", async () => {
    const base = examplePlan({ age: 45, retire_age: 62 });
    const plan = { ...base, levers: [{ key: "goal", title: "Make your basics safe first", why: "x", whatif_text: "What if I retire at 70" }] };
    const ask = vi.fn(async () => ({ kind: "answer" as const, text: "ok", citations: [] }));
    const api = { ...mockApi, ask } as Api;
    m = await render(<AskBox api={api} profile={{ age: 45, retire_age: 62 }} plan={plan} onCost={() => {}} />);
    const chips = () => Array.from(m!.el.querySelectorAll(".chip")).map((c) => c.textContent);
    expect(chips().filter((c) => /retire at 70/i.test(c ?? ""))).toHaveLength(0);
    const b = Array.from(m.el.querySelectorAll(".chip")).find((c) => c.textContent === "Make your basics safe first") as HTMLButtonElement;
    await click(b); await flush();
    expect((ask.mock.calls[0] as unknown[])[0]).toBe("What if I retire at 70");
    expect(m.el.querySelector(".turn-q")?.textContent).toContain("Make your basics safe first");
    expect(m.el.querySelector(".turn-q")?.textContent).not.toContain("retire at 70");
  });
});
