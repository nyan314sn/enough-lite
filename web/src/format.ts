import type { Profile } from "./types";

export const usd = (n: number) => `${n < 0 ? "-" : ""}$${Math.round(Math.abs(n)).toLocaleString("en-US")}`;

/** $1.2M, $850k: for chart axes and tight spots. */
export function usdShort(n: number): string {
  const a = Math.abs(n);
  if (a >= 1e6) return `$${(n / 1e6).toFixed(a >= 1e7 ? 0 : 1).replace(/\.0$/, "")}M`;
  if (a >= 1e3) return `$${Math.round(n / 1e3)}k`;
  return `$${Math.round(n)}`;
}

export const cents = (n: number) => (n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(3)}`);

export const STATES: Record<string, string> = {
  AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California", CO: "Colorado", CT: "Connecticut", DE: "Delaware", DC: "Washington, DC",
  FL: "Florida", GA: "Georgia", HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa", KS: "Kansas", KY: "Kentucky", LA: "Louisiana",
  ME: "Maine", MD: "Maryland", MA: "Massachusetts", MI: "Michigan", MN: "Minnesota", MS: "Mississippi", MO: "Missouri", MT: "Montana", NE: "Nebraska",
  NV: "Nevada", NH: "New Hampshire", NJ: "New Jersey", NM: "New Mexico", NY: "New York", NC: "North Carolina", ND: "North Dakota", OH: "Ohio",
  OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina", SD: "South Dakota", TN: "Tennessee", TX: "Texas",
  UT: "Utah", VT: "Vermont", VA: "Virginia", WA: "Washington", WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming",
};
export const stateName = (s: string) => STATES[s.toUpperCase()] ?? s;

const MONEY_KEY = /pay|saving|spend|value|mortgage|rent|social|income|balance|cost|budget|amount|wealth/i;
const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

const plain = (t: string) => t.replace(/_/g, " ");

function pensionText(p: Record<string, unknown>): string {
  const who = p.who === "partner" ? "Your partner" : "You";
  return `${who}: ${usd(Number(p.per_year) || 0)} a year${p.start_age ? ` from ${p.start_age}` : ""}${p.inflation_adjusted ? ", rises with prices" : ""}`;
}

function debtText(d: Record<string, unknown>): string {
  const kind = plain(String(d.kind ?? "debt")).replace(/^student$/, "student loan").replace(/^car$/, "car loan");
  const rate = typeof d.rate === "number" ? `, ${+(d.rate * 100).toFixed(1)}%` : "";
  const pay = d.monthly_payment ? `, ${usd(Number(d.monthly_payment))} a month` : "";
  return `${kind.charAt(0).toUpperCase()}${kind.slice(1)}: ${usd(Number(d.balance) || 0)}${rate}${pay}`;
}

function homeText(o: Record<string, unknown>): string {
  if (!o.owns) return o.rent ? `Rent, ${usd(Number(o.rent))} a month` : o.owns === false ? "Rent" : "Not given";
  const bits = ["Own"];
  if (o.mortgage_balance) bits.push(`${usd(Number(o.mortgage_balance))} left on the mortgage`);
  if (o.mortgage_payment) bits.push(`${usd(Number(o.mortgage_payment))} a month`);
  bits.push(o.value ? `worth ${usd(Number(o.value))}` : "value not given");
  return bits.join(", ");
}

/** A field's value in plain words, whatever shape the server sends. */
export function showValue(key: string, v: unknown): string {
  if (v == null || v === "") return "Not given";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "number") return MONEY_KEY.test(key) ? usd(v) + (/per_year|pay|spend|social/.test(key) ? " a year" : "") : String(v);
  if (typeof v === "string") return key === "state" ? stateName(v) : v.charAt(0).toUpperCase() + v.slice(1);
  if (Array.isArray(v)) {
    if (v.length === 0) return "None";
    if (key === "pensions") return v.map((x) => pensionText(x as Record<string, unknown>)).join("; ");
    if (key === "debts") return v.map((x) => debtText(x as Record<string, unknown>)).join("; ");
    if (key === "children" || v.every((x) => x && typeof x === "object" && "age" in x)) {
      const ages = v.map((c) => (c as { age: number }).age).sort((a, b) => a - b);
      return `${plural(ages.length, "child", "children")}, age${ages.length > 1 ? "s" : ""} ${ages.length > 1 ? `${ages.slice(0, -1).join(", ")} and ${ages[ages.length - 1]}` : ages[0]}`;
    }
    if (key === "pets" || v.every((x) => x && typeof x === "object" && "kind" in x)) {
      return v.map((x) => { const p = x as { kind: string; count: number }; return plural(p.count ?? 1, p.kind === "other" ? "pet" : p.kind); }).join(", ");
    }
    return v.map((x) => showValue(key, x)).join(", ");
  }
  if (typeof v === "object") {
    const o = v as Record<string, unknown>;
    if (key === "savings") {
      const total = ["pretax", "roth", "taxable", "cash"].reduce((s, k) => s + (Number(o[k]) || 0), 0);
      return usd(total);
    }
    if (key === "home") return homeText(o);
    if (key === "life_insurance") return o.kind && o.kind !== "none" ? `${plain(String(o.kind))} life cover${o.face ? `, ${usd(Number(o.face))}` : ""}` : "None";
    if (key === "parents_help") return o.per_year ? `${usd(Number(o.per_year))} a year${o.years ? ` for ${plural(Number(o.years), "year")}` : ""}` : "None";
    const bits = Object.entries(o).filter(([, x]) => x != null && x !== "").map(([k, x]) => `${plain(k)} ${showValue(k, x)}`);
    return bits.length ? bits.join(", ") : "Not given";
  }
  return String(v);
}

/** The savings split, for the details line under the total. */
export function savingsParts(p: Profile): string | null {
  const s = p.savings;
  if (!s) return null;
  const parts = [["pre-tax", s.pretax], ["Roth", s.roth], ["taxable", s.taxable], ["cash", s.cash]].filter(([, v]) => Number(v) > 0) as [string, number][];
  return parts.length ? parts.map(([k, v]) => `${usdShort(v)} ${k}`).join(", ") : null;
}

/** "You (45), your partner (43), 3 children (13, 10, 6) and 2 dogs": the picture in words, for screen readers and the caption. */
export function householdLine(p: Profile): string {
  const bits: string[] = [p.age != null ? `You (${p.age})` : "You"];
  if (p.partner_age != null) bits.push(`your partner (${p.partner_age})`);
  const kids = p.children ?? [];
  if (kids.length) bits.push(`${plural(kids.length, "child", "children")} (${kids.map((c) => c.age).join(", ")})`);
  for (const pet of p.pets ?? []) if (pet.count > 0) bits.push(plural(pet.count, pet.kind === "other" ? "other pet" : pet.kind));
  if (bits.length === 1) return bits[0];
  return `${bits.slice(0, -1).join(", ")} and ${bits[bits.length - 1]}`;
}

/** "smooth" scrolling, unless the person has asked their system for less motion. */
export function scrollBehavior(): ScrollBehavior {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}
