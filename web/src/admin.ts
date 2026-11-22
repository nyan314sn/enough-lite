// Admin mode (the hidden path /admin): the numbers kept from each plan, and the before and after comparison. No screen code here.
import type { Plan, Profile, Sample } from "./types";

export const ADMIN_BEFORE_KEY = "enough-lite-admin-before";

export const ADMIN_PATH = "/admin";
/** Set when the page was opened at /admin; it lasts for the browser tab, so test mode stays on while the person moves about the app. */
export const ADMIN_SESSION_KEY = "enough-lite-admin-session";

/** True only at the path /admin (not ?admin). Nothing in the app links there: one types the address. */
export function adminFromUrl(path: string = typeof window !== "undefined" ? window.location.pathname : ""): boolean {
  return path.replace(/[/]+$/, "").toLowerCase() === ADMIN_PATH;
}
export function markAdminSession() { try { sessionStorage.setItem(ADMIN_SESSION_KEY, "1"); } catch { /* storage blocked */ } }
export function adminSession(): boolean { try { return sessionStorage.getItem(ADMIN_SESSION_KEY) === "1"; } catch { return false; } }

export const TIERS: { key: Sample["tier"]; label: string }[] = [
  { key: "comfortable", label: "Comfortable" },
  { key: "average", label: "Average" },
  { key: "struggling", label: "Struggling" },
];

/** What is kept from one plan: the five figures that matter most. Dollars are a year, in today's dollars. */
export interface Metrics {
  verdict: string | null;           // works | close | below_goal | falls_short
  basics_of_100: number;            // paths in 100 where the basics are paid
  count_on: number;                 // what you can count on each year
  gap: number | null;               // how far the goal is above what you can count on (0 when met)
  savings_at_retire: number | null; // a middle path
}

export const VERDICT_WORDS: Record<string, string> = { works: "Works", close: "Close", below_goal: "Below goal", falls_short: "Falls short" };
const VERDICT_RANK: Record<string, number> = { works: 3, close: 2, below_goal: 1, falls_short: 0 };

export function summarize(plan: Plan, retireAge?: number | null): Metrics {
  const goal = plan.analysis?.how_sure?.goal_per_year;
  const age = plan.costs_by_age?.retire_age ?? retireAge ?? null;
  let at: number | null = null;
  if (age != null) {
    const i = plan.chart.ages.indexOf(age);
    if (i >= 0) at = plan.chart.median[i];
  }
  return {
    verdict: plan.verdict ?? null,
    basics_of_100: plan.needs.paid_of_100,
    count_on: plan.wants.per_year,
    gap: goal != null ? Math.max(0, Math.round(goal - plan.wants.per_year)) : null,
    savings_at_retire: at,
  };
}

export interface Saved { savedAt: string; results: Record<string, Metrics> }

export function loadBefore(): Saved | null {
  try {
    const s = JSON.parse(localStorage.getItem(ADMIN_BEFORE_KEY) ?? "null");
    return s && typeof s.savedAt === "string" && s.results && typeof s.results === "object" ? (s as Saved) : null;
  } catch { return null; }
}
export function saveBefore(results: Record<string, Metrics>): Saved {
  const s: Saved = { savedAt: new Date().toISOString(), results };
  try { localStorage.setItem(ADMIN_BEFORE_KEY, JSON.stringify(s)); } catch { /* storage blocked */ }
  return s;
}
export function clearBefore() { try { localStorage.removeItem(ADMIN_BEFORE_KEY); } catch { /* storage blocked */ } }

export type Dir = "up" | "down" | "same";
export interface Change { dir: Dir; good: boolean | null; diff: number }

/** Compare a number. Higher is better unless `lowerIsBetter`. Missing figures give "same". */
export function compare(before: number | null | undefined, after: number | null | undefined, lowerIsBetter = false, tolerance = 0): Change {
  if (before == null || after == null || Math.abs(after - before) <= tolerance) return { dir: "same", good: null, diff: 0 };
  const diff = after - before;
  return { dir: diff > 0 ? "up" : "down", good: lowerIsBetter ? diff < 0 : diff > 0, diff };
}

export function compareVerdict(before: string | null | undefined, after: string | null | undefined): Change {
  const b = before ? VERDICT_RANK[before] : undefined, a = after ? VERDICT_RANK[after] : undefined;
  return compare(b, a);
}

export interface Row { sample: Sample; metrics: Metrics | null; before: Metrics | null }

/** Every household's changes against the saved run. */
export function diffRow(before: Metrics | null | undefined, after: Metrics | null | undefined) {
  return {
    verdict: compareVerdict(before?.verdict, after?.verdict),
    basics: compare(before?.basics_of_100, after?.basics_of_100),
    count_on: compare(before?.count_on, after?.count_on, false, 500),
    gap: compare(before?.gap, after?.gap, true, 500),
    savings: compare(before?.savings_at_retire, after?.savings_at_retire, false, 5000),
  };
}

/** The file the "Download results" button writes. */
export function buildExport(samples: Sample[], results: Record<string, Metrics>, before: Saved | null, now = new Date()) {
  return {
    created: now.toISOString(),
    before_saved_at: before?.savedAt ?? null,
    households: samples.map((s) => ({
      id: s.id, tier: s.tier, name: s.name,
      after: results[s.id] ?? null,
      before: before?.results[s.id] ?? null,
    })),
  };
}

/** The figures a row shows beside its name: ages, pay, savings, spending, state. */
export function rowFacts(p: Profile) {
  const s = p.savings ?? {};
  const savings = (s.pretax ?? 0) + (s.roth ?? 0) + (s.taxable ?? 0) + (s.cash ?? 0);
  const pay = (p.pay_per_year ?? 0) + (p.partner_pay_per_year ?? 0);
  return {
    ages: p.partner_age != null ? `${p.age} and ${p.partner_age}` : `${p.age ?? "?"}`,
    pay, savings,
    spending: (p.spending_now_per_year ?? p.spending_per_year ?? null) as number | null,
    state: (p.state ?? "") as string,
  };
}

/** Run `tasks` with at most `limit` at once. */
export async function pool<T>(items: T[], limit: number, work: (item: T) => Promise<void>, stop?: () => boolean): Promise<void> {
  let next = 0;
  const lane = async () => {
    while (next < items.length && !stop?.()) await work(items[next++]);
  };
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, lane));
}
