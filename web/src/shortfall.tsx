import { usd } from "./format";
import type { Plan } from "./types";

// Shortfalls are shown big, bold and in strong colour, with an icon and words, so colour is never the only signal.
// Red: the plan falls short (needs paid in fewer than 90 of 100, or the verdict says so). Amber: close. Works stays green and calm.

export type Level = "short" | "close" | "ok";

/** Below this many of 100 the basics are not safe (the plan falls short). */
export const BASICS_SAFE = 90;

/** Needs are safe from BASICS_SAFE (90 of 100 market tests) up, the same rule as the money ladder; below that they are short. */
export const basicsLevel = (paid: number): Level => (paid < BASICS_SAFE ? "short" : "ok");

/** The plan's level: the verdict when it has one, else the basics. The worse of the two wins. */
export function planLevel(plan: Plan): Level {
  const v = plan.verdict;
  // "close" with nothing left to close (the count-on figure already meets the goal, to the dollar) is on track: one answer on the page
  const goal = goalOf(plan);
  const met = goal != null && Math.round(plan.wants.per_year) >= Math.round(goal);
  const byVerdict: Level = v === "falls_short" || v === "below_goal" ? "short" : v === "close" && !met ? "close" : "ok";
  const byBasics = basicsLevel(plan.needs.paid_of_100);
  const worse = (a: Level, b: Level): Level => (a === "short" || b === "short" ? "short" : a === "close" || b === "close" ? "close" : "ok");
  // a plan the engine calls "works" is not marked red for basics at 90 or more; below 90 it is always red
  if (v === "works") return byBasics === "short" ? "short" : "ok";
  return worse(byVerdict, byBasics);
}

/** What the goal asks for each year that the plan cannot count on, or 0. Needs the analysis (it holds the goal). */
export function yearlyGap(plan: Plan, goalFallback?: number | null): number {
  const goal = plan.analysis?.how_sure?.goal_per_year ?? goalFallback ?? null;
  return goal != null ? Math.max(0, Math.round(goal - plan.wants.per_year)) : 0;
}

export const goalOf = (plan: Plan): number | null => plan.analysis?.how_sure?.goal_per_year ?? null;

export const LEVEL_ICON: Record<Level, string> = { short: "\u26A0", close: "\u26A0", ok: "\u2713" };
export const LEVEL_WORD: Record<Level, string> = { short: "Short", close: "Close", ok: "On track" };

/** The loud block at the top of a plan that is short or close. Nothing for a plan that works. */
export function ShortfallBanner({ plan }: { plan: Plan }) {
  const level = planLevel(plan);
  if (level === "ok") return null;
  const gap = yearlyGap(plan);
  const goal = goalOf(plan);
  const paid = plan.needs.paid_of_100;
  const big = gap > 0 ? `Short ${usd(gap)} a year` : level === "short" ? "Falls short" : "Close to your goal";
  const lines: string[] = [];
  if (level === "close" && gap > 0) lines.push("Close to your goal.");
  if (gap > 0 && goal != null) lines.push(`Your goal is ${usd(goal)} a year. You can count on ${usd(plan.wants.per_year)}.`);
  if (paid < 100) lines.push(`Your needs are paid in ${paid} of 100 market tests${paid < BASICS_SAFE ? ", not enough" : ""}.`);
  return (
    <div className={`shortfall shortfall-${level}`} role="group" aria-label={level === "short" ? "Shortfall" : "Close to short"} data-testid="shortfall" data-level={level}>
      <span className="shortfall-icon" aria-hidden="true">{LEVEL_ICON[level]}</span>
      <div>
        <p className="shortfall-big num" data-testid="shortfall-big">{big}</p>
        {lines.map((l) => <p key={l} className="shortfall-line">{l}</p>)}
      </div>
    </div>
  );
}

/** A small inline mark: icon and words beside a figure that is short or close. */
export function LevelMark({ level, children }: { level: Level; children?: string }) {
  if (level === "ok") return null;
  return <span className={`lvl lvl-${level}`}><span aria-hidden="true">{LEVEL_ICON[level]}</span> {children ?? LEVEL_WORD[level]}</span>;
}
