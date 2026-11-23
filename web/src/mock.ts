// A stand-in server for building and screenshots without the backend (VITE_MOCK=1). It follows the API contract in PLAN.md and replays
// the doctor example: a 45-year-old doctor in Connecticut, a wife at home, three children and two dogs. Nothing here is a real calculation.
import type { Api, AskResponse, Field, IntakeResponse, Plan, PlanEvent, Profile, Sample, Source } from "./types";

export { EXAMPLE_TEXT } from "./examples";

const sleep = (ms: number, signal?: AbortSignal) => new Promise<void>((resolve) => {
  if (ms <= 0) return resolve();
  const t = setTimeout(resolve, ms);
  signal?.addEventListener("abort", () => { clearTimeout(t); resolve(); });
});

/** Speed for the replay: 1 is realistic, 0 is instant (tests). */
export const mockSpeed = { factor: 1 };

const WORDS: Record<string, number> = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, a: 1, an: 1 };
const num = (s: string) => (WORDS[s.toLowerCase()] ?? Number(s));

function money(text: string): number | null {
  const m = text.replace(/,/g, "").match(/\$?\s*(\d+(?:\.\d+)?)\s*(million|m\b|k\b|thousand)?/i);
  if (!m) return null;
  let v = Number(m[1]);
  const unit = (m[2] ?? "").toLowerCase();
  if (unit.startsWith("m")) v *= 1_000_000;
  else if (unit.startsWith("k") || unit.startsWith("t")) v *= 1_000;
  return v;
}

type Sources = Record<string, { source: Source; note?: string }>;

const LABELS: Record<string, string> = {
  age: "Your age", partner_age: "Partner's age", state: "State", retire_age: "Retire at", pay_per_year: "Your pay",
  partner_pay_per_year: "Partner's pay", savings: "Savings", home: "Home", children: "Children", pets: "Pets",
  spending_per_year: "Spending", social_security_per_year: "Social Security", risk: "Risk",
};
const REQUIRED = ["age", "state", "retire_age", "pay_per_year", "savings"];

function fieldsOf(p: Profile, src: Sources): Field[] {
  const out: Field[] = [];
  for (const key of Object.keys(LABELS)) {
    const v = p[key];
    if (v == null || (Array.isArray(v) && v.length === 0 && !src[key])) continue;
    out.push({ key, label: LABELS[key], value: v, source: src[key]?.source ?? "estimate", note: src[key]?.note ?? null });
  }
  return out;
}

function applyText(text: string, prev: Profile, src: Sources): Profile {
  const p: Profile = structuredClone(prev);
  const t = text.trim();
  const said = (k: string, v: unknown, note?: string) => { p[k] = v; src[k] = { source: "you said", note }; };
  const guess = (k: string, v: unknown, note: string) => { if (p[k] == null || src[k]?.source !== "you said") { p[k] = v; src[k] = { source: "estimate", note }; } };

  const change = t.match(/^change (.+?) to:?\s*(.+)$/i);
  if (change) {
    const key = Object.keys(LABELS).find((k) => LABELS[k].toLowerCase() === change[1].trim().toLowerCase());
    if (key) {
      const v = money(change[2]);
      if (key === "savings" && v != null) said("savings", { pretax: Math.round(v * 0.6), roth: Math.round(v * 0.1), taxable: Math.round(v * 0.25), cash: Math.round(v * 0.05) });
      else if (key === "state") said("state", change[2].trim().slice(0, 2).toUpperCase());
      else if (key === "risk") said("risk", /care/i.test(change[2]) ? "careful" : /grow/i.test(change[2]) ? "growth" : "balanced");
      else if (v != null) said(key, v);
    }
    return p;
  }

  const age = t.match(/\bI'?m (\d{2})\b|\b(\d{2})[- ]year[- ]old/i);
  if (age) said("age", Number(age[1] ?? age[2]));
  if (/connecticut|\bCT\b/i.test(t)) said("state", "CT");
  const retire = t.match(/retire (?:at|by) (\d{2})/i);
  if (retire) said("retire_age", Number(retire[1]));
  if (/doctor|physician/i.test(t)) guess("pay_per_year", 380000, "Typical pay for a doctor in Connecticut");
  const pay = t.match(/(?:earn|make|pay is)\s+(\$?[\d,.]+\s*(?:k|million)?)/i);
  if (pay) said("pay_per_year", money(pay[1]));
  const partner = t.match(/(?:wife|husband|partner)(?: is (\d{2}))?/i);
  if (partner) {
    if (partner[1]) said("partner_age", Number(partner[1]));
    else guess("partner_age", (p.age ?? 45) - 2, "Two years younger than you");
  }
  if (/stays? (?:at )?home|stay-at-home/i.test(t)) said("partner_pay_per_year", 0);
  const kids = t.match(/(\d|one|two|three|four|five|six|a) (?:kids|children|child|kid)\b[^.]*?((?:\d{1,2}(?:,\s*|\s+and\s+|\s*\)?)){1,6})/i);
  if (kids) {
    const ages = (kids[2].match(/\d{1,2}/g) ?? []).map(Number).slice(0, num(kids[1]));
    said("children", ages.map((a) => ({ age: a, college: true })), "College assumed for each child");
  }
  const dogs = t.match(/(\d|one|two|three|four|a) dogs?/i);
  const cats = t.match(/(\d|one|two|three|four|a) cats?/i);
  if (dogs || cats) {
    const pets: Profile["pets"] = [];
    if (dogs) pets.push({ kind: "dog", count: num(dogs[1]) });
    if (cats) pets.push({ kind: "cat", count: num(cats[1]) });
    said("pets", pets);
  }
  if (/careful/i.test(t)) said("risk", "careful");
  if (/more risk|growth/i.test(t)) said("risk", "growth");
  if (/saved|savings|have about|about \$|million|^\$/i.test(t) && !age) {
    const v = money(t);
    if (v != null) said("savings", { pretax: Math.round(v * 0.6), roth: Math.round(v * 0.1), taxable: Math.round(v * 0.25), cash: Math.round(v * 0.05) }, "Split across accounts as is typical; change it if you know");
  }
  if (/not sure/i.test(t) && p.savings == null && p.age != null) guess("savings", { pretax: 840000, roth: 120000, taxable: 360000, cash: 80000 }, "Typical for a doctor your age");

  if (p.age != null && p.state) {
    guess("spending_per_year", 165000, "Typical for a family of five in Connecticut, before children's costs");
    guess("social_security_per_year", 52000, "From your pay, both of you, starting at 67");
    guess("home", { owns: true, value: 900000, mortgage_balance: 410000, mortgage_payment: 3800 }, "Typical for your town and pay");
    if (!p.risk) { p.risk = "balanced"; src.risk = { source: "assumed", note: "Change to careful or growth" }; }
    if (!p.children) p.children = [];
    if (!p.pets) p.pets = [];
  }
  return p;
}

function question(p: Profile, missing: string[]): IntakeResponse["question"] {
  if (missing.includes("age") || missing.includes("state"))
    return { text: "How old are you, and which state do you live in?", quick_answers: ["I'm 40, in New York", "I'm 55, in Texas"] };
  if (missing.includes("retire_age"))
    return { text: "When would you like to retire?", quick_answers: ["At 60", "At 62", "At 65", "At 67"] };
  if (missing.includes("savings"))
    return { text: "About how much have you saved in all, counting retirement accounts and other savings?", quick_answers: ["About $1 million", "About $1.4 million", "About $2 million", "Not sure"] };
  if (missing.includes("pay_per_year"))
    return { text: "What do you earn a year, before tax?", quick_answers: ["$120,000", "$250,000", "Not sure"] };
  return { text: `That is all we need. Check your numbers, then build your plan.${p.risk === "balanced" ? " How do you feel about risk?" : ""}`, quick_answers: ["We want to be careful", "Balanced is fine", "We can take more risk"] };
}

let src: Sources = {};

const MOCK_SAMPLES: { id: string; tier: Sample["tier"]; name: string; description: string; profile: Profile }[] = [
  { id: "m1", tier: "comfortable", name: "Doctor couple, 3 kids, CT", description: "Demo household.", profile: { age: 45, partner_age: 43, state: "CT", retire_age: 62, pay_per_year: 310000, savings: { pretax: 920000 }, children: [{ age: 13, college: true }], pets: [], spending_per_year: 190000 } },
  { id: "m2", tier: "average", name: "Single, 66, still working, FL", description: "Demo household.", profile: { age: 66, state: "FL", retire_age: 69, pay_per_year: 130000, savings: { pretax: 700000 }, children: [], pets: [], spending_per_year: 83000 } },
  { id: "m3", tier: "struggling", name: "Single parent, 2 kids, renting, GA", description: "Demo household.", profile: { age: 34, state: "GA", retire_age: 66, pay_per_year: 52000, savings: { pretax: 8000, cash: 2500 }, children: [{ age: 3, college: false }, { age: 7, college: false }], pets: [], spending_per_year: 40000 } },
];

/** What the mock has "spent" this session, for the session total. */
const spent = { usd: 0, tokens: 0 };

export const mockApi: Api = {
  async samples() {
    return MOCK_SAMPLES.map((h) => ({ ...h, intake: { profile: h.profile, fields: fieldsOf(h.profile, {}), missing: [], question: null, reply: "Loaded." } }));
  },
  async health() {
    return { status: "ok", provider: "anthropic", model: "claude-haiku-5-5", ai_available: true };
  },
  async modelCompare() {
    return { date: "2026-11-22", models: ["Claude Haiku 5.5", "gpt-6-luna"], rows: [{ metric: "Plan time, median", haiku: "11.0 s", gpt: "22.1 s", n: "80", winner: "Haiku", note: "2x faster" }, { metric: "Attack kit", haiku: "74/74", gpt: "74/74", n: "74", winner: "Tie" }], recommendation: "Use Claude Haiku 5.5 as the default. gpt-6-luna is fine as the staff fallback.", cost_usd: 2.6, caveats: ["Small samples."] };
  },
  async reset() { /* the mock keeps no session */ },
  async intake(text, profileSoFar, reset) {
    await sleep(700 * mockSpeed.factor);
    if (reset?.includes("all")) profileSoFar = {};
    if (!profileSoFar || Object.keys(profileSoFar).length === 0) src = {};
    const profile = applyText(text, profileSoFar ?? {}, src);
    const missing = REQUIRED.filter((k) => profile[k] == null);
    const before = profileSoFar ?? {};
    const learned = Object.keys(LABELS).filter((k) => JSON.stringify(profile[k]) !== JSON.stringify(before[k]) && src[k]?.source === "you said").map((k) => LABELS[k].toLowerCase());
    const reply = learned.length ? `Got it: ${learned.join(", ")}.` : /looks right|balanced is fine/i.test(text) ? "Good." : "I did not catch a number there. Could you say it another way?";
    return { profile, fields: fieldsOf(profile, src), missing, question: question(profile, missing), reply };
  },
  async plan(profile, onEvent, signal) {
    for (const [ms, ev] of planScript(profile)) {
      await sleep(ms * mockSpeed.factor, signal);
      if (signal?.aborted) return;
      if (ev.type === "agent_done") { spent.usd += ev.cost_usd; spent.tokens += ev.tokens.input + ev.tokens.cached + ev.tokens.output; }
      onEvent(ev);
    }
  },
  async ask(q, profile, plan) {
    await sleep(1100 * mockSpeed.factor);
    const r = mockAsk(q, profile, plan);
    spent.usd += r.cost_usd ?? 0; spent.tokens += typeof r.tokens === "object" && r.tokens ? r.tokens.input + r.tokens.cached + r.tokens.output : 0;
    return r;
  },
  async costs() {
    return { total_usd: Math.round(spent.usd * 1e6) / 1e6, total_tokens: spent.tokens };
  },
};

// ---- the plan ----

const PRICE = { input: 0.1 / 1e6, cached: 0.01 / 1e6, output: 0.5 / 1e6 };
const cost = (input: number, cached: number, output: number) => Math.round(((input - cached) * PRICE.input + cached * PRICE.cached + output * PRICE.output) * 1e6) / 1e6;

export function makeChart(age: number, retire: number, start: number, save: number, spend: number): Plan["chart"] {
  const ages: number[] = [], median: number[] = [], low: number[] = [], high: number[] = [];
  let w = start;
  for (let a = age; a <= 95; a++) {
    ages.push(a);
    const yrs = a - age;
    const spread = Math.min(0.75, 0.05 * Math.sqrt(yrs) * 1.6);
    median.push(Math.round(Math.max(0, w)));
    low.push(Math.round(Math.max(0, w * (1 - spread) - (a > retire ? (a - retire) * spend * 0.06 : 0))));
    high.push(Math.round(w * (1 + spread * 1.5)));
    w = a < retire ? w * 1.05 + save : w * 1.025 - spend;
  }
  return { ages, median, low, high };
}

export function examplePlan(p: Profile): Plan {
  const age = p.age ?? 45, retire = p.retire_age ?? 62;
  const kids = p.children?.length ?? 0;
  const s = p.savings ?? {};
  const start = (s.pretax ?? 0) + (s.roth ?? 0) + (s.taxable ?? 0) + (s.cash ?? 0) || 1_400_000;
  const early = Math.max(0, 62 - retire);
  const paid = Math.max(40, Math.min(99, 96 - early * 4 - Math.max(0, kids - 3) * 5));
  const wants = Math.round((158000 - early * 9000 - Math.max(0, kids - 3) * 7000) / 1000) * 1000;
  return {
    needs: { basics_per_year: 112000, paid_of_100: paid, line: `Housing, food, health care and the dogs: about $112,000 a year after tax, paid in ${paid} of 100 market tests.` },
    wants: { per_year: wants, line: `You can count on spending about $${wants.toLocaleString("en-US")} a year from ${retire} to 95, in 90 of 100 market tests.` },
    wishes: { line: "A lake house or a big trip each year is open if markets do well; it is not part of the plan." },
    actions: [
      { title: "Max out both 401(k) and a spousal IRA", why: "Your wife has no pay, but a spousal IRA lets you save $7,000 more a year for her, tax-deferred." },
      { title: "Open 529 plans for the three children", why: "College for three is the biggest bill before you retire. Connecticut lets you deduct up to $10,000 a year from state tax." },
      { title: "Buy term life insurance until the youngest is 22", why: "The family depends on one income. If you died early, the plan fails in most market tests without it." },
    ],
    family_moments: [
      "2031: your eldest starts college (about $38,000 a year for four years)",
      "2033: one dog likely gone; pet costs fall by half",
      "2038: your youngest finishes high school; costs at home fall",
      `${2026 + (retire - age)}: you retire at ${retire}; your wife is ${retire - 2}`,
    ],
    neighbors: { used: true, note: "12 similar households in our library; the life-insurance step comes from them." },
    chart: makeChart(age, retire, start, 95000 - Math.max(0, kids - 3) * 15000, wants + 30000),
  };
}

function planScript(p: Profile): [number, PlanEvent][] {
  const plan = examplePlan(p);
  const runs = [
    { agent: "longevity", label: "Longevity", tools: [["life_table", "Life table: you 45 and your wife 43, planning to age 95"], ["life_table", "1 in 4 chance one of you lives past 95"]],
      finding: { headline: "Plan to age 95.", details: ["Your wife is younger, so the plan runs until she is 93.", "Half of couples like you have one partner alive at 90."], numbers: { horizon_age: 95 } }, t: [1840, 600, 210] },
    { agent: "family", label: "Family", tools: [["family_costs", "Family costs: 3 children at home until 2038"], ["family_costs", "College for 3: about $450,000 in today's dollars"], ["pet_costs", "Pet costs: 2 dogs, about $3,200 a year"]],
      finding: { headline: "Children and dogs add about $58,000 a year until 2038.", details: ["College is the biggest cost, from 2031 to 2042.", "Costs drop sharply once the youngest leaves home."], numbers: { family_per_year: 58000 } }, t: [2320, 600, 340] },
    { agent: "tax", label: "Tax", tools: [["tax", "Tax: federal and Connecticut rates on $380,000 pay"], ["tax", "Withdrawal order: taxable, then pre-tax, then Roth"]],
      finding: { headline: "In retirement you keep about 84 cents of each dollar you draw.", details: ["Connecticut taxes most withdrawals; Social Security is mostly exempt at your income.", "Drawing taxable savings first keeps early tax low."], numbers: { effective_rate: 0.16 } }, t: [2050, 1200, 280] },
    { agent: "research", label: "Research", tools: [["sources", "Sources: 2 passages found on 401(k) and spousal IRA limits"]],
      finding: { headline: "Two official sources back the rules we use.", details: ["IRS limits for 2026 and the spousal IRA rule."], numbers: { passages: 2 } }, t: [1200, 400, 150] },
    { agent: "markets", label: "Markets", tools: [["simulate", "Simulation: 2,000 market tests, 65% stocks now, 45% at 62"], ["simulate", `Money lasts to 95 in ${plan.needs.paid_of_100} of 100 market tests for the needs`], ["simulate", `Most spending that lasts in 90 of 100 market tests: $${plan.wants.per_year.toLocaleString("en-US")} a year`]],
      finding: { headline: `Your needs are paid in ${plan.needs.paid_of_100} of 100 market tests.`, details: ["Bad markets in the first five years of retirement are the main risk.", "Your savings peak near $4.1 million at 62 in a middle market test."], numbers: { paid_of_100: plan.needs.paid_of_100 } }, t: [2610, 1800, 390] },
    { agent: "adviser", label: "Lead adviser", tools: [["neighbors", "Similar households: 12 found; 1 step borrowed"], ["number_check", "Number check: all 11 figures match the tools"]],
      finding: { headline: "You can retire at 62 if you keep saving and protect the one income.", details: ["Three steps matter most: spousal IRA, 529 plans and term life insurance."], numbers: {} }, t: [6180, 2400, 910] },
  ];
  const ev: [number, PlanEvent][] = [];
  let tokens = 0, usd = 0;
  const budget = 0.05;
  const done = (r: (typeof runs)[number]): [number, PlanEvent][] => {
    const c = cost(r.t[0], r.t[1], r.t[2]);
    tokens += r.t[0] + r.t[2];
    usd = Math.round((usd + c) * 1e6) / 1e6;
    return [[700, { type: "agent_done", agent: r.agent, finding: r.finding, tokens: { input: r.t[0], cached: r.t[1], output: r.t[2] }, cost_usd: c }],
      [80, { type: "cost", total_tokens: tokens, total_usd: usd, budget_usd: budget }]];
  };
  const [lon, fam, tax, res, mkt, adv] = runs;
  const say = (from: string, to: string, message: string): [number, PlanEvent] => [260, { type: "handoff", from, to, message }];
  ev.push([500, { type: "cost", total_tokens: 0, total_usd: 0, budget_usd: budget }]);
  ev.push(say("adviser", "longevity", "How long should this plan last for a couple aged 45 and 43?"),
    say("adviser", "family", "Three children, two dogs and a stay-at-home wife in Connecticut."),
    say("adviser", "tax", "Work out what you keep of each dollar in Connecticut."),
    say("adviser", "research", "Find official sources for the retirement account limits."));
  for (const r of [lon, fam, tax, res]) ev.push([350, { type: "agent_start", agent: r.agent, label: r.label }]);
  for (let i = 0; i < 3; i++) for (const r of [lon, fam, tax, res]) if (r.tools[i]) ev.push([450, { type: "tool", agent: r.agent, tool: r.tools[i][0], summary: r.tools[i][1] }]);
  ev.push(...done(lon), ...done(tax), ...done(fam), ...done(res));
  ev.push(say("longevity", "markets", "Plan to age 95."), say("family", "markets", "Children and dogs add about $58,000 a year until 2038."),
    say("tax", "markets", "You keep about 84 cents of each dollar you draw."), say("adviser", "markets", "How much can you spend each year and still last to 95?"));
  for (const r of [mkt, adv]) {
    if (r === adv) ev.push(say("markets", "adviser", `Your needs are paid in ${plan.needs.paid_of_100} of 100 market tests.`), say("family", "adviser", "Three family moments to show."), say("research", "adviser", "2 official passages to cite."));
    ev.push([500, { type: "agent_start", agent: r.agent, label: r.label }]);
    for (const [tool, summary] of r.tools) ev.push([700, { type: "tool", agent: r.agent, tool, summary }]);
    ev.push(...done(r));
  }
  ev.push([500, { type: "plan", plan }], [100, { type: "done" }]);
  return ev;
}

// ---- Ask or try a What If ----

export function mockAsk(q: string, profile: Profile, _plan: Plan): AskResponse {
  const t = q.toLowerCase();
  const tokens = { input: 3100, cached: 1800, output: 260 };
  const c = cost(3100, 1800, 260);
  if (/hide|hiding|medicaid|\bssi\b|ignore (all |previous|the )/i.test(t))
    return { kind: "refused", text: "I can't help with that. Moving money to qualify for Medicaid or SSI can break the law. An elder-law attorney can explain the legal choices.", citations: [], tokens, cost_usd: c };
  const retire = t.match(/retire (?:at|by) (\d{2})/);
  if (retire || /another (child|kid|baby)|get a (dog|cat)|another (dog|cat)/.test(t)) {
    const p: Profile = structuredClone(profile);
    let text = "";
    if (retire) { p.retire_age = Number(retire[1]); text = `Retiring at ${retire[1]} instead of ${profile.retire_age ?? 62} means fewer years of saving and more years of drawing.`; }
    if (/another (child|kid|baby)/.test(t)) { p.children = [...(p.children ?? []), { age: 0, college: true }]; text = "A fourth child adds about $310,000 through college, and pushes costs into your sixties."; }
    if (/(dog|cat)/.test(t) && !retire && !/child|kid|baby/.test(t)) {
      const kind = /cat/.test(t) ? "cat" : "dog";
      const pets = (p.pets ?? []).map((x) => ({ ...x }));
      const hit = pets.find((x) => x.kind === kind);
      if (hit) hit.count += 1; else pets.push({ kind, count: 1 });
      p.pets = pets;
      text = `One more ${kind} costs about $1,600 a year for some 12 years. It barely moves the plan.`;
    }
    const plan = examplePlan(p);
    if (/(dog|cat)/.test(t) && !retire) { plan.wants.per_year -= 2000; plan.wants.line = plan.wants.line.replace(/\$[\d,]+/, `$${plan.wants.per_year.toLocaleString("en-US")}`); }
    if (/another (child|kid|baby)/.test(t)) plan.family_moments = [...plan.family_moments, "2044: your fourth child starts college"];
    return { kind: "whatif", text, citations: [], plan, tokens, cost_usd: c };
  }
  if (/401|ira|contribut|limit/.test(t))
    return { kind: "answer", text: "For 2026 you can put up to $24,500 into a 401(k), plus $8,000 more from age 50. A spousal IRA allows $7,500 for your wife even though she has no pay.", citations: [{ title: "IRS: 401(k) limit increases to $24,500 for 2026", url: "https://www.irs.gov/newsroom/401k-limit-increases-to-24500-for-2026-ira-limit-increases-to-7500" }, { title: "IRS: Spousal IRA rules (Publication 590-A)", url: "https://www.irs.gov/publications/p590a" }], tokens, cost_usd: c };
  if (/social security|claim/.test(t))
    return { kind: "answer", text: "Waiting from 67 to 70 raises your Social Security check by 8% for each year. Your wife can get up to half of your amount at her full retirement age.", citations: [{ title: "SSA: Delayed retirement credits", url: "https://www.ssa.gov/benefits/retirement/planner/delayret.html" }, { title: "SSA: Benefits for spouses", url: "https://www.ssa.gov/benefits/retirement/planner/applying7.html" }], tokens, cost_usd: c };
  return { kind: "answer", text: "I don't have a source for that, so I won't guess. Try asking about retirement accounts, Social Security or taxes, or try a What If.", citations: [], tokens, cost_usd: c };
}
