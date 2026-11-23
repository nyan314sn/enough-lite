import { useEffect, useId, useRef, useState, type KeyboardEvent as KeyEv } from "react";
import { usd, usdShort } from "../format";
import type { Plan } from "../types";

// Savings by age: the middle path as a line, the low-high range as a soft band. Hand-written SVG, no chart library.
// Hover or touch shows the figures for one age; the same figures are in a table under "See the numbers".
// With `before`, the old middle path is drawn as a dashed line for a What If.

type Chart = Plan["chart"];

/** A round step for about four gridlines: 1, 2, 2.5 or 5 times a power of ten. */
function niceStep(v: number): number {
  const raw = Math.max(v, 1) / 4;
  const p = 10 ** Math.floor(Math.log10(raw));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= raw) return m * p;
  return 10 * p;
}

/** The chart in words, for a screen reader: where the middle path starts, peaks and ends, and the range at the end. The full table sits under the chart. */
export function chartSummary(title: string, c: Chart, retireAge?: number | null): string {
  const { ages, median, low, high } = c;
  const n = ages.length;
  if (n < 2) return title;
  const pk = median.indexOf(Math.max(...median));
  const end = n - 1;
  const atRetire = retireAge != null ? ages.indexOf(retireAge) : -1;
  return `${title}. Typical market: ${usd(median[0])} at age ${ages[0]}${atRetire > 0 ? `, ${usd(median[atRetire])} at retirement, age ${retireAge}` : ""}, highest ${usd(median[pk])} at age ${ages[pk]}, ${usd(median[end])} at age ${ages[end]}. Range at age ${ages[end]}: ${usd(low[end])} to ${usd(high[end])}. The table below lists every five years.`;
}

export default function SavingsChart({ chart, retireAge, before, title = "Savings by age" }: { chart: Chart; retireAge?: number | null; before?: Chart | null; title?: string }) {
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(640);
  const [hover, setHover] = useState<number | null>(null);
  const tid = useId();
  const gid = `grad${tid.replace(/[^a-zA-Z0-9]/g, "")}`;
  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(260, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { ages, median, low, high } = chart;
  const n = ages.length;
  if (n < 2) return <p className="muted">No chart for this plan.</p>;
  const h = w < 480 ? 200 : 240;
  const pad = { l: 52, r: 14, t: 14, b: 28 };
  const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
  const peak = Math.max(...high, ...median, ...(before?.median ?? [0]), 1);
  const stepY = niceStep(peak);
  const top = Math.ceil(peak / stepY) * stepY;
  const a0 = ages[0], a1 = ages[n - 1];
  const x = (a: number) => pad.l + ((a - a0) / (a1 - a0 || 1)) * iw;
  const y = (v: number) => pad.t + ih - (Math.max(0, v) / top) * ih;
  const line = (vals: number[], as = ages) => vals.map((v, i) => `${i ? "L" : "M"}${x(as[i]).toFixed(1)} ${y(v).toFixed(1)}`).join("");
  const bandPath = high.map((v, i) => `${i ? "L" : "M"}${x(ages[i]).toFixed(1)} ${y(v).toFixed(1)}`).join("") +
    ages.slice().reverse().map((a, j) => `L${x(a).toFixed(1)} ${y(low[n - 1 - j]).toFixed(1)}`).join("") + "Z";
  const ticksY = Array.from({ length: Math.round(top / stepY) + 1 }, (_, i) => i * stepY);
  const step = w < 480 ? 10 : 5;
  const ticksX = ages.filter((a) => a % step === 0);

  const svgRect = (e: { currentTarget: SVGRectElement }) => (e.currentTarget.ownerSVGElement ?? e.currentTarget).getBoundingClientRect();
  const onMove = (clientX: number, rect: DOMRect) => {
    const px = ((clientX - rect.left) / (rect.width || w)) * w;
    const a = Math.round(a0 + ((px - pad.l) / iw) * (a1 - a0));
    setHover(Math.max(0, Math.min(n - 1, a - a0)));
  };
  // Keyboard: arrows step one age, Home and End jump to the ends, Escape hides the readout (the same keys as the costs chart).
  const onKey = (e: KeyEv) => {
    const cur = hover ?? -1;
    let next: number;
    if (e.key === "ArrowRight") next = Math.min(n - 1, cur + 1);
    else if (e.key === "ArrowLeft") next = cur < 0 ? 0 : Math.max(0, cur - 1);
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = n - 1;
    else if (e.key === "Escape") { setHover(null); return; }
    else return;
    e.preventDefault();
    setHover(next);
  };
  const hi = hover != null && hover >= 0 && hover < n ? hover : null;
  const tipLeft = hi != null ? Math.min(Math.max(x(ages[hi]), 80), w - 80) : 0;

  return (
    <figure className="chart">
      <figcaption className="chart-title" id={tid}>{title}
        <span className="legend">
          <span className="key key-line" aria-hidden="true" /> Typical market
          <span className="key key-band" aria-hidden="true" /> Range, weak to strong markets
          {before && <><span className="key key-dash" aria-hidden="true" /> Baseline</>}
        </span>
      </figcaption>
      <div className="chart-box" ref={box}>
        <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" tabIndex={0} aria-label={`${chartSummary(title, chart, retireAge)} Use the arrow keys to read each age.`}
          onKeyDown={onKey}>
          {ticksY.map((v) => (
            <g key={v}>
              <line x1={pad.l} x2={w - pad.r} y1={y(v)} y2={y(v)} className="grid" />
              <text x={pad.l - 8} y={y(v) + 4} textAnchor="end" className="axis">{usdShort(v)}</text>
            </g>
          ))}
          {ticksX.map((a) => <text key={a} x={x(a)} y={h - 8} textAnchor="middle" className="axis">{a}</text>)}
          {retireAge != null && retireAge >= a0 && retireAge <= a1 && (
            <g>
              <line x1={x(retireAge)} x2={x(retireAge)} y1={pad.t} y2={pad.t + ih} className="retire" />
              <text x={x(retireAge) + 5} y={pad.t + 12} className="axis axis-strong">Retire at {retireAge}</text>
            </g>
          )}
          <defs>
            <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1"><stop offset="0" className="grad-top" /><stop offset="1" className="grad-bottom" /></linearGradient>
          </defs>
          <path d={bandPath} className="band" />
          <path d={`${line(median)}L${x(a1).toFixed(1)} ${y(0).toFixed(1)}L${x(a0).toFixed(1)} ${y(0).toFixed(1)}Z`} fill={`url(#${gid})`} className="area-fade" pointerEvents="none" />
          {before && <path d={line(before.median, before.ages)} className="median-before" />}
          <path d={line(median)} className="median" pathLength={1} />
          {hi != null && (
            <g pointerEvents="none">
              <line x1={x(ages[hi])} x2={x(ages[hi])} y1={pad.t} y2={pad.t + ih} className="cross" />
              <circle cx={x(ages[hi])} cy={y(median[hi])} r={4.5} className="dot" />
            </g>
          )}
          {/* one overlay takes every pointer event, so the lines and the readout never steal the hover; a finger can tap or drag */}
          <rect x={0} y={0} width={w} height={h} fill="transparent" data-testid="savings-hit" style={{ touchAction: "pan-y" }}
            onPointerMove={(e) => onMove(e.clientX, svgRect(e))} onPointerDown={(e) => onMove(e.clientX, svgRect(e))}
            onPointerLeave={(e) => { if (e.pointerType === "mouse") setHover(null); }} />
        </svg>
        {hi != null && (
          <div className="tip" style={{ left: tipLeft }} data-testid="savings-tip">
            <strong>Age {ages[hi]}</strong>
            <span>Middle {usd(median[hi])}</span>
            <span className="muted">{usd(low[hi])} to {usd(high[hi])}</span>
          </div>
        )}
        <div className="sr-only" aria-live="polite" data-testid="savings-live">
          {hi != null ? `Age ${ages[hi]}. Typical market ${usd(median[hi])}. Range ${usd(low[hi])} to ${usd(high[hi])}.` : ""}
        </div>
      </div>
      <details className="table-view">
        <summary>See the numbers</summary>
        <div className="table-scroll">
          <table>
            <thead><tr><th scope="col">Age</th><th scope="col">Low</th><th scope="col">Middle</th><th scope="col">High</th></tr></thead>
            <tbody>{ages.map((a, i) => (a % 5 === 0 || i === 0 || i === n - 1) && (
              <tr key={a}><th scope="row">{a}</th><td>{usd(low[i])}</td><td>{usd(median[i])}</td><td>{usd(high[i])}</td></tr>
            ))}</tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
