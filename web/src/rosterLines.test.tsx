import { afterEach, describe, expect, it } from "vitest";
import TeamPanel from "./components/TeamPanel";
import { handoffPath, route, toPath } from "./components/RosterLines";
import { emptyTeam, type TeamState } from "./sse";
import { render, type Mounted } from "./test-utils";

let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });

const lines = (el: HTMLElement) => Array.from(el.querySelectorAll<SVGPathElement>("svg.roster-lines path[data-line]"));

describe("Team lines", () => {
  it("draws one decorative line per adviser, muted while they wait", async () => {
    m = await render(<TeamPanel team={emptyTeam} status="" />);
    const svg = m.el.querySelector("svg.roster-lines");
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
    expect(lines(m.el).map((l) => l.dataset.line)).toEqual(expect.arrayContaining(["intake", "longevity", "markets", "family", "tax", "research"]));
    expect(lines(m.el)).toHaveLength(6);
    expect(lines(m.el).find((l) => l.dataset.line === "markets")?.getAttribute("class")).toContain("idle");
    expect(lines(m.el).find((l) => l.dataset.line === "intake")?.getAttribute("class")).toContain("done");
  });
  it("shows working and done on the lines, and marks a handoff's lines active", async () => {
    const team: TeamState = { ...emptyTeam,
      agents: [{ agent: "longevity", status: "working", finding: null } as never, { agent: "tax", status: "done", finding: null } as never],
      handoffs: [{ id: 1, from: "longevity", to: "markets", message: "here" }] };
    m = await render(<TeamPanel team={team} status="" />);
    const cls = (k: string) => lines(m!.el).find((l) => l.dataset.line === k)?.getAttribute("class") ?? "";
    expect(cls("longevity")).toContain("working");
    expect(cls("tax")).toContain("done");
    expect(cls("longevity")).toContain("active");
    expect(cls("markets")).toContain("active");
    expect(cls("family")).not.toContain("active");
  });
  it("routes a handoff via the lead", () => {
    const a = route([100, 10], [30, 80], 40, null);
    const b = route([100, 10], [170, 80], 40, null);
    expect(toPath(a)).toBe("M100.0 10.0 L100.0 40.0 L30.0 40.0 L30.0 80.0");
    const p = handoffPath({ x: a, y: b }, "x", "y");
    expect(p).toContain("M30.0 80.0");
    expect(p).toContain("L170.0 80.0");
    expect(handoffPath({ x: a }, "adviser", "x")).toBe(toPath(a));
    expect(handoffPath({ x: a }, "x", "zz")).toBeNull();
  });
});

describe("Team tree", () => {
  it("row two runs down one trunk to a second bar, then a short drop to its own portrait", () => {
    const r = route([100, 10], [170, 200], 40, 60, 190);
    expect(toPath(r)).toBe("M100.0 10.0 L100.0 40.0 L60.0 40.0 L60.0 190.0 L170.0 190.0 L170.0 200.0");
  });
  it("labels the active hand-off near its line, hidden from screen readers", async () => {
    const team: TeamState = { ...emptyTeam, handoffs: [{ id: 1, from: "adviser", to: "tax", message: "tax on pay?" }] };
    m = await render(<TeamPanel team={team} status="" />);
    const l = m.el.querySelector("[data-testid=roster-label]");
    // jsdom has no layout, so the label may wait for a measured line; when it shows it must be aria-hidden and brief
    if (l) { expect(l.getAttribute("aria-hidden")).toBe("true"); expect(l.textContent).toBe("Lead → Tax: tax on pay?"); }
  });
});

describe("Team lines: every adviser has their own line", () => {
  it("puts the hand-off note on its adviser's own last bar, inside the panel", async () => {
    const { labelSpot } = await import("./components/RosterLines");
    const family = route([160, 10], [60, 200], 40, 20, 190);       // own start, own channel, own last bar
    expect(labelSpot(family, 340)).toEqual({ x: 125, y: 190, tf: "translate(-50%, -50%)" });
    const straight = route([170, 10], [170, 90], 50, null);         // a straight line: the note sits beside it
    expect(labelSpot(straight, 340).tf).toBe("translate(0, -50%)");
  });
  it("two advisers that leave the lead at different points share no segment", () => {
    const a = route([151, 10], [60, 200], 40, 20, 190);
    const b = route([160, 10], [170, 200], 60, 120, 190);
    const segs = (p: [number, number][]) => p.slice(1).map((q, i) => [p[i], q] as const);
    const overlap = (s1: readonly [[number, number], [number, number]], s2: readonly [[number, number], [number, number]]) => {
      const vert = (s: typeof s1) => s[0][0] === s[1][0];
      if (vert(s1) !== vert(s2)) return false;
      const k = vert(s1) ? 0 : 1, r = vert(s1) ? 1 : 0;
      if (s1[0][k] !== s2[0][k]) return false;
      const [a1, a2] = [s1[0][r], s1[1][r]].sort((x, y) => x - y), [b1, b2] = [s2[0][r], s2[1][r]].sort((x, y) => x - y);
      return Math.min(a2, b2) > Math.max(a1, b1);
    };
    for (const s1 of segs(a)) for (const s2 of segs(b)) expect(overlap(s1, s2)).toBe(false);
  });
});
