import { useEffect, useRef, useState, type FormEvent } from "react";
import { cents, scrollBehavior, showValue } from "../format";
import { useCompact } from "./TeamPanel";
import { MAX_WHATIFS, shortName } from "./WhatIf";
import { movesOf } from "../readiness";
import type { Api, AskResponse, Plan, PlanEvent, Profile } from "../types";

// The chat box: the only text box on the plan screen. Answers to rule questions come with their sources; a What If goes up to the plan
// area (the baseline folds to one line) and the chat keeps a note with a way to reopen it; a refusal is said plainly.

export const SUGGEST = ["Retire at 60", "Another child", "Get a dog", "Markets fall 30%"];

/** The What If chips, fitted to the person: no retire age at or below their age (or any, if they have already retired or are 70 or more),
 *  none that repeats the plan as it stands, and no "Another child" past about 50. */
export function suggestions(retireAge?: number | null, age?: number | null, alreadyRetired?: boolean | null): string[] {
  const retired = alreadyRetired === true || (age != null && retireAge != null && retireAge <= age);
  const out: string[] = [];
  for (const s of SUGGEST) {
    if (s === "Another child") { if (age == null || age <= 50) out.push(s); continue; }
    if (!/^Retire at \d{2}$/.test(s)) { out.push(s); continue; }
    if (retired || (age != null && age >= 70)) continue;
    const cands = [Number(s.slice(10)), ...(retireAge != null ? [retireAge + 2, retireAge - 2] : [])];
    const pick = cands.find((t) => t !== retireAge && t <= 70 && (age == null || t > age));
    if (pick != null) out.push(`Retire at ${pick}`);
  }
  return out;
}

const norm = (q: string) => q.trim().toLowerCase().replace(/\s+/g, " ");

export interface WhatIfEntry { id: number; q: string; name: string; text: string; plan: Plan; retireAfter: number | null; citations: AskResponse["citations"]; tokens?: AskResponse["tokens"]; cost_usd?: number | null }

/** Which advisers a What If sends back to work: a guess from the words, shown while the answer is on its way. */
export function rerunFor(q: string): string[] {
  const s = q.toLowerCase();
  const out = new Set<string>(["adviser"]);
  if (/retire|age|live|longev|health/.test(s)) { out.add("longevity"); out.add("markets"); out.add("tax"); }
  if (/child|kid|baby|college|dog|cat|pet|house|home|mortgage|parent|school/.test(s)) { out.add("family"); out.add("markets"); }
  if (/market|fall|crash|drop|return|stock|inflation|%|recession/.test(s)) out.add("markets");
  if (/tax|state|move|roth|401|ira/.test(s)) out.add("tax");
  if (out.size === 1) out.add("markets");
  return [...out];
}

const CHANGE_LABEL: Record<string, (v: string) => string> = {
  age: (v) => `Your age is now ${v}`,
  partner_age: (v) => `Your partner's age is now ${v}`,
  state: (v) => `You now live in ${v}`,
  pay_per_year: (v) => `Your pay is now ${v}`,
  partner_pay_per_year: (v) => `Your partner's pay is now ${v}`,
  spending_per_year: (v) => `Your spending is now ${v}`,
  social_security_per_year: (v) => `Your Social Security is now ${v}`,
  retire_age: (v) => `You plan to retire at ${v}`,
  savings: (v) => `Your savings are now ${v}`,
  risk: (v) => `Your risk setting is now ${v.toLowerCase()}`,
};

/** "Your pay is now $150,000 a year." One plain sentence for each answer that changed. */
export function updateNote(before: Profile, after: Profile, only?: string[]): string {
  const bits = Object.keys(after).filter((k) => k in CHANGE_LABEL).filter((k) => !only || only.length === 0 || only.includes(k)).filter((k) => JSON.stringify(after[k]) !== JSON.stringify(before[k]) && after[k] != null)
    .map((k) => `${CHANGE_LABEL[k](showValue(k, after[k]))}.`);
  return bits.length ? bits.join(" ") : "Your plan was updated.";
}

/** "Worth trying": the plan's levers (debt, match, cover and so on), each sent to the server as its own What If, word for word.
 *  With no levers (an older backend, or nothing to flag) a plain fallback is built from the person's own numbers. */
/** True when a What If sentence makes no sense for this person: "retire at N" for someone retired or past N, "another child" past 50. */
export function pointless(q: string, age?: number | null, alreadyRetired?: boolean | null): boolean {
  const m = q.toLowerCase().match(/retire\w*\s+(?:at|by|in)?\s*(?:age\s+)?(\d{2})\b/);
  if (m && (alreadyRetired === true || (age != null && Number(m[1]) <= age))) return true;
  if (/(another|one more|a new|a fifth|a third|a fourth|second)\s+(child|kid|baby)|have a (baby|child)/.test(q.toLowerCase()) && age != null && age > 50) return true;
  return false;
}

export const MAX_IDEAS = 5;

export function ideas(profile: Profile, plan?: Plan | null): { label: string; q: string; why?: string }[] {
  const retired = plan?.already_retired === true;
  const levers = (plan?.levers ?? []).filter((l) => l.whatif_text && !pointless(l.whatif_text, profile.age, retired) && !pointless(l.title, profile.age, retired));
  // the plan's own moves come first, by their concrete titles: this is now the only place to try one
  const own: { label: string; q: string; why?: string }[] = [];
  if (plan && Array.isArray(plan.actions)) for (const m of movesOf(plan)) {
    const q = m.tryQ ?? m.points.find((p) => p.whatif_text)?.whatif_text ?? null;
    if (q && !pointless(q, profile.age, retired) && !pointless(m.title, profile.age, retired)) own.push({ label: m.title, q, why: m.why });
  }
  const seen = new Set<string>();
  const uniq = [...own, ...levers.map((l) => ({ label: l.title, q: l.whatif_text as string, why: l.why }))].filter((x) => { const k = norm(x.q); if (seen.has(k)) return false; seen.add(k); return true; });
  if (uniq.length > 0) return uniq.slice(0, MAX_IDEAS);
  if ((plan?.levers ?? []).length > 0) return [];
  const out: { label: string; q: string }[] = [];
  const ra = profile.retire_age;
  if (!retired && ra != null && ra + 2 <= 70 && (profile.age == null || ra + 2 > profile.age)) out.push({ label: "Retire 2 years later", q: `Retire at ${ra + 2}` });
  const rate = typeof profile.save_rate === "number" ? profile.save_rate : 0.1;
  const pay = (Number(profile.pay_per_year) || 0) + (Number(profile.partner_pay_per_year) || 0);
  // saving more only means something while someone is at work with pay; a retiree or someone with no pay can spend less instead
  if (!retired && pay > 0) {
    if (rate < 0.4) out.push({ label: "Save 5% more of pay", q: `Save ${Math.round((rate + 0.05) * 100)}% of my pay` });
  } else {
    out.push({ label: "Spend $500 less a month", q: "What if I spend $500 less a month" });
  }
  return out;
}

/** A bare yes: the person agrees to the What If the app offered. */
const YES = /^\s*(?:yes|yeah|yep|yup|sure|ok|okay|please|go ahead|do it|run it)\b[\s\S]{0,20}$/i;
interface Turn { q: string; shown?: string; r?: AskResponse; error?: boolean; stale?: boolean; whatif?: number; updated?: string; full?: boolean }

/** Said in the chat when five What Ifs are already open. */
export const FULL_TEXT = `You have ${MAX_WHATIFS} What Ifs open. Remove one first (the ✕ on its tab), then ask again.`;

export const ASK_ERROR = "That did not work, and your plan has not changed. Your question is still in the box.";

export default function AskBox({ api, profile, plan, onCost, onWhatIf, onOpen, onAsking, onChange, stale = false, canRebuild = true, onRebuild, whatifIds, request, full = false, composing = false, onCancel, onRunEvent, onRunEnd }: {
  api: Api; profile: Profile; plan: Plan; onCost: (usd: number, tokens?: AskResponse["tokens"]) => void;
  onWhatIf?: (e: Omit<WhatIfEntry, "id">) => number | null; onOpen?: (id: number) => void; onAsking?: (agents: string[]) => void; onChange?: (profile: Profile, plan: Plan) => void;
  /** The plan is older than the person's answers: a What If would run on the old plan, so offer a rebuild first. */
  stale?: boolean; canRebuild?: boolean; onRebuild?: () => void;
  /** The What Ifs that are still on screen; a "Show" button for any other has nothing to open. Omit to leave every button on. */
  whatifIds?: number[];
  /** A What If asked from elsewhere on the page (a starting point): it runs the same way a chip does. A new id runs it again. */
  request?: { id: number; q: string } | null;
  /** The most What Ifs are open: a chip that makes a What If says so and sends nothing. A typed message that turns out to be a What If is not added. */
  full?: boolean;
  /** The person pressed "+ What if" at the top: this section is highlighted and offers Cancel. */
  composing?: boolean; onCancel?: () => void;
  /** A What If's run, as it happens: the team's events with the What If's short name (the panel shows them), then onRunEnd when the ask ends. */
  onRunEvent?: (e: PlanEvent, name: string) => void; onRunEnd?: () => void;
}) {
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [ideasOpen, setIdeasOpen] = useState<boolean | null>(null);
  const compact = useCompact();
  const last = useRef<HTMLElement>(null);
  const pending = useRef<Record<string, unknown> | null>(null);   // a change waiting for the person's reply: sent back with the next message

  useEffect(() => {
    const t = turns[turns.length - 1];
    if (t?.r && t.r.kind !== "whatif") last.current?.scrollIntoView?.({ block: "nearest", behavior: scrollBehavior() });
  }, [turns]);

  async function ask(q: string, force = false, shown?: string, isWhatIf = false) {
    const t = q.trim();
    if (!t || busy) return;
    setDraft((d) => (norm(d) === norm(t) ? "" : d));
    if (stale && !force) {   // the plan is out of date: say so, keep the question, and offer the rebuild
      setTurns((ts) => [...ts.filter((x) => !(x.stale && x.q === t)), { q: t, shown, stale: true }]);
      return;
    }
    if (/retire/i.test(t) && !pending.current && pointless(t, profile.age, plan.already_retired)) {   // said here, not sent: there is nothing to test
      const text = plan.already_retired ? "You have already retired, so there is no retirement age to test. These What Ifs can change your plan:" : `You are already ${profile.age}, so that age has passed. Try a later one.`;
      // a retiree gets the What Ifs that can move their plan as buttons, not a dead end
      const offer = plan.already_retired ? ["What if I spend $500 less a month", "What if markets fall 30%"] : null;
      setTurns((ts) => [...ts, { q: t, shown, r: { kind: offer ? "clarify" : "answer", text, citations: [], quick_answers: offer } }]);
      return;
    }
    if (full && isWhatIf && !pending.current) {
      setTurns((ts) => [...ts, { q: t, shown, full: true }]);
      return;
    }
    setBusy(true);
    setTurns((ts) => [...ts.filter((x) => !((x.error || x.stale) && x.q === t)), { q: t, shown }]);
    onAsking?.(rerunFor(t));
    try {
      const sent = pending.current;   // the change the person is answering: its answers are the ones to name, not figures the rebuild derived
      const facts = sent && typeof sent.facts === "object" && sent.facts ? Object.keys(sent.facts) : [];
      // a typed "yes" to an offered What If: name the tab from the sentence the app built, not from "yes"
      const said = sent && typeof sent.whatif === "string" && sent.whatif && YES.test(t) ? sent.whatif : t;
      // a What If streams its team's work to the panel (the same events as the plan); other answers send none
      const runName = shortName(said, said === t ? shown : undefined);
      const r = onRunEvent ? await api.ask(t, profile, plan, sent, (e) => onRunEvent(e, runName)) : await api.ask(t, profile, plan, sent);
      pending.current = r.pending_change ?? null;
      if (r.cost_usd) onCost(r.cost_usd, r.tokens);
      let whatif: number | undefined;
      let wasFull = false;
      if (r.kind === "whatif" && r.plan && onWhatIf) {
        const retireAfter = Number(said.match(/retire\b[^.?!]*?\b(?:at|by) (\d{2})\b/i)?.[1]) || null;
        const id = onWhatIf({ q: said, name: shortName(said, said === t ? shown : undefined), text: r.text, plan: r.plan, retireAfter, citations: r.citations, tokens: r.tokens, cost_usd: r.cost_usd });
        if (id == null) wasFull = true; else whatif = id;
      }
      let updated: string | undefined;
      if (r.kind === "change" && r.profile && r.plan && onChange) {
        if (r.status === "applied") { const n = updateNote(profile, r.profile, facts); updated = n === "Your plan was updated." && r.text ? r.text : n; }
        else updated = updateNote(profile, r.profile, facts);
        onChange(r.profile, r.plan);
      }
      setTurns((ts) => [...ts.slice(0, -1), { q: t, shown, r, whatif, updated, full: wasFull }]);
    } catch {
      // Never show the server's own words: they are for logs, not for people. The question goes back in the box and the turn offers Retry.
      setTurns((ts) => [...ts.slice(0, -1), { q: t, shown, error: true }]);
      setDraft((d) => d || t);
    } finally {
      setBusy(false);
      onAsking?.([]);
      onRunEnd?.();
    }
  }
  const submit = (e: FormEvent) => { e.preventDefault(); void ask(draft); };
  const lastReq = useRef(0);
  useEffect(() => {
    if (request && request.id !== lastReq.current) { lastReq.current = request.id; void ask(request.q, false, undefined, true); }
  }, [request?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // What If chips already tried on this plan are marked; a confirmed change starts the count again.
  const lastChange = turns.reduce((n, t, i) => (t.r?.kind === "change" && t.updated ? i : n), -1);
  const tried = new Set(turns.slice(lastChange + 1).filter((t) => t.r?.kind === "whatif").map((t) => norm(t.q)));
  const chip = (key: string, label: string, q: string, title?: string, shown?: string) => (
    <button key={key} type="button" className={`chip${tried.has(norm(q)) ? " tried" : ""}`} disabled={busy} title={title ?? q} onClick={() => ask(q, false, shown, true)}>
      {tried.has(norm(q)) && <span aria-hidden="true">✓ </span>}{label}{tried.has(norm(q)) && <span className="sr-only"> (already tried)</span>}
    </button>
  );
  const ideaList = ideas(profile, plan);
  const showChips = ideasOpen ?? !compact;

  // A What If lives in its tab, not in the chat: the log keeps rule questions, refusals, clarifications, changes and errors.
  const shown = turns.filter((t) => !(t.r?.kind === "whatif" && t.whatif != null));
  return (
    <>
      {shown.length > 0 && (
        <section className="turns card" aria-label="Your questions" aria-live="polite">
          {shown.map((t, i) => (
            <TurnView key={i} t={t} el={i === shown.length - 1 ? last : undefined} onOpen={onOpen} chips={i === shown.length - 1 && !busy ? t.r?.quick_answers ?? [] : []} onChip={ask}
              onRetry={() => ask(t.q, false, t.shown)} onAskAnyway={() => ask(t.q, true, t.shown)} onRebuild={onRebuild} canRebuild={canRebuild} stale={stale}
              showable={whatifIds == null || (t.whatif != null && whatifIds.includes(t.whatif))} />
          ))}
        </section>
      )}
      <section className={`ask${composing ? " composing" : ""}`} aria-labelledby="ask-h" data-testid="whatif-section">
        <div className="ask-head">
          <h2 id="ask-h" className="ask-title">Try a What If</h2>
          <p className="ask-line">Change one thing and see your plan again. Your baseline stays as it is.</p>
          {composing && <button type="button" className="btn btn-quiet btn-small ask-cancel" onClick={onCancel}>Cancel</button>}
        </div>
        {showChips && (
          <div className="chip-scroll" role="group" aria-label="Ideas and What Ifs">
            {ideaList.length > 0 && (
              <div className="quick ideas" role="group" aria-label="Ideas to try">
                <span className="h-mini">Worth trying</span>
                {ideaList.map((s) => chip(s.label, s.label, s.q, s.why, s.label))}
              </div>
            )}
            <div className="quick" role="group" aria-label="Try a What If">
              {suggestions(profile.retire_age, profile.age, plan.already_retired).filter((s) => !ideaList.some((i) => norm(i.q).replace(/^what if i /, "") === norm(s).replace(/^what if i /, ""))).map((s) => chip(s, s, s))}
            </div>
          </div>
        )}
        <form className="composer" onSubmit={submit}>
          <label htmlFor="ask-input" className="sr-only">Ask a question, or try a What If</label>
          <input id="ask-input" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Ask a rule question, or type a What If such as “retire at 60”" maxLength={500} autoComplete="off" />
          {compact && <button type="button" className="btn btn-quiet ideas-toggle" aria-expanded={showChips} onClick={() => setIdeasOpen(!showChips)}>Ideas {showChips ? "▾" : "▴"}</button>}
          <button type="submit" className="btn btn-primary" disabled={busy || !draft.trim()}>{busy ? "Checking…" : "Ask"}</button>
        </form>
      </section>
    </>
  );
}

function TurnView({ t, el, onOpen, chips, onChip, onRetry, onAskAnyway, onRebuild, canRebuild, stale, showable }: {
  t: Turn; el?: React.Ref<HTMLElement>; onOpen?: (id: number) => void; chips: string[]; onChip: (q: string) => void;
  onRetry: () => void; onAskAnyway: () => void; onRebuild?: () => void; canRebuild: boolean; stale: boolean; showable: boolean;
}) {
  return (
    <article className={`turn ${t.r ? `turn-${t.r.kind}` : ""}`} ref={el}>
      <p className="turn-q"><span className="sr-only">You asked: </span>{t.shown ?? t.q}</p>
      {!t.r && !t.error && !t.stale && <p className="muted" role="status"><span className="spinner" aria-hidden="true" /> Checking…</p>}
      {t.error && (
        <div className="alert" role="alert">
          <p>{ASK_ERROR}</p>
          <button type="button" className="btn btn-primary btn-small" onClick={onRetry}>Retry</button>
        </div>
      )}
      {t.stale && (
        <div className="alert stale-ask" role="status">
          <p>Your answers changed after this plan was built, so the plan is out of date. A What If would run on the old plan.</p>
          <div className="row">
            <button type="button" className="btn btn-primary btn-small" onClick={onRebuild}>{canRebuild ? "Rebuild plan" : "Finish your answers"}</button>
            <button type="button" className="btn btn-quiet btn-small" onClick={onAskAnyway}>Ask on the old plan</button>
          </div>
        </div>
      )}
      {t.full && <p className="turn-a" role="status" data-testid="whatif-full">{FULL_TEXT}</p>}
      {t.r?.kind === "refused" && <div className="refused" role="note">{!t.r.emergency && <strong>We can't help with that.</strong>}<p>{t.r.text}</p></div>}
      {(t.r?.kind === "answer" || t.r?.kind === "change" || t.r?.kind === "clarify") && !t.updated && <p className="turn-a">{t.r.text}</p>}
      {t.updated && <p className="updated-note" role="status">{t.updated}</p>}
      {chips.length > 0 && <div className="quick turn-chips" role="group" aria-label="Quick answers">{chips.map((c) => <button key={c} type="button" className="chip" onClick={() => onChip(c)}>{c}</button>)}</div>}
      {t.r?.kind === "whatif" && !t.full && (
        <>
          <p className="turn-a">{t.r.text}</p>
          {t.whatif == null || !onOpen
            ? <p className="muted small">No new plan came back for this What If.</p>
            : showable && !stale
              ? <button type="button" className="btn btn-quiet btn-small" onClick={() => onOpen(t.whatif!)}>Show this What If ▴</button>
              : <p className="muted small" data-testid="whatif-gone">{stale ? "Your answers changed since this What If, so it is out of date." : "This What If is no longer on screen: it was removed, or your answers changed. Ask it again."}</p>}
        </>
      )}
      {t.r && t.r.kind !== "change" && t.r.citations.length > 0 && (
        <div className="cites">
          <p className="h-mini">Sources</p>
          <ul>{t.r.citations.map((c, i) => <li key={i}><a href={c.url} target="_blank" rel="noreferrer noopener">{c.title}</a></li>)}</ul>
        </div>
      )}
      {t.r?.cost_usd != null && <p className="turn-cost muted small">AI cost {cents(t.r.cost_usd)}</p>}
    </article>
  );
}
