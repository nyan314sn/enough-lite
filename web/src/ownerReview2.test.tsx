import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import PlanCard from "./components/PlanCard";
import TeamScreen from "./components/TeamScreen";
import IntakeScreen from "./components/IntakeScreen";
import { ideas } from "./components/AskBox";
import { movesOf } from "./readiness";
import { fkGrade } from "./readability";
import { mockApi } from "./mock";
import { byText, click, render, until, type Mounted } from "./test-utils";
import raw from "./testdata/plans.json";
import type { Api, Plan } from "./types";

// Owner review 2: no Try it in the plan view, What If only in its own section, the plan greys out while one is written, and a Build hint on page 1.

const P = raw as unknown as Record<"e11" | "e24" | "e27" | "s011", Plan>;
let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });
const q = (s: string) => m!.el.querySelector(s);

async function team() {
  const plan = vi.fn(async (_p: unknown, on: (e: never) => void) => { on({ type: "plan", plan: P.e24 } as never); on({ type: "done" } as never); });
  m = await render(<TeamScreen api={{ ...mockApi, plan } as unknown as Api} profile={{ age: 49, retire_age: 65 }} model="x" onBack={() => {}} />);
  await until(() => q(".plan"));
}

describe("The plan view has no Try it", () => {
  it("no Try it or Try this button anywhere, and no Mark as planned", async () => {
    for (const id of ["e11", "e24", "e27", "s011"] as const) {
      m = await render(<PlanCard plan={P[id]} retireAge={65} />);
      m.el.querySelectorAll("details").forEach((d) => { d.open = true; });
      expect(Array.from(m.el.querySelectorAll("button")).filter((b) => /^Try\b|Try it|Try this/i.test(b.textContent ?? "")), id).toEqual([]);
      expect(m.el.textContent, id).not.toMatch(/Mark as planned|moves planned|All your moves/);
      m.unmount();
    }
    m = null;
  });
  it("the plan's moves are among the What If chips, by their titles", () => {
    const labels = ideas({ age: 49, retire_age: 66 }, P.e11).map((x) => x.label);
    const withQ = movesOf(P.e11).filter((x) => x.tryQ || x.points.some((p) => p.whatif_text));
    expect(withQ.length).toBeGreaterThan(0);
    for (const mv of withQ) expect(labels).toContain(mv.title);
  });
});

describe("The What If section", () => {
  it("has its heading, one line, the chips and the box", async () => {
    await team();
    const s = q("[data-testid=whatif-section]")!;
    expect(s.querySelector("h2")?.textContent).toBe("Try a What If");
    expect(s.textContent).toContain("Change one thing and see your plan again. Your baseline stays as it is.");
    expect(s.querySelector("input#ask-input")).toBeTruthy();
    expect(s.querySelectorAll(".chip").length).toBeGreaterThan(0);
    expect(fkGrade("Change one thing and see your plan again. Your baseline stays as it is.")).toBeLessThanOrEqual(8);
  });
  it("+ What if dims the plan; Cancel and Esc bring it back", async () => {
    await team();
    const panel = () => q("#scenario-panel") as HTMLElement;
    expect(panel().className).not.toMatch(/dimmed/);
    await click(byText(m!.el, "button", "+ What if"));
    expect(panel().className).toMatch(/dimmed/);
    expect(panel().hasAttribute("inert")).toBe(true);
    expect(panel().getAttribute("aria-hidden")).toBe("true");
    expect(q("[data-testid=whatif-section]")!.className).toMatch(/composing/);
    expect(document.activeElement?.id).toBe("ask-input");
    await click(byText(m!.el, ".ask-cancel", "Cancel"));
    expect(panel().className).not.toMatch(/dimmed/);
    expect(panel().hasAttribute("inert")).toBe(false);
    expect(q(".ask-cancel")).toBeNull();
    await click(byText(m!.el, "button", "+ What if"));
    expect(panel().className).toMatch(/dimmed/);
    await act(async () => { document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); });
    expect(panel().className).not.toMatch(/dimmed/);
  });
});

describe("Page 1 greeting", () => {
  it("adds a coloured line about Build my plan, with an arrow", async () => {
    m = await render(<IntakeScreen api={mockApi} onBuild={() => {}} />);
    const first = q(".bubble-us")!;
    const hint = first.querySelector("[data-testid=build-hint]")!;
    expect(hint.textContent).toContain("press Build my plan");
    expect(hint.textContent).toContain("on the right");
    expect(hint.textContent).toContain("below");
    expect(hint.querySelector(".build-hint-arrow")).toBeTruthy();
    expect(fkGrade("When you've told me a little, press Build my plan on the right. You don't need to answer everything first.")).toBeLessThanOrEqual(8);
  });
});
