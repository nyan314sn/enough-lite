import { usd } from "../format";
import { LevelMark, basicsLevel } from "../shortfall";
import type { Plan } from "../types";
import { keyFigures } from "./WhatIf";

// "Compare": all tabs side by side. Baseline first; each What If shows its change from the baseline beside the figure.

export interface Col { key: string; label: string; full?: string; plan: Plan; retire?: number | null }

function Chg({ d, good = "up", fmt }: { d: number; good?: "up" | "down"; fmt: (n: number, up: boolean) => string }) {
  if (Math.round(d) === 0) return <span className="delta same">no change</span>;
  const up = d > 0, better = (up ? "up" : "down") === good;
  return <span className={`delta ${better ? "up" : "down"}`}>{up ? "▲" : "▼"} {fmt(Math.abs(d), up)}<span className="sr-only">, {better ? "better" : "worse"}</span></span>;
}

export default function CompareTable({ cols, onOpen }: { cols: Col[]; onOpen: (key: string) => void }) {
  const base = cols[0];
  const figs = cols.map((c) => keyFigures(c.plan, base.plan));
  const bf = figs[0];
  const hasGoal = figs.some((f) => f.gap != null);
  const hasLasts = figs.some((f) => f.goalLasts != null);
  const hasRetire = cols.some((c) => c.retire != null);
  return (
    <section className="card compare-view" aria-labelledby="cmp-h" data-testid="compare-view">
      <h2 id="cmp-h" className="h-screen">Compare</h2>
      <p className="muted small">The baseline first. Each What If changes one thing in the baseline, nothing else.</p>
      <div className="table-scroll">
        <table className="compare compare-all" data-testid="compare-table">
          <caption className="sr-only">Baseline and each What If, side by side</caption>
          <thead>
            <tr>
              <th scope="col"><span className="sr-only">Measure</span></th>
              {cols.map((c, i) => (
                <th key={c.key} scope="col" className={i === 0 ? "col-base" : undefined}>
                  <button type="button" className="cmp-open" onClick={() => onOpen(c.key)} title={i === 0 ? undefined : c.full ?? c.label}>{i === 0 ? "Baseline" : c.label}</button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {hasRetire && (
              <tr><th scope="row">Retire at</th>{cols.map((c) => <td key={c.key} className="num">{c.retire ?? "—"}</td>)}</tr>
            )}
            <tr>
              <th scope="row">Basics paid, of 100</th>
              {cols.map((c, i) => {
                const lv = basicsLevel(figs[i].paid);
                return <td key={c.key} className={`num${lv !== "ok" ? ` cell-${lv}` : ""}`}><span>{figs[i].paid} of 100</span> <LevelMark level={lv} />{i > 0 && <Chg d={figs[i].paid - bf.paid} fmt={(n, up) => `${n} ${up ? "more" : "fewer"}`} />}</td>;
              })}
            </tr>
            <tr>
              <th scope="row">You can count on, a year</th>
              {cols.map((c, i) => <td key={c.key} className="num"><span>{usd(figs[i].countOn)}</span>{i > 0 && <Chg d={figs[i].countOn - bf.countOn} fmt={(n, up) => `${usd(n)} ${up ? "more" : "less"}`} />}</td>)}
            </tr>
            <tr>
              <th scope="row">Basics a year</th>
              {cols.map((c, i) => <td key={c.key} className="num"><span>{usd(figs[i].basics)}</span></td>)}
            </tr>
            {hasGoal && (
              <tr data-testid="gap-row">
                <th scope="row">Short of your goal, a year</th>
                {cols.map((c, i) => {
                  const g = figs[i].gap;
                  return <td key={c.key} className={`num${g ? " cell-short" : ""}`}><span className={g ? "gap-big" : undefined}>{g == null ? "—" : g > 0 ? `Short ${usd(g)}` : "None"}</span>{g != null && bf.gap != null && i > 0 && <Chg d={g - bf.gap} good="down" fmt={(n, up) => `${usd(n)} ${up ? "more short" : "less short"}`} />}</td>;
                })}
              </tr>
            )}
            {hasLasts && (
              <tr>
                <th scope="row">Goal lasts in, of 100</th>
                {cols.map((c, i) => {
                  const g = figs[i].goalLasts;
                  return <td key={c.key} className="num"><span>{g == null ? "—" : `${g} of 100`}</span>{g != null && bf.goalLasts != null && i > 0 && <Chg d={g - bf.goalLasts} fmt={(n, up) => `${n} ${up ? "more" : "fewer"}`} />}</td>;
                })}
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
