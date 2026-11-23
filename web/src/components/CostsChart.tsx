import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent as KeyEv } from "react";
import { usd, usdShort } from "../format";
import type { Plan } from "../types";

// "Your costs, now and later": total costs a year against basics, by age, with a marker for each event. Hidden when the plan has no costs_by_age.

type Costs = NonNullable<Plan["costs_by_age"]>;

export function costsLine(c: Costs, retireAge?: number | null): string {
  // "costs now" is the same spending-now figure as the answers panel (the server sends it as now_per_year)
  const now = c.now_per_year ?? c.total[0];
  // already retired: there is no "first year retired" to compare with
  if (retireAge != null && retireAge <= c.ages[0]) return `Costs now: ${usd(now)} a year.`;
  const at = retireAge != null && c.ages.includes(retireAge) ? c.total[c.ages.indexOf(retireAge)] : c.total[c.total.length - 1];
  const goal = c.retired_per_year;
  // the first retired year can cost more than the goal: health cover before Medicare, college or debts come on top of it
  if (goal != null && at > goal * 1.02)
    return `Costs now: ${usd(now)} a year. In your first year retired: about ${usd(at)}, your goal of ${usd(goal)} plus costs on top of it, such as ${retireAge != null && retireAge < 65 ? "health cover before Medicare, " : ""}college or debts.`;
  return `Costs now: ${usd(now)} a year. In retirement: about ${usd(at)}.`;
}

/** What one age costs, in parts. The server sends the parts (they add up to the total); older plans have only the
 * total and the basics, so everything above the basics is then one line. */
export function costsReadout(c: Costs, i: number) {
  const age = c.ages[i];
  const ev = c.events.find((e) => e.year != null);
  const year = ev && ev.year != null ? ev.year + (age - ev.age) : null;
  const basics = Math.min(c.basics[i] ?? 0, c.total[i]);
  const extra = Math.max(0, c.total[i] - basics);
  const events = c.events.filter((e) => e.age === age).map((e) => e.label);
  const parts = (c.parts ?? []).map((p) => ({ label: p.label, value: p.values[i] ?? 0 })).filter((p) => p.value >= 1);
  const said = parts.length ? ` ${parts.map((p) => `${p.label}: ${usd(p.value)}`).join(". ")}.` : ` Needs ${usd(basics)}.${extra >= 1 ? ` On top of needs: ${usd(extra)}.` : ""}`;
  const text = `Age ${age}${year != null ? `, ${year}` : ""}. Total costs ${usd(c.total[i])} a year.${said}${events.length ? ` ${events.join(". ")}.` : ""} In today's dollars.`;
  return { age, year, total: c.total[i], basics, extra, parts, events, text };
}

export default function CostsChart({ costs, retireAge }: { costs?: Costs | null; retireAge?: number | null }) {
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(560);
  const [hover, setHover] = useState<number | null>(null);
  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(260, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  if (!costs || costs.ages.length < 2 || costs.total.length !== costs.ages.length) return null;

  const { ages, total, basics, events } = costs;
  const h = 170, pad = { l: 48, r: 12, t: 22, b: 24 };
  const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
  const top = Math.max(...total, ...basics, 1) * 1.08;
  const a0 = ages[0], a1 = ages[ages.length - 1];
  const x = (a: number) => pad.l + ((a - a0) / (a1 - a0 || 1)) * iw;
  const y = (v: number) => pad.t + ih - (Math.max(0, v) / top) * ih;
  const path = (vs: number[]) => vs.map((v, i) => `${i ? "L" : "M"}${x(ages[i]).toFixed(1)} ${y(v).toFixed(1)}`).join("");
  const area = `${path(basics)}L${x(a1).toFixed(1)} ${y(0)}L${x(a0).toFixed(1)} ${y(0)}Z`;
  const ticks = [0, 0.5, 1].map((f) => f * top);
  const step = w < 480 ? 20 : 10;
  const evs = (events ?? []).filter((e) => e.age >= a0 && e.age <= a1);

  const n = ages.length;
  const pick = (clientX: number, rect: DOMRect) => {
    const px = ((clientX - rect.left) / (rect.width || w)) * w;
    const a = Math.round(a0 + ((px - pad.l) / iw) * (a1 - a0));
    setHover(Math.max(0, Math.min(n - 1, a - a0)));
  };
  const onKey = (e: KeyEv) => {
    const cur = hover ?? -1;
    let next: number | null = null;
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
  const r = hi != null ? costsReadout(costs, hi) : null;
  const hx = hi != null ? x(ages[hi]) : 0;
  const right = hx < w / 2;
  // keep clear of the point: readout sits in the half of the plot away from the line
  const below = hi != null && y(total[hi]) < pad.t + ih / 2;
  const tipStyle: CSSProperties = { left: right ? hx + 10 : hx - 10, transform: right ? "none" : "translateX(-100%)", ...(below ? { top: "auto", bottom: pad.b + 6 } : { top: pad.t }) };

  return (
    <figure className="chart costs">
      <figcaption className="chart-title">Your costs, now and later
        <span className="legend"><span className="key key-line" aria-hidden="true" /> Total <span className="key key-band" aria-hidden="true" /> Needs</span>
      </figcaption>
      <p className="costs-line">{costsLine(costs, retireAge)}</p>
      <div className="chart-box" ref={box}>
        <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" tabIndex={0} aria-label="Costs a year by age. Use the arrow keys to read each age."
          onPointerMove={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())} onPointerDown={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())}
          onPointerLeave={(e) => { if (e.pointerType === "mouse") setHover(null); }} onKeyDown={onKey}>
          {ticks.map((v) => <g key={v}><line x1={pad.l} x2={w - pad.r} y1={y(v)} y2={y(v)} className="grid" /><text x={pad.l - 8} y={y(v) + 4} textAnchor="end" className="axis">{usdShort(v)}</text></g>)}
          {ages.filter((a) => a % step === 0).map((a) => <text key={a} x={x(a)} y={h - 7} textAnchor="middle" className="axis">{a}</text>)}
          <path d={area} className="band" />
          <path d={path(total)} className="costs-total" />
          {evs.map((e, i) => (
            <g key={i} className="ev">
              <line x1={x(e.age)} x2={x(e.age)} y1={pad.t - 4} y2={pad.t + ih} className="retire" />
              <circle cx={x(e.age)} cy={y(total[ages.indexOf(e.age)] ?? total[0])} r={3.5} className="dot" />
            </g>
          ))}
          {hi != null && (
            <g>
              <line x1={hx} x2={hx} y1={pad.t} y2={pad.t + ih} className="cross" />
              <circle cx={hx} cy={y(total[hi])} r={4.5} className="dot" />
            </g>
          )}
        </svg>
        {r && (
          <div className="tip tip-costs" style={tipStyle} data-testid="costs-tip">
            <strong>Age {r.age}{r.year != null ? `, ${r.year}` : ""}</strong>
            <span>Total {usd(r.total)} a year</span>
            {r.parts.length > 0 ? r.parts.map((p) => <span key={p.label} className="muted tip-part"><span>{p.label}</span> <span className="num">{usd(p.value)}</span></span>) : <>
              <span className="muted">Needs {usd(r.basics)}</span>
              {r.extra >= 1 && <span className="muted">On top of needs {usd(r.extra)}</span>}
            </>}
            {r.events.map((l, i) => <span key={i} className="tip-ev">{l}</span>)}
          </div>
        )}
        <div className="sr-only" aria-live="polite" data-testid="costs-live">{r ? r.text : ""}</div>
      </div>
      {evs.length > 0 && <ul className="events">{evs.map((e, i) => <li key={i}><span className="num">{e.age}</span> {e.label}</li>)}</ul>}
      {costs.notes && costs.notes.length > 0 && <ul className="events notes small muted">{costs.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
    </figure>
  );
}
