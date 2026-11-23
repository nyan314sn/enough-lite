import { useEffect, useState } from "react";
import { usd } from "../format";
import { MAX_TITLE_WORDS, PLAN_WORDS, clampWords, ladder, type Ladder as LadderModel, type Move } from "../readiness";
import type { Plan } from "../types";
import { VsMarker } from "./WhatIf";

// The money ladder: needs, wants, wishes as three layers of one bar, all in dollars a year, one scale. It is the plan's main picture.
// Needs come first and must be safe, wants are what you can count on above them, wishes are the rest of the goal (open).
// Three levels to unlock: needs safe, wants sure, goal covered. Every figure comes from the plan (readiness.ts: ladder()).
// Colour is never the only signal: each layer has an icon and a word. A row can be hovered, tapped or reached with the keyboard to read it.

const W = PLAN_WORDS.ladder;
type Key = "needs" | "wants" | "wishes";

const reduced = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Grows from 0 to the value once shown (and between values on a What If), unless the person asked for less motion. */
export function useGrow(value: number): number {
  const [v, setV] = useState(() => (reduced() ? value : 0));
  useEffect(() => {
    if (reduced() || typeof requestAnimationFrame === "undefined") { setV(value); return; }
    const id = requestAnimationFrame(() => setV(value));
    return () => cancelAnimationFrame(id);
  }, [value]);
  return v;
}

const ICON = { needs: "M3 11.5 12 4l9 7.5M5.5 10v9.5h13V10M10 19.5v-5h4v5", wants: "M4 7h16l-1.6 9.2a2 2 0 0 1-2 1.8H7.6a2 2 0 0 1-2-1.8L4 7Zm4 0 1.5-3M16 7l-1.5-3", wishes: "m12 3.5 2.5 5.2 5.7.8-4.1 4 1 5.6L12 16.4l-5.1 2.7 1-5.6-4.1-4 5.7-.8L12 3.5Z" };
const Icon = ({ k }: { k: Key }) => <svg className="lad-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d={ICON[k]} /></svg>;

export interface Layer { key: Key; label: string; amount: number; shown: string; eg: string; reached: boolean; word: string; mark: string; note: string; read: string }

/** The three rows as words, from the model. A layer with no goal to measure (no wishes) is left out. */
export function layers(l: LadderModel, pets: boolean): Layer[] {
  const out: Layer[] = [];
  const sure = l.wantsSure;
  out.push({
    key: "needs", label: W.needs, amount: l.needs, shown: usd(l.needs), eg: pets ? W.needsEgPets : W.needsEg, reached: l.needsSafe,
    word: l.needsSafe ? W.needsSafe : W.needsNot, mark: l.needsSafe ? "✓" : "!", note: `${l.paid} of 100 tests`,
    read: `Needs: ${usd(l.needs)} a year. Paid in ${l.paid} of 100 market tests.`,
  });
  const none = l.countOn < l.needs ? W.wantsNone : "Your needs use all of it, so nothing is left for wants.";
  const noneShort = l.countOn < l.needs ? W.wantsNoneShort : W.wantsZeroShort;
  out.push({
    key: "wants", label: W.wants, amount: l.wants, shown: `+${usd(l.wants)}`, eg: W.wantsEg, reached: sure,
    word: sure ? W.wantsSure : W.wantsNot, mark: sure ? "✓" : "○", note: sure ? "" : noneShort,
    read: sure ? `Wants: ${usd(l.wants)} a year on top of your needs. You can count on ${usd(l.countOn)} in all.` : `Wants: $0 a year. ${none} You can count on ${usd(l.countOn)}.`,
  });
  if (l.goal != null) {
    const lasts = l.lasts != null ? ` Goal lasts in ${l.lasts} of 100 tests.` : "";
    out.push({
      key: "wishes", label: W.wishes, amount: l.wishes, shown: `+${usd(l.wishes)}`, eg: "", reached: l.covered,
      // needs not safe: wishes are locked, not "open" (the ladder unlocks in order: needs, then wants, then wishes)
      word: l.covered ? W.wishesCovered : !l.needsSafe ? W.wishesLocked : W.wishesOpen, mark: l.covered ? "✓" : !l.needsSafe ? "🔒" : "○",
      note: l.covered ? "" : (!l.needsSafe ? W.wishesLockedNote : W.wishesOpenNote).replace(/.$/, ""),
      read: l.covered ? `Wishes: none left. ${W.wishesDone}` : !l.needsSafe ? `Wishes: ${usd(l.wishes)} a year, the rest of your goal of ${usd(l.goal)}. Locked: ${W.wishesLockedNote}${lasts}` : `Wishes: ${usd(l.wishes)} a year, the rest of your goal of ${usd(l.goal)}. ${W.wishesOpenNote}${lasts}`,
    });
  }
  return out;
}

/** The text alternative for the whole bar. */
export function ladderAlt(l: LadderModel, rows: Layer[]): string {
  const parts = rows.map((r) => `${r.label} ${r.key === "needs" ? usd(r.amount) : `${usd(r.amount)} more`}, ${r.word.toLowerCase()}`);
  const sum = l.goal != null && l.countOn < l.goal ? l.goal : l.total;
  return `${l.goal != null ? `Your goal is ${usd(l.goal)} a year. ` : ""}${parts.join(". ")}. Together ${usd(sum)} a year.`;
}

/** The first layer not yet reached, and the move that unlocks it. */
export function nextLevel(rows: Layer[], moves: Move[]): { key: Key; title: string; q: string | null } | null {
  const first = rows.find((r) => !r.reached);
  if (!first) return null;
  const point = moves.find((m) => m.points.length > 0)?.points[0];
  const withTry = moves.filter((m) => m.tryQ);
  if (first.key === "needs" && point) return { key: "needs", title: point.title, q: point.whatif_text || null };
  const pick = (first.key === "wishes" ? withTry.find((m) => m.worth?.text === "Closes the gap") : null) ?? withTry[0] ?? moves[0];
  if (first.key === "needs" && !pick) return null;
  return pick ? { key: first.key, title: pick.title, q: pick.tryQ } : null;
}

export default function Ladder({ plan, base, moves, hideCountOn = false }: { plan: Plan; base?: Plan; moves: Move[]; hideCountOn?: boolean }) {
  const l = ladder(plan, base ? ladder(base).goal : null);
  const lb = base ? ladder(base) : null;
  const pets = /\b(dogs?|cats?|pets?)\b/i.test(plan.needs.line ?? "");
  const rows = layers(l, pets);
  const next = nextLevel(rows, moves);
  const [active, setActive] = useState<Key | null>(null);
  // grows in on first show, and slides between plans on a What If tab
  const [grown, setGrown] = useState(() => reduced());
  useEffect(() => {
    if (reduced() || typeof requestAnimationFrame === "undefined") { setGrown(true); return; }
    const id = requestAnimationFrame(() => setGrown(true));
    return () => cancelAnimationFrame(id);
  }, []);
  const pct = (n: number) => `${grown ? Math.max(0, Math.min(100, (n / l.scale) * 100)).toFixed(2) : "0"}%`;
  const goalAt = l.goal != null ? `${Math.min(100, (l.goal / l.scale) * 100).toFixed(2)}%` : null;
  const reachedBefore = (k: Key) => (!lb ? true : k === "needs" ? lb.needsSafe : k === "wants" ? lb.wantsSure : lb.covered);
  const done = rows.filter((r) => r.reached).length;
  const shownRead = rows.find((r) => r.key === active)?.read ?? "";
  const keyStop = (e: React.KeyboardEvent) => { if (e.key === "Escape") setActive(null); };

  return (
    <section className={`ladder`} aria-labelledby="ladder-h" data-testid="ladder" data-done={done} onKeyDown={keyStop}>
      <div className="lad-head">
        <h3 id="ladder-h" className="lad-title">{W.title}</h3>
      </div>
      <div className="lad-bar" role="img" aria-label={ladderAlt(l, rows)} data-testid="ladder-bar" onMouseLeave={() => setActive(null)}>
        {rows.map((r) => (
          <span key={r.key} data-seg={r.key} data-amount={r.amount}
            className={`lad-seg seg-${r.key}${r.key === "needs" && !r.reached ? " unsafe" : ""}${active === r.key ? " on" : ""}`}
            style={{ width: pct(r.amount) }} onMouseEnter={() => setActive(r.key)} />
        ))}
        {goalAt && <span className="lad-goalmark" style={{ left: goalAt }} aria-hidden="true" />}
      </div>
      <p className="lad-scale small">
        {hideCountOn ? <span /> : <span data-testid="ladder-counton">You can count on <strong className="num">{usd(l.countOn)}</strong></span>}
        {l.goal != null && <strong className="num" data-testid="ladder-goal">Your goal: {usd(l.goal)} a year</strong>}
      </p>
      <ul className="lad-rows">
        {rows.map((r) => {
          const up = r.reached && !reachedBefore(r.key);
          const k = r.key;
          return (
            <li key={r.key} className={`lad-row row-${r.key} ${r.reached ? "reached" : "locked"}${active === r.key ? " on" : ""}`} data-layer={r.key} data-reached={r.reached ? "true" : "false"}>
              <button type="button" className="lad-hit" aria-pressed={active === r.key} aria-describedby="ladder-read"
                onClick={() => setActive(active === r.key ? null : r.key)} onMouseEnter={() => setActive(r.key)} onFocus={() => setActive(r.key)} onBlur={() => setActive(null)}>
                <span className="lad-name"><Icon k={k} />{r.label}</span>
                <span className="lad-amt num" data-testid={`ladder-${k}`}>{r.shown}</span>
                {r.eg && <span className="lad-eg">{r.eg}</span>}
                <span className="lad-status"><span className="lad-mark" aria-hidden="true">{r.mark}</span> <strong>{r.word}</strong>{r.note && <span className="lad-note small"> · {r.note}</span>}</span>
              </button>
              {up && <span className="lad-up" data-testid={`levelup-${k}`}><span aria-hidden="true">{"▲"} </span>{W.levelUp}<span className="sr-only">: {r.label.toLowerCase()} {r.word.toLowerCase()} now</span></span>}
              {lb && k === "needs" && <VsMarker testid="vs-paid" d={l.paid - lb.paid} unit={(n, u) => `${n} ${u ? "more" : "fewer"} of 100`} />}
              {lb && k === "wants" && <VsMarker testid="vs-count" d={l.wants - lb.wants} unit={(n, u) => `${usd(n)} ${u ? "more" : "less"} a year`} />}
              {lb && k === "wishes" && l.lasts != null && lb.lasts != null && <VsMarker testid="vs-lasts" d={l.lasts - lb.lasts} unit={(n, u) => `${n} ${u ? "more" : "fewer"} of 100`} />}
            </li>
          );
        })}
      </ul>
      <p className="lad-tests small muted" data-testid="ladder-tests-tip">{W.testsTip}</p>
      <p id="ladder-read" className="lad-read small" role="status" aria-live="polite" data-testid="ladder-readout">{shownRead}</p>
      {next && (
        <p className="lad-next small" data-testid="ladder-next">
          <span className="lad-next-k">{W.next}:</span> <strong title={next.title}>{clampWords(next.title, MAX_TITLE_WORDS)}</strong>
        </p>
      )}
    </section>
  );
}
