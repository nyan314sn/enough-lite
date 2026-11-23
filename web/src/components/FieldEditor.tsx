import { useEffect, useRef, useState, type FormEvent } from "react";
import { stateName, showValue, usd, usdShort } from "../format";
import type { Field, Profile } from "../types";
import {
  AGES, CHOICES, MONEYS, NOUN, READ_ONLY, SPECS, STATE_NAMES, TEXTS, YESNO, stateFromText,
  type Col, type Parsed, type Row, type Spec,
} from "./editSpecs";

export { applyEdit, synthField } from "./editSpecs";

// A small inline editor for one figure in "What we have so far". One form is one typing place.
// Every figure the panel shows has one, except the few that are worked out (see READ_ONLY).

export type Kind = "split" | "money" | "choice" | "number" | "college" | "text" | "state" | "yesno" | "home" | "form" | "rows";
export type CollegeChoice = { college_type: "public" | "private" | "none"; college_share: number };
const COLLEGE_TYPES: { id: CollegeChoice["college_type"]; label: string }[] = [
  { id: "public", label: "Public, in-state" }, { id: "private", label: "Private" }, { id: "none", label: "None" },
];
export const SPLIT_KEYS = ["pretax", "roth", "taxable", "cash"] as const;
export type Split = Record<(typeof SPLIT_KEYS)[number], number>;
const SPLIT_LABELS: Record<string, string> = {
  pretax: "Pre-tax (401(k), IRA)", roth: "Roth", taxable: "Taxable brokerage", cash: "Cash or bank",
};
const NUMBER_KEYS = /^(age|partner_age|retire_age|partner_retire_age|emergency_months)$/;
const MONEY_KEY = /pay|spend|social|income|rent|mortgage|value|balance/i;
const HOME_MODES: [string, string][] = [["outright", "Own outright"], ["mortgage", "Own with a mortgage"], ["rent", "Rent"]];

export const isReadOnly = (f: Field) => READ_ONLY.has(f.key);

/** What kind of editor a field gets: ours by key first, else the server's word, else a guess from the key. */
export function editorFor(f: Field): { kind: Kind; options: string[]; spec?: Spec } | null {
  const e = f.editable;
  if (e && typeof e === "object" && e.kind === "college") return { kind: "college", options: e.options ?? [] };
  const k = f.key;
  if (k === "savings") return { kind: "split", options: [] };
  if (k === "state") return { kind: "state", options: [] };
  if (k === "home") return { kind: "home", options: [] };
  if (SPECS[k]) return { kind: SPECS[k].list ? "rows" : "form", options: [], spec: SPECS[k] };
  if (CHOICES[k]) return { kind: "choice", options: CHOICES[k] };
  if (YESNO.has(k)) return { kind: "yesno", options: [] };
  if (TEXTS.has(k)) return { kind: "text", options: [] };
  if (k in MONEYS) return { kind: "money", options: [] };
  if (NUMBER_KEYS.test(k)) return { kind: "number", options: [] };
  if (e && typeof e === "object" && e.kind && ["money", "choice", "number"].includes(e.kind)) return { kind: e.kind as Kind, options: e.options ?? [] };
  if (MONEY_KEY.test(k) && (typeof f.value === "number" || f.value == null)) return { kind: "money", options: [] };
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

const o = (v: unknown) => ((v && typeof v === "object" ? v : {}) as Record<string, unknown>);
const pc = (v: unknown) => `${+(Number(v) * 100).toFixed(1)}%`;

/** A new value in plain words, for the chat line. */
function say(key: string, v: unknown): string {
  const x = o(v);
  switch (key) {
    case "part_time": return `${usd(Number(x.per_year) || 0)} a year${x.until_age ? ` until ${x.until_age}` : ""}`;
    case "match": return `${pc(x.rate)} of what you save${x.cap != null ? `, up to ${pc(x.cap)} of pay` : ""}`;
    case "contributions": return [x.contrib_you != null && `you ${usd(Number(x.contrib_you))}`, x.contrib_partner != null && `partner ${usd(Number(x.contrib_partner))}`].filter(Boolean).join(", ").concat(" a year").replace(/^ a year$/, "none");
    case "inheritance": return `${usd(Number(x.amount) || 0)}${x.year ? ` in ${x.year}` : ""}, ${x.count ? "counted in the plan" : "information only"}`;
    case "big_costs": return Array.isArray(v) && v.length ? v.map((b) => `${o(b).label} ${usd(Number(o(b).amount) || 0)}${o(b).year ? ` in ${o(b).year}` : ""}`).join("; ") : "none";
    case "budget": return Object.entries(x).filter(([, n]) => Number(n) > 0).map(([k, n]) => `${k} ${usd(Number(n))}`).join(", ").concat(" a month").replace(/^ a month$/, "none");
    case "save_rate": return `${pc(v)} of pay`;
    case "state": return stateName(String(v ?? ""));
    case "other_saving": return `${usd(Number(v) || 0)} a month`;
    case "life_insurance": return x.kind && x.kind !== "none" ? `${x.kind === "term" ? "term" : "whole"} life${x.face ? `, ${usd(Number(x.face))} cover` : ""}${x.premium ? `, premium ${usd(Number(x.premium))} a year` : ""}` : "none";
    case "home": return x.owns ? `own${Number(x.mortgage_balance) > 0 ? `, ${usd(Number(x.mortgage_balance))} left on the mortgage` : ", no mortgage"}${x.value ? `, worth ${usd(Number(x.value))}` : ""}` : `rent${x.rent ? `, ${usd(Number(x.rent))} a month` : ""}`;
    case "disability": case "ltc": return v ? "yes" : "no";
    default: return showValue(key, v);
  }
}

/** The chat line a saved edit sends: "Updated your pay: $120,000 a year (was $100,000 a year)." The server reads it as the person's own word. */
export const chatLine = (f: Field, value: unknown): string => {
  if (f.editable?.kind === "college") return collegeLine(f, value as CollegeChoice);
  const noun = NOUN[f.key] ?? f.label.toLowerCase().replace(/^your /, "").replace(/[^a-z' ]/g, "").trim();
  let now: string;
  if (f.key === "savings") {
    const s = value as Split;
    now = SPLIT_KEYS.filter((k) => s[k] > 0).map((k) => `${usdShort(s[k])} ${k === "pretax" ? "pre-tax" : k === "roth" ? "Roth" : k}`).join(", ") || "none";
  } else if (typeof value === "number" && !(f.key in MONEYS) && f.key !== "save_rate") now = String(value);
  else now = say(f.key, value);
  const was = (f.display ?? "").replace(/\s+/g, " ").trim().slice(0, 140);
  return `Updated your ${noun}: ${now}.` + (was && !/^(not given|typical|none counted)/i.test(was) && was !== now ? ` (was ${was})` : "");
};

type Res = { v: string | number | null } | { err: string };

/** One box's text to its value, or a plain message. */
function readCol(c: Col, raw: string): Res {
  const t = raw.trim();
  if (c.kind === "select") return { v: raw };
  if (c.kind === "text") return t ? { v: t.slice(0, 40) } : c.optional ? { v: null } : { err: `Say what ${c.label.toLowerCase()} is.` };
  if (c.kind === "money") {
    const n = parseAmount(raw);
    if (n == null) return { err: `${c.label}: use numbers only, such as 250000 or 250k.` };
    if (t === "") return c.optional ? { v: null } : { err: `${c.label}: enter an amount (0 is fine).` };
    return { v: n };
  }
  if (t === "") return c.optional ? { v: null } : { err: `${c.label}: enter a number.` };
  const x = Number(t.replace(/%$/, ""));
  const lo = c.min ?? 0, hi = c.max ?? 100;
  if (c.kind === "int") {
    if (!/^\d+$/.test(t) || x < lo || x > hi) return { err: `${c.label}: use a whole number from ${lo} to ${hi}.` };
    return { v: x };
  }
  if (!Number.isFinite(x) || x < lo || x > hi) return { err: `${c.label}: use a number from ${lo} to ${hi}.` };
  return { v: Math.round(x * 100) / 10000 };
}

interface Props { field: Field; profile: Profile; idp: string; onSave: (f: Field, value: unknown) => void; onCancel: () => void }

export default function FieldEditor({ field, profile, idp, onSave, onCancel }: Props) {
  const ed = editorFor(field)!;
  const id = `${idp}-ed-${field.key}`;
  const [parts, setParts] = useState<Record<string, string>>(() => {
    const s = splitOf(profile);
    return Object.fromEntries(SPLIT_KEYS.map((k) => [k, s[k] ? String(s[k]) : ""]));
  });
  const [text, setText] = useState(() => typeof field.value === "number" ? String(field.value) : typeof field.value === "string" ? (ed.kind === "state" ? stateName(field.value) : ed.kind === "text" ? field.value : "") : "");
  const [error, setError] = useState<string | null>(null);
  const cur = (field.value ?? {}) as { college_type?: string | null; college?: boolean; college_share?: number };
  const [ctype, setCtype] = useState<CollegeChoice["college_type"]>((cur.college_type as CollegeChoice["college_type"]) ?? (cur.college === false ? "none" : "public"));
  const [cshare, setCshare] = useState(String(Math.round((cur.college_share ?? 1) * 100)));
  const spec = ed.spec;
  const form = useRef<HTMLFormElement>(null);
  // focus goes into the editor when it opens (so Esc and Tab work from the first key), whatever its first control is
  useEffect(() => { const f = form.current; if (f && !f.contains(document.activeElement)) f.querySelector<HTMLElement>("input, select, button")?.focus(); }, []);
  const [rows, setRows] = useState<Row[]>(() => (spec ? (spec.list ? spec.from(field, profile) : spec.from(field, profile)) : []));
  const h = o(field.value);
  const [hmode, setHmode] = useState<string>(() => (h.owns === false ? "rent" : h.owns ? (Number(h.mortgage_balance) > 0 ? "mortgage" : "outright") : ""));
  const [home, setHome] = useState<Record<string, string>>(() => Object.fromEntries(["value", "mortgage_balance", "mortgage_payment", "rent"].map((k) => [k, Number(h[k]) ? String(h[k]) : ""])));

  const amounts = SPLIT_KEYS.map((k) => parseAmount(parts[k]));
  const total = amounts.reduce<number>((t, a) => t + (a ?? 0), 0);
  const cols = (spec?.cols ?? []).filter((c) => !c.when || c.when(profile));

  const fail = (m: string) => { setError(m); };
  const setCell = (i: number, k: string, v: string) => { setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [k]: v } : r))); setError(null); };

  function submit(e: FormEvent) {
    e.preventDefault();
    if (ed.kind === "college") {
      const pct = Number(cshare.trim().replace(/%$/, ""));
      if (ctype !== "none" && (cshare.trim() === "" || !Number.isFinite(pct) || pct < 0 || pct > 100)) return fail("Use a share from 0 to 100.");
      return onSave(field, { college_type: ctype, college_share: ctype === "none" ? 1 : pct / 100 } satisfies CollegeChoice);
    }
    if (ed.kind === "split") {
      if (amounts.some((a) => a == null)) return fail("Use numbers only, such as 250000 or 250k.");
      if (total <= 0) return fail("Enter at least one amount.");
      return onSave(field, Object.fromEntries(SPLIT_KEYS.map((k, i) => [k, amounts[i]!])) as Split);
    }
    if (ed.kind === "state") {
      const code = stateFromText(text);
      if (!code) return fail("Pick a state from the list, such as Connecticut or Washington, DC.");
      return onSave(field, code);
    }
    if (ed.kind === "text") {
      const t = text.trim();
      if (!t) return fail("Write a few words, such as Nurse.");
      return onSave(field, t.slice(0, 60));
    }
    if (ed.kind === "home") {
      if (!hmode) return fail("Say whether you own or rent.");
      const need = hmode === "rent" ? ["rent"] : hmode === "mortgage" ? ["value", "mortgage_balance", "mortgage_payment"] : ["value"];
      const n: Record<string, number> = { value: 0, mortgage_balance: 0, mortgage_payment: 0, rent: 0 };
      for (const k of need) {
        const a = parseAmount(home[k]);
        if (a == null) return fail("Use numbers only, such as 450000 or 450k.");
        n[k] = a;
      }
      if (hmode === "rent" && n.rent <= 0) return fail("Enter the rent a month.");
      return onSave(field, { ...h, owns: hmode !== "rent", ...n });
    }
    if (spec) {
      const out: Parsed[] = [];
      for (let i = 0; i < rows.length; i++) {
        const p: Parsed = {};
        for (const c of cols) {
          const r = readCol(c, rows[i][c.key] ?? "");
          if ("err" in r) return fail(spec.list ? `${spec.list.noun} ${i + 1}. ${r.err}` : r.err);
          p[c.key] = r.v;
        }
        if (rows[i]._i != null) p._i = rows[i]._i;
        out.push(p);
      }
      if (field.key === "pensions" && !hasBoth(profile)) out.forEach((p) => { p.who = "you"; });
      return onSave(field, spec.to(out, profile));
    }
    const n = parseAmount(text);
    const dec = field.key === "emergency_months" ? Number(text.trim()) : null;
    const val = dec != null && Number.isFinite(dec) ? dec : n;
    if (val == null || text.trim() === "") return fail(ed.kind === "number" ? (AGES[field.key] ? "Use a whole number of years, such as 45." : "Use a number, such as 4 or 4.5.") : "Use a number, such as 120000 or 120k.");
    const [alo, ahi] = AGES[field.key] ?? [1, 110];
    const lo = field.editable?.min ?? alo, hi = field.editable?.max ?? ahi;
    if (ed.kind === "number" && (val < lo || val > hi)) return fail(`Use a whole number from ${lo} to ${hi}.`);
    const own = field.key === "retire_age" ? [profile.age, profile.pay_per_year] : field.key === "partner_retire_age" ? [profile.partner_age as number | null | undefined, profile.partner_pay_per_year as number | null | undefined] : null;
    const retired = (profile.notes as Record<string, string> | undefined)?.retired === "yes";
    if (own && typeof own[0] === "number" && val < own[0] && (Number(own[1]) || 0) > 0 && !retired) return fail(`That is below the age now (${own[0]}). Use ${own[0]} or more, or set the pay to 0 if you have stopped work.`);
    onSave(field, val);
  }

  const key = (e: { key: string; stopPropagation: () => void }) => { if (e.key === "Escape") { e.stopPropagation(); onCancel(); } };
  const per = MONEYS[field.key];
  const autoOnce = (i: number, j: number) => i === 0 && j === 0;

  /** One box, labelled, for a column of a form. */
  const cell = (c: Col, i: number, j: number) => {
    const cid = `${id}-${i}-${c.key}`;
    const lab = `${c.label}${c.per ? `, ${c.per}` : ""}`;
    const val = rows[i]?.[c.key] ?? "";
    return (
      <label key={c.key} htmlFor={cid} className="split-field">
        <span>{lab}{c.optional ? " (optional)" : ""}</span>
        {c.kind === "select" ? (
          <select id={cid} value={val} onChange={(e) => setCell(i, c.key, e.target.value)}>
            {c.options!.map(([v, w]) => <option key={v} value={v}>{w}</option>)}
          </select>
        ) : (
          <input id={cid} inputMode={c.kind === "text" ? "text" : "decimal"} autoComplete="off" autoFocus={autoOnce(i, j)} placeholder={c.kind === "money" ? "$0" : ""} value={val}
            onChange={(e) => setCell(i, c.key, e.target.value)} />
        )}
      </label>
    );
  };

  return (
    <form ref={form} className="editor" aria-label={`Change ${field.label}`} onSubmit={submit} onKeyDown={key}>
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
            {SPLIT_KEYS.map((k, i) => (
              <label key={k} htmlFor={`${id}-${k}`} className="split-field">
                <span>{SPLIT_LABELS[k]}{total > 0 && amounts[i] != null ? <span className="muted"> · {Math.round(((amounts[i] ?? 0) / total) * 100)}%</span> : null}</span>
                <input id={`${id}-${k}`} name={k} inputMode="numeric" autoComplete="off" placeholder="$0" value={parts[k]}
                  onChange={(e) => { setParts({ ...parts, [k]: e.target.value }); setError(null); }} />
              </label>
            ))}
          </div>
          <p className="split-total num" role="status">Total: <strong>{usd(total)}</strong>{total > 0 && amounts.every((a) => a != null) ? <span className="muted"> · shares add to 100%</span> : null}</p>
        </>
      )}
      {(ed.kind === "money" || ed.kind === "number") && (
        <>
          <label htmlFor={id} className="split-field">
            <span>{field.label}{ed.kind === "money" ? (per ? `, ${per}` : per === "" ? "" : /per_year|pay|spend|social/.test(field.key) ? ", a year" : "") : ""}{field.key === "emergency_months" ? ", months" : ""}</span>
            <input id={id} inputMode={field.key === "emergency_months" ? "decimal" : "numeric"} autoFocus autoComplete="off" placeholder={ed.kind === "money" ? "$0" : ""} value={text}
              onChange={(e) => { setText(e.target.value); setError(null); }} />
          </label>
          {ed.kind === "number" && AGES[field.key] && <p className="editor-hint small muted">{AGES[field.key][0]} to {AGES[field.key][1]}.{/retire_age/.test(field.key) ? " Enough never suggests retiring after 70." : ""}</p>}
        </>
      )}
      {ed.kind === "text" && (
        <label htmlFor={id} className="split-field">
          <span>{field.label}</span>
          <input id={id} autoFocus autoComplete="off" maxLength={60} value={text} onChange={(e) => { setText(e.target.value); setError(null); }} />
        </label>
      )}
      {ed.kind === "state" && (
        <label htmlFor={id} className="split-field">
          <span>State (start typing, then pick one)</span>
          <input id={id} list={`${id}-list`} autoFocus autoComplete="off" placeholder="Connecticut" value={text} onChange={(e) => { setText(e.target.value); setError(null); }} />
          <datalist id={`${id}-list`}>{STATE_NAMES.map(([c, n]) => <option key={c} value={n} />)}</datalist>
        </label>
      )}
      {ed.kind === "home" && (
        <>
          <div className="choices" role="group" aria-label="Home">
            {HOME_MODES.map(([m, w]) => (
              <button key={m} type="button" className={`chip${hmode === m ? " chip-on" : ""}`} aria-pressed={hmode === m} onClick={() => { setHmode(m); setError(null); }}>{w}</button>
            ))}
          </div>
          <div className="split-grid">
            {hmode === "rent" && (
              <label htmlFor={`${id}-rent`} className="split-field"><span>Rent, a month</span>
                <input id={`${id}-rent`} inputMode="numeric" autoFocus autoComplete="off" placeholder="$0" value={home.rent} onChange={(e) => { setHome({ ...home, rent: e.target.value }); setError(null); }} /></label>
            )}
            {(hmode === "outright" || hmode === "mortgage") && (
              <label htmlFor={`${id}-value`} className="split-field"><span>What the home is worth</span>
                <input id={`${id}-value`} inputMode="numeric" autoComplete="off" placeholder="$0" value={home.value} onChange={(e) => { setHome({ ...home, value: e.target.value }); setError(null); }} /></label>
            )}
            {hmode === "mortgage" && (
              <>
                <label htmlFor={`${id}-mortgage_balance`} className="split-field"><span>Left on the mortgage</span>
                  <input id={`${id}-mortgage_balance`} inputMode="numeric" autoComplete="off" placeholder="$0" value={home.mortgage_balance} onChange={(e) => { setHome({ ...home, mortgage_balance: e.target.value }); setError(null); }} /></label>
                <label htmlFor={`${id}-mortgage_payment`} className="split-field"><span>Mortgage payment, a month</span>
                  <input id={`${id}-mortgage_payment`} inputMode="numeric" autoComplete="off" placeholder="$0" value={home.mortgage_payment} onChange={(e) => { setHome({ ...home, mortgage_payment: e.target.value }); setError(null); }} /></label>
              </>
            )}
          </div>
        </>
      )}
      {spec && (
        <>
          {spec.intro && <p className="editor-hint small muted">{spec.intro}</p>}
          {rows.map((_r, i) => (
            <fieldset key={i} className="editor-row">
              {spec.list && <legend>{spec.list.noun} {i + 1}</legend>}
              <div className="split-grid">{cols.map((c, j) => cell(c, i, j))}</div>
              {spec.list && <button type="button" className="btn btn-quiet btn-small" aria-label={`Remove ${spec.list.noun.toLowerCase()} ${i + 1}`}
                onClick={() => { setRows((rs) => rs.filter((_, j) => j !== i)); setError(null); }}>Remove</button>}
            </fieldset>
          ))}
          {spec.list && rows.length === 0 && <p className="small muted" role="status">None. Add one, or save to keep none.</p>}
          {spec.list && rows.length < spec.list.max && (
            <button type="button" className="btn btn-quiet btn-small editor-add"
              onClick={() => { setRows((rs) => [...rs, Object.fromEntries(cols.map((c) => [c.key, c.kind === "select" ? (c.options![0][0]) : c.key === "count" ? "1" : ""]))]); setError(null); }}>{spec.list.add}</button>
          )}
        </>
      )}
      {ed.kind === "college" && (
        <>
          <div className="choices" role="group" aria-label={`${field.label}: type`}>
            {COLLEGE_TYPES.map((c) => (
              <button key={c.id} type="button" className={`chip${ctype === c.id ? " chip-on" : ""}`} aria-pressed={ctype === c.id}
                onClick={() => { setCtype(c.id); setError(null); }}>{c.label}</button>
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
          {ed.options.map((c) => (
            <button key={c} type="button" className={`chip${String(field.value) === c ? " chip-on" : ""}`} aria-pressed={String(field.value) === c} onClick={() => onSave(field, c)}>
              {c.charAt(0).toUpperCase() + c.slice(1)}
            </button>
          ))}
        </div>
      )}
      {ed.kind === "yesno" && (
        <div className="choices" role="group" aria-label={field.label}>
          {([["Yes", true], ["No", false]] as const).map(([w, b]) => (
            <button key={w} type="button" className={`chip${field.value === b ? " chip-on" : ""}`} aria-pressed={field.value === b} onClick={() => onSave(field, b)}>{w}</button>
          ))}
        </div>
      )}
      {error && <p className="editor-error small" role="alert">{error}</p>}
      <div className="editor-actions">
        {ed.kind !== "choice" && ed.kind !== "yesno" && <button type="submit" className="btn btn-primary btn-small">Save</button>}
        <button type="button" className="btn btn-quiet btn-small" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

const hasBoth = (p: Profile) => p.partner_age != null || (p as Record<string, unknown>).has_partner === true;
