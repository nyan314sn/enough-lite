import { usd } from "../format";
import { LEVEL_ICON, goalOf, planLevel, yearlyGap, type Level } from "../shortfall";
import { PLAN_WORDS, badges, readinessShare, ringOf, verdictKind, verdictLine, type Move } from "../readiness";
import type { Plan } from "../types";
import { VsMarker, keyFigures } from "./WhatIf";
import Clamp from "./Clamp";
import Ladder, { useGrow } from "./Ladder";

// The top of the plan: one plain verdict, one big number, a readiness ring, a bar toward the goal, and the badges earned.
// Read in a few seconds. Every figure is the plan's own (R11, R12); the ring's formula is in readiness.ts and in "How is this scored?".

const R = 52, C = 2 * Math.PI * R;

export function Ring({ value, kind, level, before }: { value: number; kind: "ready" | "basics"; level: Level; before?: number | null }) {
  const shown = useGrow(value);
  const label = kind === "ready"
    ? `${PLAN_WORDS.scoreName} ${value} out of 100. You can count on ${value} percent of your goal.`
    : `Needs paid in ${value} of 100 market tests.`;
  return (
    <div className={`ring ring-${level}`} role="img" aria-label={label} data-testid="ring" data-value={value}>
      <svg viewBox="0 0 128 128" aria-hidden="true" focusable="false">
        <circle cx="64" cy="64" r={R} className="ring-track" />
        {before != null && <circle cx="64" cy="64" r={R} className="ring-before" strokeDasharray={C} strokeDashoffset={C * (1 - before / 100)} transform="rotate(-90 64 64)" />}
        <circle cx="64" cy="64" r={R} className="ring-arc" strokeDasharray={C} strokeDashoffset={C * (1 - shown / 100)} transform="rotate(-90 64 64)" />
      </svg>
      <span className="ring-mid" aria-hidden="true">
        <span className="ring-num num">{value}</span>
        <span className="ring-of">{kind === "ready" ? PLAN_WORDS.scoreName : "needs, of 100"}</span>
      </span>
    </div>
  );
}

export function Badges({ plan }: { plan: Plan }) {
  const list = badges(plan);
  return (
    <ul className="miles" aria-label="Milestones" data-testid="badges">
      {list.map((b) => (
        <li key={b.key} className={`mile ${b.earned ? "earned" : "locked"}`} data-badge={b.key} data-earned={b.earned ? "true" : "false"}>
          <span className="mile-icon" aria-hidden="true">{b.earned ? "✓" : b.key === "basics" ? "⚠" : "○"}</span>
          <span>{b.label}</span>
          <span className="sr-only">{b.earned ? ", earned" : ", not yet"}. {b.sr}</span>
        </li>
      ))}
    </ul>
  );
}

export default function PlanHero({ plan, base, list = [], retireAge }: { plan: Plan; base?: Plan; list?: Move[]; retireAge?: number | null }) {
  const level = planLevel(plan);
  const kind = verdictKind(plan);
  const ring = ringOf(plan);
  const ringBase = base ? ringOf(base) : null;
  const gap = yearlyGap(plan, base ? goalOf(base) : null);
  const goal = goalOf(plan) ?? (base ? goalOf(base) : null);
  const retired = plan.already_retired ?? false;
  const age = retireAge ?? plan.costs_by_age?.retire_age ?? null;
  const line = verdictLine(kind, gap, age, retired);
  // The verdict says a Close or Not yet shortfall itself. The banner only adds the number when the verdict does not: needs not safe.
  const big = gap > 0 && kind === "basics" ? `Short ${usd(gap)} a year` : null;
  const kf = base ? { now: keyFigures(plan, base), was: keyFigures(base, base) } : null;
  const closes = !!kf && kf.was.gap != null && kf.was.gap > 0 && kf.now.gap === 0;
  return (
    <section className={`hero hero-${level}`} aria-labelledby="verdict-h" data-testid="plan-hero" data-verdict={kind}>
      <div className="hero-ring">
        <Ring value={ring.value} kind={ring.kind} level={level} before={ringBase && ringBase.kind === ring.kind ? ringBase.value : null} />
        {ringBase && ringBase.kind === ring.kind && <VsMarker testid="vs-ready" d={ring.value - ringBase.value} unit={(n) => `${n} point${n === 1 ? "" : "s"}`} />}
        <details className="score-how">
          <summary>{PLAN_WORDS.scoreHow}</summary>
          <p>{ring.kind === "ready" ? PLAN_WORDS.scoreTip : PLAN_WORDS.noGoalTip}</p>
          {ring.kind === "ready" && goal != null && <p className="num score-sum">{usd(plan.wants.per_year)} ÷ {usd(goal)} = {readinessShare(plan)} of 100{readinessShare(plan) !== ring.value && <> → {ring.value}. {PLAN_WORDS.cappedNote}</>}</p>}
        </details>
      </div>
      <div className="hero-main">
        {level !== "ok" ? (
          <div className={`shortfall shortfall-${level}`} role="group" aria-label={level === "short" ? "Shortfall" : "Close to short"} data-testid="shortfall" data-level={level}>
            <span className="shortfall-icon" aria-hidden="true">{LEVEL_ICON[level]}</span>
            <div>
              <h3 id="verdict-h" className={`verdict verdict-${level}`} data-testid="verdict">{line}</h3>
              {big && <p className="shortfall-big num" data-testid="shortfall-big">{big}</p>}
            </div>
          </div>
        ) : (
          <>
            <h3 id="verdict-h" className={`verdict verdict-${level}`} data-testid="verdict">{line}</h3>
            <div className="hero-good" data-testid="hero-big">
              <span className="hero-ok-icon" aria-hidden="true">{LEVEL_ICON.ok}</span>
              <div>
                <p className="hero-num num">{usd(plan.wants.per_year)} <span className="hero-unit">a year</span></p>
                <p className="hero-sub">you can count on.</p>
              </div>
            </div>
          </>
        )}
        {kf && kf.now.gap != null && kf.was.gap != null && (
          <p className="vs-row" data-testid="vs-goal"><span className="sr-only">Short of your goal: {kf.now.gap > 0 ? usd(kf.now.gap) : "none"}.</span><VsMarker testid="vs-gap" good="down" d={kf.now.gap - kf.was.gap} unit={(n, up) => `${usd(n)} ${up ? "more short" : "less short"}`} /></p>
        )}
        {closes && <p className="closes" role="status" data-testid="closes-gap"><span className="closes-check" aria-hidden="true">{"✓"}</span> {PLAN_WORDS.closesGap}</p>}
        <Ladder plan={plan} base={base} moves={list} hideCountOn={level === "ok"} />
        {plan.headline && <Clamp text={plan.headline} words={18} className="headline hero-why" testid="plan-headline" />}
        {plan.headline && plan.headline_why && <details className="headline-why small muted" data-testid="headline-why"><summary>Why?</summary><p>{plan.headline_why}</p></details>}
      </div>
      <div className="hero-foot">
        <Badges plan={plan} />
      </div>
    </section>
  );
}
