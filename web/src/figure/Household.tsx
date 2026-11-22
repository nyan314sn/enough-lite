import { Arm, Body, Form, Ground, Ink, type HairKind, type Shirt, type Tone } from "./figure";
import { householdLine } from "../format";
import type { Profile } from "../types";
import "./figures.css";

// The household picture, drawn from the profile: you, a partner, each child at their age, pets as dogs or cats, a house if you own one.
// Copied and simplified from the full app's interview figure (components/Avatar.tsx). Hand-inked shapes; a short fade as each one arrives.

type Band = "20s" | "30s" | "40s" | "50s" | "60+";
const band = (age: number | null | undefined): Band => (age == null || age < 30 ? "20s" : age < 40 ? "30s" : age < 50 ? "40s" : age < 60 ? "50s" : "60+");
const HAIR: Record<Band, { tone: "dark" | "gray" | "white"; temples: boolean; sparse: boolean }> = {
  "20s": { tone: "dark", temples: false, sparse: false }, "30s": { tone: "dark", temples: false, sparse: false },
  "40s": { tone: "dark", temples: true, sparse: false }, "50s": { tone: "gray", temples: false, sparse: false }, "60+": { tone: "white", temples: false, sparse: true },
};

/** Median height by age (CDC), so a 6-year-old stands at about two thirds of a grown-up. */
const HEIGHT_CM = [50, 76, 87, 95, 102, 109, 115, 121, 127, 133, 138, 144, 150, 156, 162, 166, 169, 171, 172];
export function childScale(age: number): number {
  const a = Math.max(0, Math.min(18, age));
  const i = Math.min(17, Math.floor(a));
  const cm = HEIGHT_CM[i] + (HEIGHT_CM[i + 1] - HEIGHT_CM[i]) * (a - i);
  return Math.round(0.88 * (cm / 172) * 1000) / 1000;
}

/** The i-th figure of a group stands a step behind and to the right, a little smaller and lighter. */
const depth = (i: number, x0: number, y0: number) => ({ x: x0 + i * 16, y: y0 - i * 7, scale: 1 - i * 0.08, fade: 1 - i * 0.17 });
const MAX = { kids: 4, pets: 3 };

function Person({ x, y = 196, scale = 1, fade = 1, b, shirt, hair, tone, kid, baby, briefcase }: {
  x: number; y?: number; scale?: number; fade?: number; b: Band; shirt: Shirt; hair: HairKind; tone: Tone; kid?: boolean; baby?: boolean; briefcase?: boolean;
}) {
  const h = kid ? HAIR["20s"] : HAIR[b];
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`} style={fade < 1 ? { opacity: fade } : undefined}><g className="fg-pop"><g className="fg-bob">
      <Body tone={tone} hair={hair} hairTone={h.tone} sparse={h.sparse} temples={h.temples} shirt={shirt} kid={kid && !baby} baby={baby}
        lean={kid ? 0 : b === "60+" ? 2.2 : b === "50s" ? 0.8 : 0} seed={shirt.charCodeAt(0) - 90 + hair.length * 3}
        rightArm={briefcase ? <Arm pts={[[0, 0], [4, 21], [6, 41]]} shirt={shirt} tone={tone} seed={9} /> : undefined}>
        {briefcase && (
          <g transform="translate(-6.5 -8.5)">
            <Ink pts={[[26, -58], [29, -64.6], [35.6, -64.6], [38.4, -58]]} w={1.2} seed={31} />
            <Form pts={[[21.6, -58.4], [38, -59.2], [44.6, -58], [45.2, -42], [22.4, -41.2]]} cls="fg-deep" seed={32} jit={0.4} w={1} />
            <Form pts={[[30, -53.6], [34, -53.8], [34.2, -50], [30.2, -49.8]]} cls="fg-gold" seed={34} jit={0.2} w={0.5} />
          </g>
        )}
      </Body>
    </g></g></g>
  );
}

function Dog({ x, y, scale, fade }: { x: number; y: number; scale: number; fade: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`} style={fade < 1 ? { opacity: fade } : undefined} data-pet="dog"><g className="fg-pop">
      <Form pts={[[-15, -24], [-13.4, -1], [-8, 0], [-7, -14]]} cls="fg-tan" seed={41} jit={0.3} w={0.9} />
      <Form pts={[[11, -22], [12, 0], [18, 0], [17.4, -18]]} cls="fg-tan" seed={42} jit={0.3} w={0.9} />
      <g className="fg-wag"><Ink pts={[[-26, -38], [-33, -44], [-34, -53], [-31, -57]]} w={2.8} cls="fg-hair-brown" seed={44} /></g>
      <Form pts={[[-28, -36], [-23, -46], [-8, -48.6], [12, -48], [24, -45], [27, -36], [21, -25], [-4, -22.4], [-22, -25]]} cls="fg-tan" seed={43} jit={0.5} w={1.1} />
      <Form pts={[[22, -60], [30, -62.4], [38, -58], [40.6, -51], [36, -43], [26, -43.4], [21, -50]]} cls="fg-tan" seed={45} jit={0.4} w={1} />
      <Form pts={[[22, -62], [27.6, -63.4], [28.4, -52], [24, -47.4], [19.6, -54]]} cls="fg-hair-brown" seed={46} jit={0.3} w={0.8} />
      <Form pts={[[36.4, -53.4], [42.4, -52.4], [42.6, -48.6], [37.4, -48]]} cls="fg-pen" seed={47} jit={0.2} w={0.3} />
      <circle cx="32.8" cy="-55.4" r="1.3" className="fg-pen" />
    </g></g>
  );
}

function Cat({ x, y, scale, fade }: { x: number; y: number; scale: number; fade: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`} style={fade < 1 ? { opacity: fade } : undefined} data-pet="cat"><g className="fg-pop">
      <Form pts={[[-10, -14], [-9.6, 0], [-4, 0], [-4.6, -12]]} cls="fg-stone" seed={51} jit={0.3} w={0.9} />
      <Form pts={[[6, -14], [6.4, 0], [12, 0], [11.4, -12]]} cls="fg-stone" seed={52} jit={0.3} w={0.9} />
      <Form pts={[[-20, -22], [-14, -33], [0, -35], [12, -32], [19, -22], [14, -12.6], [-6, -12], [-17, -14]]} cls="fg-stone" seed={53} jit={0.5} w={1.1} />
      <g className="fg-wag"><Ink pts={[[-18, -18], [-28, -20], [-31, -30], [-27, -38]]} w={2.6} cls="fg-stone" seed={54} /></g>
      <Form pts={[[13, -44], [15, -52.4], [20.4, -47.4], [27, -52.4], [29, -43.4], [30, -37], [22, -31.4], [13.6, -37]]} cls="fg-stone" seed={56} jit={0.4} w={1} />
      <circle cx="19" cy="-40.6" r="1.1" className="fg-pen" />
      <circle cx="25.4" cy="-40.8" r="1.1" className="fg-pen" />
      <Ink pts={[[21, -37], [22.2, -36], [23.4, -37]]} w={0.7} cls="fg-pen" seed={57} />
    </g></g>
  );
}

function House({ x }: { x: number }) {
  return (
    <g transform={`translate(${x} 196)`}><g className="fg-pop">
      <Form pts={[[-23, -38], [0, -38.6], [23.4, -38], [24, 0], [0, 0.6], [-24, 0]]} cls="fg-paper" seed={61} jit={0.4} w={1.1} />
      <Form pts={[[-31, -36.4], [-14, -50], [0, -64], [14, -50], [31, -36.6], [0, -38]]} cls="fg-terra" seed={62} jit={0.4} w={1.2} />
      <Form pts={[[-6.4, -23], [6, -23.6], [6.4, 0], [-6.6, 0]]} cls="fg-deep" seed={63} jit={0.3} w={0.9} />
      <Form pts={[[11, -32], [19.4, -32.4], [19, -23.6], [11.4, -24]]} cls="fg-glass" seed={64} jit={0.2} w={0.8} />
    </g></g>
  );
}

const KID_LOOK: { shirt: Shirt; hair: HairKind; tone: Tone }[] = [{ shirt: "c", hair: "curly", tone: 2 }, { shirt: "d", hair: "bun", tone: 1 }, { shirt: "b", hair: "bob", tone: 3 }];

export default function Household({ profile }: { profile: Profile }) {
  const partner = profile.partner_age != null;
  const kids = (profile.children ?? []).map((c, i) => ({ ...c, i }));
  const pets: ("dog" | "cat")[] = [];
  for (const p of profile.pets ?? []) for (let k = 0; k < Math.min(p.count, 6); k++) if (p.kind !== "other") pets.push(p.kind);
  const nKids = Math.min(kids.length, MAX.kids), nPets = Math.min(pets.length, MAX.pets);
  // the youngest stands in front so the taller ones behind still show
  const front = kids.slice(0, nKids).sort((a, b) => a.age - b.age || a.i - b.i);
  const back = (n: number) => Array.from({ length: n }, (_, k) => n - 1 - k);
  const kid0 = partner ? 250 : 200;
  const extra = kids.length - nKids + pets.length - nPets;
  const line = householdLine(profile);
  const working = (profile.pay_per_year ?? 0) > 0;
  return (
    <figure className="household">
      <svg viewBox="0 0 400 210" aria-hidden="true" focusable="false" className="household-svg">
        <Ground x0={8} x1={392} y={197} />
        {profile.home?.owns && <House x={364} />}
        {back(nPets).map((i) => { const at = depth(i, 40, 196); return pets[i] === "dog" ? <Dog key={`d${i}`} {...at} /> : <Cat key={`c${i}`} {...at} />; })}
        <Person x={120} b={band(profile.age)} shirt="a" hair="crop" tone={2} briefcase={working} />
        {partner && <Person x={190} b={band(profile.partner_age)} shirt="b" hair="bob" tone={3} scale={0.96} briefcase={(profile.partner_pay_per_year ?? 0) > 0} />}
        {back(nKids).map((i) => {
          const c = front[i];
          const at = depth(i, kid0, 196);
          const look = KID_LOOK[c.i % 3];
          return <Person key={`k${c.i}`} x={at.x} y={at.y} fade={at.fade} b="20s" shirt={look.shirt} hair={look.hair} tone={look.tone} scale={childScale(c.age) * at.scale} kid={c.age < 18} baby={c.age < 2} />;
        })}
        {extra > 0 && <text x={350} y={110} className="household-more">+{extra}</text>}
      </svg>
      <figcaption className="household-caption" aria-live="polite">{line}</figcaption>
    </figure>
  );
}
