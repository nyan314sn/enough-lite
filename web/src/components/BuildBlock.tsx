import { useEffect, useRef } from "react";
import { neededLabel, isGuess } from "./LivePanel";
import type { Field, Profile } from "../types";

const MORE: Record<string, string> = { home: "your home", debts: "your debts", children_count: "how many children", children: "your children", spending_now_per_year: "your spending now" };
const label = (k: string) => MORE[k] ?? neededLabel(k);

/** "your age and your state": the plain list of what is still missing. Three at most, then "and 4 more". */
export const stillNeeded = (missing: string[]) => {
  const l = missing.map(label);
  if (l.length === 0) return "a few answers in the chat";
  const shown = l.length > 3 ? [...l.slice(0, 2), `${l.length - 2} more`] : l;
  return shown.length === 1 ? shown[0] : `${shown.slice(0, -1).join(", ")} and ${shown[shown.length - 1]}`;
};

export const ESCAPE_TEXT = "Build my plan with typical numbers for the rest";

/** The figures that drive the plan most. */
export const KEY_FIGURES = ["age", "partner_age", "pay_per_year", "partner_pay_per_year", "savings", "spending_now_per_year", "spending_per_year", "retire_age", "social_security_per_year"];


/** The key figures present now, those the person never gave (estimate, assumed, default) first. */
export function keyFigures(fields: Field[]): Field[] {
  const mine = KEY_FIGURES.map((k) => fields.find((f) => f.key === k)).filter((f): f is Field => !!f);
  return [...mine.filter(isGuess), ...mine.filter((f) => !isGuess(f))];
}

/** What was checked: which key figures were guesses, and the numbers. Used to decide whether to ask again. */
export interface Checked { guesses: string[]; nums: Record<string, number> }
export function snapshot(fields: Field[]): Checked {
  const fs = keyFigures(fields);
  return { guesses: fs.filter(isGuess).map((f) => f.key), nums: Object.fromEntries(fs.filter((f) => typeof f.value === "number").map((f) => [f.key, f.value as number])) };
}
/** Ask again only if a guessed figure was added, or a figure moved by more than 20%. */
export function needsCheck(before: Checked | null, fields: Field[]): boolean {
  if (!before) return true;
  const now = snapshot(fields);
  if (now.guesses.some((k) => !before.guesses.includes(k))) return true;
  return Object.entries(now.nums).some(([k, v]) => { const o = before.nums[k]; return o === undefined ? false : o === 0 ? v !== 0 : Math.abs(v - o) / Math.abs(o) > 0.2; });
}

export const CHECK_NOTE = "Before I build, check your figures below. The ones marked estimate are my guesses; change any that are wrong.";
const reduced = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** The inline note before the first build. It holds no figures: it points at the answers panel, where the guessed rows are
 *  highlighted (and their groups opened). Focus moves in when it opens; Esc closes it. */
function CheckPanel({ idp, onConfirm, onClose }: { idp: string; onConfirm: () => void; onClose: (change: boolean) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const head = useRef<HTMLParagraphElement>(null);
  const live = () => box.current?.closest(".live");
  useEffect(() => {
    head.current?.focus({ preventScroll: true });
    // Groups open on the render after this one: scroll once they have.
    let a = 0, b = 0;
    a = requestAnimationFrame(() => { b = requestAnimationFrame(() => {
      live()?.querySelector<HTMLElement>(".field.is-check")?.scrollIntoView?.({ block: "nearest", behavior: reduced() ? "auto" : "smooth" });
    }); });
    return () => { cancelAnimationFrame(a); cancelAnimationFrame(b); };
  }, []);
  const change = () => {
    const root = live();
    onClose(true);
    requestAnimationFrame(() => {
      let el = root?.querySelector<HTMLElement>(".field.is-check .pen") ?? null;
      const hid = el?.closest("[hidden]");
      if (el && hid) el = hid.parentElement?.querySelector<HTMLElement>(".group-toggle") ?? null;
      (el ?? root?.querySelector<HTMLElement>(".pen"))?.focus();
    });
  };
  return (
    <div ref={box} className="check" role="group" aria-labelledby={`${idp}-check-h`} onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onClose(false); } }}>
      <p id={`${idp}-check-h`} ref={head} tabIndex={-1} className="check-h">{CHECK_NOTE}</p>
      <div className="check-btns">
        <button type="button" className="btn btn-primary btn-big" onClick={onConfirm}>Looks right, build my plan</button>
        <button type="button" className="btn btn-quiet btn-big" onClick={change}>Let me change something</button>
      </div>
    </div>
  );
}

/** The one "Build my plan" button. It sits under the family picture, always shown, and works only when the answers are ready.
 *  Not ready: it is marked aria-disabled (still focusable, so a screen reader can find out why) and a line says what is missing.
 *  Ready: it takes the accent fill and a polite live region says so once. The first press opens a note that points at the answers panel. */
export default function BuildBlock({ idp, canBuild, missing, started, onBuild, onEscape, compact = false, checking = false, onConfirm, onCloseCheck }: { idp: string; canBuild: boolean; missing: string[]; started: boolean; onBuild: () => void; onEscape?: () => void; compact?: boolean; checking?: boolean; fields?: Field[]; profile?: Profile; onConfirm?: () => void; onCloseCheck?: (change: boolean) => void }) {
  const why = `${idp}-build-why`;
  const btn = useRef<HTMLButtonElement>(null);
  return (
    <div className={`build${compact ? " build-compact" : ""}${canBuild ? " is-ready" : ""}`} data-testid="build-block">
      <button type="button" ref={btn} className={`btn btn-big ${canBuild ? "btn-primary" : "btn-off"}`} aria-disabled={!canBuild} aria-describedby={why}
        onClick={() => { if (canBuild) onBuild(); }}>Build my plan</button>
      <p id={why} className="build-why">{canBuild ? "Check the figures, then build." : `Still needed: ${stillNeeded(missing)}.`}</p>
      {checking && canBuild && onConfirm && onCloseCheck && <CheckPanel idp={idp} onConfirm={onConfirm} onClose={(change) => { onCloseCheck(change); if (!change) btn.current?.focus(); }} />}
      {!canBuild && started && onEscape && !compact && <button type="button" className="build-escape" onClick={onEscape}>Build with typical numbers for the rest</button>}
      <p className="sr-only" role="status" aria-live="polite">{canBuild ? "Ready: you can build your plan." : ""}</p>
    </div>
  );
}
