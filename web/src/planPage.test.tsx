import { afterEach, describe, expect, it, vi } from "vitest";
import PlanCard from "./components/PlanCard";
import CompareTable from "./components/CompareTable";
import { changes } from "./components/WhatIf";
import { layers } from "./components/Ladder";
import { act } from "react";
import TeamScreen from "./components/TeamScreen";
import TeamPanel from "./components/TeamPanel";
import LivePanel, { withStateRow } from "./components/LivePanel";
import BuildBlock from "./components/BuildBlock";
import { PLAN_WORDS, badges, clampWords, ladder, movesOf, READINESS_CAP_UNSAFE, readiness, readinessShare, ringOf, shortText, verdictKind, verdictLine } from "./readiness";
import { fkGrade } from "./readability";
import { examplePlan, mockApi } from "./mock";
import { emptyTeam } from "./sse";
import { byText, click, render, until, type Mounted } from "./test-utils";
import raw from "./testdata/plans.json";
import type { Api, AskResponse, Plan } from "./types";

// Feedback round B (R26): the plan page a high-school graduate can read in a minute. Real plans from the live app
// (docs/loop/feedback_round/plan/fixtures): e11 falls short, s011 close, e27 works, e24 below the goal, e24_whatif retire a year later.

const P = raw as unknown as Record<"e11" | "s011" | "e27" | "e24" | "e09" | "e24_whatif", Plan>;
let m: Mounted | null = null;
afterEach(() => { m?.unmount(); m = null; });
const q = (s: string) => m!.el.querySelector(s);

describe("Readiness score", () => {
  it("is the share of the goal you can count on, floored, capped at 100", () => {
    // e11: $23,300 of $44,000 -> 52.9 -> 52 as a share; its basics are not safe, so the score is held at 40
    expect(readinessShare(P.e11)).toBe(52);
    expect(readiness(P.e11)).toBe(READINESS_CAP_UNSAFE);
    expect(readiness(P.s011)).toBe(Math.floor((100 * 77800) / 83000));   // 93
    expect(readiness(P.e27)).toBe(100);                                    // $122,600 against $110,000: capped
    const just = { ...P.s011, wants: { ...P.s011.wants, per_year: 82990 } };
    expect(readiness(just)).toBe(99);                                      // a $10 gap is not 100
  });
  it("is null without a goal, and the ring then shows the basics", () => {
    const mock = examplePlan({ age: 45, retire_age: 62 });
    expect(readiness(mock)).toBeNull();
    expect(ringOf(mock)).toEqual({ value: mock.needs.paid_of_100, kind: "basics" });
  });
  it("is held at 40 while the basics are not safe, so the ring and the verdict agree", () => {
    expect(verdictKind(P.e11)).toBe("basics");
    expect(readiness(P.e11)).toBe(40);
    expect(readiness(P.s011)).toBe(readinessShare(P.s011));   // basics safe: no cap
    const low = { ...P.e11, wants: { ...P.e11.wants, per_year: 8800 } };   // 20 of 100: already under the cap
    expect(readiness(low)).toBe(20);
  });
  it("never mixes in the needs: they get their own badge", () => {
    expect(badges(P.e11).find((b) => b.key === "basics")).toMatchObject({ earned: false, label: "Needs not safe yet" });
  });
});

describe("The answer at a glance", () => {
  const cases: [keyof typeof P, string, string | null][] = [
    ["e11", "Retire at 65? Not yet — first make your needs safe.", "Short $20,700 a year"],
    ["e24", "Retire at 65? Not yet — short $17,300 a year.", null],
    ["s011", "Retire at 65? Close — short $5,200 a year.", null],
    ["e27", "Retire at 65? Yes, you're on track.", null],
  ];
  for (const [id, verdict, big] of cases) {
    it(`${id}: verdict, ring, bar and the big number, all from the plan`, async () => {
      const plan = P[id];
      m = await render(<PlanCard plan={plan} retireAge={65} />);
      expect(q(".verdict")?.textContent).toBe(verdict);
      const ring = q("[data-testid=ring]")!;
      expect(ring.getAttribute("role")).toBe("img");
      expect(ring.getAttribute("data-value")).toBe(String(readiness(plan)));
      expect(ring.getAttribute("aria-label")).toMatch(new RegExp(`Readiness ${readiness(plan)} out of 100`));
      const bar = q("[data-testid=ladder-bar]")!;
      const goal = plan.analysis!.how_sure.goal_per_year;
      expect(bar.getAttribute("role")).toBe("img");
      expect(bar.getAttribute("aria-label")).toContain(`Your goal is $${goal.toLocaleString("en-US")} a year`);
      expect(bar.getAttribute("aria-label")).toContain(`$${plan.needs.basics_per_year.toLocaleString("en-US")}`);
      if (big) {
        expect(q("[data-testid=shortfall-big]")?.textContent).toBe(big);
        expect(q("[data-testid=hero-big]")).toBeNull();
      } else if (id !== "e27") {
        // the verdict says the shortfall; the banner does not say it again (R12)
        expect(q("[data-testid=shortfall-big]")).toBeNull();
        expect(q("[data-testid=shortfall]")).toBeTruthy();
      } else {
        expect(q("[data-testid=shortfall]")).toBeNull();
        expect(q("[data-testid=hero-big]")?.textContent).toContain("$122,600");
      }
      // the ladder sits in the hero, with the ring and the verdict, before the moves; the old three tiles are gone
      expect(q("[data-testid=plan-hero] [data-testid=ladder]")).toBeTruthy();
      expect(q("[data-testid=ladder]")!.compareDocumentPosition(q("[data-testid=moves]")!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(q(".nww, .tiles-sec, [data-testid=goal-bar]")).toBeNull();
    });
  }
  it("verdictKind: basics not safe comes first, then the plan's level", () => {
    expect([P.e11, P.e24, P.s011, P.e27].map(verdictKind)).toEqual(["basics", "short", "close", "works"]);
  });
  it("shortening never cuts a figure: '2.4 months' is not a sentence end", () => {
    const why = "You hold about 2.4 months of spending in cash. Three months is about $21,275, so you are about $3,975 short.";
    expect(shortText(why, 15)).toBe("You hold about 2.4 months of spending in cash.");
    expect(shortText("One two three four five six seven eight nine ten.", 4)).toBe("One two three four…");
  });
  it("a long headline shows its first sentence and a 'more' button; the whole text is one click away", async () => {
    m = await render(<PlanCard plan={P.e11} retireAge={66} />);
    const h = q("[data-testid=plan-headline]")!;
    expect(h.textContent).toBe("You can count on $23,300 a year, but your needs cost $28,700. The plan does not work yet.");
    const more = h.parentElement!.querySelector(".more-btn") as HTMLButtonElement;
    expect(more.getAttribute("aria-expanded")).toBe("false");
    await click(more);
    expect(q("[data-testid=plan-headline]")?.textContent).toBe(P.e11.headline);
  });
});

describe("Badges: earned only from the plan's own figures", () => {
  const keys = (p: Plan) => badges(p).filter((b) => b.earned).map((b) => b.key);
  it("e27 earns needs, wants, goal, match and saving; e11 earns only saving", () => {
    expect(keys(P.e27)).toEqual(["basics", "wants", "goal", "match", "saving"]);
    expect(keys(P.e11)).toEqual(["saving"]);              // the match lever is open, so no match badge
    expect(badges(P.e11).map((b) => b.key)).toEqual(["basics", "wants", "goal", "saving"]);
  });
  it("no match badge without a match, and no saving badge once retired", () => {
    const retired = { ...P.e27, already_retired: true };
    expect(keys(retired)).toEqual(["basics", "wants", "goal"]);
    const noMatch = { ...P.e27, saving: { ...P.e27.saving!, match_per_year: 0 } };
    expect(keys(noMatch)).not.toContain("match");
    const old = examplePlan({ age: 45, retire_age: 62 });   // an older plan: no goal, no saving, no levers
    expect(badges(old).map((b) => b.key)).toEqual(["basics"]);
  });
  it("shows earned and not-yet badges in words and icons, with screen-reader text", async () => {
    m = await render(<PlanCard plan={P.e11} retireAge={66} />);
    const items = Array.from(m.el.querySelectorAll("[data-testid=badges] li"));
    expect(items.map((li) => li.getAttribute("data-earned"))).toEqual(["false", "false", "false", "true"]);
    expect(items[0].textContent).toMatch(/Needs not safe yet, not yet\. Your needs are paid in 1 of 100 market tests\./);
    expect(items[1].textContent).toMatch(/Wants not sure yet/);
    expect(items[3].querySelector(".mile-icon")?.textContent).toBe("✓");
  });
});

describe("Moves: a checklist with what each is worth", () => {
  it("builds the moves from the actions, levers and the analysis", () => {
    const mv = movesOf(P.e11);
    expect(mv.map((x) => x.title)).toEqual(["Make your needs safe first", "Pay off your high-rate debt first", "Save enough to get the full employer match"]);
    expect(mv[0].points.length).toBe(3);
    expect(mv[0].worth?.text).toBe("Needs paid up to 100 of 100");
    expect(mv[0].tryQ).toBeNull();                                         // its starting points carry their own Try it
    expect(mv[2].worth?.text).toBe("+$2,500 a year · +34 in 100 for needs");
    expect(mv[2].tryQ).toBe("What if I raise my 401(k) saving to the full match");
    expect(movesOf(P.e24)[0].worth?.text).toBe("Closes the gap");
    for (const x of [...movesOf(P.e27), ...mv]) expect(x.title.split(/\s+/).length).toBeLessThanOrEqual(8);
  });

  it("the moves are a plain read-only list: no Try it, no tick, no meter, nothing kept on the device", async () => {
    m = await render(<PlanCard plan={P.e11} retireAge={66} />);
    expect(m.el.querySelectorAll("[data-move]")).toHaveLength(3);
    expect(q("[data-move=debt]")?.textContent).toContain("Pay off your high-rate debt first");
    expect(q("[data-testid=moves-meter]")).toBeNull();
    expect(q("[data-testid=moves-count]")).toBeNull();
    expect(q(".move-tick")).toBeNull();
    expect(m.el.textContent).not.toMatch(/Mark as planned|moves planned|Try it|Try this/);
    expect(Array.from(m.el.querySelectorAll("button")).some((b) => /^Try/.test(b.textContent ?? ""))).toBe(false);
  });

  it("a What If from the What If section chips opens a tab with 'vs baseline' markers", async () => {
    const plan = vi.fn(async (_p: unknown, on: (e: never) => void) => { on({ type: "plan", plan: P.e24 } as never); on({ type: "done" } as never); });
    const ask = vi.fn(async (_q: string) => ({ kind: "whatif", text: "If you retire at 66, you can count on $72,000 a year.", citations: [], plan: P.e24_whatif }) as AskResponse);
    m = await render(<TeamScreen api={{ ...mockApi, plan, ask } as unknown as Api} profile={{ age: 49, retire_age: 65 }} model="x" onBack={() => {}} />);
    await until(() => q(".plan"));
    await click(byText(m.el, ".ask .chip", "Set your spending goal nearer the safe level"));
    await until(() => m!.el.querySelectorAll("[role=tab]").length === 2);
    expect(ask.mock.calls[0][0]).toBe("What if I spend $68,000 a year");
    expect(q("#plan-h")?.textContent).toMatch(/^What if:/);
    expect(q("[data-testid=vs-ready]")?.textContent).toMatch(/▲ 5 points.*vs baseline/);
    expect(q("[data-testid=vs-gap]")?.textContent).toMatch(/▼ \$4,300 less short/);
    expect(q("[data-testid=ring] .ring-before")).toBeTruthy();                 // the baseline arc, faint, under the new one
    await click(byText(m.el, "button", "Compare"));
    expect(q("[data-testid=compare-table]")).toBeTruthy();
  });

  it("a What If that closes the gap says so", async () => {
    const closed = { ...P.e24_whatif, wants: { ...P.e24_whatif.wants, per_year: 86000 } };
    m = await render(<PlanCard plan={closed} retireAge={66} scenario={{ name: "Retire at 66", baseline: P.e24, change: "Retire at 66 instead of 65" }} />);
    expect(q("[data-testid=closes-gap]")?.textContent).toContain(PLAN_WORDS.closesGap);
    m.unmount();
    m = await render(<PlanCard plan={P.e24_whatif} retireAge={66} scenario={{ name: "Retire at 66", baseline: P.e24, change: "Retire at 66 instead of 65" }} />);
    expect(q("[data-testid=closes-gap]")).toBeNull();
  });
});

describe("Details are folded", () => {
  it("everything past the chart starts closed; the savings chart shows", async () => {
    m = await render(<PlanCard plan={P.e24} retireAge={65} />);
    for (const id of ["plan-meaning", "plan-analysis", "plan-costs", "plan-moments", "plan-assumptions"]) {
      const d = q(`[data-testid=${id}]`) as HTMLDetailsElement;
      expect(d, id).toBeTruthy();
      expect(d.tagName).toBe("DETAILS");
      expect(d.open, id).toBe(false);
    }
    expect(Array.from(m.el.querySelectorAll("details[open]"))).toEqual([]);
    const chart = q("[data-testid=savings-hit]")!;
    expect(chart.closest("details")).toBeNull();
    expect(q(".chart-title")?.textContent).toContain(PLAN_WORDS.chartTitle);
    expect(q("[data-testid=plan-costs] [data-testid=costs-chart], [data-testid=plan-costs] svg")).toBeTruthy();
  });
  it("Team talk is folded once the plan is there", async () => {
    const team = { ...emptyTeam, plan: P.e27, done: true, handoffs: [{ id: 1, from: "adviser", to: "tax", message: "go" }] };
    m = await render(<TeamPanel team={team} status="Done." />);
    const d = q("[data-testid=talk-fold]") as HTMLDetailsElement;
    expect(d.open).toBe(false);
    expect(d.querySelector("summary h3")?.textContent).toBe("Team talk");
    expect(q("[data-testid=cost-block]")).toBeTruthy();                         // token costs stay in view
  });
});

describe("Plain words (R26: reading grade 8 or lower)", () => {
  const texts = (o: unknown): string[] => (typeof o === "string" ? [o] : Object.values(o as object).flatMap(texts));
  it("the grade function behaves: plain text scores low, dense text scores high", () => {
    expect(fkGrade("You can count on this. Your needs are safe.")).toBeLessThan(4);
    expect(fkGrade("The sustainable withdrawal methodology incorporates stochastic considerations regarding intergenerational wealth.")).toBeGreaterThan(14);
  });
  it("every fixed sentence the plan page writes is grade 8 or lower", () => {
    const all = texts(PLAN_WORDS).filter((t) => t.split(/\s+/).length >= 3);
    expect(all.length).toBeGreaterThan(15);
    for (const t of all) expect(fkGrade(t), t).toBeLessThanOrEqual(8);
    expect(fkGrade(all.join(" "))).toBeLessThanOrEqual(8);
  });
  it("the hero as a person reads it is grade 8 or lower and short", async () => {
    for (const id of ["e11", "s011", "e27"] as const) {
      m = await render(<PlanCard plan={P[id]} retireAge={65} />);
      const hero = q("[data-testid=plan-hero]")!.cloneNode(true) as Element;
      hero.querySelectorAll(".sr-only, details, [data-testid=plan-headline], .more-btn, .ladder").forEach((e) => e.remove());
      const text = Array.from(hero.querySelectorAll("h3, p, li")).map((e) => e.textContent!.trim().replace(/[^.!?]$/, "$&.")).join(" ");
      expect(fkGrade(text), `${id}: ${text}`).toBeLessThanOrEqual(8);
      expect(text.split(/\s+/).length, id).toBeLessThan(80);
      m.unmount(); m = null;
    }
  });
});

// ---- The money ladder: needs, wants, wishes on one bar, in dollars a year ----
describe("The money ladder", () => {
  const dollars = (n: number) => `$${n.toLocaleString("en-US")}`;
  const num = (sel: string) => Number((q(sel)!.textContent ?? "").replace(/[^0-9]/g, ""));
  // worked out here from the plan's own figures, not from the ladder code
  const expected = (p: Plan) => {
    const needs = p.needs.basics_per_year, countOn = p.wants.per_year, goal = p.analysis!.how_sure.goal_per_year;
    return { needs, wants: Math.max(0, countOn - needs), wishes: Math.max(0, goal - Math.max(countOn, needs)), goal, countOn };
  };
  const cases: [keyof typeof P, string][] = [["e27", "works"], ["s011", "close"], ["e24", "short"], ["e11", "needs not safe"]];
  for (const [id, label] of cases) {
    it(`${id} (${label}): three amounts come from the plan and add up`, async () => {
      const plan = P[id], e = expected(plan);
      m = await render(<PlanCard plan={plan} retireAge={65} />);
      expect(num("[data-testid=ladder-needs]")).toBe(e.needs);
      expect(num("[data-testid=ladder-wants]")).toBe(e.wants);
      expect(num("[data-testid=ladder-wishes]")).toBe(e.wishes);
      expect(q("[data-testid=ladder-wants]")!.textContent).toBe(`+${dollars(e.wants)}`);
      expect(q("[data-testid=ladder-goal]")!.textContent).toBe(`Your goal: ${dollars(e.goal)} a year`);
      // they add up to the goal exactly, or to what you can count on when the goal is covered
      const sum = e.needs + e.wants + e.wishes;
      expect(sum).toBe(e.countOn >= e.goal ? e.countOn : e.goal);
      const segs = Array.from(m.el.querySelectorAll("[data-seg]")).map((s) => Number(s.getAttribute("data-amount")));
      expect(segs).toEqual([e.needs, e.wants, e.wishes]);
      expect(segs.reduce((a, b) => a + b, 0)).toBe(sum);
      // one figure, one place: the count-on figure is in the ladder unless the hero already says it big
      if (id === "e27") expect(q("[data-testid=ladder-counton]")).toBeNull(); else expect(q("[data-testid=ladder-counton]")!.textContent).toContain(dollars(e.countOn));
    });
  }

  it("says safe, sure and open in words and icons (needs safe, wants sure, wishes open)", async () => {
    m = await render(<PlanCard plan={P.s011} retireAge={65} />);
    const row = (k: string) => q(`.row-${k}`)!.textContent!;
    expect(row("needs")).toMatch(/Needs.*\$52,900.*home, food, health care.*✓ Safe · 100 of 100 tests/);
    expect(row("wants")).toMatch(/Wants.*\+\$24,900.*travel, eating out, gifts.*✓ Sure/);
    expect(row("wishes")).toMatch(/Wishes.*\+\$5,200.*○ Open · Only if markets help/);
    expect(Array.from(m.el.querySelectorAll(".lad-row")).map((r) => r.getAttribute("data-reached"))).toEqual(["true", "true", "false"]);
  });

  it("a goal that is covered says so, with no wishes left open", async () => {
    m = await render(<PlanCard plan={P.e27} retireAge={65} />);
    expect(q(".row-wishes")!.textContent).toMatch(/\+\$0.*✓ Covered/);
    expect(q(".row-wishes")!.getAttribute("data-reached")).toBe("true");
  });

  it("needs not safe: wants are $0 and it says so plainly; wishes are the rest of the goal", async () => {
    m = await render(<PlanCard plan={P.e11} retireAge={66} />);
    expect(q(".row-needs")!.textContent).toMatch(/\$28,700.*! Not safe yet · 1 of 100 tests/);
    expect(q(".row-wants")!.textContent).toMatch(/\+\$0.*○ Not sure yet · Your needs use it all/);
    expect(q(".row-wishes")!.textContent).toMatch(/\+\$15,300.*Locked.*Make your needs safe first/);   // locked until needs are safe, not "open"
    expect(q(".row-wishes")!.textContent).not.toMatch(/Only if markets help/);
    expect(q(".lad-row[data-layer=needs]")!.className).toMatch(/locked/);
  });

  it("a plan with no goal shows needs and wants only", async () => {
    m = await render(<PlanCard plan={examplePlan({ age: 45, retire_age: 62 })} retireAge={62} />);
    expect(m.el.querySelectorAll(".lad-row")).toHaveLength(2);
    expect(q("[data-testid=ladder-goal]")).toBeNull();
  });

  it("has a text alternative for the bar and one readout per row (hover, focus, tap, Escape)", async () => {
    m = await render(<PlanCard plan={P.s011} retireAge={65} />);
    const bar = q("[data-testid=ladder-bar]")!;
    expect(bar.getAttribute("aria-label")).toBe("Your goal is $83,000 a year. Needs $52,900, safe. Wants $24,900 more, sure. Wishes $5,200 more, open. Together $83,000 a year.");
    const out = () => q("[data-testid=ladder-readout]")!.textContent;
    expect(out()).toBe("");
    const btn = (k: string) => q(`.row-${k} button`) as HTMLButtonElement;
    expect(btn("needs").getAttribute("aria-pressed")).toBe("false");
    await click(btn("wants"));
    expect(out()).toBe("Wants: $24,900 a year on top of your needs. You can count on $77,800 in all.");
    expect(btn("wants").getAttribute("aria-pressed")).toBe("true");
    expect(q(".seg-wants")!.className).toMatch(/\bon\b/);
    await click(btn("wishes"));
    expect(out()).toBe("Wishes: $5,200 a year, the rest of your goal of $83,000. Only if markets help. Goal lasts in 65 of 100 tests.");
    await act(async () => { btn("wishes").dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); });
    expect(out()).toBe("");
    await act(async () => { btn("needs").focus(); });
    expect(out()).toBe("Needs: $52,900 a year. Paid in 100 of 100 market tests.");
    await act(async () => { q(".seg-wishes")!.dispatchEvent(new MouseEvent("mouseover", { bubbles: true })); });
    expect(out()).toContain("Wishes");
    expect(q("[data-testid=ladder-readout]")!.getAttribute("aria-live")).toBe("polite");
    // the rows are real buttons, so a keyboard reaches them
    expect(m.el.querySelectorAll(".lad-row button.lad-hit")).toHaveLength(3);
  });

  it("the next level to unlock names the move, with no button", async () => {
    m = await render(<PlanCard plan={P.e11} retireAge={66} />);
    const next = q("[data-testid=ladder-next]")!;
    expect(next.textContent).toContain(`Next level: ${clampWords(P.e11.starting_points![0].title, 8)}`);
    expect(next.querySelector("button")).toBeNull();
    m.unmount();
    m = await render(<PlanCard plan={P.e27} retireAge={65} />);
    expect(q("[data-testid=ladder-next]")).toBeNull();   // every level reached
  });

  it("a What If shows each layer against the baseline, and a level up when a layer is newly reached", async () => {
    m = await render(<PlanCard plan={P.e24} retireAge={65} scenario={{ name: "Test", baseline: P.e11, change: "x" }} />);
    expect(q("[data-testid=levelup-needs]")?.textContent).toMatch(/Level up/);
    expect(q("[data-testid=levelup-wants]")?.textContent).toMatch(/Level up/);
    expect(q("[data-testid=levelup-wishes]")).toBeNull();
    expect(q("[data-testid=vs-paid]")?.textContent).toMatch(/▲ 99 more of 100.*vs baseline/);
    expect(q("[data-testid=vs-count]")?.textContent).toMatch(/▲ \$27,800 more a year/);
    m.unmount();
    m = await render(<PlanCard plan={P.e24_whatif} retireAge={66} scenario={{ name: "Retire at 66", baseline: P.e24, change: "x" }} />);
    expect(q("[data-testid=levelup-needs]")).toBeNull();   // nothing newly reached
    expect(q("[data-testid=vs-lasts]")?.textContent).toMatch(/▲ 17 more of 100/);
  });

});

describe("One vocabulary: needs, wants, wishes (no 'basics' in text the app writes)", () => {
  const BASICS = /\bbasics?\b/i;
  const texts = (o: unknown): string[] => (typeof o === "string" ? [o] : Object.values(o as object).flatMap(texts));
  it("PLAN_WORDS and the badges never say basics", () => {
    for (const t of texts(PLAN_WORDS)) expect(t, t).not.toMatch(BASICS);
    for (const p of [P.e11, P.s011, P.e27]) for (const b of badges(p)) expect(`${b.label} ${b.sr}`).not.toMatch(BASICS);
  });
  for (const id of ["e11", "s011", "e27"] as const) {
    it(`${id}: the hero, the move chips and the plan's own labels say needs, wants, wishes`, async () => {
      m = await render(<PlanCard plan={P[id]} retireAge={65} />);
      // frontend-owned text only: the headline and the moves' titles and reasons come from the server
      const own = (sel: string) => Array.from(m!.el.querySelectorAll(sel)).map((e) => {
        const c = e.cloneNode(true) as Element;
        c.querySelectorAll("[data-testid=plan-headline], .more-btn, .move-title, .move-line, .starting-points strong, .pt-text .sr-only").forEach((n) => n.remove());
        return c.textContent ?? "";
      }).join(" ");
      for (const sel of ["[data-testid=plan-hero]", ".worth-chip", ".starting-points .pt-text", "[data-testid=moves-count]"]) expect(own(sel), sel).not.toMatch(BASICS);
      expect(q("[data-testid=ring]")!.getAttribute("aria-label")).not.toMatch(BASICS);
    });
  }
  it("Compare rows and What If markers say needs", async () => {
    m = await render(<CompareTable cols={[{ key: "b", label: "Baseline", plan: P.s011 }, { key: "1", label: "x", plan: P.e24 }]} onOpen={() => {}} />);
    expect(m.el.textContent).not.toMatch(BASICS);
    const labels = Array.from(m.el.querySelectorAll("tbody th")).map((t) => t.textContent);
    expect(labels).toEqual(expect.arrayContaining(["Needs paid, of 100", "Needs, a year", "Count on, a year", "Wants, a year"]));
    for (const r of changes(P.s011, P.e24)) expect(r.label).not.toMatch(BASICS);
  });
});

describe("The ladder's fixed words are plain (grade 8 or lower)", () => {
  const texts = (o: unknown): string[] => (typeof o === "string" ? [o] : Object.values(o as object).flatMap(texts));
  it("every ladder sentence, and the rows and readouts as rendered, are grade 8 or lower", () => {
    const words = texts(PLAN_WORDS.ladder).filter((t) => t.split(/\s+/).length >= 3);
    expect(words.length).toBeGreaterThan(5);
    for (const t of words) expect(fkGrade(t), t).toBeLessThanOrEqual(8);
    for (const id of ["e11", "s011", "e27"] as const) {
      for (const r of layers(ladder(P[id]), false)) {
        for (const t of [r.read, `${r.label} ${r.word}. ${r.note}.`.replace(/. .$/, ".")]) expect(fkGrade(t.replace(/\$[\d,]+/g, "ten")), t).toBeLessThanOrEqual(8);
      }
    }
  });
  it("the ladder adds few words to the hero", async () => {
    m = await render(<PlanCard plan={P.s011} retireAge={65} />);
    const l = q("[data-testid=ladder]")!.cloneNode(true) as Element;
    l.querySelectorAll(".sr-only").forEach((e) => e.remove());
    const w = (l.textContent ?? "").replace(/([a-z$%)])([A-Z+$✓!○])/g, "$1 $2").split(/\s+/).filter(Boolean).length;
    expect(w).toBeLessThan(70);
  });
});

describe("The headline's reason", () => {
  it("sits folded under the headline as 'Why?' and only when the plan has one", async () => {
    m = await render(<PlanCard plan={P.e11} retireAge={66} />);
    const d = q("[data-testid=headline-why]") as HTMLDetailsElement;
    expect(d.open).toBe(false);
    expect(d.textContent).toContain(P.e11.headline_why!);
    expect(P.e11.headline_why).toBeTruthy();
    m = await render(<PlanCard plan={{ ...P.e11, headline_why: "" }} retireAge={66} />);
    expect(q("[data-testid=headline-why]")).toBeNull();
  });
});

// ---- Round 4 fixes: the verdict names the age, concrete moves, plain wants, state row, early check ----
describe("Round 4: the verdict answers 'Can I retire at my age?'", () => {
  const verdict = () => q(".verdict")!.textContent;
  it("names the age for all four kinds", async () => {
    const want: [keyof typeof P, string][] = [
      ["e27", "Retire at 62? Yes, you're on track."],
      ["s011", "Retire at 62? Close — short $5,200 a year."],
      ["e24", "Retire at 62? Not yet — short $17,300 a year."],
      ["e11", "Retire at 62? Not yet — first make your needs safe."],
    ];
    for (const [id, text] of want) {
      m = await render(<PlanCard plan={P[id]} retireAge={62} />);
      expect(verdict(), id).toBe(text);
      expect(verdict()!.split(/\s+/).length).toBeLessThanOrEqual(12);
      m.unmount(); m = null;
    }
  });
  it("a What If tab uses the tab's own age", async () => {
    m = await render(<PlanCard plan={P.e24_whatif} retireAge={64} scenario={{ name: "Retire at 64", baseline: P.e24, change: "x" }} />);
    expect(verdict()).toMatch(/^Retire at 64\? (Yes|Close|Not yet)/);
  });
  it("already retired: 'Retired: …'", async () => {
    m = await render(<PlanCard plan={{ ...P.s011, already_retired: true }} retireAge={70} />);
    expect(verdict()).toBe("Retired: close — short $5,200 a year.");
    expect(verdictLine("works", 0, 70, true)).toBe("Retired: yes, you're on track.");
  });
  it("without an age the answer stands alone", () => {
    expect(verdictLine("works", 0, null, false)).toBe("Yes, you're on track.");
  });
  it("says the shortfall number once on the hero (no banner repeat)", async () => {
    for (const id of ["s011", "e24"] as const) {
      m = await render(<PlanCard plan={P[id]} retireAge={62} />);
      const gap = id === "s011" ? "$5,200" : "$17,300";
      const hero = q("[data-testid=plan-hero]")!.cloneNode(true) as Element;
      hero.querySelectorAll(".sr-only, .ladder, details").forEach((e) => e.remove());
      expect((hero.textContent!.match(new RegExp(gap.replace("$", "\\$"), "g")) ?? []).length, id).toBe(1);
      m.unmount(); m = null;
    }
  });
  it("close with nothing left to close is on track, not 'Close' with wishes $0 open", async () => {
    const met = { ...P.s011, wants: { ...P.s011.wants, per_year: P.s011.analysis!.how_sure.goal_per_year } };
    m = await render(<PlanCard plan={met} retireAge={62} />);
    expect(verdict()).toBe("Retire at 62? Yes, you're on track.");
    expect(q(".row-wishes")!.textContent).toMatch(/✓ Covered/);
    expect(q(".row-wishes")!.textContent).not.toMatch(/Open/);
  });
  it("the verdict words are plain (grade 8 or lower)", () => {
    for (const k of ["works", "close", "short", "basics"] as const) expect(fkGrade(verdictLine(k, 5200, 62, false).replace(/\$[\d,]+/g, "ten")), k).toBeLessThanOrEqual(8);
  });
});

describe("Round 4: concrete moves", () => {
  it("the action's whatif_text (else the lever's) is what the What If section sends", async () => {
    const plan = { ...P.e11, actions: P.e11.actions.map((a, i) => (i === 1 ? { ...a, title: "Spend $4,000 less a year", whatif_text: "What if I spend $4,000 less a year" } : a)) };
    m = await render(<PlanCard plan={plan} retireAge={66} />);
    expect(movesOf(plan)[1].title).toBe("Spend $4,000 less a year");     // shown as sent
    expect(movesOf(plan)[1].tryQ).toBe("What if I spend $4,000 less a year");
    expect(Array.from(m.el.querySelectorAll(".move button")).some((b) => /^Try/.test(b.textContent ?? ""))).toBe(false);
    expect(movesOf(P.e11)[2].tryQ).toBe("What if I raise my 401(k) saving to the full match");   // no whatif_text: the lever's
  });
  it("a concrete title is not swapped; one past eight words gets a graceful cut", () => {
    const t = (title: string) => movesOf({ ...P.e11, actions: [{ title, why: "x" }, ...P.e11.actions.slice(1)] })[0].title;
    expect(t("Retire at 64 instead of 62")).toBe("Retire at 64 instead of 62");
    expect(t("Pay off your high-rate debt of $12,000 first and then save more each month")).toMatch(/^Pay off your high-rate debt of \$12,000 first…$/);
  });
});

describe("Round 4: wording", () => {
  it("the ladder says what '100 tests' means, once", async () => {
    m = await render(<PlanCard plan={P.s011} retireAge={62} />);
    expect(q("[data-testid=ladder-tests-tip]")?.textContent).toBe("We test your plan in 100 good and bad markets.");
    expect(m.el.querySelectorAll("[data-testid=ladder-tests-tip]")).toHaveLength(1);
  });
  it("Wants +$0 has a plain reason", async () => {
    m = await render(<PlanCard plan={P.e11} retireAge={62} />);
    expect(q(".row-wants")!.textContent).toMatch(/\+\$0.*Your needs use it all/);
    m.unmount();
    const flat = { ...P.s011, wants: { ...P.s011.wants, per_year: P.s011.needs.basics_per_year } };   // count on equals needs
    m = await render(<PlanCard plan={flat} retireAge={62} />);
    expect(q(".row-wants")!.textContent).toMatch(/\+\$0.*Your needs use it all/);
    expect(q(".row-wishes")!.textContent).not.toMatch(/\$0 open/i);
  });
});

describe("Round 4: state row and the early check", () => {
  const fields = [
    { key: "age", label: "Your age", value: 45, display: "45", source: "you said", section: "Household" },
    { key: "retire_age", label: "Retire at", value: 65, display: "65", source: "default", section: "Work & pay" },
  ];
  it("adds a State row marked typical, with a pen, when the state was not given", async () => {
    expect(withStateRow([], {})).toEqual([]);
    m = await render(<LivePanel profile={{ age: 45 }} fields={fields} missing={[]} onEdit={() => {}} onBuild={() => {}} canBuild={false} />);
    const row = q("[data-key=state]")!;
    expect(row).toBeTruthy();
    expect(row.querySelector(".tag")?.textContent).toBe("typical");
    expect(row.querySelector("button.pen")?.getAttribute("aria-label")).toBe("Change State");
    expect(row.closest("[data-section=Household]")).toBeTruthy();
  });
  it("keeps the person's own State row, and adds none twice", () => {
    const own = [...fields, { key: "state", label: "State", value: "CT", display: "Connecticut", source: "you said", section: "Household" }];
    expect(withStateRow(own, { state: "CT" })).toBe(own);
  });
  it("the check step lists the retirement age to confirm, marked typical", async () => {
    m = await render(<BuildBlock idp="t" canBuild canStart fields={fields} checking onConfirm={() => {}} onCloseCheck={() => {}} onBuild={() => {}} />);
    const li = q("[data-testid=check-figures] li")!;
    expect(li.textContent).toBe("Retire at 65 typical");
  });
});
