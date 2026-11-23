import { useEffect, useRef, useState, type FormEvent } from "react";
import BuildBlock from "./BuildBlock";
import LivePanel, { NEEDED, sectionNoun, type SsPlan } from "./LivePanel";
import { ESCAPE_TEXT, CHAT_HINT, needsCheck, snapshot, type Checked } from "./BuildBlock";
import { applyEdit, chatLine, editorFor } from "./FieldEditor";
import { EXAMPLE_TEXT } from "../examples";
import { showValue } from "../format";
import type { Api, Field, IntakeResponse, Profile } from "../types";

// Screen 1, "Tell us about yourself": the chat on the left (the one place to type), the live panel on the right.
// While a figure's editor is open on the right, the chat box gives way to a one-line note, so there is still one place to type.
// On a phone the chat fills the screen and the panel opens as a sheet from "Your numbers ▲".

interface Msg { who: "you" | "us"; text: string; hint?: boolean }
interface Quick { label: string; text: string }

/** The question groups the chat can open from a field's pen. */
const GROUP_CHIPS: Record<string, string> = { debts: "Add debts", pension: "Add a pension", saving: "Add saving", insurance: "Add insurance", goals: "Add goals", health: "Add health", costs: "Add costs" };

const OPENING = "Hi. Tell me about your household in a few sentences: your age, your work, where you live, who lives with you, and when you'd like to retire.";
const OPENING_QUICK: Quick[] = [{ label: "Use an example: a doctor with 3 kids, 2 dogs and a mortgage", text: EXAMPLE_TEXT }];

export default function IntakeScreen({ api, onBuild, onProfile, patch = null, load = null, returned = 0, planSS = null, onFirstSend }: { onFirstSend?: () => void; api: Api; load?: { id: number; intake: IntakeResponse; name: string } | null; returned?: number; planSS?: SsPlan | null; patch?: { id: number; profile: Profile } | null; onBuild: (p: Profile) => void; onProfile?: (p: Profile, canBuild: boolean) => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([{ who: "us", text: OPENING }]);
  const [state, setState] = useState<IntakeResponse | null>(null);
  const [quick, setQuick] = useState<Quick[]>(OPENING_QUICK);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSent, setLastSent] = useState<string | null>(null);
  const [sheet, setSheet] = useState(false);
  const [editing, setEditing] = useState<string | null>(null); // the one figure being edited in the panel
  const input = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);

  useEffect(() => { const el = log.current; if (el) el.scrollTop = el.scrollHeight; }, [msgs, busy, error]);

  // The phone sheet is a dialog: Esc closes it from anywhere, Tab stays inside it, and the keyboard goes back to "Your numbers" on close.
  const opener = useRef<HTMLButtonElement>(null);
  const sheetEl = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!sheet) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setSheet(false); return; }
      if (e.key !== "Tab" || !sheetEl.current) return;
      const items = Array.from(sheetEl.current.querySelectorAll<HTMLElement>("button:not(:disabled), input, textarea, select, a[href], [tabindex]:not([tabindex='-1'])")).filter((el) => !el.closest("[hidden]"));
      if (items.length === 0) return;
      const first = items[0], last = items[items.length - 1], a = document.activeElement;
      if (!sheetEl.current.contains(a)) { e.preventDefault(); first.focus(); }
      else if (e.shiftKey && a === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && a === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    const o = opener.current;
    return () => { document.removeEventListener("keydown", onKey); o?.focus(); };
  }, [sheet]);

  const profile: Profile = state?.profile ?? {};
  const fields: Field[] = state?.fields ?? [];
  const missing = state?.missing ?? [];
  const canBuild = fields.length > 0 && missing.length === 0;
  const canStart = fields.length > 0;   // anything to start from: the rest gets typical figures, shown for checking
  const hinted = useRef(false);

  useEffect(() => { onProfile?.(profile, canBuild); }, [state]); // eslint-disable-line react-hooks/exhaustive-deps

  // Admin mode: a sample household opened on page 1, every figure filled in.
  useEffect(() => {
    if (!load) return;
    setState(load.intake);
    setMsgs([{ who: "us", text: `Loaded: ${load.name}. Check any figure on the right, change it, then build the plan.` }]);
    setQuick([]); setError(null); setDraft("");
  }, [load?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // A correction confirmed in the plan chat: the panel shows the new answers, marked "you said".
  useEffect(() => {
    if (!patch) return;
    setState((s) => {
      if (!s) return s;
      const np = patch.profile;
      let ssDisplay: string | null = null;
      const fields = s.fields.map((f) => {
        if (!(f.key in np) || JSON.stringify(np[f.key]) === JSON.stringify(s.profile[f.key])) return f;
        // a figure the chat worked out (the Social Security estimate after a new start age) stays an estimate; only a figure the person gave is "you said"
        const src = ((np.sources as Record<string, string> | undefined) ?? {})[f.key];
        const computed = f.key === "social_security_per_year" && (src === "estimate" || (src == null && f.source === "estimate"));
        let display = showValue(f.key, np[f.key]);
        if (f.key === "social_security_per_year" && np.claim_age != null && Number(np.age ?? 0) < Number(np.claim_age)) {
          display += ` at ${np.claim_age}` + (computed && np.partner_age ? " (each at their own age)" : "");
          ssDisplay = display;
        }
        return { ...f, value: np[f.key], display, source: computed ? "estimate" : "you said", note: computed ? (f.note ?? "").replace(/claiming at \d{2} and your partner at \d{2}/, `claiming at ${np.claim_age} and your partner at ${np.claim_age}`) : null };
      });
      // the section summary says the same as its row
      const sections_status = ssDisplay == null ? s.sections_status : s.sections_status?.map((x) => (x.note && /Social Security/.test(x.note) ? { ...x, note: x.note.replace(/Social Security [^;]*/, `Social Security ${ssDisplay}`) } : x));
      return { ...s, profile: np, fields, sections_status };
    });
  }, [patch?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Back from the plan to change answers: the question the chat was waiting on is old, so its chips go and the chat says what to do now.
  const seen = useRef(returned);   // a fresh start (Start over) mounts with the count it had: that is not a return
  useEffect(() => {
    if (!returned || returned === seen.current) return;
    seen.current = returned;
    setQuick([]); setError(null); setDraft("");
    setMsgs((m) => [...m, { who: "us", text: "Your plan is kept. Change any answer on the right, or tell me what to change." }]);
  }, [returned]);

  /** Clear one section. The fields are removed here (the server keeps no draft) and the server is told, so its next question fits. */
  async function resetSection(name: string, fs: Field[]) {
    if (busy) return;
    const keys = new Set(fs.map((f) => f.key));
    const p: Profile = { ...(state?.profile ?? {}) };
    keys.forEach((k) => { delete p[k]; });
    const gone = [...keys].filter((k) => k in NEEDED);
    setState((s) => s && { ...s, profile: p, fields: s.fields.filter((f) => !keys.has(f.key)), missing: Array.from(new Set([...s.missing, ...gone])) });
    const lead = `Cleared your ${sectionNoun(name)}.`;
    setBusy(true); setError(null);
    try {
      const r = await api.intake("", p, [name]);
      setState(r);
      setMsgs((m) => [...m, { who: "us", text: [lead, r.question?.text].filter(Boolean).join(" ") }]);
      setQuick((r.question?.quick_answers ?? []).map((q) => ({ label: q, text: q })));
    } catch {
      setMsgs((m) => [...m, { who: "us", text: `${lead} Tell me again, or skip.` }]);
      setQuick([{ label: "Skip, use typical", text: "Skip, use typical" }]);
    } finally {
      setBusy(false);
    }
  }

  async function send(text: string, echo = true, profileSoFar?: Profile) {
    const t = text.trim();
    if (!t || busy) return;
    onFirstSend?.();
    if (echo) setMsgs((m) => [...m, { who: "you", text: t }]);
    setBusy(true); setError(null); setLastSent(t); setDraft("");
    try {
      const r = await api.intake(t, profileSoFar ?? state?.profile ?? null);
      setState(r);
      const say = [r.reply, r.question?.text].filter(Boolean).join(" ");
      const hint = !hinted.current && r.fields.length > 0 && r.missing.length > 0;   // once, after the first answer, and only while something is still missing
      if (hint) hinted.current = true;
      if (say || hint) setMsgs((m) => [...m, ...(say ? [{ who: "us" as const, text: say }] : []), ...(hint ? [{ who: "us" as const, text: CHAT_HINT, hint: true }] : [])]);
      setQuick((r.question?.quick_answers ?? []).map((q) => ({ label: q, text: q })));
    } catch (e) {
      setError((e as Error).message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const submit = (e: FormEvent) => { e.preventDefault(); void send(draft); };

  /** A figure edited in the panel: the profile changes here, the source becomes "you said", and the chat is told. */
  function save(f: Field, value: unknown) {
    if (!state) return;
    if (f.editable?.kind === "college") {      // one child's college: that child changes, no other
      const i = f.editable.child ?? 0, v = value as { college_type: "public" | "private" | "none"; college_share: number };
      const kids = (state.profile.children ?? []).map((c, j) => (j === i ? { ...c, ...v, college: v.college_type !== "none", college_source: "you said" as const } : c));
      const profile: Profile = { ...state.profile, children: kids };
      setState({ ...state, profile, fields: state.fields.map((x) => (x.key === f.key ? { ...x, value: kids[i], source: "you said", note: null } : x)) });
      setEditing(null);
      setSheet(false);
      void send(chatLine(f, value), true, profile);
      return;
    }
    const profile: Profile = applyEdit(state.profile, f.key, value);   // the figure goes back to where the profile keeps it
    setState({
      ...state, profile, missing: state.missing.filter((k) => k !== f.key),
      fields: state.fields.map((x) => (x.key === f.key ? { ...x, value, display: showValue(f.key, value), source: "you said", note: null } : x)),
    });
    setEditing(null);
    setSheet(false);   // on a phone the sheet would cover the reply that comes next
    void send(chatLine(f, value), true, profile);
  }

  function edit(f: Field) {
    const ed = f.editable;
    if (editorFor(f)) { setEditing((cur) => (cur === f.key ? null : f.key)); return; }   // every figure has its own editor
    const chip = ed && ed.kind === "group" && ed.ask ? GROUP_CHIPS[ed.ask] : undefined;
    if (chip) { setSheet(false); setEditing(null); void send(chip); return; }   // only a figure with no editor falls back to the chat
    setSheet(false);
    setEditing(null);
    setDraft(`Change ${f.label} to: `);
    requestAnimationFrame(() => { const el = input.current; if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); } });
  }

  function add(what: string) {
    setSheet(false);
    setEditing(null);
    setDraft(`Add ${what}: `);
    requestAnimationFrame(() => { const el = input.current; if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); } });
  }

  // One Build my plan button on screen: under the family picture in the side panel on a desktop; on a phone, in the bottom bar,
  // and under the picture inside the "Your numbers" sheet while it is open.
  const [phone, setPhone] = useState(() => typeof window !== "undefined" && !!window.matchMedia?.("(max-width: 860px)").matches);
  useEffect(() => {
    const mq = window.matchMedia?.("(max-width: 860px)");
    if (!mq) return;
    const on = () => setPhone(mq.matches);
    on(); mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, []);
  // The first press of Build my plan opens a short note and highlights the guessed rows in the answers panel. After one confirmation, later presses build at once,
  // unless a guessed figure was added or a figure moved by more than 20%. Start over remounts this screen, so it asks again.
  const [checking, setChecking] = useState(false);
  const [marking, setMarking] = useState(false);   // the guessed rows are highlighted until the build, Escape, or the person edits that row
  const checked = useRef<Checked | null>(null);
  const afterEscape = useRef(false);
  const press = () => {
    if (!canBuild) { escape(); return; }   // answers missing: fill typical figures for the rest, then the check step shows them
    if (!needsCheck(checked.current, fields)) { setMarking(false); onBuild(profile); return; }
    setChecking(true); setMarking(true);
    if (phone) setSheet(true);          // the figure, the check and the figures to change are together in the sheet
  };
  const confirm = () => { checked.current = snapshot(fields); setChecking(false); setMarking(false); setSheet(false); onBuild(profile); };
  const closeCheck = (change: boolean) => { setChecking(false); if (!change) setMarking(false); };
  const escape = () => { setSheet(false); setEditing(null); afterEscape.current = true; void send(ESCAPE_TEXT); };
  useEffect(() => { if (afterEscape.current && !busy) {
    afterEscape.current = false;
    // the server may ask one more thing first (the retirement age): its question and chips stay on screen, and the check waits for the answer
    if (canBuild && !/\bretire/i.test(state?.question?.text ?? "")) press();
  } }); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!canBuild) { setChecking(false); setMarking(false); } }, [canBuild]);

  const panel = (idp: string, showBuild: boolean) => <LivePanel idp={idp} profile={profile} fields={fields} missing={missing} onEdit={edit} editing={editing} onSave={save} onCancel={() => setEditing(null)} onAdd={add} onChip={(c) => { setSheet(false); setEditing(null); void send(c); }} sections={state?.sections_status} planSS={planSS} onReset={resetSection} onBuild={press} canBuild={canBuild} canStart={canStart} showBuild={showBuild} checking={checking} marking={marking} onConfirm={confirm} onCloseCheck={closeCheck} />;

  return (
    <div className="intake">
      <section className="chat card" aria-labelledby="chat-h">
        <h2 id="chat-h" className="h-screen">Tell us about yourself</h2>
        <div className="log" ref={log} role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions" tabIndex={0}>
          {msgs.map((m, i) => (
            <div key={i} className={`bubble bubble-${m.who}${m.hint ? " bubble-hint" : ""}`}>
              <span className="sr-only">{m.who === "you" ? "You said: " : "Enough said: "}</span>{m.text}
              {i === 0 && m.who === "us" && (
                <span className="build-hint" data-testid="build-hint">
                  <span className="build-hint-arrow build-hint-right" aria-hidden="true">→</span>
                  <span className="build-hint-arrow build-hint-down" aria-hidden="true">↓</span>
                  <span>When you've told me a little, press Build my plan <span className="hint-wide">on the right</span><span className="hint-phone">below</span>. You don't need to answer everything first.</span>
                </span>
              )}
            </div>
          ))}
          {busy && <div className="bubble bubble-us typing" role="status"><span className="sr-only">Reading your answer</span><i /><i /><i /></div>}
          {error && (
            <div className="alert" role="alert">
              <p>{error}</p>
              {lastSent && <button type="button" className="btn btn-quiet" onClick={() => send(lastSent, false)}>Try again</button>}
            </div>
          )}
        </div>
        {quick.length > 0 && !busy && (
          <div className="quick" role="group" aria-label="Quick answers">
            {quick.map((q) => <button key={q.label} type="button" className="chip" onClick={() => send(q.text)}>{q.label}</button>)}
          </div>
        )}
        {editing ? (
          <p className="composer-note" role="status">Finish or cancel the edit on the right.</p>
        ) : (
        <form className="composer" onSubmit={submit}>
          <label htmlFor="chat-input" className="sr-only">Your answer</label>
          <textarea id="chat-input" ref={input} rows={2} value={draft} placeholder="Type here, in your own words" onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(draft); } }} maxLength={2000} />
          <button type="submit" className="btn btn-primary" disabled={busy || !draft.trim()}>Send</button>
        </form>
        )}
      </section>

      <aside className="side card" aria-label="Your numbers">{panel("lp", !phone)}</aside>

      <div className="phone-bar">
        <button type="button" ref={opener} className="btn btn-quiet sheet-open" aria-haspopup="dialog" aria-expanded={sheet} aria-controls="numbers-sheet" onClick={() => setSheet(true)}>
          Your numbers ▲{fields.length > 0 && <span className="count">{fields.length}</span>}
        </button>
        {phone && !sheet && <BuildBlock idp="bar" compact canBuild={canBuild} canStart={canStart} onBuild={press} />}
      </div>
      {sheet && (
        <div className="sheet-backdrop" onClick={() => setSheet(false)}>
          <div id="numbers-sheet" ref={sheetEl} className="sheet" role="dialog" aria-modal="true" aria-label="Your numbers" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="btn btn-quiet sheet-close" autoFocus onClick={() => setSheet(false)}>Your numbers ▼</button>
            {panel("sheet", phone)}
          </div>
        </div>
      )}
    </div>
  );
}
