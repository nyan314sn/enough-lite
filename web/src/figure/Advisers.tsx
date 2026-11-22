import type { ReactNode } from "react";
import { Ink, LineWeight, blobPath, taperPath, wobble, type P, type W } from "./figure";

// The advisers as hand-inked portraits: invented people, not photos. Drawn the way the household figures are (figure.tsx): a flat fill with
// a tapered contour that swells and thins, and a small fixed wobble, so no shape is a perfect circle or rectangle. One small kit (head, hair,
// clothes, a few accessories) draws them all, so they read as one team. Each differs in age, gender and skin tone. Decorative: the role
// badge beside each names it. The same portrait always draws the same.

export type AgentKey = "intake" | "longevity" | "markets" | "family" | "tax" | "research" | "adviser";

interface Look {
  bg: string; skin: string; shade: string; hair: string; cloth: string; collar?: string;
  hairStyle: "bun" | "short" | "thin" | "curly" | "bob" | "wavy" | "crop";
  glasses?: "round" | "square"; beard?: boolean; tie?: string; earrings?: boolean; brow: string; lips: string; streak?: string; cardigan?: string;
  alt: string;
  tone: 1 | 2 | 3 | 4;
}

const LOOK: Record<AgentKey, Look> = {
  // Intake: a young woman, medium-brown skin, dark hair in a bun
  intake: { bg: "var(--pbg-intake)", skin: "#b9784e", shade: "#a4663f", hair: "#2a1d18", cloth: "#1f6f7d", hairStyle: "bun", brow: "#2a1d18", lips: "#8a3f35", earrings: true, alt: "a young woman with her hair in a bun", tone: 3 },
  // Longevity: an older man, light skin, white hair, glasses, a grey cardigan
  longevity: { bg: "var(--pbg-longevity)", skin: "#efcdb0", shade: "#dcb594", hair: "#e4e1dc", cloth: "#f3f5f8", collar: "#f3f5f8", cardigan: "#5c6b80", hairStyle: "thin", glasses: "round", brow: "#b9b5ae", lips: "#b4685c", alt: "an older man with white hair and glasses", tone: 1 },
  // Markets: a man in his thirties, dark brown skin, short hair, a short beard and a tie
  markets: { bg: "var(--pbg-markets)", skin: "#7b4b33", shade: "#6a3f2a", hair: "#16110f", cloth: "#f3f5f8", collar: "#f3f5f8", tie: "#1f3a5f", hairStyle: "crop", beard: true, brow: "#16110f", lips: "#4d2a22", alt: "a man with short hair and a short beard, in a tie", tone: 4 },
  // Family: a woman in her forties, light-medium skin, wavy auburn hair, a warm cardigan
  family: { bg: "var(--pbg-family)", skin: "#e3b08a", shade: "#cf9a73", hair: "#8a3f22", cloth: "#c98a3c", hairStyle: "wavy", brow: "#6d3018", lips: "#b4584c", alt: "a woman with wavy auburn hair", tone: 2 },
  // Tax: a woman in her fifties, East Asian, black bob with a grey streak, glasses, a blazer
  tax: { bg: "var(--pbg-tax)", skin: "#f0c8a0", shade: "#dcb08a", hair: "#1c1a1d", cloth: "#2c3e5e", collar: "#f3f5f8", hairStyle: "bob", glasses: "square", brow: "#1c1a1d", lips: "#a9544c", streak: "#aeb4bd", alt: "a woman with a dark bob and glasses, in a blazer", tone: 1 },
  // Research: a young man, tan skin, curly hair, round glasses, a sweater
  research: { bg: "var(--pbg-research)", skin: "#c68b5e", shade: "#b27a4f", hair: "#241812", cloth: "#4f7f6f", hairStyle: "curly", glasses: "round", brow: "#241812", lips: "#8e4a3c", alt: "a young man with curly hair and round glasses", tone: 2 },
  // Lead adviser: a woman in her fifties, deep brown skin, short grey-black hair, a navy blazer, earrings
  adviser: { bg: "var(--pbg-adviser)", skin: "#8d5a3b", shade: "#7a4b2f", hair: "#3b3a3d", cloth: "#1c2f4d", collar: "#f3f5f8", hairStyle: "short", earrings: true, brow: "#2b2a2c", lips: "#6b2f2c", alt: "a woman with short grey hair in a navy blazer", tone: 4 },
};

const hash = (n: number) => { const s = Math.sin(n * 12.9898 + 78.233) * 43758.5453; return s - Math.floor(s); };
const mirror = (p: P[]): P[] => p.map(([x, y]) => [64 - x, y] as P);
/** Points round an ellipse, a little off true. */
function ell(cx: number, cy: number, rx: number, ry: number, n = 9, rot = 0): P[] {
  return Array.from({ length: n }, (_, i) => { const a = (i / n) * Math.PI * 2 + rot; return [cx + Math.cos(a) * rx, cy + Math.sin(a) * ry] as P; });
}
/** A small ring of ink, open at one end like a pen lift (glasses). */
function loop(cx: number, cy: number, r: number, seed: number): P[] {
  return Array.from({ length: 10 }, (_, i) => { const a = (i / 9) * Math.PI * 2 + 0.7 * seed; return [cx + Math.cos(a) * r * (1 + 0.05 * (hash(seed + i) - 0.5)), cy + Math.sin(a) * r * 0.96] as P; });
}

/** A filled form with a hand-inked contour, like Form in figure.tsx, but the fill is any colour. The contour is a ring of tapered strokes that
 *  starts and ends at a seed-chosen point, so it overlaps and leaves a tiny gap as a pen does. */
function Shape({ pts, fill, cls = "pt-fill", seed, jit = 0.3, w = 1, line = true }: { pts: P[]; fill: string; cls?: string; seed: number; jit?: number; w?: number; line?: boolean }) {
  const p = wobble(pts, seed, jit);
  const n = p.length;
  const start = Math.floor(hash(seed) * n);
  const ring: P[] = [];
  for (let i = 0; i <= n + 1; i++) ring.push(p[(start + i) % n]);
  const wp: W[] = ring.map(([x, y], i) => [x, y, Math.max(0.2, w * (i === 0 || i === ring.length - 1 ? 0.3 : 1) * (0.55 + 0.95 * hash(seed * 1.7 + i * 3.1)))]);
  return (
    <g>
      <path d={blobPath(p)} className={cls} style={{ fill }} transform="translate(0.3 0.25)" />
      {line && <path d={taperPath(wp)} className="fg-ink" fillRule="evenodd" />}
    </g>
  );
}

/** One ink mark in a colour. */
const Mark = ({ pts, color, w = 0.8, seed }: { pts: P[]; color: string; w?: number; seed: number }) => <g fill={color}><Ink pts={pts} w={w} cls="pt-mark" seed={seed} /></g>;

const BACK: Partial<Record<Look["hairStyle"], P[]>> = {
  bob: [[19, 31], [19, 19], [24, 11.5], [32, 10], [40, 11.5], [45, 19], [45, 31], [45.2, 41], [42, 45], [22, 45], [18.8, 41]],
  wavy: [[18.5, 30], [19, 17.5], [24, 10.5], [32, 9.5], [40, 10.5], [45, 17.5], [45.5, 30], [46.5, 40], [49, 47], [40, 47.5], [24, 47.5], [15, 47], [17.5, 40]],
};
const FRONT: Record<Look["hairStyle"], P[]> = {
  bun: [[20.5, 28], [19.8, 19], [25, 13.5], [32, 12.3], [39, 13.5], [44.2, 19], [43.5, 28], [39.5, 21.5], [34.5, 18.8], [28, 19.5], [23.5, 22.5]],
  short: [[20.5, 28], [19.8, 18], [25, 12.8], [32, 12], [39, 12.8], [44.2, 18], [43.5, 28], [40, 22], [32, 20], [24, 22]],
  crop: [[21, 27], [20.5, 18], [25, 13.5], [32, 12.5], [39, 13.5], [43.5, 18], [43, 27], [39, 22.5], [32, 20.5], [25, 22.5]],
  thin: [[23.5, 18.5], [27, 15], [32, 13.8], [37, 15], [40.5, 18.5], [36, 16.8], [32, 16.2], [28, 16.8]],
  curly: [[21, 25], [23, 21.5], [32, 19], [41, 21.5], [43, 25], [32, 24]],
  bob: [[20, 30], [19.5, 19], [25, 13], [32, 12], [39, 13], [44.5, 19], [44, 30], [40, 20.5], [35, 18], [28, 19], [22.5, 23]],
  wavy: [[19.5, 31], [19, 18], [25, 12.5], [32, 11.5], [39, 12.5], [45, 18], [44.5, 31], [41, 22], [36, 18.5], [29, 21], [23, 24]],
};
const THIN_SIDE: P[] = [[20.5, 30], [20, 24], [22, 19], [24.5, 18.5], [22.5, 24], [22, 30]];
const CURLS: [number, number, number][] = [[22, 22, 5], [27, 16.5, 5.5], [33, 15, 5.5], [39, 17, 5.5], [43, 23, 5]];

function HairBack({ k, c, s }: { k: Look["hairStyle"]; c: string; s: number }): ReactNode {
  const b = BACK[k];
  if (b) return <Shape pts={b} fill={c} seed={s + 1} jit={0.4} />;
  if (k === "bun") return <Shape pts={ell(32, 10.5, 5.5, 5, 8)} fill={c} seed={s + 1} jit={0.4} />;
  return null;
}

function HairFront({ k, c, streak, s }: { k: Look["hairStyle"]; c: string; streak?: string; s: number }): ReactNode {
  if (k === "thin") return <><Shape pts={THIN_SIDE} fill={c} seed={s + 2} jit={0.2} w={0.7} /><Shape pts={mirror(THIN_SIDE)} fill={c} seed={s + 3} jit={0.2} w={0.7} /><Shape pts={FRONT.thin} fill={c} seed={s + 4} jit={0.2} w={0.7} /></>;
  if (k === "curly") return <>{CURLS.map(([x, y, r], i) => <Shape key={i} pts={ell(x, y, r, r * 0.95, 7, i)} fill={c} seed={s + 2 + i} jit={0.5} w={0.8} />)}<Shape pts={FRONT.curly} fill={c} seed={s + 8} jit={0.3} w={0.7} /></>;
  return (
    <>
      <Shape pts={FRONT[k]} fill={c} seed={s + 2} jit={0.4} w={0.9} />
      {streak && k === "bob" && <Shape pts={[[33, 12.5], [37, 13.3], [40.5, 18], [36, 15.8], [31, 14.5]]} fill={streak} seed={s + 3} jit={0.2} w={0.5} />}
    </>
  );
}

/** One adviser, a hand-inked head and shoulders. The page clips it to a circle, so every portrait is the same shape. */
export default function AgentPortrait({ agent }: { agent: AgentKey }) {
  const L = LOOK[agent];
  const s = (Object.keys(LOOK) as AgentKey[]).indexOf(agent) * 40 + 5;
  const skin = `fg-skin-${L.tone}`;
  return (
    <svg className="portrait" viewBox="0 0 64 64" aria-hidden="true" focusable="false" data-draws={L.alt}>
      <LineWeight.Provider value={0.7}>
        <Shape pts={[[-3, -3], [32, -4], [67, -3], [68, 32], [67, 67], [32, 68], [-3, 67], [-4, 32]]} fill={L.bg} seed={s} jit={0.5} line={false} />
        <HairBack k={L.hairStyle} c={L.hair} s={s} />
        {/* shoulders and clothes */}
        <Shape pts={[[4, 67], [5, 59], [10, 53], [19, 49], [27, 47], [32, 47.8], [37, 47], [45, 49], [54, 53], [59, 59], [60, 67]]} fill={L.cardigan ?? L.cloth} seed={s + 10} jit={0.5} w={1.1} />
        {L.cardigan && <Shape pts={[[24, 48.5], [32, 66], [40, 48.5], [36, 50.5], [32, 51.5], [28, 50.5]]} fill={L.cloth} seed={s + 11} jit={0.3} w={0.8} />}
        {/* neck, ears, head */}
        <Shape pts={[[27.5, 36], [36.5, 36], [36.8, 47], [32, 51], [27.2, 47]]} fill={L.shade} cls={skin} seed={s + 12} jit={0.25} w={0.8} />
        {L.collar && !L.cardigan && <Shape pts={[[26, 47.5], [32, 53.5], [38, 47.5], [42, 50.5], [32, 60], [22, 50.5]]} fill={L.collar} seed={s + 13} jit={0.3} w={0.8} />}
        {L.cardigan && L.collar && <Shape pts={[[26, 47.5], [32, 52], [38, 47.5], [39.5, 49.5], [32, 56], [24.5, 49.5]]} fill={L.collar} seed={s + 13} jit={0.3} w={0.7} />}
        {L.tie && <Shape pts={[[32, 52.5], [29.8, 56], [32, 66], [34.2, 56]]} fill={L.tie} seed={s + 14} jit={0.2} w={0.7} />}
        {L.collar && !L.cardigan && !L.tie && <><Ink pts={[[26, 51], [28.5, 59], [31, 66]]} w={0.9} seed={s + 15} /><Ink pts={[[38, 51], [35.5, 59], [33, 66]]} w={0.9} seed={s + 16} /></>}
        <Shape pts={ell(20.8, 30.5, 2.3, 3, 6)} fill={L.skin} cls={skin} seed={s + 17} jit={0.15} w={0.6} />
        <Shape pts={ell(43.2, 30.5, 2.3, 3, 6)} fill={L.skin} cls={skin} seed={s + 18} jit={0.15} w={0.6} />
        {L.earrings && <><Shape pts={ell(20.5, 34.5, 1.2, 1.3, 5)} fill="#e0b65a" cls="fg-gold" seed={s + 19} jit={0.1} line={false} /><Shape pts={ell(43.5, 34.5, 1.2, 1.3, 5)} fill="#e0b65a" cls="fg-gold" seed={s + 20} jit={0.1} line={false} /></>}
        <Shape pts={[[32, 15.3], [38.6, 17.6], [43.2, 24], [43, 31.5], [40.2, 38.5], [36, 41.2], [32, 41.8], [28, 41.2], [23.8, 38.5], [21, 31.5], [20.8, 24], [25.4, 17.6]]} fill={L.skin} cls={skin} seed={s + 21} jit={0.3} w={1} />
        <HairFront k={L.hairStyle} c={L.hair} streak={L.streak} s={s} />
        {L.beard && <Shape pts={[[20.8, 30], [21, 38], [25, 44], [32, 46.5], [39, 44], [43, 38], [43.2, 30], [40.5, 36.5], [37, 38.5], [32, 37], [27, 38.5], [23.5, 36.5]]} fill={L.hair} seed={s + 22} jit={0.3} w={0.7} />}
        {/* the face: two brows, two eyes, a nose, a mouth */}
        <Mark pts={[[24.5, 25.4], [27.5, 23.9], [30.5, 25.2]]} color={L.brow} w={0.95} seed={s + 23} />
        <Mark pts={[[33.5, 25.2], [36.5, 23.9], [39.5, 25.4]]} color={L.brow} w={0.95} seed={s + 24} />
        <Shape pts={ell(27.5, 29, 1.3, 1.2, 6)} fill="#241a17" seed={s + 25} jit={0.1} line={false} />
        <Shape pts={ell(36.5, 29, 1.3, 1.2, 6, 1)} fill="#241a17" seed={s + 26} jit={0.1} line={false} />
        <Mark pts={[[32, 30.5], [30.9, 33.6], [32.4, 34.6]]} color={L.shade} w={0.75} seed={s + 27} />
        <Mark pts={[[28.8, 36.3], [32, 38.2], [35.2, 36.2]]} color={L.beard ? "#e8c9b0" : L.lips} w={1.3} seed={s + 28} />
        {L.glasses === "round" && <><Mark pts={loop(27.5, 29, 4.3, 1)} color="#27364d" w={0.9} seed={s + 29} /><Mark pts={loop(36.5, 29, 4.3, 2)} color="#27364d" w={0.9} seed={s + 30} /><Mark pts={[[31.4, 28.8], [32, 28.4], [32.6, 28.8]]} color="#27364d" w={0.6} seed={s + 31} /></>}
        {L.glasses === "square" && <><Mark pts={[[23, 26.4], [27.5, 25.7], [32, 26.1], [32.3, 29.5], [31.8, 32.3], [27.5, 32.6], [23.4, 32], [22.9, 26.5]]} color="#27364d" w={0.9} seed={s + 29} /><Mark pts={[[32, 26.1], [36.5, 25.7], [41, 26.4], [41.2, 32], [37, 32.6], [32.7, 32.3], [32.3, 29.5], [32, 26.2]]} color="#27364d" w={0.9} seed={s + 30} /><Mark pts={[[31.6, 28.4], [32, 28.1], [32.5, 28.4]]} color="#27364d" w={0.6} seed={s + 31} /></>}
      </LineWeight.Provider>
    </svg>
  );
}

export const portraitAlt = (a: AgentKey) => LOOK[a].alt;
