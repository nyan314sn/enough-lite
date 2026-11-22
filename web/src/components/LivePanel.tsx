import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import Household from "../figure/Household";
import { savingsParts, showValue, usd } from "../format";
import FieldEditor, { editorFor } from "./FieldEditor";
import BuildBlock from "./BuildBlock";
import type { Field, Profile } from "../types";

// The live panel beside the chat: the household picture, money in and out, and "What we have so far" with each figure's source.
// ✎ hands the change to the chat box; nothing is typed here.

export const NEEDED: Record<string, string> = {
  age: "your age", partner_age: "your partner's age", state: "your state", retire_age: "when you want to retire", pay_per_year: "your pay",
  savings: "your savings", spending_per_year: "your spending", risk: "how much risk you can take",
};
export const neededLabel = (k: string) => NEEDED[k] ?? k.replace(/_/g, " ");

/** A figure the person never gave: estimate, assumed or default. */
export const isGuess = (f: Field) => f.source === "estimate" || f.source === "assumed" || f.source === "default";

export function SourceTag({ source }: { source: string }) {
  const kind = source === "you said" ? "said" : source === "estimate" ? "estimate" : source === "default" ? "default" : "assumed";
  return <span className={`tag tag-${kind}`}>{source === "default" ? "typical" : source}</span>;
}

/** The Social Security figure the plan uses beside the one in the answers (the plan's `ss_basis`). */
export interface SsPlan { panel_per_year: number; plan_per_year: number; panel_age: number; claim_age: number | null; partner_claim_age?: number | null; already: boolean; same: boolean }
const SsPlanCtx = createContext<SsPlan | null>(null);

/** "$82,000 a year at 67" becomes "$82,000 a year at 67; your plan starts it at 70 ($95,100)" when the plan starts it at another age. */
export function withPlanStart(display: string, ss: SsPlan | null): string {
  if (!ss || ss.same || ss.already || ss.claim_age == null || /your plan starts it/.test(display)) return display;
  const who = ss.partner_claim_age != null && ss.partner_claim_age !== ss.claim_age ? `at ${ss.claim_age} for you and ${ss.partner_claim_age} for your partner` : `at ${ss.claim_age}`;
  return `${display}; your plan starts it ${who} (${usd(ss.plan_per_year)})`;
}

/** True while the guessed rows are marked for the person to check (the note under Build my plan is open, or they chose to change something). */
const MarkCtx = createContext(false);

const SECTIONS = ["Household", "Work & pay", "Saving", "Home & debts", "Pensions & income", "Insurance", "Goals", "Health", "Costs"];
/** Sections a person may leave out: shown as "Not added, using typical" with a way to add them in the chat. */
const OPTIONAL: Record<string, string> = { "Home & debts": "debts", "Pensions & income": "a pension", Insurance: "insurance", Goals: "goals", Health: "health", Costs: "costs" };

/** "Home & debts" reads as "home and debts"; the optional ones have their own plain nouns. */
/** The chat chip each section opens (the same words the server offers). */
export const SECTION_CHIP: Record<string, string> = { Saving: "Add saving", "Home & debts": "Add debts", "Pensions & income": "Add a pension", Insurance: "Add insurance", Goals: "Add goals", Health: "Add health", Costs: "Add costs" };

export const sectionNoun = (name: string) => OPTIONAL[name] ?? name.toLowerCase().replace(/&/g, "and");

interface Props {
  onReset?: (section: string, fields: Field[]) => void;
  onAdd?: (what: string) => void;
  /** Send a chip to the chat as is ("Add debts"). */
  onChip?: (chip: string) => void;
  sections?: { section: string; status: "added" | "default" | "estimated"; note?: string }[];
  /** The plan's own Social Security start, when it differs from the one the answers show. */
  planSS?: SsPlan | null;
  profile: Profile;
  fields: Field[];
  missing: string[];
  onEdit: (f: Field) => void;
  editing?: string | null;
  onSave?: (f: Field, value: unknown) => void;
  onCancel?: () => void;
  onBuild: () => void;
  canBuild: boolean;
  /** Show the Build my plan button under the family picture (one per screen: the caller decides which panel has it). */
  showBuild?: boolean;
  onEscape?: () => void;
  checking?: boolean;
  onConfirm?: () => void;
  onCloseCheck?: (change: boolean) => void;
  /** Highlight the guessed rows and open the groups that hold them. */
  marking?: boolean;
  idp?: string;
}

export default function LivePanel({ profile, fields, missing, onEdit, editing = null, onSave, onCancel, onAdd, onChip, sections, planSS = null, onReset, onBuild, canBuild, showBuild = true, onEscape, checking, onConfirm, onCloseCheck, marking = false, idp = "lp" }: Props) {
  const byKey = (k: string) => fields.find((f) => f.key === k);
  const pay = profile.pay_per_year ?? null;
  const ppay = profile.partner_pay_per_year ?? null;
  const later = profile.spending_per_year ?? null;
  const payIn = (pay ?? 0) + (ppay ?? 0);
  // working: pay against spending now. Not working: Social Security and pensions against spending in retirement.
  const working = payIn > 0;
  const ss = working ? 0 : Number(profile.social_security_per_year ?? 0) || 0;
  const pensions = working ? 0 : ((profile.pensions as { per_year?: number }[] | undefined) ?? []).reduce((a, x) => a + (Number(x?.per_year) || 0), 0);
  const spend = working ? ((profile.spending_now_per_year as number | null | undefined) ?? later) : later;
  const inc = payIn + ss + pensions;
  const Money = ({ k, label, v, sign }: { k: string; label: string; v: number; sign?: "-" }) => {
    const f = byKey(k);
    return (
      <div className="money-row">
        <dt>{label}{f && <> <SourceTag source={f.source} /></>}</dt>
        <dd className="num">{sign && v > 0 ? "−" : ""}{usd(v)}</dd>
      </div>
    );
  };
  return (
    <MarkCtx.Provider value={marking}>
    <SsPlanCtx.Provider value={planSS}>
    <div className="live" data-testid="live-panel">
      <section className="panel-block house-block" aria-labelledby={`${idp}-house`}>
        <h2 id={`${idp}-house`} className="h-panel">Your household</h2>
        {fields.length === 0
          ? <p className="muted">Your household appears here as you answer.</p>
          : <Household profile={profile} />}
        {showBuild && <BuildBlock idp={idp} canBuild={canBuild} missing={missing} started={profile.age != null} onBuild={onBuild} onEscape={onEscape} checking={checking} onConfirm={onConfirm} onCloseCheck={onCloseCheck} />}
      </section>

      {pay != null && (
        <section className="panel-block" aria-labelledby={`${idp}-money`}>
          <h2 id={`${idp}-money`} className="h-panel">Money in and out <span className="muted small">a year, before tax</span></h2>
          <dl className="money">
            <Money k="pay_per_year" label={ppay != null && profile.partner_age != null ? "Your pay" : "Pay"} v={pay} />
            {ppay != null && profile.partner_age != null && <Money k="partner_pay_per_year" label="Partner's pay" v={ppay} />}
            {ss > 0 && <Money k="social_security_per_year" label="Social Security" v={ss} />}
            {pensions > 0 && <Money k="pensions" label="Pensions" v={pensions} />}
            {spend != null && <Money k={working ? "spending_now_per_year" : "spending_per_year"} label={working ? "Costs now" : "Costs a year"} v={spend} sign="-" />}
            {spend != null && (
              <div className={`money-row money-total ${inc - spend < 0 ? "neg" : "pos"}`}>
                <dt>{inc - spend < 0 ? "Short each year" : "Left before tax"}</dt>
                <dd className="num">{usd(Math.abs(inc - spend))}</dd>
              </div>
            )}
          </dl>
        </section>
      )}

      <section className="panel-block" aria-labelledby={`${idp}-sofar`}>
        <h2 id={`${idp}-sofar`} className="h-panel">What we have so far</h2>
        {fields.length === 0 ? <p className="muted">Nothing yet.</p> : (
          <Fields fields={fields} profile={profile} onEdit={onEdit} onAdd={onAdd} onChip={onChip} sections={sections} onReset={onReset} ed={{ editing, onSave, onCancel, idp }} />
        )}
      </section>
    </div>
    </SsPlanCtx.Provider>
    </MarkCtx.Provider>
  );
}

export interface Ed { editing: string | null; onSave?: (f: Field, value: unknown) => void; onCancel?: () => void; idp: string }

function FieldRow({ f, profile, onEdit, ed }: { f: Field; profile: Profile; onEdit: (f: Field) => void; ed: Ed }) {
  // When this row's editor closes (Save, Cancel or Esc), put the keyboard back on its pen instead of losing it to the page.
  const mark = useContext(MarkCtx);
  const ssPlan = useContext(SsPlanCtx);
  const shown = f.display || showValue(f.key, f.value);
  const pen = useRef<HTMLButtonElement>(null);
  const was = useRef(false);
  const isOpen = ed.editing === f.key && !!editorFor(f);
  useEffect(() => {
    if (was.current && !isOpen) {
      const a = document.activeElement;
      if (!a || a === document.body) pen.current?.focus();
    }
    was.current = isOpen;
  }, [isOpen]);
  return (
    <li className={`field${mark && isGuess(f) ? " is-check" : ""}`} data-key={f.key}>
      <div className="field-main">
        <span className="field-label">{f.label}</span>
        <span className="field-value">{f.key === "social_security_per_year" ? withPlanStart(shown, ssPlan) : shown}</span>
        <button type="button" ref={pen} className="pen" aria-label={`Change ${f.label}`} title={`Change ${f.label}`} aria-expanded={editorFor(f) ? ed.editing === f.key : undefined} onClick={() => onEdit(f)}>✎</button>
      </div>
      <div className="field-meta">
        <SourceTag source={f.source} />
        {f.source === "assumed" && <span className="check-tag">Assumed: check this</span>}
        {f.note && <span className="field-note">{f.note}</span>}
        {f.key === "savings" && savingsParts(profile) && <span className="field-note">{savingsParts(profile)}</span>}
      </div>
      {ed.editing === f.key && editorFor(f) && ed.onSave && ed.onCancel && <FieldEditor field={f} profile={profile} idp={ed.idp} onSave={ed.onSave} onCancel={ed.onCancel} />}
    </li>
  );
}

/** One section: a toggle button (name and note) with its own buttons beside it, never inside it, so every control is reachable and named. */
function Group({ name, idp, meta, open: start, forceOpen = false, action, className = "", children }: { forceOpen?: boolean; name: string; idp: string; meta: string; open: boolean; action?: ReactNode; className?: string; children: ReactNode }) {
  const [open, setOpen] = useState(start);
  useEffect(() => { if (forceOpen) setOpen(true); }, [forceOpen]);
  useEffect(() => { if (start) setOpen(true); }, [start]);      // a section the person has just filled in opens, so the new figure shows
  const body = `${idp}-grp-${name.replace(/[^a-z0-9]+/gi, "-")}`;
  return (
    <div className={`group ${className}${open ? " open" : ""}`} data-section={name}>
      <div className="group-h">
        <button type="button" className="group-toggle" aria-expanded={open} aria-controls={body} onClick={() => setOpen((o) => !o)}>
          <span className="group-name">{name}</span><span className="muted small">{meta}</span>
        </button>
        {action}
      </div>
      <div id={body} hidden={!open}>{children}</div>
    </div>
  );
}

/** Fields grouped by section, in compact groups. An older backend sends no section: then it is one flat list. */
function Fields({ fields, profile, onEdit, onAdd, onChip, sections, onReset, ed }: { ed: Ed; onChip?: (chip: string) => void; sections?: { section: string; status: string; note?: string }[]; onReset?: (section: string, fields: Field[]) => void; fields: Field[]; profile: Profile; onEdit: (f: Field) => void; onAdd?: (what: string) => void }) {
  const mark = useContext(MarkCtx);
  const ssPlan = useContext(SsPlanCtx);
  const grouped = fields.some((f) => f.section);
  if (!grouped) return <ul className="fields">{fields.map((f) => <FieldRow key={f.key} f={f} profile={profile} onEdit={onEdit} ed={ed} />)}</ul>;
  const names = [...SECTIONS, ...Array.from(new Set(fields.map((f) => f.section ?? "Other"))).filter((n) => !SECTIONS.includes(n))];
  return (
    <div className="groups">
      {names.map((n) => {
        const mine = fields.filter((f) => (f.section ?? "Other") === n);
        if (mine.length === 0) {
          const what = OPTIONAL[n];
          if (!what) return null;
          return (
            <div key={n} className="group group-empty" data-section={n}>
              <div className="group-h"><span className="group-name">{n}</span><span className="muted small">Not added, using typical</span>
                <button type="button" className="pen" aria-label={`Add ${what}`} title={`Add ${what}`} onClick={() => onAdd?.(what)}>✎</button></div>
            </div>
          );
        }
        const chip = SECTION_CHIP[n];
        const rows = <ul className="fields">{mine.map((f) => <FieldRow key={f.key} f={f} profile={profile} onEdit={onEdit} ed={ed} />)}</ul>;
        const sec = sections?.find((x) => x.section === n);
        const st = sec?.status;
        if (chip && (st === "default" || st === "estimated")) {
          return (
            <Group key={n} name={n} idp={ed.idp} className="group-default" meta={sec?.note ? (n === "Pensions & income" ? sec.note.replace(/(Social Security [^;]*)/, (m) => withPlanStart(m, ssPlan)) : sec.note) :st === "estimated" ? "Estimated, change it if you know" : "Not added, using typical"} open={false} forceOpen={mark && mine.some(isGuess)}
              action={<button type="button" className="pen" aria-label={`${chip}`} title={chip} onClick={() => { if (onChip) onChip(chip); else onAdd?.(sectionNoun(n)); }}>✎</button>}>
              {rows}
            </Group>
          );
        }
        return (
          <Group key={n} name={n} idp={ed.idp} meta={String(mine.length)} open
            action={onReset ? <button type="button" className="reset" aria-label={`Reset ${n}`} onClick={() => onReset(n, mine)}>Reset</button> : undefined}>
            {rows}
          </Group>
        );
      })}
    </div>
  );
}
