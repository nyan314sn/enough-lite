import { useEffect, useRef } from "react";
import { neededLabel, isGuess, SourceTag } from "./LivePanel";
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
function CheckPanel({ idp, fields = [], onConfirm, onClose }: { idp: string; fields?: Field[]; onConfirm: () => void; onClose: (change: boolean) => void }) {
  const retire = fields.find((f) => f.key === "retire_age");
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
      {retire && (
        <ul className="check-figures" data-testid="check-figures">
          <li>Retire at <strong className="num">{retire.display ?? String(retire.value)}</strong> <SourceTag source={retire.source} /></li>
        </ul>
      )}
      <div className="check-btns">
        <button type="button" className="btn btn-primary btn-big" onClick={onConfirm}>Looks right, build my plan</button>
        <button type="button" className="btn btn-quiet btn-big" onClick={change}>Let me change something</button>
      </div>
    </div>
  );
}

export const BUILD_NOW = "You can build now. We'll use typical figures for anything you skip — you can check them first.";
export const BUILD_FIRST = "Tell us a little about yourself first, then you can build.";
export const CHAT_HINT = "You can press Build my plan at any time. I'll fill in typical figures for what you skip.";

/** The one "Build my plan" button. It sits under the family picture. It is active as soon as the person has said anything to start from.
 *  With answers missing, pressing it fills typical figures for the rest (the parent does that) and the check step then shows every guess,
 *  marked estimate, for approval. Before the first answer it is truly disabled, with a line that says why. */
/** Shown under the dimmed button while the check note is open. */
export const CHECK_FIRST = "Check the figures below first.";

export default function BuildBlock({ idp, canBuild, canStart = canBuild, onBuild, compact = false, checking = false, onConfirm, onCloseCheck, fields, }: { idp: string; canBuild: boolean; canStart?: boolean; missing?: string[]; started?: boolean; onBuild: () => void; compact?: boolean; checking?: boolean; fields?: Field[]; profile?: Profile; onConfirm?: () => void; onCloseCheck?: (change: boolean) => void }) {
  const why = `${idp}-build-why`;
  const btn = useRef<HTMLButtonElement>(null);
  // While the check note is open, its own "Looks right, build my plan" is the one button to press: this one steps back (dimmed).
  const open = checking && canBuild && !!onConfirm && !!onCloseCheck;
  const active = canStart && !open;
  return (
    <div className={`build${compact ? " build-compact" : ""}${active ? " is-ready" : ""}${open ? " is-checking" : ""}`} data-testid="build-block">
      <button type="button" ref={btn} className={`btn btn-big ${active ? "btn-primary" : "btn-off"}`} disabled={!active} aria-describedby={why} onClick={onBuild}>Build my plan</button>
      <p id={why} className="build-why">{open ? CHECK_FIRST : !canStart ? BUILD_FIRST : canBuild ? "Check the figures, then build." : BUILD_NOW}</p>
      {checking && canBuild && onConfirm && onCloseCheck && <CheckPanel idp={idp} fields={fields} onConfirm={onConfirm} onClose={(change) => { onCloseCheck(change); if (!change) btn.current?.focus(); }} />}
      <p className="sr-only" role="status" aria-live="polite">{canStart ? "You can build your plan now." : ""}</p>
    </div>
  );
}
