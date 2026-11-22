"""The household profile and the API shapes (see PLAN.md, API contract)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Source = Literal["you said", "estimate", "assumed", "default"]
HISTORY_ITEMS, HISTORY_CHARS = 8, 400       # the last 4 turns (person and app), each cut short


class Savings(BaseModel):
    pretax: float = 0
    roth: float = 0
    taxable: float = 0
    cash: float = 0

    @property
    def total(self) -> float:
        return self.pretax + self.roth + self.taxable + self.cash


class Home(BaseModel):
    owns: bool | None = None
    value: float = 0
    mortgage_balance: float = 0
    mortgage_payment: float = 0      # per month
    rent: float = 0                  # per month
    mortgage_rate: float | None = None   # a year, as a fraction (0.05); assumed 5% when not given


class Child(BaseModel):
    age: int | None = None
    college: bool = True
    college_type: Literal["public", "private", "none"] | None = None   # none means no college
    college_share: float = 1.0       # share of the cost the family pays (0 to 1)
    college_source: Literal["you said", "estimate"] | None = None   # per child: the person's own choice, or the typical one proposed
    sex: Literal["female", "male"] | None = None   # only when the person said "girl of 8", "my son (9)": it picks the child a college choice is for


class Pet(BaseModel):
    kind: Literal["dog", "cat", "other"] = "dog"
    count: int = 1


Health = Literal["excellent", "good", "fair", "poor"]


class Debt(BaseModel):
    kind: Literal["student", "car", "credit_card", "other"] = "other"
    balance: float = 0
    rate: float | None = None             # a year, as a fraction (0.06); assumed by kind when not given
    monthly_payment: float | None = None  # assumed from a standard payoff term when not given
    assumed: list[str] = Field(default_factory=list)   # which of rate / monthly_payment were assumed


class Pension(BaseModel):
    who: Literal["you", "partner"] = "you"
    per_year: float = 0
    start_age: int | None = None          # the pensioner's own age; assumed 65
    inflation_adjusted: bool | None = None  # assumed no
    survivor_share: float | None = None   # share paid to a surviving partner (0 to 1); assumed 0.5
    assumed: list[str] = Field(default_factory=list)


class Saving(BaseModel):
    """What the household puts away now. Money amounts are per year unless the name says month."""
    contrib_you: float | None = None          # 401(k)/IRA contributions a year
    contrib_partner: float | None = None
    match_rate: float | None = None           # employer match, e.g. 0.5 = 50 cents per dollar
    match_cap: float | None = None            # up to this share of pay, e.g. 0.06
    other_per_month: float | None = None      # other saving a month

    def given(self) -> bool:
        return any(v is not None for v in (self.contrib_you, self.contrib_partner, self.other_per_month))


class Insurance(BaseModel):
    life_kind: Literal["none", "term", "whole"] | None = None
    life_face: float | None = None
    life_premium: float | None = None         # a year
    disability: bool | None = None
    ltc: bool | None = None                   # long-term care cover


class BigCost(BaseModel):
    label: str = "Big cost"
    amount: float = 0
    year: int | None = None


class Goals(BaseModel):
    legacy: float | None = None               # money to leave behind, in today's dollars
    big_costs: list[BigCost] = Field(default_factory=list)
    parents_per_year: float | None = None
    parents_years: int | None = None


class PartTime(BaseModel):
    per_year: float = 0
    until_age: int | None = None              # your age; assumed 70


class Inheritance(BaseModel):
    amount: float = 0
    year: int | None = None
    count: bool = False                       # counted in the plan only when the person says to
    gift: bool = False                        # a gift, not an inheritance (same rule: information only)


class Budget(BaseModel):
    """Current spending split, per month."""
    housing: float | None = None      # rent or mortgage and upkeep
    food: float | None = None
    transport: float | None = None
    health: float | None = None
    childcare: float | None = None
    debt: float | None = None         # debt payments
    other: float | None = None

    def total_month(self) -> float:
        return sum(v or 0 for v in self.model_dump().values())

    def given(self) -> bool:
        return any(v is not None for v in self.model_dump().values())


class Profile(BaseModel):
    age: int | None = None
    partner_age: int | None = None
    has_partner: bool = False
    state: str | None = None
    retire_age: int | None = None
    pay_per_year: float | None = None
    partner_pay_per_year: float | None = None
    savings: Savings = Field(default_factory=Savings)
    savings_known: bool = False
    home: Home = Field(default_factory=Home)
    children: list[Child] = Field(default_factory=list)
    pets: list[Pet] = Field(default_factory=list)
    spending_per_year: float | None = None
    social_security_per_year: float | None = None
    risk: Literal["careful", "balanced", "growth"] | None = None
    # extras (round-trip through the frontend; not required by the contract)
    job: str | None = None
    partner_job: str | None = None
    sex: Literal["male", "female"] | None = None
    partner_sex: Literal["male", "female"] | None = None
    save_rate: float | None = None           # share of pay saved each year before retirement
    sources: dict[str, Source] = Field(default_factory=dict)
    notes: dict[str, str] = Field(default_factory=dict)
    asking: str | None = None                # the key the last question asked about
    # optional detail (every one has a typical default; see household.complete)
    health: Health | None = None
    partner_health: Health | None = None
    partner_retire_age: int | None = None
    debts: list[Debt] = Field(default_factory=list)
    pensions: list[Pension] = Field(default_factory=list)
    saving: Saving = Field(default_factory=Saving)
    insurance: Insurance = Field(default_factory=Insurance)
    goals: Goals = Field(default_factory=Goals)
    emergency_months: float | None = None    # months of spending held in cash now
    part_time: PartTime | None = None        # work in retirement
    inheritance: Inheritance | None = None
    spending_now_per_year: float | None = None   # what the household spends now
    budget: Budget = Field(default_factory=Budget)
    retire_spend_ratio: float | None = None  # retirement spending as a share of spending now (assumed 0.8)
    offered: list[str] = Field(default_factory=list)   # optional groups already offered or answered
    claim_age: int | None = None             # Social Security claiming age (62 to 70); default follows the retirement age
    partner_claim_age: int | None = None     # your partner's claiming age (62 to 70); default: yours if given, else their own retirement age rule
    # intake chat memory (the server is stateless, so it travels with the profile): the last turns, and how many turns so far
    history: list[str] = Field(default_factory=list)
    turns: int = 0

    @field_validator("history", mode="before")
    @classmethod
    def _short_history(cls, v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        return [str(x)[:HISTORY_CHARS] for x in v if isinstance(x, str)][-HISTORY_ITEMS:]

    @field_validator("turns", mode="before")
    @classmethod
    def _turns(cls, v: Any) -> int:
        try:
            return max(0, min(1000, int(v)))
        except (TypeError, ValueError):
            return 0

    def household_pay(self) -> float:
        return (self.pay_per_year or 0) + (self.partner_pay_per_year or 0)

    def adults(self) -> int:
        return 2 if (self.has_partner or self.partner_age) else 1


class FieldOut(BaseModel):
    key: str
    label: str
    value: Any
    source: Source
    note: str = ""
    display: str = ""
    section: str = ""
    editable: dict[str, Any] | None = None   # how the panel may edit it: {kind: split|money|number|choice|text|group|percent, ask, ...}


class Question(BaseModel):
    text: str
    quick_answers: list[str] = Field(default_factory=list)


class IntakeRequest(BaseModel):
    text: str = Field("", max_length=4000)
    profile_so_far: dict[str, Any] | None = None
    reset: list[str] = Field(default_factory=list, max_length=10)   # sections to clear first, or "all"


class IntakeResponse(BaseModel):
    profile: dict[str, Any]
    fields: list[FieldOut]
    missing: list[str]
    question: Question | None
    reply: str
    ready: bool = False
    sections_status: list[dict[str, str]] = Field(default_factory=list)   # [{section, status: "added" | "default"}]
    tokens: dict[str, int] = Field(default_factory=lambda: {"input": 0, "cached": 0, "output": 0})
    cost_usd: float = 0.0


class PlanRequest(BaseModel):
    profile: dict[str, Any]


class AskRequest(BaseModel):
    question: str = Field(..., max_length=2000)
    profile: dict[str, Any]
    plan: dict[str, Any] | None = None
    pending_change: dict[str, Any] | None = None   # echoed from the last "change" reply (a confirm or a targeted question)


# ------------------------------------------------------------------ the plan's analysis (app/analysis.py), today's dollars
class AnalysisLevel(BaseModel):
    of_100: int
    per_year: float


class HowSure(BaseModel):
    levels: list[AnalysisLevel]                 # the most you could spend a year and have it last in 50, 75, 90, 95 of 100
    curve_spend: list[float]                    # yearly spending ...
    curve_lasts_of_100: list[int]               # ... and how many scenarios of 100 last at it
    goal_per_year: float
    goal_lasts_of_100: int
    count_on_per_year: float
    basics_per_year: float
    basics_paid_of_100: int
    line: str


class AnalysisRow(BaseModel):
    key: str
    title: str
    what: str = ""                              # a stress in one plain sentence
    count_on_per_year: float
    basics_paid_of_100: int
    count_on_change: float                      # against the plan
    basics_change: int
    note: str = ""
    # a stress played out at the plan's own count-on spending (today's dollars); stress rows only
    label: str = ""                             # the risk in a few words
    kind: str = ""                              # basics, fails, holds or small: which story the sentence tells
    short: str = ""                             # for "holds": the part particular to this risk (after the group's lead line)
    sentence: str = ""                          # the risk as one plain consequence, built in code from these figures
    count_on_drop: float = 0.0
    basics_at_risk: bool = False
    stress_years: int | None = None
    to_age: int | None = None
    survivor_spend_pct: int | None = None
    plan_spend_per_year: float = 0.0
    worst_runs_out_age: int | None = None       # worst 1 in 10 scenarios: the age savings run out
    worst_years_short: int = 0
    worst_gap_per_year: float = 0.0
    typical_runs_out_age: int | None = None     # the middle scenario
    typical_years_short: int = 0
    typical_gap_per_year: float = 0.0
    typical_income_per_year: float = 0.0        # income without savings in those years
    typical_income_from: str = ""
    typical_lasts: bool = True


class AnalysisRows(BaseModel):
    rows: list[AnalysisRow]
    line: str
    lead: str = ""                              # when the shown risks all "hold": one shared lead line, then each risk's short line
    top: list[str] = []                         # keys of the (at most 3) risks that hurt most, worst first


class AnalysisSeries(BaseModel):
    key: str
    label: str
    values: list[float]


class Sources(BaseModel):
    ages: list[int]
    spending: list[float]                       # each year's spending (the costs chart's total while at work)
    series: list[AnalysisSeries]                # pay, Social Security (each person), pensions, annuity, savings, not covered
    surplus: list[float]                        # income above spending in a year (saved)
    line: str
    goal_per_year: float


class Analysis(BaseModel):
    paths: int
    seed: int
    plan_count_on_per_year: float
    plan_basics_paid_of_100: int
    how_sure: HowSure
    stresses: AnalysisRows
    levers: AnalysisRows
    sources: Sources
    seconds: float
