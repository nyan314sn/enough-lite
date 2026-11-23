import { STATES } from "../format";
import type { Field, Profile } from "../types";

// What each figure in "What we have so far" lets a person type, and how an edit lands in the profile.
// One entry per field key the server can show. A field with no entry here (and no server hint) has no editor.

export type ColKind = "money" | "int" | "pct" | "text" | "select";
export interface Col {
  key: string; label: string; kind: ColKind;
  per?: string;                       // "a year", "a month"
  min?: number; max?: number;
  options?: [string, string][];       // value, words
  optional?: boolean;                 // blank is allowed (the plan then uses a typical figure)
  hint?: string;
  when?: (p: Profile) => boolean;     // shown only for some households (partner)
}
export type Row = Record<string, string>;
export type Parsed = Record<string, string | number | boolean | null>;

export interface Spec {
  cols: Col[];
  intro?: string;
  list?: { add: string; noun: string; max: number };
  /** Starting text for each box, from the field's value. */
  from: (f: Field, p: Profile) => Row[];
  /** The field's new value from the typed rows (in the same shape the server sends). */
  to: (rows: Parsed[], p: Profile) => unknown;
}

const s = (v: unknown) => (v == null ? "" : String(v));
const pct = (v: unknown) => (v == null || v === "" ? "" : String(+(Number(v) * 100).toFixed(2)));
const obj = (v: unknown) => ((v && typeof v === "object" && !Array.isArray(v) ? v : {}) as Record<string, unknown>);
const arr = (v: unknown) => (Array.isArray(v) ? (v as Record<string, unknown>[]) : []);
const hasPartner = (p: Profile) => p.partner_age != null || (p as Record<string, unknown>).has_partner === true;

const KINDS_DEBT: [string, string][] = [["student", "Student loan"], ["car", "Car loan"], ["credit_card", "Credit card"], ["other", "Other debt"]];
const RISES: [string, string][] = [["", "Not sure"], ["yes", "Rises with prices"], ["no", "Does not rise"]];
const COUNTED: [string, string][] = [["no", "Information only"], ["yes", "Count it in the plan"]];
const CAP = (min = 0, max = 100) => ({ min, max });

export const SPECS: Record<string, Spec> = {
  children: {
    cols: [{ key: "age", label: "Age", kind: "int", min: 0, max: 30 }],
    intro: "One line for each child. Add or remove lines. College is set for each child in its own row.",
    list: { add: "Add a child", noun: "Child", max: 12 },
    from: (f) => arr(f.value).map((c, i) => ({ age: s(c.age), _i: String(i) })),
    to: (rows, p) => rows.map((r) => {
      const old = r._i != null ? arr(p.children)[Number(r._i)] : undefined;
      return old ? { ...old, age: r.age } : { age: r.age, college: true };
    }),
  },
  pets: {
    cols: [{ key: "kind", label: "Kind", kind: "select", options: [["dog", "Dog"], ["cat", "Cat"], ["other", "Other pet"]] }, { key: "count", label: "How many", kind: "int", min: 1, max: 20 }],
    list: { add: "Add a pet", noun: "Pet", max: 8 },
    from: (f) => arr(f.value).map((x) => ({ kind: s(x.kind) || "dog", count: s(x.count || 1) })),
    to: (rows) => rows.map((r) => ({ kind: r.kind, count: r.count })),
  },
  debts: {
    cols: [
      { key: "kind", label: "Kind", kind: "select", options: KINDS_DEBT },
      { key: "balance", label: "Balance", kind: "money" },
      { key: "rate", label: "Interest rate, % a year", kind: "pct", optional: true, ...CAP(0, 60) },
      { key: "monthly_payment", label: "Payment", kind: "money", per: "a month", optional: true },
    ],
    intro: "Leave the rate or payment blank if you do not know it. The plan then uses a typical one and marks it.",
    list: { add: "Add a debt", noun: "Debt", max: 10 },
    from: (f) => arr(f.value).map((d) => ({ kind: s(d.kind) || "other", balance: s(d.balance), rate: pct(d.rate), monthly_payment: s(d.monthly_payment) })),
    to: (rows) => rows.map((r) => ({ kind: r.kind, balance: r.balance, rate: r.rate, monthly_payment: r.monthly_payment, assumed: ["rate", "monthly_payment"].filter((k) => r[k] == null) })),
  },
  pensions: {
    cols: [
      { key: "who", label: "Whose", kind: "select", options: [["you", "Yours"], ["partner", "Your partner's"]], when: hasPartner },
      { key: "per_year", label: "Pension", kind: "money", per: "a year" },
      { key: "start_age", label: "Starts at age", kind: "int", min: 40, max: 90, optional: true },
      { key: "inflation_adjusted", label: "Does it rise with prices?", kind: "select", options: RISES },
      { key: "survivor_share", label: "Share a surviving partner gets, %", kind: "pct", optional: true, when: hasPartner, ...CAP() },
    ],
    intro: "Leave the start age blank and the plan uses 65, marked assumed.",
    list: { add: "Add a pension", noun: "Pension", max: 6 },
    from: (f) => arr(f.value).map((x) => ({ who: s(x.who) || "you", per_year: s(x.per_year), start_age: s(x.start_age), inflation_adjusted: x.inflation_adjusted == null ? "" : x.inflation_adjusted ? "yes" : "no", survivor_share: pct(x.survivor_share) })),
    to: (rows) => rows.map((r) => ({ who: r.who ?? "you", per_year: r.per_year, start_age: r.start_age, inflation_adjusted: r.inflation_adjusted === "yes" ? true : r.inflation_adjusted === "no" ? false : null, survivor_share: r.survivor_share, assumed: ["start_age"].filter((k) => r[k] == null) })),
  },
  big_costs: {
    cols: [
      { key: "label", label: "What for", kind: "text" },
      { key: "amount", label: "Cost", kind: "money" },
      { key: "year", label: "Year", kind: "int", min: 2026, max: 2100, optional: true },
    ],
    list: { add: "Add a big cost", noun: "Cost", max: 10 },
    from: (f) => arr(f.value).map((b) => ({ label: s(b.label), amount: s(b.amount), year: s(b.year) })),
    to: (rows) => rows.map((r) => ({ label: r.label, amount: r.amount, year: r.year })),
  },
  part_time: {
    cols: [{ key: "per_year", label: "Part-time pay in retirement", kind: "money", per: "a year" }, { key: "until_age", label: "Until age", kind: "int", min: 50, max: 90, optional: true }],
    from: (f) => [{ per_year: s(obj(f.value).per_year), until_age: s(obj(f.value).until_age) }],
    to: (rows) => ({ per_year: rows[0].per_year, until_age: rows[0].until_age }),
  },
  inheritance: {
    cols: [
      { key: "amount", label: "Amount", kind: "money" },
      { key: "year", label: "Year", kind: "int", min: 2026, max: 2100, optional: true },
      { key: "gift", label: "Is it", kind: "select", options: [["no", "An inheritance"], ["yes", "A gift"]] },
      { key: "count", label: "In the plan?", kind: "select", options: COUNTED },
    ],
    intro: "An inheritance or gift is counted only if you say to count it.",
    from: (f) => { const o = obj(f.value); return [{ amount: s(o.amount), year: s(o.year), gift: o.gift ? "yes" : "no", count: o.count ? "yes" : "no" }]; },
    to: (rows) => ({ amount: rows[0].amount, year: rows[0].year, gift: rows[0].gift === "yes", count: rows[0].count === "yes" }),
  },
  life_insurance: {
    cols: [
      { key: "kind", label: "Cover", kind: "select", options: [["none", "None"], ["term", "Term life"], ["whole", "Whole life"]] },
      { key: "face", label: "Cover amount", kind: "money", optional: true },
      { key: "premium", label: "Premium", kind: "money", per: "a year", optional: true },
    ],
    from: (f) => { const o = obj(f.value); return [{ kind: s(o.kind) || "none", face: s(o.face), premium: s(o.premium) }]; },
    to: (rows) => { const r = rows[0]; return r.kind === "none" ? { kind: "none", face: null, premium: null } : { kind: r.kind, face: r.face, premium: r.premium }; },
  },
  parents_help: {
    cols: [{ key: "per_year", label: "Help for parents", kind: "money", per: "a year" }, { key: "years", label: "For how many years", kind: "int", min: 1, max: 40, optional: true }],
    from: (f) => [{ per_year: s(obj(f.value).per_year), years: s(obj(f.value).years) }],
    to: (rows) => ({ per_year: rows[0].per_year, years: rows[0].years }),
  },
  contributions: {
    cols: [
      { key: "contrib_you", label: "You put into a 401(k) or IRA", kind: "money", per: "a year", optional: true },
      { key: "contrib_partner", label: "Your partner puts in", kind: "money", per: "a year", optional: true, when: hasPartner },
    ],
    from: (f) => [{ contrib_you: s(obj(f.value).contrib_you), contrib_partner: s(obj(f.value).contrib_partner) }],
    to: (rows) => ({ contrib_you: rows[0].contrib_you, contrib_partner: rows[0].contrib_partner }),
  },
  match: {
    cols: [
      { key: "rate", label: "Employer match, cents per dollar you save", kind: "pct", ...CAP(0, 200) },
      { key: "cap", label: "Up to this share of pay, %", kind: "pct", optional: true, ...CAP() },
    ],
    from: (f) => [{ rate: pct(obj(f.value).rate), cap: pct(obj(f.value).cap) }],
    to: (rows) => ({ rate: rows[0].rate, cap: rows[0].cap }),
  },
  save_rate: {
    cols: [{ key: "rate", label: "Share of pay you save each year, %", kind: "pct", ...CAP() }],
    from: (f) => [{ rate: pct(f.value) }],
    to: (rows) => rows[0].rate,
  },
  budget: {
    cols: ["housing", "food", "transport", "health", "childcare", "debt", "other"].map((k) => ({
      key: k, label: k === "debt" ? "Debt payments" : k.charAt(0).toUpperCase() + k.slice(1), kind: "money" as const, per: "a month", optional: true,
    })),
    intro: "Spending now, by kind. Leave a line blank if it is none or you do not know.",
    from: (f) => [Object.fromEntries(["housing", "food", "transport", "health", "childcare", "debt", "other"].map((k) => [k, s(obj(f.value)[k])]))],
    to: (rows) => Object.fromEntries(Object.entries(rows[0])),
  },
};

/** Single-box kinds that are not a form. */
export const CHOICES: Record<string, string[]> = {
  risk: ["careful", "balanced", "growth"],
  sex: ["male", "female"], partner_sex: ["male", "female"],
  health: ["excellent", "good", "fair", "poor"], partner_health: ["excellent", "good", "fair", "poor"],
};
export const YESNO = new Set(["disability", "ltc"]);
export const TEXTS = new Set(["job", "partner_job"]);
export const AGES: Record<string, [number, number]> = { age: [18, 110], partner_age: [18, 110], retire_age: [30, 80], partner_retire_age: [30, 80] };
/** Plain money boxes and what they are per. */
export const MONEYS: Record<string, string> = {
  pay_per_year: "a year", partner_pay_per_year: "a year", social_security_per_year: "a year", spending_per_year: "a year", spending_now_per_year: "a year",
  legacy: "", other_saving: "a month",
};
/** Shown for fields that are worked out, never typed. */
export const READ_ONLY = new Set(["mortgage_end"]);

/** The word each field has in the chat line "Updated your <noun>: ..." (the server reads these, intake.UPDATED_LABELS). */
export const NOUN: Record<string, string> = {
  age: "age", partner_age: "partner's age", sex: "sex", partner_sex: "partner's sex", state: "state", children: "children", pets: "pets",
  job: "job", partner_job: "partner's job", pay_per_year: "pay", partner_pay_per_year: "partner's pay", retire_age: "retirement age",
  partner_retire_age: "partner's retirement age", part_time: "part-time work", savings: "savings", save_rate: "yearly saving",
  contributions: "retirement account saving", match: "employer match", other_saving: "other saving", emergency_months: "emergency fund",
  risk: "investing style", home: "home", debts: "other debts", social_security_per_year: "social security", pensions: "pensions",
  inheritance: "possible inheritance", life_insurance: "life insurance", disability: "disability insurance", ltc: "long-term care insurance",
  legacy: "money to leave behind", big_costs: "big planned costs", parents_help: "help for parents", health: "health", partner_health: "partner's health",
  spending_now_per_year: "spending now", budget: "spending split", spending_per_year: "spending in retirement",
};

const LABELS: Record<string, string> = {
  debts: "Other debts", pensions: "Pensions", contributions: "401(k) or IRA saving a year", life_insurance: "Life insurance", big_costs: "Big planned costs",
  health: "Your health", budget: "Spending split, a month", state: "State", children: "Children", pets: "Pets", home: "Home",
};

/** A field's current value read from the profile, for a pen that opens before the server has a row for it (an "Add" pen). */
export function valueFor(key: string, p: Profile): unknown {
  const r = p as Record<string, unknown>;
  const sv = obj(r.saving), ins = obj(r.insurance), g = obj(r.goals);
  switch (key) {
    case "contributions": return { contrib_you: sv.contrib_you ?? null, contrib_partner: sv.contrib_partner ?? null };
    case "match": return { rate: sv.match_rate ?? null, cap: sv.match_cap ?? null };
    case "other_saving": return sv.other_per_month ?? null;
    case "life_insurance": return { kind: ins.life_kind ?? "none", face: ins.life_face ?? null, premium: ins.life_premium ?? null };
    case "disability": return ins.disability ?? null;
    case "ltc": return ins.ltc ?? null;
    case "legacy": return g.legacy ?? null;
    case "big_costs": return g.big_costs ?? [];
    case "parents_help": return { per_year: g.parents_per_year ?? null, years: g.parents_years ?? null };
    default: return r[key] ?? (key in SPECS && SPECS[key].list ? [] : null);
  }
}

/** A row the server has not sent yet (an empty section's "Add" pen), built from the profile. */
export function synthField(key: string, p: Profile): Field {
  return { key, label: LABELS[key] ?? key, value: valueFor(key, p), source: "default", display: "", note: null, section: null };
}

/** The profile after one field is edited: the field's own shape goes back to where the profile keeps it. */
export function applyEdit(p: Profile, key: string, value: unknown): Profile {
  const r = p as Record<string, unknown>;
  const v = obj(value);
  const sv = { ...obj(r.saving) }, ins = { ...obj(r.insurance) }, g = { ...obj(r.goals) };
  switch (key) {
    case "savings": return { ...p, savings: value as Profile["savings"], savings_known: true };
    case "contributions": return { ...p, saving: { ...sv, contrib_you: v.contrib_you, contrib_partner: v.contrib_partner } };
    case "match": return { ...p, saving: { ...sv, match_rate: v.rate, match_cap: v.cap } };
    case "other_saving": return { ...p, saving: { ...sv, other_per_month: value } };
    case "life_insurance": return { ...p, insurance: { ...ins, life_kind: v.kind, life_face: v.face, life_premium: v.premium } };
    case "disability": return { ...p, insurance: { ...ins, disability: value } };
    case "ltc": return { ...p, insurance: { ...ins, ltc: value } };
    case "legacy": return { ...p, goals: { ...g, legacy: value } };
    case "big_costs": return { ...p, goals: { ...g, big_costs: value } };
    case "parents_help": return { ...p, goals: { ...g, parents_per_year: v.per_year, parents_years: v.years } };
    default: return { ...p, [key]: value };
  }
}

/** Every state and DC by full name, for the state box. */
export const STATE_NAMES: [string, string][] = Object.entries(STATES).sort((a, b) => a[1].localeCompare(b[1]));
export function stateFromText(t: string): string | null {
  const x = t.trim().toLowerCase();
  if (!x) return null;
  if (x === "district of columbia" || x === "washington dc" || x === "washington d.c.") return "DC";
  const hit = STATE_NAMES.find(([c, n]) => n.toLowerCase() === x || c.toLowerCase() === x);
  return hit ? hit[0] : null;
}
