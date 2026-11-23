import { usd, usdShort } from "../format";
import { LEVEL_ICON } from "../shortfall";
import type { Analysis, AnalysisRow } from "../types";
import { useReadout, useWidth } from "./useReadout";

// "The analysis": a closed expander under the plan's actions. It answers four questions a person asks before acting:
// how sure is it, what could go wrong, what is each choice worth, where does the money come from. One sentence, two
// small tables and one chart. Every figure comes from the server (app/analysis.py); the server still works out
// everything, and only the display is short.

type Sure = Analysis["how_sure"];
type Src = Analysis["sources"];

/** Most rows either table shows. */
export const MAX_ROWS = 3;
/** A choice shows only if it adds this much a year to what you can count on, or this many more basics paid of 100. */
export const MIN_GAIN_PER_YEAR = 500;
export const MIN_GAIN_BASICS = 5;
/** Below this many of 100, the plan already falls short and the stress tests would only pile on. */
export const SAFE_OF_100 = 90;

/** "Spending $X a year lasts in 75 of 100 market tests; $Y lasts in 95." Falls back to the server's sentence. */
export function sureSentence(s: Sure): string {
  const at = (n: number) => s.levels.find((l) => l.of_100 === n)?.per_year ?? 0;
  const a = at(75), b = at(95);
  if (a <= 0 || b <= 0) return s.line;
  return `Spending ${usd(a)} a year lasts in 75 of 100 market tests; ${usd(b)} lasts in 95.`;
}

const RISK_WORDS: Record<string, string> = {
  bad_decade: "Stocks do badly for 10 years",
  inflation: "Prices rise faster for 10 years",
};

/** The risks that hurt this plan most: only those that cut what you can count on, worst first, three at most. */
export function topRisks(rows: AnalysisRow[]): AnalysisRow[] {
  return rows.filter((r) => r.count_on_change < 0 || r.basics_change < 0)
    .sort((a, b) => a.count_on_change - b.count_on_change || a.basics_change - b.basics_change)
    .slice(0, MAX_ROWS);
}

/** The risks to show: the server's own top three (it works out the sentences), else the worst three by the figures. */
export function shownRisks(s: Analysis["stresses"]): AnalysisRow[] {
  if (!s.top) return topRisks(s.rows);
  return s.top.map((k) => s.rows.find((r) => r.key === k)).filter((r): r is AnalysisRow => !!r).slice(0, MAX_ROWS);
}

/** The choices worth a look: a real gain, best first, three at most. */
export function topChoices(rows: AnalysisRow[]): AnalysisRow[] {
  return rows.filter((r) => r.count_on_change >= MIN_GAIN_PER_YEAR || r.basics_change >= MIN_GAIN_BASICS)
    .sort((a, b) => b.count_on_change - a.count_on_change || b.basics_change - a.basics_change)
    .slice(0, MAX_ROWS);
}

// Four sources, as a person thinks of them: pay, Social Security, pensions and annuity, savings. The amber band is what
// they do not cover.
const MERGE: Record<string, { key: string; label: string }> = {
  pay: { key: "pay", label: "Pay" },
  ss_you: { key: "ss", label: "Social Security" }, ss_partner: { key: "ss", label: "Social Security" },
  pension: { key: "pension", label: "Pensions and annuity" }, annuity: { key: "pension", label: "Pensions and annuity" },
  savings: { key: "savings", label: "From savings" },
  short: { key: "short", label: "Not covered: savings run out" },
};
const ORDER = ["pay", "ss", "pension", "savings", "short"];

export function mergeSources(src: Src): Src {
  const by = new Map<string, { key: string; label: string; values: number[] }>();
  for (const s of src.series) {
    const m = MERGE[s.key] ?? { key: s.key, label: s.label };
    const cur = by.get(m.key) ?? { key: m.key, label: m.label, values: new Array(src.ages.length).fill(0) };
    s.values.forEach((v, i) => { cur.values[i] += v; });
    by.set(m.key, cur);
  }
  const series = [...by.values()].sort((a, b) => ORDER.indexOf(a.key) - ORDER.indexOf(b.key));
  return { ...src, series };
}

const SERIES_CLASS: Record<string, string> = {
  pay: "s-pay", ss: "s-ss-you", pension: "s-pension", savings: "s-savings", short: "s-short",
};

/** One year of "where the money comes from", as figures and words. */
export function sourcesReadout(s: Src, i: number) {
  const parts = s.series.map((x) => ({ key: x.key, label: x.label, value: x.values[i] ?? 0 })).filter((p) => p.value >= 1);
  const surplus = s.surplus[i] ?? 0;
  const text = `Age ${s.ages[i]}. Spending ${usd(s.spending[i])} a year. ${parts.map((p) => `${p.label}: ${usd(p.value)}`).join(". ")}.${surplus >= 1 ? ` Saved: ${usd(surplus)} more than you spend.` : ""} After tax, in today's dollars.`;
  return { age: s.ages[i], spending: s.spending[i], parts, surplus, text };
}

export function SourcesChart({ src: raw }: { src: Src }) {
  const src = mergeSources(raw);
  const { box, w } = useWidth();
  const { ages, series } = src;
  const n = ages.length;
  const h = 210, pad = { l: 48, r: 12, t: 14, b: 26 };
  const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
  const a0 = ages[0], a1 = ages[n - 1];
  const x = (a: number) => pad.l + ((a - a0) / (a1 - a0 || 1)) * iw;
  const { hi, setHover, pick, onKey } = useReadout(n, (px) => Math.round(((px - pad.l) / iw) * (n - 1)));
  if (n < 2 || !series.length) return null;
  const stackTop = ages.map((_, i) => series.reduce((t, s) => t + (s.values[i] ?? 0), 0));
  const top = Math.max(...stackTop, ...src.spending, 1) * 1.06;
  const y = (v: number) => pad.t + ih - (Math.max(0, v) / top) * ih;
  const base = new Array(n).fill(0);
  const areas = series.map((s) => {
    const lo = base.slice();
    for (let i = 0; i < n; i++) base[i] += s.values[i] ?? 0;
    const up = ages.map((a, i) => `${i ? "L" : "M"}${x(a).toFixed(1)} ${y(base[i]).toFixed(1)}`).join("");
    const down = ages.slice().reverse().map((a, j) => `L${x(a).toFixed(1)} ${y(lo[n - 1 - j]).toFixed(1)}`).join("");
    return { key: s.key, d: `${up}${down}Z` };
  });
  const spendPath = ages.map((a, i) => `${i ? "L" : "M"}${x(a).toFixed(1)} ${y(src.spending[i]).toFixed(1)}`).join("");
  const step = w < 480 ? 10 : 5;
  const r = hi != null ? sourcesReadout(src, hi) : null;
  const hx = hi != null ? x(ages[hi]) : 0;
  const right = hx < w / 2;
  return (
    <figure className="chart an-chart">
      <figcaption className="chart-title">Where each year's spending comes from</figcaption>
      <ul className="an-legend" aria-label="Key">
        {series.map((s) => <li key={s.key}><span className={`an-swatch ${SERIES_CLASS[s.key] ?? ""}`} aria-hidden="true" />{s.label}</li>)}
        <li><span className="key key-line an-key-spend" aria-hidden="true" />Spending</li>
      </ul>
      <div className="chart-box" ref={box}>
        <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" tabIndex={0} data-testid="sources-chart"
          aria-label={`Where each year's spending comes from, by age. ${src.line} Use the arrow keys to read each age.`}
          onKeyDown={onKey}>
          <defs>
            <pattern id="an-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" className="an-hatch-bg" />
              <line x1="0" y1="0" x2="0" y2="6" className="an-hatch-line" />
            </pattern>
          </defs>
          {[0, 0.5, 1].map((f) => <g key={f}><line x1={pad.l} x2={w - pad.r} y1={y(f * top)} y2={y(f * top)} className="grid" /><text x={pad.l - 8} y={y(f * top) + 4} textAnchor="end" className="axis">{usdShort(f * top)}</text></g>)}
          {ages.filter((a) => a % step === 0).map((a) => <text key={a} x={x(a)} y={h - 8} textAnchor="middle" className="axis">{a}</text>)}
          {areas.map((a) => <path key={a.key} pointerEvents="none" d={a.d} className={`an-area ${SERIES_CLASS[a.key] ?? ""}`} />)}
          <path d={spendPath} className="an-spend" pointerEvents="none" />
          {hi != null && <line x1={hx} x2={hx} y1={pad.t} y2={pad.t + ih} className="cross" pointerEvents="none" />}
          {/* one overlay takes every pointer event; the marks never steal the hover, and a finger can tap or drag */}
          <rect x={0} y={0} width={w} height={h} fill="transparent" data-testid="sources-hit" style={{ touchAction: "pan-y" }}
            onPointerMove={(e) => pick(e.clientX, (e.currentTarget.ownerSVGElement ?? e.currentTarget).getBoundingClientRect(), w)}
            onPointerDown={(e) => pick(e.clientX, (e.currentTarget.ownerSVGElement ?? e.currentTarget).getBoundingClientRect(), w)}
            onPointerLeave={(e) => { if (e.pointerType === "mouse") setHover(null); }} />
        </svg>
        {r && (
          <div className="tip tip-costs" data-testid="sources-tip" style={{ left: right ? hx + 10 : hx - 10, transform: right ? "none" : "translateX(-100%)", top: pad.t }}>
            <strong>Age {r.age}: spending {usd(r.spending)}</strong>
            {r.parts.map((p) => <span key={p.key} className="muted tip-part"><span className={`an-swatch ${SERIES_CLASS[p.key] ?? ""}`} aria-hidden="true" /><span>{p.label}</span> <span className="num">{usd(p.value)}</span></span>)}
            {r.surplus >= 1 && <span className="muted">Saved: {usd(r.surplus)} more than you spend</span>}
          </div>
        )}
        <div className="sr-only" aria-live="polite" data-testid="sources-live">{r ? r.text : ""}</div>
      </div>
    </figure>
  );
}

export default function AnalysisSection({ analysis, level = "short" }: { analysis?: Analysis | null; level?: "short" | "close" | "ok" }) {
  if (!analysis) return null;
  const falls = analysis.plan_basics_paid_of_100 < SAFE_OF_100;
  const gap = Math.max(0, Math.round(analysis.how_sure.goal_per_year - analysis.how_sure.count_on_per_year));
  const risks = falls ? [] : shownRisks(analysis.stresses);
  const choices = topChoices(analysis.levers.rows);
  const grouped = !!analysis.stresses.lead && risks.length > 1 && risks.every((r) => !!r.short);
  const allPaid = risks.length > 0 && risks.every((r) => r.sentence && r.basics_paid_of_100 >= 100);
  const all100 = !allPaid ? "" : risks.length === 1 ? "Your needs stay paid in every path." : `In ${risks.length === 2 ? "both" : "all three"}, your needs stay paid in every path.`;
  return (
    <details className="worth-checking analysis" data-testid="plan-analysis">
      <summary>The analysis</summary>
      <p className="muted small">{analysis.paths.toLocaleString("en-US")} market tests, in today's dollars. Chances, not promises.</p>

      <section className="an-part" aria-labelledby="an-sure-h">
        <h4 id="an-sure-h" className="an-h">How sure is it?</h4>
        <p data-testid="an-sure">{sureSentence(analysis.how_sure)}</p>
        {gap > 0 && level !== "ok" && <p className={`an-gap an-gap-${level}`} data-testid="an-gap"><span aria-hidden="true">{LEVEL_ICON.short}</span> Short {usd(gap)} a year <span className="an-gap-sub">Your goal is {usd(analysis.how_sure.goal_per_year)}; you can count on {usd(analysis.how_sure.count_on_per_year)}.</span></p>}
      </section>

      <section className="an-part" aria-labelledby="an-wrong-h">
        <h4 id="an-wrong-h" className="an-h">What could go wrong?</h4>
        {falls ? (
          <p className="an-fall" data-testid="an-short"><span aria-hidden="true">{LEVEL_ICON.short}</span> Your plan pays your needs in {analysis.plan_basics_paid_of_100} of 100 market tests, so it already falls short. Fix that first.</p>
        ) : risks.length > 0 ? (
          <>
          {grouped && <p data-testid="an-lead">{analysis.stresses.lead}</p>}
          <ul className="an-risks" data-testid="an-stresses">
            {risks.map((r) => grouped ? (
              <li key={r.key} className={r.basics_at_risk ? "an-risk an-risk-warn" : "an-risk"} data-at-risk={r.basics_at_risk ? "true" : undefined}>
                <strong>{r.label || RISK_WORDS[r.key] || r.title}:</strong> {r.short}
              </li>
            ) : (
              <li key={r.key} className={r.basics_at_risk ? "an-risk an-risk-warn" : "an-risk"} data-at-risk={r.basics_at_risk ? "true" : undefined}>
                <strong>{r.label || RISK_WORDS[r.key] || r.title}.</strong>{" "}
                {r.basics_at_risk && <span className="sr-only">Needs at risk. </span>}
                {r.sentence || `You could count on ${usd(r.count_on_per_year)} a year, and your needs are paid in ${r.basics_paid_of_100} of 100 market tests.`}
              </li>
            ))}
          </ul>
          </>
        ) : null}
        {all100 && <p className="muted small" data-testid="an-basics-all">{all100}</p>}
      </section>

      {choices.length > 0 && (
        <section className="an-part" aria-labelledby="an-worth-h">
          <h4 id="an-worth-h" className="an-h">What each choice is worth</h4>
          <div className="table-scroll">
            <table className="an-table" data-testid="an-levers">
              <caption className="sr-only">Choices that change what you can count on</caption>
              <thead><tr><th scope="col">Choice</th><th scope="col">Adds a year to what you can count on</th></tr></thead>
              <tbody>{choices.map((r) => (
                <tr key={r.key}>
                  <th scope="row">{r.title}</th>
                  <td className="num">{r.count_on_change >= MIN_GAIN_PER_YEAR ? `+${usd(r.count_on_change)}` : "Little"}{r.basics_change >= MIN_GAIN_BASICS && <span className="muted small"> · needs paid in {r.basics_change} more of 100</span>}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </section>
      )}

      <section className="an-part" aria-labelledby="an-src-h">
        <h4 id="an-src-h" className="an-h">Where the money comes from</h4>
        <p>{analysis.sources.line}</p>
        <SourcesChart src={analysis.sources} />
      </section>
    </details>
  );
}
