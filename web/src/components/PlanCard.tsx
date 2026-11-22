import AnalysisSection from "./AnalysisSection";
import SavingsChart from "./SavingsChart";
import CostsChart from "./CostsChart";
import { usd } from "../format";
import { LevelMark, ShortfallBanner, basicsLevel, planLevel, goalOf } from "../shortfall";
import { VsMarker, actionIsNew, keyFigures } from "./WhatIf";
import type { Plan } from "../types";

// The plan: needs, wants, wishes, three things to do, family moments, and savings by age.

/** The adviser's first action repeats the starting points in a long sentence; the box above it already says it, so cut that tail. */
export function withoutRepeat(why: string, hasPoints: boolean): string {
  return hasPoints ? why.replace(/s*Starting points:.*$/s, "").trim() : why;
}

/** How many assumptions show at first; the rest sit behind "More assumptions". */
export const ASSUMPTIONS_SHOWN = 4;

/** A What If tab shows this same view: pass the baseline plan to mark each key figure "vs baseline", and the one line of what changed. */
export interface Scenario { name: string; baseline: Plan; change: string; /** The full reply, kept once, under "Why". */ text?: string; citations?: { title: string; url: string }[] }

export default function PlanCard({ plan, retireAge, onTry, scenario }: { plan: Plan; retireAge?: number | null; onTry?: (q: string) => void; scenario?: Scenario }) {
  const base = scenario?.baseline;
  const kf = base ? { now: keyFigures(plan, base), was: keyFigures(base, base) } : null;
  const isNew = base ? actionIsNew(base, plan) : () => false;
  const oldMoments = new Set(base?.family_moments ?? []);
  const showGoal = !!kf && (kf.now.gap != null || kf.now.goalLasts != null) && (goalOf(plan) != null || goalOf(base!) != null);
  const retired = plan.already_retired ?? false;
  const points = plan.starting_points ?? [];
  const assumptions = plan.assumptions ?? [];
  return (
    <article className="plan card" aria-labelledby="plan-h">
      <h2 id="plan-h" className="h-screen">{scenario ? <><span className="muted">What if:</span> {scenario.name}</> : "Baseline plan"}{retireAge && !retired ? <span className="muted"> · retire at {retireAge}</span> : null}</h2>
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
      <ShortfallBanner plan={plan} />
      {plan.headline && <p className="headline" data-testid="plan-headline">{plan.headline}</p>}
      {plan.headline && <p className="muted small dollars-note">All figures are in today's dollars.</p>}
      {points.length > 0 && (
        <section className="starting-points" aria-labelledby="points-h">
          <h3 id="points-h" className="h-sub">Starting points</h3>
          <ul>
            {points.map((x) => (
              <li key={x.title}>
                <span><strong>{x.title}:</strong> {x.result}.</span>
                {onTry && x.whatif_text && <button type="button" className="btn btn-quiet btn-small" onClick={() => onTry(x.whatif_text)}>Try this<span className="sr-only">: {x.title}</span></button>}
              </li>
            ))}
          </ul>
        </section>
      )}
      {showGoal && kf && (
        <dl className="vs-goal" data-testid="vs-goal" aria-label="Your goal, against the baseline">
          {kf.now.gap != null && kf.was.gap != null && (
            <div><dt>Short of your goal, a year</dt><dd><strong className="num">{kf.now.gap > 0 ? usd(kf.now.gap) : "None"}</strong> <VsMarker testid="vs-gap" good="down" d={kf.now.gap - kf.was.gap} unit={(n, up) => `${usd(n)} ${up ? "more short" : "less short"}`} /></dd></div>
          )}
          {kf.now.goalLasts != null && kf.was.goalLasts != null && (
            <div><dt>Your goal lasts in</dt><dd><strong className="num">{kf.now.goalLasts} of 100</strong> <VsMarker testid="vs-lasts" d={kf.now.goalLasts - kf.was.goalLasts} unit={(n, up) => `${n} ${up ? "more" : "fewer"} of 100`} /></dd></div>
          )}
        </dl>
      )}
      <div className="nww">
        <section className={`nww-item nww-needs ${basicsLevel(plan.needs.paid_of_100) === "ok" ? "safe" : basicsLevel(plan.needs.paid_of_100) === "close" ? "close" : "risk"}`} aria-label="Needs">
          <p className="eyebrow">Needs <LevelMark level={basicsLevel(plan.needs.paid_of_100)} /></p>
          <p className="big"><span className="num">{plan.needs.paid_of_100}</span><span className="of"> of 100</span></p>
          {kf && <p className="vs-row"><VsMarker testid="vs-paid" d={kf.now.paid - kf.was.paid} unit={(n, up) => `${n} ${up ? "more" : "fewer"} of 100`} /></p>}
          <p className="nww-sub">scenarios pay your basics, about {usd(plan.needs.basics_per_year)} a year</p>
          <p className="nww-line">{plan.needs.line}</p>
        </section>
        <section className="nww-item nww-wants" aria-label="Wants">
          <p className="eyebrow">Wants</p>
          <p className="big"><span className="num">{usd(plan.wants.per_year)}</span></p>
          <p className="nww-sub">a year you can count on</p>
          {kf && <p className="vs-row"><VsMarker testid="vs-count" d={kf.now.countOn - kf.was.countOn} unit={(n, up) => `${usd(n)} ${up ? "more" : "less"} a year`} /></p>}
          {plan.wants.line !== plan.headline && <p className="nww-line">{plan.wants.line}</p>}
        </section>
        <section className="nww-item nww-wishes" aria-label="Wishes">
          <p className="eyebrow">Wishes</p>
          <p className="nww-line nww-wish">{plan.wishes.line}</p>
        </section>
      </div>

      <section aria-labelledby="actions-h">
        <h3 id="actions-h" className="h-sub">Three things to do</h3>
        <ol className="actions">
          {plan.actions.slice(0, 3).map((a, i) => (
            <li key={i} className={isNew(a.title) ? "new" : undefined}><span className="action-n" aria-hidden="true">{i + 1}</span><div><strong>{a.title}</strong>{isNew(a.title) && <span className="new-tag">new</span>}<p>{i === 0 ? withoutRepeat(a.why, points.length > 0) : a.why}</p></div></li>
          ))}
        </ol>
      </section>

      <AnalysisSection analysis={plan.analysis} onTry={onTry} level={planLevel(plan)} />

      {(plan.worth_checking ?? []).length > 0 && (
        <details className="worth-checking">
          <summary>Worth checking</summary>
          <ul className="moments">
            {(plan.worth_checking ?? []).map((w) => <li key={w.kind}><strong>{w.title}.</strong> {w.why}</li>)}
          </ul>
        </details>
      )}

      {plan.family_moments.length > 0 && (
        <section aria-labelledby="moments-h">
          <h3 id="moments-h" className="h-sub">Family moments</h3>
          <ul className="moments">{plan.family_moments.map((m, i) => { const fresh = !!base && !oldMoments.has(m); return <li key={i} className={fresh ? "new" : undefined}>{m}{fresh && <span className="new-tag">new</span>}</li>; })}</ul>
        </section>
      )}

      <SavingsChart chart={plan.chart} before={base?.chart} retireAge={retired ? null : retireAge} title={scenario ? "Savings by age, what if" : undefined} />
      <CostsChart costs={plan.costs_by_age} retireAge={retired ? null : retireAge} />
      {plan.neighbors?.used && plan.neighbors.note && <p className="muted small">Similar households: {plan.neighbors.note}</p>}

      {assumptions.length > 0 && (
        <details className="worth-checking assumptions" data-testid="plan-assumptions">
          <summary>Assumptions</summary>
          <ul className="moments">{assumptions.slice(0, ASSUMPTIONS_SHOWN).map((a, i) => <li key={i}>{a}</li>)}</ul>
          {onTry && (plan.assumption_changes ?? []).length > 0 && (
            <p className="assumption-changes">
              {(plan.assumption_changes ?? []).map((c) => (
                <button key={c.q} type="button" className="btn btn-quiet btn-small" onClick={() => onTry(c.q)}>{c.label}</button>
              ))}
            </p>
          )}
          {assumptions.length > ASSUMPTIONS_SHOWN && (
            <details className="more-assumptions">
              <summary>More assumptions ({assumptions.length - ASSUMPTIONS_SHOWN})</summary>
              <ul className="moments">{assumptions.slice(ASSUMPTIONS_SHOWN).map((a, i) => <li key={i}>{a}</li>)}</ul>
            </details>
          )}
        </details>
      )}
    </article>
  );
}
