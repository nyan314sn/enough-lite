import { usd } from "../format";
import { goalOf, yearlyGap } from "../shortfall";
import type { Plan } from "../types";

// Helpers for What If tabs: the key figures, the "vs baseline" markers (▲/▼ with words, never colour alone), and how a tab is named.

/** Most What Ifs kept at once. */
export const MAX_WHATIFS = 5;

interface Row { label: string; before: number; after: number; show: (n: number) => string; unit?: string }

export function changes(before: Plan, after: Plan): Row[] {
  return [
    { label: "Needs paid", before: before.needs.paid_of_100, after: after.needs.paid_of_100, show: (n) => `${n} of 100` },
    { label: "Needs a year", before: before.needs.basics_per_year, after: after.needs.basics_per_year, show: usd },
    { label: "You can count on, a year", before: before.wants.per_year, after: after.wants.per_year, show: usd },
  ];
}

/** An action is "new" in a What If only if the plan did not have it before. Titles get reworded and carry figures, so a lever's key decides
 *  where there is one; the rest are matched on the title with its numbers taken out. */
export function actionIsNew(before: Plan, after: Plan): (title: string) => boolean {
  const words = (t: string) => t.toLowerCase().replace(/[$\d,.%]+/g, "#").replace(/\s+/g, " ").trim();
  const keyOf = (p: Plan, title: string) => p.levers?.find((l) => l.title === title || words(l.title) === words(title))?.key;
  const oldKeys = new Set((before.levers ?? []).map((l) => l.key));
  const oldTitles = new Set(before.actions.map((a) => words(a.title)));
  const haveLevers = (before.levers?.length ?? 0) > 0 || (after.levers?.length ?? 0) > 0;
  return (title) => {
    const key = keyOf(after, title);
    if (key) return !oldKeys.has(key) && !oldTitles.has(words(title));
    // With levers on the plans, an action that matches no lever has been reworded as often as it is new: say nothing rather than tag every one.
    return !haveLevers && !oldTitles.has(words(title));
  };
}


const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const clean = (q: string) => q.trim().replace(/[?.!\s]+$/, "").replace(/^(what if|what about|suppose|say)\s+/i, "").replace(/^(i|we)\s+(?=\S)/i, "").replace(/\s+/g, " ");
const WORD_N: Record<string, number> = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, a: 1, an: 1, another: 1 };
const num = (s: string) => WORD_N[s.toLowerCase()] ?? Number(s);
/** $32,000 becomes $32k; $32,500 becomes $32.5k; $500 stays. */
export function shortMoney(raw: string, k = false): string {
  let n = Number(raw.replace(/,/g, ""));
  if (k) n *= 1000;
  if (!Number.isFinite(n)) return raw;
  return n >= 1000 ? `$${parseFloat((n / 1000).toFixed(1))}k` : `$${Math.round(n)}`;
}

/** The tab's name: a short label of the change ("Retire at 64", "Spend $32k", "Full 401(k) match"), read from the words of the question and,
 *  for a chip, its label. With no pattern it is the person's words cut at 22 characters. */
export function shortName(q: string, shown?: string): string {
  for (const t of [q, shown ?? ""]) {
    if (!t) continue;
    // "retire at 64", and "Retire 1 year later, at 66" (an analysis choice)
    let m = t.match(/retire\w*\s+(?:at|by|in)?\s*(?:age\s+)?(\d{2})\b/i) ?? t.match(/retire\b[^.?!]*?\b(?:at|by)\s+(?:age\s+)?(\d{2})\b/i);
    if (m) return `Retire at ${m[1]}`;
    m = t.match(/markets?\s+(?:fall|drop|crash|go down|decline)\w*\s+(?:by\s+)?(\d+)\s*%/i);
    if (m) return `Markets fall ${m[1]}%`;
    m = t.match(/spend\w*[^$\d]{0,40}\$\s?([\d,]+(?:\.\d+)?)\s?(k)?(?:\s+a\s+\w+)?\s*(less|more)?/i);
    if (m) return `Spend ${shortMoney(m[1], !!m[2])}${m[3] ? ` ${m[3].toLowerCase()}` : ""}`;
    if (/employer match|401\(k\) match|full match/i.test(t)) return "Full 401(k) match";
    m = t.match(/(\d+|one|two|three|four|five|six)[- ]months?/i);
    if (m && /emergency|cash/i.test(t)) return `${num(m[1])}-month cash fund`;
    m = t.match(/save\s+(\d+)\s*%/i);
    if (m) return `Save ${m[1]}%`;
    m = t.match(/(?:(\d+|two|three|four|five|a|another)\s+)?(dog|cat)s?\b/i);
    if (m && /get|have|had|adopt|got|another|new|\d/i.test(t)) { const n = m[1] ? num(m[1]) : 1; return n > 1 ? `${n} ${m[2].toLowerCase()}s` : `Get a ${m[2].toLowerCase()}`; }
    if (/another (child|kid|baby)|have a (baby|child)|one more (child|kid)/i.test(t)) return "Another child";
    if (/life (cover|insurance)/i.test(t)) return "More life cover";
    if (/pay(ing)? off/i.test(t)) return /card/i.test(t) ? "Pay off the card" : "Pay off debt";
  }
  const s = cap(clean(shown || q) || q.trim());
  return s.length > 22 ? `${s.slice(0, 21).trimEnd()}…` : s;
}
export const tabName = (q: string) => shortName(q);

/** One short line saying what changed against the baseline. */
export function changeLine(q: string, base: Plan, retireBefore?: number | null, retireAfter?: number | null): string {
  if (retireAfter && retireBefore && retireAfter !== retireBefore) return `Retire at ${retireAfter} instead of ${retireBefore}`;
  const spend = q.match(/spend\w*[^$\d]{0,40}\$\s?([\d,]+(?:\.\d+)?)\s?(k)?\s*(?:a\s+year|per\s+year|yearly|a\s+yr)?\s*$/i);
  const goal = goalOf(base);
  if (spend && goal != null) {
    const n = Number(spend[1].replace(/,/g, "")) * (spend[2] ? 1000 : 1);
    return `Spending goal ${usd(n)} instead of ${usd(goal)}`;
  }
  const s = cap(clean(q));
  return s.length > 90 ? `${s.slice(0, 89).trimEnd()}…` : s;
}

/** "▲ $1,200 more a year vs baseline". good: which direction is better for the person. */
export function VsMarker({ d, unit, good = "up", testid }: { d: number; unit: (n: number, up: boolean) => string; good?: "up" | "down"; testid?: string }) {
  if (Math.round(d) === 0) return <span className="vs vs-same" data-testid={testid}><span className="delta same">same as baseline</span></span>;
  const up = d > 0;
  const better = (up ? "up" : "down") === good;
  return (
    <span className="vs" data-testid={testid}>
      <span className={`delta ${better ? "up" : "down"}`}>{up ? "▲" : "▼"} {unit(Math.abs(d), up)}<span className="sr-only">, {better ? "better" : "worse"}</span></span>
      <span className="vs-l"> vs baseline</span>
    </span>
  );
}


/** The key figures of a plan, for the Compare table and the markers. goalLasts is null without the analysis. */
export function keyFigures(p: Plan, base: Plan) {
  const goal = goalOf(p) ?? goalOf(base);
  return {
    countOn: p.wants.per_year,
    paid: p.needs.paid_of_100,
    basics: p.needs.basics_per_year,
    wants: Math.max(0, p.wants.per_year - p.needs.basics_per_year),
    gap: goal != null ? yearlyGap(p, goalOf(base)) : null,
    goalLasts: p.analysis?.how_sure?.goal_lasts_of_100 ?? null,
  };
}
