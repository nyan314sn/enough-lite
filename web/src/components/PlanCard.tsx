import { type ReactNode } from "react";
import AnalysisSection from "./AnalysisSection";
import SavingsChart from "./SavingsChart";
import CostsChart from "./CostsChart";
import PlanHero from "./PlanHero";
import Moves, { withoutRepeat } from "./Moves";
import { planLevel } from "../shortfall";
import { PLAN_WORDS, movesOf } from "../readiness";
import { actionIsNew } from "./WhatIf";
import type { Plan } from "../types";

// The plan (feedback round B, R26): the answer at a glance (verdict, readiness ring, bar to the goal, badges), the money ladder (needs, wants, wishes), the next moves as a
// checklist, the savings chart, and everything else folded under "More details".

export { withoutRepeat };

/** How many assumptions show at first; the rest sit behind "More assumptions". */
export const ASSUMPTIONS_SHOWN = 4;

/** A What If tab shows this same view: pass the baseline plan to mark each key figure "vs baseline", and the one line of what changed. */
export interface Scenario { name: string; baseline: Plan; change: string; /** The full reply, kept once, under "Why". */ text?: string; citations?: { title: string; url: string }[] }

function Fold({ title, testid, className = "", children }: { title: string; testid?: string; className?: string; children: ReactNode }) {
  return <details className={`worth-checking fold ${className}`} data-testid={testid}><summary>{title}</summary><div className="fold-body">{children}</div></details>;
}

export default function PlanCard({ plan, retireAge, scenario }: { plan: Plan; retireAge?: number | null; scenario?: Scenario }) {
  const base = scenario?.baseline;
  const isNew = base ? actionIsNew(base, plan) : () => false;
  const oldMoments = new Set(base?.family_moments ?? []);
  const retired = plan.already_retired ?? false;
  const assumptions = plan.assumptions ?? [];
  const moves = movesOf(plan);
  return (
    <article className="plan card plan-b" aria-labelledby="plan-h" data-level={planLevel(plan)}>
      <h2 id="plan-h" className="h-screen plan-title">{scenario ? <><span className="muted">What if:</span> {scenario.name}</> : "Baseline plan"}{retireAge && !retired ? <span className="muted"> · retire at {retireAge}</span> : null}</h2>
      {scenario && (
        <div className="wi-change" data-testid="wi-change">
          <p className="wi-line"><strong>What changed:</strong> {scenario.change}</p>
          {scenario.text && <details className="wi-why"><summary>Why</summary><p className="wi-text">{scenario.text}</p></details>}
          {(scenario.citations ?? []).length > 0 && (
            <details className="wi-why" data-testid="wi-sources"><summary>Sources</summary>
              <ul className="moments">{(scenario.citations ?? []).map((c, i) => <li key={i}><a href={c.url} target="_blank" rel="noreferrer noopener">{c.title}</a></li>)}</ul>
            </details>
          )}
        </div>
      )}

      <PlanHero plan={plan} base={base} retireAge={retireAge} list={moves} />
      <p className="muted small dollars-note">{PLAN_WORDS.dollars}</p>

      <Moves moves={moves} isNew={isNew} />

      <SavingsChart chart={plan.chart} before={base?.chart} retireAge={retired ? null : retireAge} title={scenario ? `${PLAN_WORDS.chartTitle}, what if` : PLAN_WORDS.chartTitle} />

      <section className="plan-more" aria-labelledby="more-h">
        <h3 id="more-h" className="h-sub">{PLAN_WORDS.detailsTitle}</h3>
        <p className="sec-line">{PLAN_WORDS.detailsLine}</p>
        <div className="more-list">
          <Fold title={PLAN_WORDS.meaning} testid="plan-meaning">
            <ul className="moments">
              <li><strong>Needs.</strong> {plan.needs.line}</li>
              {plan.wants.line !== plan.headline && <li><strong>Wants.</strong> {plan.wants.line}</li>}
              <li><strong>Wishes.</strong> {plan.wishes.line}</li>
            </ul>
          </Fold>

          <AnalysisSection analysis={plan.analysis} level={planLevel(plan)} />

          {plan.costs_by_age && (
            <Fold title={PLAN_WORDS.costs} testid="plan-costs">
              <CostsChart costs={plan.costs_by_age} retireAge={retired ? null : retireAge} />
            </Fold>
          )}

          {plan.family_moments.length > 0 && (
            <Fold title={`${PLAN_WORDS.moments} (${plan.family_moments.length})`} testid="plan-moments">
              <ul className="moments">{plan.family_moments.map((m, i) => { const fresh = !!base && !oldMoments.has(m); return <li key={i} className={fresh ? "new" : undefined}>{m}{fresh && <span className="new-tag">new</span>}</li>; })}</ul>
            </Fold>
          )}

          {(plan.worth_checking ?? []).length > 0 && (
            <Fold title={PLAN_WORDS.checking}>
              <ul className="moments">
                {(plan.worth_checking ?? []).map((w) => <li key={w.kind}><strong>{w.title}.</strong> {w.why}</li>)}
              </ul>
            </Fold>
          )}

          {assumptions.length > 0 && (
            <details className="worth-checking fold assumptions" data-testid="plan-assumptions">
              <summary>Assumptions</summary>
              <ul className="moments">{assumptions.slice(0, ASSUMPTIONS_SHOWN).map((a, i) => <li key={i}>{a}</li>)}</ul>
              {assumptions.length > ASSUMPTIONS_SHOWN && (
                <details className="more-assumptions">
                  <summary>More assumptions ({assumptions.length - ASSUMPTIONS_SHOWN})</summary>
                  <ul className="moments">{assumptions.slice(ASSUMPTIONS_SHOWN).map((a, i) => <li key={i}>{a}</li>)}</ul>
                </details>
              )}
            </details>
          )}
        </div>
        {plan.neighbors?.used && plan.neighbors.note && <p className="muted small">Similar households: {plan.neighbors.note}</p>}
      </section>
    </article>
  );
}
