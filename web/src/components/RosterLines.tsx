import { useCallback, useLayoutEffect, useRef, useState, type ReactNode } from "react";

// The org-chart lines behind the roster: one from the lead adviser to each of the six advisers.
// Decorative only (aria-hidden). Positions come from the DOM, so they follow any width and the panel opening on a phone.
// A line is grey while its adviser waits, teal while it works, green when done; a handoff lights the lines it uses and sends a dot along them.

type Pt = [number, number];
export type LineState = "idle" | "working" | "done";
export interface Pulse { from: string; to: string; n: number; text?: string }

const ROW_TOL = 6;

/** One adviser's own route from the lead: down from its own start point under the lead to its own level, along it, and (row two) down its own channel
 *  in the margin or the gap between columns to a last bar, then a short drop onto the portrait. No two advisers share a segment. */
export function route(start: Pt, fig: Pt, bus: number, channel: number | null, bus2?: number): Pt[] {
  const [lx, ly] = start;
  const [fx, fy] = fig;
  if (channel == null) return [[lx, ly], [lx, bus], [fx, bus], [fx, fy]];
  const b2 = bus2 ?? fy - 10;
  return [[lx, ly], [lx, bus], [channel, bus], [channel, b2], [fx, b2], [fx, fy]];
}

export const toPath = (pts: Pt[]) => pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");

/** The dot's path for a handoff: down one line, or up one line, or up one and down another (two specialists, routed via the lead). */
export function handoffPath(routes: Record<string, Pt[]>, from: string, to: string): string | null {
  const up = from !== "adviser" ? routes[from] : undefined;
  const down = to !== "adviser" ? routes[to] : undefined;
  if (from !== "adviser" && !up) return null;
  if (to !== "adviser" && !down) return null;
  const pts: Pt[] = [...(up ? [...up].reverse() : []), ...(down ?? [])];
  return pts.length > 1 ? toPath(pts) : null;
}

/** Where the hand-off's note sits: on its adviser's own last bar (centred, kept inside the panel), or beside the line when the line is straight. */
export function labelSpot(pts: Pt[], width: number): { x: number; y: number; tf: string } {
  for (let i = pts.length - 2; i >= 0; i--) {
    const [x1, y1] = pts[i], [x2, y2] = pts[i + 1];
    if (Math.abs(y1 - y2) < 0.5 && Math.abs(x1 - x2) >= 28) {
      const half = Math.min(125, width / 2);
      return { x: Math.min(width - half, Math.max(half, (x1 + x2) / 2)), y: y1, tf: "translate(-50%, -50%)" };
    }
  }
  const [x1, y1] = pts[pts.length - 2], [, y2] = pts[pts.length - 1];
  const right = x1 > width * 0.6;
  return { x: x1 + (right ? -8 : 8), y: (y1 + y2) / 2, tf: right ? "translate(-100%, -50%)" : "translate(0, -50%)" };
}

const rank = { idle: 0, done: 1, working: 2 } as const;

export default function RosterLines({ advisers, states, pulse, children }: {
  advisers: string[]; states: Record<string, LineState>; pulse: Pulse | null; children: ReactNode;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const [routes, setRoutes] = useState<Record<string, Pt[]>>({});
  const [size, setSize] = useState<[number, number]>([0, 0]);

  const measure = useCallback(() => {
    const w = wrap.current;
    if (!w) return;
    const box = w.getBoundingClientRect();
    if (box.width === 0 || box.height === 0) return; // folded away on a phone: measure again when it opens
    const rel = (r: DOMRect) => ({ l: r.left - box.left, r: r.right - box.left, t: r.top - box.top, b: r.bottom - box.top, cx: (r.left + r.right) / 2 - box.left });
    const get = (k: string) => {
      const fig = w.querySelector<HTMLElement>(`[data-agent="${k}"] .node-fig`);
      const badge = w.querySelector<HTMLElement>(`[data-agent="${k}"] .badge`);
      return fig && badge ? { fig: rel(fig.getBoundingClientRect()), badge: rel(badge.getBoundingClientRect()) } : null;
    };
    const lead = get("adviser");
    const items = advisers.map((k) => ({ k, m: get(k) })).filter((x): x is { k: string; m: NonNullable<ReturnType<typeof get>> } => x.m != null);
    if (!lead || items.length === 0) return;
    const firstTop = Math.min(...items.map((x) => x.m.fig.t));
    const row1 = items.filter((x) => x.m.fig.t - firstTop <= ROW_TOL).sort((a, b) => a.m.fig.cx - b.m.fig.cx);
    const row2 = items.filter((x) => !row1.includes(x));
    const y0 = lead.badge.b + 2;
    const avail = Math.max(24, firstTop - y0);
    const lvlRow1 = firstTop - Math.max(8, avail * 0.22);   // the lowest bar: the row-one advisers
    const lvlMid = y0 + avail * 0.5;                         // a row-two adviser whose channel is a gap between columns
    const lvlOut = y0 + avail * 0.22;                        // a row-two adviser whose channel is the margin: the highest bar
    const secondTop = row2.length ? Math.min(...row2.map((x) => x.m.fig.t)) : 0;
    const tol = 14;
    const cx = lead.fig.cx;
    type Item = (typeof items)[number];
    const side = (x: Item) => (x.m.fig.cx < cx - tol ? -1 : x.m.fig.cx > cx + tol ? 1 : 0);
    // where each line leaves the lead, left to right: margin lines first, then the gap line, then the row-one lines
    const order = [
      ...row2.filter((x) => side(x) < 0).sort((a, b) => a.m.fig.cx - b.m.fig.cx),
      ...row2.filter((x) => side(x) === 0),
      ...row1.filter((x) => side(x) < 0),
      ...row1.filter((x) => side(x) === 0),
      ...row1.filter((x) => side(x) > 0),
      ...row2.filter((x) => side(x) > 0).sort((a, b) => a.m.fig.cx - b.m.fig.cx),
    ];
    const mid = order.findIndex((x) => row1.includes(x) && side(x) === 0);
    const step = Math.min(9, Math.max(4, (lead.fig.r - lead.fig.l) * 0.7 / Math.max(1, order.length - 1)));
    const out: Record<string, Pt[]> = {};
    order.forEach((x, i) => {
      const start: Pt = [cx + (i - (mid >= 0 ? mid : (order.length - 1) / 2)) * step, y0];
      const end: Pt = [x.m.fig.cx, x.m.fig.t - 1];
      if (row1.includes(x)) { out[x.k] = route(start, end, lvlRow1, null); return; }
      const sd = side(x);
      const left = row1.filter((r) => r.m.fig.cx < x.m.fig.cx - tol).pop();
      const channel = sd < 0 ? Math.max(3, x.m.badge.l - 7)
        : sd > 0 ? Math.min(box.width - 3, x.m.badge.r + 7)
        : left ? (left.m.badge.r + x.m.badge.l) / 2 : Math.max(3, x.m.badge.l - 7);
      out[x.k] = route(start, end, sd === 0 ? lvlMid : lvlOut, channel, secondTop - 10);
    });
    setRoutes(out);
    setSize([box.width, box.height]);
  }, [advisers]);

  useLayoutEffect(() => {
    measure();
    const w = wrap.current;
    if (!w) return;
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => measure()) : null;
    ro?.observe(w);
    w.querySelectorAll(".node").forEach((n) => ro?.observe(n));
    window.addEventListener("resize", measure);
    return () => { ro?.disconnect(); window.removeEventListener("resize", measure); };
  }, [measure]);

  const active = (k: string) => !!pulse && (pulse.from === k || pulse.to === k);
  const ordered = [...advisers].sort((a, b) => {
    const ra = (active(a) ? 3 : rank[states[a] ?? "idle"]);
    const rb = (active(b) ? 3 : rank[states[b] ?? "idle"]);
    return ra - rb;
  });
  const dot = pulse ? handoffPath(routes, pulse.from, pulse.to) : null;
  // the hand-off's note, as a small label above the bar of the adviser it goes to (or comes from, for a note to the lead)
  const target = pulse ? (pulse.to !== "adviser" ? pulse.to : pulse.from) : null;
  const tr = target ? routes[target] : undefined;
  const short = (k: string) => (k === "adviser" ? "Lead" : k.charAt(0).toUpperCase() + k.slice(1));
  const label = pulse && pulse.text && tr && tr.length >= 2 && size[0] > 0 ? { ...labelSpot(tr, size[0]), text: `${short(pulse.from)} → ${short(pulse.to)}: ${pulse.text.length > 90 ? pulse.text.slice(0, 89).trimEnd() + "…" : pulse.text}` } : null;

  return (
    <div className="roster-wrap" ref={wrap}>
      <svg className="roster-lines" width={size[0]} height={size[1]} viewBox={`0 0 ${size[0] || 1} ${size[1] || 1}`} aria-hidden="true" focusable="false">
        {ordered.map((k) => (
          <path key={k} className={`rline ${states[k] ?? "idle"}${active(k) ? " active" : ""}`} data-line={k} d={routes[k] ? toPath(routes[k]) : "M0 0"} />
        ))}
        {dot && <circle key={pulse!.n} className="rdot" r="4.5" style={{ offsetPath: `path("${dot}")` }} />}
      </svg>
      {children}
      {label && <div key={pulse!.n} className="rlabel" aria-hidden="true" data-testid="roster-label" data-line={target ?? undefined} style={{ left: label.x, top: label.y, transform: label.tf }}>{label.text}</div>}
    </div>
  );
}
