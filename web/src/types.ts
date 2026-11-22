// The API contract from PLAN.md. The backend (app) and this frontend both build against it.

export type Source = "you said" | "estimate" | "assumed" | "default";
export type Risk = "careful" | "balanced" | "growth";

export interface Profile {
  age?: number | null;
  partner_age?: number | null;
  state?: string | null;
  retire_age?: number | null;
  pay_per_year?: number | null;
  partner_pay_per_year?: number | null;
  savings?: { pretax?: number; roth?: number; taxable?: number; cash?: number } | null;
  home?: { owns?: boolean; value?: number; mortgage_balance?: number; mortgage_payment?: number; rent?: number } | null;
  children?: { age: number; college: boolean; college_type?: "public" | "private" | "none" | null; college_share?: number; college_source?: "you said" | "estimate" | null }[];
  pets?: { kind: "dog" | "cat" | "other"; count: number }[];
  spending_per_year?: number | null;
  social_security_per_year?: number | null;
  risk?: Risk | null;
  [k: string]: unknown;
}

export interface Editable { kind: "split" | "money" | "choice" | "number" | "text" | "group" | "percent" | "college"; child?: number; options?: string[]; ask?: string; min?: number; max?: number; per?: string }
export interface Field { key: string; display?: string | null; label: string; value: unknown; source: Source | string; note?: string | null; section?: string | null; editable?: Editable | null }

export interface IntakeResponse {
  profile: Profile;
  fields: Field[];
  missing: string[];
  question: { text: string; quick_answers: string[] } | null;
  reply: string;
  ready?: boolean;
  /** All nine sections: "default" means nothing there is the person's own yet. Older backends omit it. */
  sections_status?: { section: string; status: "added" | "default" | "estimated"; note?: string }[];
}

export interface Finding { headline: string; details: string[]; numbers: Record<string, unknown> }
export interface Tokens { input: number; cached: number; output: number }

export interface Plan {
  needs: { basics_per_year: number; paid_of_100: number; line: string };
  /** per_year: what you can count on a year (safe in 90 of 100 scenarios), basics included; the headline's figure. */
  wants: { per_year: number; line: string; above_basics_per_year?: number };
  wishes: { line: string };
  actions: { title: string; why: string }[];
  /** Products to look into (term life, disability, income annuity). Information, never priced. Older backends omit it. */
  worth_checking?: { kind: string; title: string; why: string }[];
  family_moments: string[];
  neighbors?: { used: boolean; note: string } | null;
  chart: { ages: number[]; median: number[]; low: number[]; high: number[] };
  /** Optional: what life costs by age, with markers for events. Older backends omit it. */
  costs_by_age?: { ages: number[]; total: number[]; basics: number[]; events: { age: number; label: string; year?: number; change_per_year?: number | null; one_off?: boolean }[]; notes?: string[]; now_per_year?: number; retired_per_year?: number; retire_age?: number; /** Each year's total in parts that add up to it (basics, mortgage, children and college, health, debts, other). */ parts?: CostPart[] } | null;
  /** Actions the person's own answers call for (high-rate debt, the employer match, and so on). */
  levers?: { key: string; title: string; why: string; whatif_text?: string }[] | null;
  /** One plain sentence for the main line of the plan. Older backends omit it. */
  headline?: string | null;
  /** works | close | below_goal (basics safe, goal above what lasts) | falls_short (basics paid in under 90 of 100). */
  verdict?: string | null;
  verdict_words?: string | null;
  already_retired?: boolean | null;
  horizon_text?: string | null;
  /** The plan's assumptions in plain sentences, with the figures used. Older backends omit it. */
  assumptions?: string[] | null;
  /** The plan's own choices a person may change from the plan page (retirement age, Social Security start): each sends `q` to the chat, which confirms first. */
  assumption_changes?: { label: string; q: string }[] | null;
  /** The Social Security figure in the answers beside the one this plan uses. Older backends omit it. */
  ss_basis?: { panel_per_year: number; plan_per_year: number; panel_age: number; claim_age: number | null; partner_claim_age?: number | null; already: boolean; same: boolean } | null;
  /** The yearly saving the plan uses until retirement, in its parts. */
  saving?: { per_year: number; accounts_per_year: number; other_per_year: number; match_per_year: number; unspent_pay_per_year: number; field: string } | null;
  /** When the basics are not safe: changes worked out on the person's numbers, each with its result. */
  starting_points?: { title: string; result: string; whatif_text: string; paid_of_100: number; count_on_per_year: number }[] | null;
  /** The analysis: how sure, what could go wrong, what each choice is worth, where the money comes from. Older backends and market What Ifs omit it. */
  analysis?: Analysis | null;
}

export interface CostPart { key: string; label: string; values: number[] }

/** One row of "What could go wrong" or "What each choice is worth", against the plan. */
export interface AnalysisRow { key: string; title: string; ask?: string; what?: string; note?: string; count_on_per_year: number; basics_paid_of_100: number; count_on_change: number; basics_change: number;
  /** Stress rows only: the risk as one plain sentence built on the server from these figures, today's dollars. */
  label?: string; kind?: string; short?: string; sentence?: string; count_on_drop?: number; basics_at_risk?: boolean; stress_years?: number | null; to_age?: number | null;
  survivor_spend_pct?: number | null; plan_spend_per_year?: number; worst_runs_out_age?: number | null; worst_years_short?: number;
  worst_gap_per_year?: number; typical_runs_out_age?: number | null; typical_years_short?: number; typical_gap_per_year?: number;
  typical_income_per_year?: number; typical_income_from?: string; typical_lasts?: boolean }

/** app/analysis.py, all in today's dollars, on the plan's own scenarios. */
export interface Analysis {
  paths: number;
  seed: number;
  plan_count_on_per_year: number;
  plan_basics_paid_of_100: number;
  how_sure: {
    levels: { of_100: number; per_year: number }[];
    curve_spend: number[];
    curve_lasts_of_100: number[];
    goal_per_year: number;
    goal_lasts_of_100: number;
    count_on_per_year: number;
    basics_per_year: number;
    basics_paid_of_100: number;
    line: string;
  };
  stresses: { rows: AnalysisRow[]; line: string; top?: string[]; lead?: string };
  levers: { rows: AnalysisRow[]; line: string };
  sources: { ages: number[]; spending: number[]; series: { key: string; label: string; values: number[] }[]; surplus: number[]; line: string; goal_per_year: number };
  seconds?: number;
}

export type PlanEvent =
  | { type: "agent_start"; agent: string; label: string }
  | { type: "handoff"; from: string; to: string; message: string }
  | { type: "tool"; agent: string; tool: string; summary: string }
  | { type: "agent_done"; agent: string; finding: Finding; tokens: Tokens; cost_usd: number }
  | { type: "plan"; plan: Plan }
  | { type: "cost"; total_tokens: number; total_usd: number; budget_usd: number }
  | { type: "error"; message: string }
  | { type: "done" };

export interface AskResponse {
  /** True for the fixed 911/988 pointer: shown alone, with no "can't help" heading. */
  emergency?: boolean;
  kind: "answer" | "whatif" | "refused" | "change" | "clarify";
  /** On a change: confirm (a proposal), ask (a targeted question), applied (the plan was rebuilt) or cancelled. */
  status?: "confirm" | "ask" | "applied" | "cancelled" | null;
  /** Send this back with the person's next message. Absent after Yes or No. */
  pending_change?: Record<string, unknown> | null;
  /** Chips to offer under the reply: a confirmation ("Yes, rebuild" / "No") or a follow-up. */
  quick_answers?: string[] | null;
  /** Set on a confirmed change: the corrected answers, with the rebuilt plan in `plan`. */
  profile?: Profile | null;
  text: string;
  citations: { title: string; url: string }[];
  plan?: Plan | null;
  tokens?: Tokens | number | null;
  cost_usd?: number | null;
}

/** One household in the admin list (?admin). `intake` is page 1 as it would stand after a full chat. */
export interface Sample { id: string; tier: "comfortable" | "average" | "struggling"; name: string; description: string; profile: Profile; intake: IntakeResponse }

export interface Health { status: string; provider: string; model: string; ai_available: boolean }

/** Everything the screens need from the server. The real one calls /api; the mock (VITE_MOCK=1) replays fixed answers. */
export interface Api {
  health(): Promise<Health>;
  /** The sample households for the admin screen. */
  samples(): Promise<Sample[]>;
  /** The saved model comparison for the admin page. Rejects when none has been saved. */
  modelCompare?(): Promise<ModelCompare>;
  intake(text: string, profileSoFar: Profile | null, reset?: string[]): Promise<IntakeResponse>;
  reset(): Promise<void>;
  plan(profile: Profile, onEvent: (e: PlanEvent) => void, signal?: AbortSignal): Promise<void>;
  ask(question: string, profile: Profile, plan: Plan, pendingChange?: Record<string, unknown> | null): Promise<AskResponse>;
  /** The session total from /api/costs. Older servers and test doubles may omit it. */
  costs?(): Promise<CostSummary>;
}

/** GET /api/costs for this session: what the AI has cost since the page was opened (or Start over). */
export interface CostSummary {
  total_usd: number;
  total_tokens: number;
  budget?: { run_usd?: number; session_usd?: number; total_usd?: number };
  by_agent?: { agent: string; runs: number; input: number; cached: number; output: number; cost_usd: number }[];
}

/** eval/model_compare/summary.json, as GET /api/admin/model-compare returns it. */
export interface ModelCompare {
  date: string | null;
  models: string[];
  rows: { metric: string; haiku: string; gpt: string; n: string; winner: string; note?: string }[];
  recommendation: string;
  cost_usd: number | null;
  caveats: string[];
}
