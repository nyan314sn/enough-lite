import { usd } from "./format";
import { BASICS_SAFE, goalOf, planLevel, yearlyGap } from "./shortfall";
import type { AnalysisRow, Plan } from "./types";

// The plan page at a glance (feedback round B, R26): a verdict, a readiness score, the moves to make and the badges earned.
// Everything here is worked out from the plan the server sent. Nothing new is estimated: no figure appears that the plan does not hold.

/** Every fixed sentence the plan page writes itself, kept in one place so a test can check the reading grade (R26: grade 8 or lower). */
export const PLAN_WORDS = {
  verdict: {
    works: "Yes, you're on track.",
    close: "Close. A few changes get you there.",
    short: "Not yet. Here's how to close the gap.",
    basics: "Not yet. First, make your needs safe.",
  },
  scoreName: "Readiness",
  scoreHow: "How is this scored?",
  scoreTip: "Readiness is the share of your goal you can count on each year. It stops at 100. We test your plan in 100 ways the markets could go. Count on means it lasts in 90 of them. If your needs are not safe, the score stops at 40.",
  cappedNote: "Held at 40 until your needs are safe.",
  noGoalTip: "We could not find a goal in this plan, so the ring shows your needs. It is how many of 100 market tests pay them.",
  dollars: "All figures are in today's dollars.",
  movesTitle: "Your next moves",
  movesLine: "What each move is worth. To test one, use Try a What If at the end of the page.",
  extraTitle: "More moves to try",
  pointsTitle: "Starting points",
  ladder: {
    title: "Needs, wants, wishes",
    needs: "Needs", wants: "Wants", wishes: "Wishes",
    needsEg: "home, food, health care",
    needsEgPets: "home, food, health care, pets",
    wantsEg: "travel, eating out, gifts",
    needsSafe: "Safe", needsNot: "Not safe yet",
    wantsSure: "Sure", wantsNot: "Not sure yet",
    wishesOpen: "Open", wishesCovered: "Covered",
    wantsNone: "You can count on less than your needs, so there is nothing left for wants.",
    wantsNoneShort: "Your needs use it all",
    wantsZeroShort: "Your needs use it all",
    testsTip: "We test your plan in 100 good and bad markets.",
    wishesOpenNote: "Only if markets help.",
    wishesLocked: "Locked", wishesLockedNote: "Make your needs safe first.",
    wishesDone: "Your whole goal is covered.",
    next: "Next level",
    levelUp: "Level up",
  },
  chartTitle: "Your savings by age",
  chartLine: "The line is a middle case. The band runs from bad to good markets.",
  detailsTitle: "More details",
  detailsLine: "Open any part to see more.",
  meaning: "What these numbers mean",
  costs: "Your costs by age",
  moments: "Family moments",
  checking: "Worth checking",
  closesGap: "This change closes the gap.",
  more: "more",
  less: "less",
} as const;

export type VerdictKind = keyof typeof PLAN_WORDS.verdict;

/**
 * The top line of the plan: a direct answer to "Can I retire when I want?", with the person's own retirement age.
 *   "Retire at 62? Close — short $5,200 a year."   Already retired: "Retired: close — short $5,200 a year."
 * The shortfall is said here once (R12), so the banner under it never repeats it. Without an age the answer stands alone.
 */
export const VERDICT_ANSWER = {
  works: "Yes, you're on track.",
  close: "Close",
  short: "Not yet",
  basics: "Not yet — first make your needs safe.",
} as const;
export function verdictLine(kind: VerdictKind, gap: number, retireAge: number | null | undefined, retired: boolean): string {
  const lead = retired ? "Retired: " : retireAge ? `Retire at ${retireAge}? ` : "";
  let a: string = VERDICT_ANSWER[kind];
  if (kind === "close" || kind === "short") a = gap > 0 ? `${a} — short ${usd(gap)} a year.` : PLAN_WORDS.verdict[kind];
  if (!lead) return a;
  const body = retired ? a.charAt(0).toLowerCase() + a.slice(1) : a;
  return `${lead}${body}`;
}

/** Which of the four answers the plan gives. Basics not safe (under 90 of 100, or the engine says falls short) comes first. */
export function verdictKind(plan: Plan): VerdictKind {
  if (plan.needs.paid_of_100 < BASICS_SAFE || plan.verdict === "falls_short") return "basics";
  const level = planLevel(plan);
  return level === "ok" ? "works" : level === "close" ? "close" : "short";
}

/**
 * Readiness, 0 to 100: the share of the yearly goal you can count on, capped at 100.
 *
 *     readiness = min(100, floor(100 × count_on ÷ goal))
 *
 * count_on is plan.wants.per_year (what lasts in 90 of 100 market tests, basics included, the headline's figure); goal is the
 * spending goal the analysis used (plan.analysis.how_sure.goal_per_year). Floor, so 100 means the goal is fully covered.
 * Null when the plan has no goal (older backends, market What Ifs): the ring then shows the basics instead. The basics are
 * not mixed into the share, but while they are not safe (verdict "basics") the score is held at READINESS_CAP_UNSAFE, so the ring
 * and the verdict always agree (owner's choice, 2026-11-22).
 */
export const READINESS_CAP_UNSAFE = 40;

/** The plain share before any cap: min(100, floor(100 × count_on ÷ goal)); null without a goal. */
export function readinessShare(plan: Plan): number | null {
  const goal = goalOf(plan);
  if (goal == null || !(goal > 0)) return null;
  return Math.max(0, Math.min(100, Math.floor((100 * plan.wants.per_year) / goal)));
}

export function readiness(plan: Plan): number | null {
  const share = readinessShare(plan);
  if (share == null) return null;
  return verdictKind(plan) === "basics" ? Math.min(share, READINESS_CAP_UNSAFE) : share;
}

/** What the ring shows: readiness when the plan has a goal, else the basics paid of 100. */
export function ringOf(plan: Plan): { value: number; kind: "ready" | "basics" } {
  const r = readiness(plan);
  return r != null ? { value: r, kind: "ready" } : { value: plan.needs.paid_of_100, kind: "basics" };
}

/**
 * The money ladder: three layers on one scale, in dollars a year. All from the plan.
 *   needs  = the needs figure (plan.needs.basics_per_year)
 *   wants  = count on - needs, never below 0 (what you can count on above your needs)
 *   wishes = goal - max(count on, needs), never below 0 (the rest of the goal, open)
 * The three add up to the goal; when the goal is covered they add up to count on instead. Without a goal there are no wishes.
 */
export interface Ladder {
  needs: number; wants: number; wishes: number; goal: number | null; countOn: number; total: number; scale: number;
  paid: number; lasts: number | null;
  needsSafe: boolean; wantsSure: boolean; covered: boolean;
}
export function ladder(plan: Plan, goalFallback?: number | null): Ladder {
  const goal = goalOf(plan) ?? goalFallback ?? null;
  const needs = Math.round(plan.needs.basics_per_year), countOn = Math.round(plan.wants.per_year);
  const wants = Math.max(0, countOn - needs);
  const wishes = goal != null ? Math.max(0, Math.round(goal) - Math.max(countOn, needs)) : 0;
  const total = needs + wants + wishes;
  return {
    needs, wants, wishes, goal, countOn, total, scale: Math.max(total, goal ?? 0, 1),
    paid: plan.needs.paid_of_100, lasts: plan.analysis?.how_sure?.goal_lasts_of_100 ?? null,
    needsSafe: plan.needs.paid_of_100 >= BASICS_SAFE, wantsSure: plan.needs.paid_of_100 >= BASICS_SAFE && wants > 0,
    covered: goal != null && countOn >= Math.round(goal),
  };
}

export interface Badge { key: string; label: string; earned: boolean; sr: string }

/** Milestones, each earned only on the plan's own figures: one per layer of the ladder (needs safe, wants sure, goal covered), then the rest once earned. */
export function badges(plan: Plan): Badge[] {
  const out: Badge[] = [];
  const paid = plan.needs.paid_of_100;
  const safe = paid >= BASICS_SAFE;
  out.push({ key: "basics", label: safe ? "Needs safe" : "Needs not safe yet", earned: safe, sr: `Your needs are paid in ${paid} of 100 market tests.` });
  const goal = goalOf(plan);
  if (goal != null) {
    const l = ladder(plan);
    out.push({ key: "wants", label: l.wantsSure ? "Wants sure" : "Wants not sure yet", earned: l.wantsSure, sr: l.wantsSure ? `You can count on ${usd(l.wants)} a year above your needs.` : "You cannot yet count on money above your needs." });
    const ok = plan.wants.per_year >= goal;
    out.push({ key: "goal", label: ok ? "Goal covered" : "Goal not covered yet", earned: ok, sr: ok ? `You can count on ${usd(plan.wants.per_year)} a year, your goal or more.` : `You can count on ${usd(plan.wants.per_year)} of your ${usd(goal)} goal.` });
  }
  const s = plan.saving;
  const working = !plan.already_retired;
  // an employer match is paid, and the plan has no "get the full match" move: the match is not being left on the table
  if (working && s && s.match_per_year > 0 && Array.isArray(plan.levers) && !plan.levers.some((l) => l.key === "match"))
    out.push({ key: "match", label: "Employer match", earned: true, sr: "You get your employer's match." });
  if (working && s && s.per_year > 0) out.push({ key: "saving", label: "Saving each year", earned: true, sr: "You save some money each year." });
  return out;
}

// ---- moves ----

/** The server's titles are concrete actions with a number, so they show as sent. Only a title past eight words gets a graceful cut. */
export const MAX_TITLE_WORDS = 8;
const words = (t: string) => t.toLowerCase().replace(/[$\d,.%]+/g, "#").replace(/\s+/g, " ").trim();
const wordCount = (t: string) => t.trim().split(/\s+/).filter(Boolean).length;

/** At most n words; a cut ends with "…". */
export function clampWords(t: string, n: number): string {
  const w = t.trim().split(/\s+/);
  return w.length <= n ? t.trim() : `${w.slice(0, n).join(" ").replace(/[,;:.]+$/, "")}…`;
}

/** A short version of a long text: whole sentences up to n words, else the first n words with "…". The full text stays a click away. */
export function shortText(t: string, n: number): string {
  const s = t.trim();
  if (wordCount(s) <= n) return s;
  // a sentence ends at . ! or ? followed by a space: "2.4 months" and "$1.5k" stay whole
  const sentences = s.split(/(?<=[.!?])\s+/);
  let out = "";
  for (const x of sentences) {
    const next = out ? `${out} ${x}` : x;
    if (wordCount(next) > n) break;
    out = next;
  }
  return out.trim() || clampWords(s, n);
}

export interface Worth { text: string; sr: string }
export interface Move {
  /** The lever key, or the action's own words: what a tick is stored under. */
  id: string;
  title: string;
  /** The server's title, for "new" in a What If. */
  original: string;
  why: string;
  worth: Worth | null;
  tryQ: string | null;
  points: NonNullable<Plan["starting_points"]>;
}

export const MIN_GAIN_PER_YEAR = 500;
export const MIN_GAIN_BASICS = 5;

/** What a row of "what each choice is worth" adds, in words: "+$2,500 a year" and/or "+34 in 100 for basics". */
export function rowWorth(r: AnalysisRow): Worth | null {
  const parts: string[] = [], sr: string[] = [];
  if (r.count_on_change >= MIN_GAIN_PER_YEAR) { parts.push(`+${usd(r.count_on_change)} a year`); sr.push(`adds ${usd(r.count_on_change)} a year you can count on`); }
  if (r.basics_change >= MIN_GAIN_BASICS) { parts.push(`+${r.basics_change} in 100 for needs`); sr.push(`needs paid in ${r.basics_change} more of 100 market tests`); }
  return parts.length ? { text: parts.join(" · "), sr: `Worth: ${sr.join(", and ")}.` } : null;
}

/** The plan's three actions as moves: a short title, the reason, what it is worth where the plan says, and the What If that tries it. */
export function movesOf(plan: Plan): Move[] {
  const levers = plan.levers ?? [];
  const rows = plan.analysis?.levers?.rows ?? [];
  const points = plan.starting_points ?? [];
  const gap = yearlyGap(plan);
  const acts = plan.actions.slice(0, 3);
  const leverOf = (a: { title: string; key?: string | null }) =>
    levers.find((l) => (a.key && l.key === a.key) || l.title === a.title || words(l.title) === words(a.title));
  // the starting points belong to the "make your needs safe" move: the goal lever, else an action about the basics, else the first
  let pointsAt = acts.findIndex((a) => leverOf(a)?.key === "goal");
  if (pointsAt < 0) pointsAt = acts.findIndex((a) => /basics|needs/i.test(a.title));
  if (pointsAt < 0) pointsAt = 0;
  return acts.map((a, i) => {
    const lever = leverOf(a);
    const key = lever?.key;
    const title0 = a.title.trim().replace(/\.$/, "");
    const title = wordCount(title0) <= MAX_TITLE_WORDS ? title0 : clampWords(title0, MAX_TITLE_WORDS);
    const own = points.length > 0 && i === pointsAt;
    let worth: Worth | null = null;
    if (own) {
      const best = Math.max(...points.map((p) => p.paid_of_100));
      if (best > plan.needs.paid_of_100) worth = { text: `Needs paid up to ${best} of 100`, sr: `Worth: the best starting point pays your needs in ${best} of 100 market tests, against ${plan.needs.paid_of_100} now.` };
    } else if (key === "goal" && gap > 0) {
      worth = { text: "Closes the gap", sr: "Worth: your goal becomes one you can count on." };
    } else if (key) {
      const r = rows.find((x) => x.key === key);
      worth = r ? rowWorth(r) : null;
    }
    return {
      id: key ?? words(a.title), title, original: a.title, why: a.why, worth,
      tryQ: a.whatif_text || (own ? null : lever?.whatif_text) || null,
      points: own ? points : [],
    };
  });
}

/** Choices from the analysis worth a look that are not already a move: up to two, best first. */
export function extraMoves(plan: Plan, moves: Move[], n = 2): { key: string; title: string; worth: Worth; q: string }[] {
  const have = new Set(moves.map((m) => m.id));
  const rows = plan.analysis?.levers?.rows ?? [];
  return rows
    .filter((r) => !have.has(r.key) && (r.count_on_change >= MIN_GAIN_PER_YEAR || r.basics_change >= MIN_GAIN_BASICS))
    .sort((a, b) => b.count_on_change - a.count_on_change || b.basics_change - a.basics_change)
    .slice(0, n)
    .map((r) => ({ key: r.key, title: r.title, worth: rowWorth(r)!, q: r.ask || r.title }));
}

