import { createContext, useContext, type ReactNode } from "react";

// The shared drawing kit for the figures (the interview's "Your life so far" person and the working scenes). Everything is drawn as
// filled shapes, the way an illustrator inks: a flat colour fill, and over it a contour whose weight swells and thins along the line
// (a tapered stroke is a filled path), with the pen lifting at the ends. Fills sit a hair off their lines, and points carry a small
// fixed jitter, so no shape is a perfect circle or rectangle. Nothing is random at run time: the same figure always draws the same.
// Colours are CSS variables (figure/figures.css), tuned for the dark page. Copied and trimmed from the full app.

export type P = [number, number];
export type W = [number, number, number];

const f = (n: number) => String(Math.round(n * 10) / 10);
const hash = (n: number) => { const s = Math.sin(n * 12.9898 + 78.233) * 43758.5453; return s - Math.floor(s); };

/** Catmull-Rom spline through the points as cubic segments (without the opening M). */
function segs(p: P[], closed: boolean): string {
  const n = p.length;
  const at = (i: number): P => (closed ? p[(i + n) % n] : p[Math.max(0, Math.min(n - 1, i))]);
  let d = "";
  const last = closed ? n : n - 1;
  for (let i = 0; i < last; i++) {
    const p0 = at(i - 1), p1 = at(i), p2 = at(i + 1), p3 = at(i + 2);
    d += `C${f(p1[0] + (p2[0] - p0[0]) / 6)} ${f(p1[1] + (p2[1] - p0[1]) / 6)} ${f(p2[0] - (p3[0] - p1[0]) / 6)} ${f(p2[1] - (p3[1] - p1[1]) / 6)} ${f(p2[0])} ${f(p2[1])}`;
  }
  return d;
}

/** A smooth closed outline. */
export function blobPath(p: P[]): string { return `M${f(p[0][0])} ${f(p[0][1])}${segs(p, true)}Z`; }

/** A stroke whose width changes along it, as one filled path. */
export function taperPath(pts: W[]): string {
  const n = pts.length;
  const L: P[] = [], R: P[] = [];
  for (let i = 0; i < n; i++) {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)];
    let dx = b[0] - a[0], dy = b[1] - a[1];
    const len = Math.hypot(dx, dy) || 1; dx /= len; dy /= len;
    const h = pts[i][2] / 2;
    L.push([pts[i][0] - dy * h, pts[i][1] + dx * h]);
    R.push([pts[i][0] + dy * h, pts[i][1] - dx * h]);
  }
  R.reverse();
  return `M${f(L[0][0])} ${f(L[0][1])}${segs(L, false)}L${f(R[0][0])} ${f(R[0][1])}${segs(R, false)}Z`;
}

/** Points with a small fixed wobble. */
export function wobble(p: P[], seed: number, amt: number): P[] {
  return p.map(([x, y], i) => [x + (hash(seed * 7.1 + i * 2.3) - 0.5) * 2 * amt, y + (hash(seed * 3.7 + i * 5.9 + 1) - 0.5) * 2 * amt]);
}

/** The area around a path whose width changes: left edge out, right edge back. */
export function tube(axis: W[]): P[] {
  const n = axis.length;
  const L: P[] = [], R: P[] = [];
  for (let i = 0; i < n; i++) {
    const a = axis[Math.max(0, i - 1)], b = axis[Math.min(n - 1, i + 1)];
    let dx = b[0] - a[0], dy = b[1] - a[1];
    const len = Math.hypot(dx, dy) || 1; dx /= len; dy /= len;
    const h = axis[i][2] / 2;
    L.push([axis[i][0] - dy * h, axis[i][1] + dx * h]);
    R.push([axis[i][0] + dy * h, axis[i][1] - dx * h]);
  }
  return [...L, ...R.reverse()];
}

/** The line weight, in drawing units. The working scenes draw the figures smaller, so they ask for a heavier pen. */
export const LineWeight = createContext(1.5);

/** One ink line: points and a peak width; thin at both ends. */
export function Ink({ pts, w, cls = "fg-ink", seed = 1 }: { pts: P[]; w?: number; cls?: string; seed?: number }) {
  const lw = useContext(LineWeight);
  const peak = (w ?? 1) * lw;
  const n = pts.length;
  const wp: W[] = pts.map(([x, y], i) => {
    const t = n === 1 ? 0.5 : i / (n - 1);
    return [x, y, Math.max(0.25, peak * (0.3 + 0.7 * Math.sin(Math.PI * t)) * (0.85 + 0.3 * hash(seed + i)))];
  });
  return <path d={taperPath(wp)} className={cls} />;
}

/** A filled form with a hand-inked contour. `cls` is the fill class; the contour is a ring of tapered strokes that
 *  begins and ends at a seed-chosen point, so it overlaps and leaves a tiny gap as a pen does. */
export function Form({ pts, cls, seed = 1, jit = 0.5, w = 1, line = true }: { pts: P[]; cls: string; seed?: number; jit?: number; w?: number; line?: boolean }) {
  const lw = useContext(LineWeight);
  const p = wobble(pts, seed, jit);
  const n = p.length;
  const start = Math.floor(hash(seed) * n);
  const ring: P[] = [];
  for (let i = 0; i <= n + 1; i++) ring.push(p[(start + i) % n]);
  const wp: W[] = ring.map(([x, y], i) => {
    const edge = i === 0 || i === ring.length - 1 ? 0.3 : 1;
    return [x, y, Math.max(0.25, lw * w * edge * (0.55 + 0.95 * hash(seed * 1.7 + i * 3.1)))];
  });
  return (
    <g>
      <path d={blobPath(p)} className={cls} transform="translate(0.5 0.4)" />
      {line && <path d={taperPath(wp)} className="fg-ink" fillRule="evenodd" />}
    </g>
  );
}

export type Tone = 1 | 2 | 3 | 4;
export type HairKind = "crop" | "bob" | "curly" | "bun" | "wild" | "none";
export type Shirt = "a" | "b" | "c" | "d" | "e";

/** The hair, as closed outlines around the head centred at (0, -139). */
const HAIR: Record<Exclude<HairKind, "none">, P[][]> = {
  crop: [[[-10.4, -140], [-9.8, -148], [-4.5, -152.5], [3, -152.8], [9, -149.5], [10.4, -141], [8.4, -145], [3, -147.3], [-3.5, -146.5], [-8, -143.5]]],
  bob: [[[-11.6, -128], [-12, -141], [-9, -150], [-2, -153.5], [6, -152.5], [11.5, -146], [12, -134], [11, -127.5], [8.2, -129.5], [8.5, -140], [4, -146.5], [-3, -146.5], [-8.5, -140], [-8.2, -129.5]]],
  curly: [[[-11, -138], [-12.6, -144], [-9.8, -150], [-5, -153.6], [0, -155], [5.5, -153.6], [10.2, -150], [12.6, -144], [11, -138], [8.8, -143.5], [3.5, -146], [-3.5, -146], [-8.8, -143.5]]],
  bun: [[[-10.4, -140], [-9.8, -148], [-4.5, -152.2], [3, -152.2], [9.6, -148], [10.4, -140], [8, -146], [0, -148.4], [-8, -146]], [[-4, -155.6], [-4.8, -159.2], [0, -161.6], [4.6, -159.4], [4, -155.4], [0, -153.6]]],
  wild: [[[-11, -138], [-14.6, -143], [-13, -149], [-14.5, -154], [-9, -156], [-5, -160], [0, -157.5], [5.5, -160.4], [9.5, -156], [14.4, -154], [13, -148.5], [14.6, -143], [11, -138], [8.8, -144], [3.5, -147], [-3.5, -147], [-8.8, -144]]],
};

export function Hair({ kind, cls, sparse }: { kind: HairKind; cls: string; sparse?: boolean }) {
  if (kind === "none") return null;
  const shapes = HAIR[kind];
  return (
    <>
      {shapes.map((s, i) => {
        const pts: P[] = sparse && kind === "crop" ? s.map(([x, y]) => [x * 0.96, y > -147 ? y + 1.2 : y] as P) : s;
        return <Form key={i} pts={pts} cls={cls} seed={11 + i} jit={0.35} w={0.7} />;
      })}
    </>
  );
}

/** A sleeve and a hand: `pts` run from the shoulder (0, 0) to the wrist, in the figure's units; the cloth swells a little at the elbow. */
export function Arm({ pts, shirt, tone, seed = 3, hand = true }: { pts: P[]; shirt: Shirt; tone: Tone; seed?: number; hand?: boolean }) {
  const n = pts.length;
  const ax: W[] = pts.map(([x, y], i) => [x, y, 8.4 - 2 * (i / (n - 1)) + (i === Math.floor(n / 2) && n > 2 ? 0.8 : 0)]);
  const [hx, hy] = pts[n - 1];
  const [px, py] = pts[n - 2];
  const len = Math.hypot(hx - px, hy - py) || 1;
  const ux = (hx - px) / len, uy = (hy - py) / len;
  const cx = hx + ux * 3.4, cy = hy + uy * 3.4;
  const hp: P[] = [[cx - 3.4, cy - 3], [cx + 0.2, cy - 4.4], [cx + 3.4, cy - 2.6], [cx + 3, cy + 2.4], [cx - 0.4, cy + 4.6], [cx - 3.2, cy + 2.6]];
  return (
    <g>
      <Form pts={tube(ax)} cls={`fg-shirt-${shirt}`} seed={seed} jit={0.3} w={0.9} />
      {hand && <Form pts={hp} cls={`fg-skin-${tone}`} seed={seed + 5} jit={0.3} w={0.7} />}
    </g>
  );
}

export interface BodyProps {
  tone: Tone;
  hair: HairKind;
  hairTone: "dark" | "gray" | "white" | "brown" | "pale";
  sparse?: boolean;
  shirt: Shirt;
  glasses?: boolean;
  /** a grown-up body by default; children get a larger head */
  kid?: boolean;
  baby?: boolean;
  /** forward lean in degrees (the stoop of age) */
  lean?: number;
  temples?: boolean;
  apron?: boolean;
  collar?: boolean;
  chain?: boolean;
  goggles?: boolean;
  hat?: boolean;
  /** the right (viewer's right) arm drawn from the shoulder (origin), in place of the one that hangs; null draws none */
  rightArm?: ReactNode;
  /** the left arm, same idea */
  leftArm?: ReactNode;
  /** drawn after the body, in figure coordinates */
  children?: ReactNode;
  seed?: number;
}

/** A standing adult, front on: feet at y = 0, crown near y = -153, shoulders at -116 and 19 either side of the middle. */
export function Body(p: BodyProps) {
  const s = p.seed ?? 1;
  const headScale = p.baby ? 1.55 : p.kid ? 1.3 : 1;
  const leg = (sx: number, k: number) => tube([[sx * 8.2, -74, 15.4], [sx * 8.8, -40, 12.8 - k], [sx * 8.4, -6, 10.4]]);
  const head: P[] = [[0, -151], [7.2, -148.6], [9.8, -141], [8.8, -133.4], [4.6, -128.2], [0, -127.2], [-4.6, -128.2], [-8.8, -133.4], [-9.8, -141], [-7.2, -148.6]];
  const torso: P[] = [[-5.2, -119], [-14, -116.4], [-19.2, -112.6], [-19, -96], [-16.6, -80], [-15.4, -66], [-1, -64.6], [14.6, -66.2], [16.6, -80], [19.4, -96], [19.2, -112.6], [14, -116.4], [5.2, -119], [0, -117.4]];
  return (
    <g transform={p.lean ? `rotate(${p.lean} 0 -70)` : undefined}>
      <g transform="translate(0 0)">
        <Form pts={leg(-1, 0)} cls="fg-pants" seed={s + 1} jit={0.35} w={1} />
        <Form pts={leg(1, 0.4)} cls="fg-pants" seed={s + 2} jit={0.35} w={1} />
        <Form pts={[[-15.6, -6], [-7, -7.2], [-3.4, -3.6], [-3, 0], [-16.6, 0.4]]} cls="fg-shoe" seed={s + 3} jit={0.3} w={0.9} />
        <Form pts={[[3.4, -6.4], [8, -7.2], [15, -5], [17, 0], [3, 0.2]]} cls="fg-shoe" seed={s + 4} jit={0.3} w={0.9} />
        {/* the back arm and the front arm hang from the shoulders unless a scene gives one a task */}
        <g transform="translate(-18.6 -112)">{p.leftArm !== undefined ? p.leftArm : <Arm pts={[[0, 0], [-2.2, 21], [-5.8, 40]]} shirt={p.shirt} tone={p.tone} seed={s + 7} />}</g>
        <Form pts={torso} cls={`fg-shirt-${p.shirt}`} seed={s + 5} jit={0.45} w={1.1} />
        {p.apron && <Form pts={[[-11, -108], [11, -108], [13.4, -78], [14.4, -62], [-14.4, -62], [-13.4, -78]]} cls="fg-paper" seed={s + 9} jit={0.35} w={0.8} />}
        {p.collar && <><Form pts={[[-6, -119.6], [0, -112], [6, -119.6], [10.4, -115.6], [0, -105], [-10.4, -115.6]]} cls="fg-paper" seed={s + 10} jit={0.2} w={0.8} /></>}
        {/* a few folds, no more */}
        <Ink pts={[[-14, -90], [-11, -80], [-12.6, -70]]} w={0.9} seed={s + 12} />
        <Ink pts={[[8, -72], [12, -69], [15, -70]]} w={0.7} seed={s + 13} />
        <g transform="translate(18.6 -112)">{p.rightArm !== undefined ? p.rightArm : <Arm pts={[[0, 0], [4.8, 19], [3.4, 40]]} shirt={p.shirt} tone={p.tone} seed={s + 8} />}</g>
        {/* neck and head; a child's head is a little larger for the body */}
        <g transform={`translate(0 ${headScale === 1 ? 2.6 : 1.4}) ${headScale === 1 ? "" : `translate(0 -122) scale(${headScale}) translate(0 122)`}`}>
          <Form pts={[[-3.8, -126], [-3.4, -118], [0, -116], [3.4, -118], [3.8, -126]]} cls={`fg-skin-${p.tone}`} seed={s + 14} jit={0.2} w={0.8} />
          <Form pts={head} cls={`fg-skin-${p.tone}`} seed={s + 15} jit={0.3} w={1} />
          <Hair kind={p.hair} cls={`fg-hair-${p.hairTone}`} sparse={p.sparse} />
          {p.temples && <>
            <Form pts={[[-10, -142], [-9.4, -135], [-8.2, -139]]} cls="fg-hair-gray" seed={s + 16} jit={0.1} w={0.4} />
            <Form pts={[[10, -142], [9.4, -135], [8.2, -139]]} cls="fg-hair-gray" seed={s + 17} jit={0.1} w={0.4} />
          </>}
          {p.hat && <><Form pts={[[-10.8, -146], [-8, -155], [0, -158], [8, -155], [10.8, -146], [0, -144]]} cls="fg-hat" seed={s + 18} jit={0.3} w={0.8} /><Ink pts={[[-12.6, -146], [0, -143.6], [12.6, -146]]} w={1.3} seed={s + 19} /></>}
          {/* the face: two small marks for eyes, a line for the nose, a line for the mouth */}
          <circle cx="-3.5" cy="-139.4" r="0.95" className="fg-pen" />
          <circle cx="3.6" cy="-139.6" r="0.95" className="fg-pen" />
          <Ink pts={[[0.3, -138.4], [-0.9, -134.6], [0.7, -134]]} w={0.6} cls="fg-pen" seed={s + 20} />
          <Ink pts={[[-2.7, -131.2], [0, -130.5], [2.8, -131.5]]} w={0.8} cls="fg-pen" seed={s + 21} />
          {p.glasses && <>
            <Ink pts={ring(-4.4, -139.4, 3.9, 1)} w={0.75} cls="fg-pen" seed={s + 22} />
            <Ink pts={ring(4.5, -139.6, 3.9, 2)} w={0.75} cls="fg-pen" seed={s + 23} />
            <Ink pts={[[-0.8, -139.6], [0, -140], [0.9, -139.7]]} w={0.5} cls="fg-pen" seed={s + 24} />
          </>}
          {p.goggles && <Form pts={[[-9.4, -143], [0, -141], [9.4, -143], [9, -136], [3.6, -135], [0, -137], [-3.6, -135], [-9, -136]]} cls="fg-glass" seed={s + 25} jit={0.2} w={0.7} />}
          {p.chain && <Ink pts={[[-8, -128], [-9, -118], [-4, -110], [0, -109], [4, -110], [9, -118], [8, -128]]} w={0.7} cls="fg-chain" seed={s + 26} />}
          {p.baby && <Ink pts={[[0, -151.4], [1, -154.4], [-0.2, -156]]} w={0.9} seed={s + 27} />}
        </g>
        {p.children}
      </g>
    </g>
  );
}

function ring(cx: number, cy: number, r: number, seed: number): P[] {
  const out: P[] = [];
  for (let i = 0; i <= 8; i++) {
    const a = (i / 8) * Math.PI * 2 + 0.6 * seed;
    out.push([cx + Math.cos(a) * r * (1 + 0.05 * (hash(seed + i) - 0.5)), cy + Math.sin(a) * r * 0.96]);
  }
  return out;
}

/** The ground: one long, slightly uneven line that swells and thins. */
export function Ground({ x0, x1, y }: { x0: number; x1: number; y: number }) {
  const pts: P[] = [];
  const n = 7;
  for (let i = 0; i < n; i++) pts.push([x0 + ((x1 - x0) * i) / (n - 1), y + Math.sin(i * 1.3) * 1.4 - (i === 0 ? 0 : 0)]);
  return <Ink pts={pts} w={1.6} cls="fg-ground" seed={5} />;
}
