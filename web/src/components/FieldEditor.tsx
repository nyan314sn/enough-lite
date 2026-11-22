import { useState, type FormEvent } from "react";
import { usd, usdShort } from "../format";
import type { Field, Profile } from "../types";

// A small inline editor for one figure in "What we have so far". One form is one typing place.

export type Kind = "split" | "money" | "choice" | "number" | "college";
export type CollegeChoice = { college_type: "public" | "private" | "none"; college_share: number };
const COLLEGE_TYPES: { id: CollegeChoice["college_type"]; label: string }[] = [
  { id: "public", label: "Public, in-state" }, { id: "private", label: "Private" }, { id: "none", label: "None" },
];
export const SPLIT_KEYS = ["pretax", "roth", "taxable", "cash"] as const;
export type Split = Record<(typeof SPLIT_KEYS)[number], number>;
const SPLIT_LABELS: Record<string, string> = {
  pretax: "Pre-tax (401(k), IRA)", roth: "Roth", taxable: "Taxable brokerage", cash: "Cash or bank",
};
const RISK_OPTIONS = ["careful", "balanced", "growth"];
const NUMBER_KEYS = /^(age|partner_age|retire_age)$/;
const MONEY_KEY = /pay|spend|social|income|rent|mortgage|value|balance/i;

/** What kind of editor a field gets: the server's word when it sends one, else a guess from the key. */
export function editorFor(f: Field): { kind: Kind; options: string[] } | null {
  const e = f.editable;
  if (e && typeof e === "object" && e.kind && !["split", "money", "choice", "number", "college"].includes(e.kind)) return null; // text, percent, group: the chat handles them
  if (e && typeof e === "object" && e.kind) return { kind: e.kind as Kind, options: e.options ?? (f.key === "risk" ? RISK_OPTIONS : []) };
  if (f.key === "savings") return { kind: "split", options: [] };
  if (f.key === "risk") return { kind: "choice", options: RISK_OPTIONS };
  if (NUMBER_KEYS.test(f.key)) return { kind: "number", options: [] };
  if (MONEY_KEY.test(f.key) && (typeof f.value === "number" || f.value == null)) return { kind: "money", options: [] };
  return null;
}

/** "$1,200", "450k", "1.2m" or "450000" to a number; blank is zero; junk is null. */
export function parseAmount(s: string): number | null {
  const t = s.trim().toLowerCase().replace(/[$,\s]/g, "");
  if (!t) return 0;
  const m = t.match(/^(\d+(?:\.\d+)?)(k|m)?$/);
  if (!m) return null;
  return Math.round(Number(m[1]) * (m[2] === "m" ? 1e6 : m[2] === "k" ? 1e3 : 1));
}

export const splitOf = (p: Profile): Split => {
  const s = p.savings ?? {};
  return { pretax: Number(s.pretax) || 0, roth: Number(s.roth) || 0, taxable: Number(s.taxable) || 0, cash: Number(s.cash) || 0 };
};
export const splitTotal = (s: Split) => SPLIT_KEYS.reduce((t, k) => t + s[k], 0);

export const PRESETS: { label: string; shares: Split }[] = [
  { label: "Mostly 401(k)", shares: { pretax: 0.7, roth: 0.1, taxable: 0.15, cash: 0.05 } },
  { label: "Mostly bank", shares: { pretax: 0.15, roth: 0.05, taxable: 0.1, cash: 0.7 } },
  { label: "Even split", shares: { pretax: 0.25, roth: 0.25, taxable: 0.25, cash: 0.25 } },
];
export function applyPreset(total: number, shares: Split): Split {
  const out = { ...shares };
  let used = 0;
  SPLIT_KEYS.forEach((k, i) => { out[k] = i === SPLIT_KEYS.length - 1 ? total - used : Math.round(total * shares[k]); used += out[k]; });
  return out;
}

/** "College for child 1 (age 11): private, you pay 50%." The server reads this the same way it reads the person's own words. */
export const collegeLine = (f: Field, v: CollegeChoice): string => {
  const who = f.label.replace(/^College:\s*/, "").replace(/, age (\d+)/, " (age $1)");
  return `College for ${who}: ` + (v.college_type === "none" ? "no college." : `${v.college_type === "private" ? "private" : "public in-state"} college, you pay ${Math.round(v.college_share * 100)}%.`);
};

export const chatLine = (f: Field, value: unknown): string => {
  if (f.editable?.kind === "college") return collegeLine(f, value as CollegeChoice);
  if (f.key === "savings") {
    const s = value as Split;
    return `Updated your savings: ${SPLIT_KEYS.filter((k) => s[k] > 0).map((k) => `${usdShort(s[k])} ${k === "pretax" ? "pre-tax" : k === "roth" ? "Roth" : k}`).join(", ") || "none"}.`;
  }
  if (typeof value === "number") return `Updated ${f.label.toLowerCase()}: ${editorFor(f)?.kind === "money" ? usd(value) : value}.`;
  return `Updated ${f.label.toLowerCase()}: ${String(value)}.`;
};

interface Props { field: Field; profile: Profile; idp: string; onSave: (f: Field, value: unknown) => void; onCancel: () => void }

export default function FieldEditor({ field, profile, idp, onSave, onCancel }: Props) {
  const ed = editorFor(field)!;
  const id = `${idp}-ed-${field.key}`;
  const [parts, setParts] = useState<Record<string, string>>(() => {
    const s = splitOf(profile);
    return Object.fromEntries(SPLIT_KEYS.map((k) => [k, s[k] ? String(s[k]) : ""]));
  });
  const [text, setText] = useState(typeof field.value === "number" ? String(field.value) : "");
  const [error, setError] = useState<string | null>(null);
  const cur = (field.value ?? {}) as { college_type?: string | null; college?: boolean; college_share?: number };
  const [ctype, setCtype] = useState<CollegeChoice["college_type"]>((cur.college_type as CollegeChoice["college_type"]) ?? (cur.college === false ? "none" : "public"));
  const [cshare, setCshare] = useState(String(Math.round((cur.college_share ?? 1) * 100)));

  const amounts = SPLIT_KEYS.map((k) => parseAmount(parts[k]));
  const total = amounts.reduce<number>((t, a) => t + (a ?? 0), 0);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (ed.kind === "college") {
      const pct = Number(cshare.trim().replace(/%$/, ""));
      if (ctype !== "none" && (cshare.trim() === "" || !Number.isFinite(pct) || pct < 0 || pct > 100)) return setError("Use a share from 0 to 100.");
      return onSave(field, { college_type: ctype, college_share: ctype === "none" ? 1 : pct / 100 } satisfies CollegeChoice);
    }
    if (ed.kind === "split") {
      if (amounts.some((a) => a == null)) return setError("Use numbers only, such as 250000 or 250k.");
      if (total <= 0) return setError("Enter at least one amount.");
      return onSave(field, Object.fromEntries(SPLIT_KEYS.map((k, i) => [k, amounts[i]!])) as Split);
    }
    const n = parseAmount(text);
    if (n == null || text.trim() === "") return setError(ed.kind === "number" ? "Use a whole number of years, such as 45." : "Use a number, such as 120000 or 120k.");
    const lo = field.editable?.min ?? 1, hi = field.editable?.max ?? 110;
    if (ed.kind === "number" && (n < lo || n > hi)) return setError(`Use a whole number from ${lo} to ${hi}.`);
    const own = field.key === "retire_age" ? [profile.age, profile.pay_per_year] : field.key === "partner_retire_age" ? [profile.partner_age as number | null | undefined, profile.partner_pay_per_year as number | null | undefined] : null;
    const retired = (profile.notes as Record<string, string> | undefined)?.retired === "yes";
    if (own && typeof own[0] === "number" && n < own[0] && (Number(own[1]) || 0) > 0 && !retired) return setError(`That is below the age now (${own[0]}). Use ${own[0]} or more, or set the pay to 0 if you have stopped work.`);
    onSave(field, n);
  }

  return (
    <form className="editor" aria-label={`Change ${field.label}`} onSubmit={submit} onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onCancel(); } }}>
      {ed.kind === "split" && (
        <>
          <p className="editor-hint small muted">Say where the money sits. This changes how it is taxed.</p>
          <div className="presets" role="group" aria-label="Quick splits">
            {PRESETS.map((p) => (
              <button key={p.label} type="button" className="chip" onClick={() => {
                const t = total > 0 ? total : splitTotal(splitOf(profile));
                const s = applyPreset(t, p.shares);
                setParts(Object.fromEntries(SPLIT_KEYS.map((k) => [k, String(s[k])]))); setError(null);
              }}>{p.label}</button>
            ))}
          </div>
          <div className="split-grid">
            {SPLIT_KEYS.map((k) => (
              <label key={k} htmlFor={`${id}-${k}`} className="split-field">
                <span>{SPLIT_LABELS[k]}</span>
                <input id={`${id}-${k}`} name={k} inputMode="numeric" autoComplete="off" placeholder="$0" value={parts[k]}
                  onChange={(e) => { setParts({ ...parts, [k]: e.target.value }); setError(null); }} />
              </label>
            ))}
          </div>
          <p className="split-total num" role="status">Total: <strong>{usd(total)}</strong></p>
        </>
      )}
      {(ed.kind === "money" || ed.kind === "number") && (
        <label htmlFor={id} className="split-field">
          <span>{field.label}{ed.kind === "money" && /per_year|pay|spend|social/.test(field.key) ? ", a year" : ""}</span>
          <input id={id} inputMode="numeric" autoFocus autoComplete="off" placeholder={ed.kind === "money" ? "$0" : ""} value={text}
            onChange={(e) => { setText(e.target.value); setError(null); }} />
        </label>
      )}
      {ed.kind === "college" && (
        <>
          <div className="choices" role="group" aria-label={`${field.label}: type`}>
            {COLLEGE_TYPES.map((o) => (
              <button key={o.id} type="button" className={`chip${ctype === o.id ? " chip-on" : ""}`} aria-pressed={ctype === o.id}
                onClick={() => { setCtype(o.id); setError(null); }}>{o.label}</button>
            ))}
          </div>
          {ctype !== "none" && (
            <label htmlFor={`${id}-share`} className="split-field">
              <span>Share you pay, 0 to 100%</span>
              <input id={`${id}-share`} inputMode="numeric" autoComplete="off" value={cshare}
                onChange={(e) => { setCshare(e.target.value); setError(null); }} />
            </label>
          )}
        </>
      )}
      {ed.kind === "choice" && (
        <div className="choices" role="group" aria-label={field.label}>
          {ed.options.map((o) => (
            <button key={o} type="button" className={`chip${String(field.value) === o ? " chip-on" : ""}`} aria-pressed={String(field.value) === o} onClick={() => onSave(field, o)}>
              {o.charAt(0).toUpperCase() + o.slice(1)}
            </button>
          ))}
        </div>
      )}
      {error && <p className="editor-error small" role="alert">{error}</p>}
      <div className="editor-actions">
        {ed.kind !== "choice" && <button type="submit" className="btn btn-primary btn-small">Save</button>}
        <button type="button" className="btn btn-quiet btn-small" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
