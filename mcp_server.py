"""Enough as an MCP server: the app's checked retirement numbers, for any AI assistant.

No AI or model call happens in here. Every number comes from the same plain-Python tools and the same engine and
seed (409) the web app uses. Nothing is stored or logged: each call runs in memory and is forgotten.

Run (stdio, for Claude Desktop, Claude Code and other clients):   python mcp_server.py
Run (streamable HTTP, optional):                                   python mcp_server.py --http 8765
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Annotated, Any, Literal

# the planning engine runs with no model: no run log, no key needed
os.environ.setdefault("ENOUGH_RUN_LOG", "0")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastmcp import FastMCP  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from app import pipeline, safety  # noqa: E402
from app.agents.parser import STATE_NAME  # noqa: E402
from app.agents.research import NO_SOURCE  # noqa: E402
from app.schemas import Child, Debt, Pet, Profile  # noqa: E402
from app.tools import costs, estimates, lifetable, sources, tax  # noqa: E402
from app.tools import family_costs as family_tools  # noqa: E402

NOT_ADVICE = ("Planning figures from public rules and fixed market assumptions, not a forecast and not financial, "
              "tax or legal advice. A licensed adviser can check them against your full picture.")
FORBIDDEN_PORTS = {8000, 8010, 8020}
MONEY_MAX = pipeline.MONEY_MAX
Money = Annotated[float, Field(ge=0, le=MONEY_MAX)]
Age = Annotated[int, Field(ge=18, le=100)]

mcp = FastMCP(
    "enough",
    instructions=(
        "Enough checks retirement numbers with plain code and cited public rules; no model guesses inside. "
        "Use plan_check for 'what can this household count on', and the other tools for single questions. "
        "Quote the figures as returned, say which inputs were assumed, and pass on the not-financial-advice line. "
        "Do not use these tools to hide money to qualify for Medicaid or SSI, or to pick single stocks or crypto; "
        "they refuse those requests."))


# ------------------------------------------------------------------ inputs
class ChildIn(BaseModel):
    age: int = Field(ge=0, le=60, description="The child's age now, in years.")
    college_type: Literal["public", "private", "none"] | None = Field(
        None, description="Planned college: public (in-state), private, or none. Leave out for the typical choice (public).")
    college_share: float = Field(1.0, ge=0, le=1, description="Share of the college cost the family pays, 0 to 1.")


class PetIn(BaseModel):
    kind: Literal["dog", "cat", "other"] = "dog"
    count: int = Field(1, ge=0, le=50)


class DebtIn(BaseModel):
    kind: Literal["student", "car", "credit_card", "other"] = "other"
    balance: Money = 0
    rate: float | None = Field(None, ge=0, le=1, description="Yearly rate as a fraction (0.06 is 6%). Left out: a typical rate for the kind.")
    monthly_payment: Money | None = Field(None, description="Payment a month. Left out: a standard payoff term.")


class HomeIn(BaseModel):
    owns: bool | None = Field(None, description="True if the household owns its home, False if it rents.")
    value: Money = Field(0, description="Home value, dollars.")
    mortgage_balance: Money = 0
    mortgage_payment_per_month: Money = 0
    rent_per_month: Money = 0
    mortgage_rate: float | None = Field(None, ge=0, le=0.3, description="Yearly mortgage rate as a fraction (0.05 is 5%).")


class Household(BaseModel):
    """What the person told you. Every field except age is optional; missing ones are estimated and listed back as assumed."""
    age: Age = Field(description="The person's age now (18 to 100).")
    partner_age: Annotated[int, Field(ge=18, le=110)] | None = Field(None, description="Partner's age, if there is a partner.")
    state: str | None = Field(None, description="US state, two-letter code (OH) or name (Ohio). Used for tax and costs.")
    retire_age: Annotated[int, Field(ge=30, le=100)] | None = Field(
        None, description="Age the person plans to stop work. Left out: 65. Social Security claiming never goes past 70.")
    pay_per_year: Money | None = Field(None, description="The person's pay now, dollars a year, before tax. 0 if not working.")
    partner_pay_per_year: Money | None = Field(None, description="Partner's pay, dollars a year, before tax.")
    savings_total: Money | None = Field(
        None, description="All retirement and other savings, dollars. If no split is given, the app's split is assumed: 60% pre-tax, 10% Roth, 20% taxable, 10% cash.")
    savings_pretax: Money | None = Field(None, description="401(k), traditional IRA. Overrides the total split when any of the four is given.")
    savings_roth: Money | None = None
    savings_taxable: Money | None = Field(None, description="Brokerage and other taxable accounts.")
    savings_cash: Money | None = None
    spending_per_year: Money | None = Field(None, description="Spending goal in retirement, dollars a year in today's dollars. Left out: an estimate from pay.")
    social_security_per_year: Money | None = Field(
        None, description="Social Security benefit the person expects, dollars a year at age 67 (as on ssa.gov). Left out: estimated from pay.")
    claim_age: Annotated[int, Field(ge=62, le=70)] | None = Field(None, description="Age to start Social Security, 62 to 70.")
    risk: Literal["careful", "balanced", "growth"] | None = Field(None, description="Investing style. Left out: balanced.")
    health: Literal["excellent", "good", "fair", "poor"] | None = Field(None, description="Self-rated health; changes the planning age. Left out: good.")
    sex: Literal["male", "female"] | None = Field(None, description="Used only for the life table.")
    partner_sex: Literal["male", "female"] | None = Field(None, description="Partner's sex, for the life table only.")
    partner_health: Literal["excellent", "good", "fair", "poor"] | None = Field(None, description="Partner's self-rated health. Left out: good.")
    partner_retire_age: Annotated[int, Field(ge=18, le=100)] | None = Field(None, description="Age the partner stops work. Left out: assumed.")
    spending_now_per_year: Money | None = Field(None, description="What the household spends now, dollars a year. Left out: estimated from pay.")
    contribution_per_year: Money | None = Field(None, description="The person's own 401(k)/IRA saving, dollars a year.")
    partner_contribution_per_year: Money | None = Field(None, description="Partner's 401(k)/IRA saving, dollars a year.")
    employer_match_rate: Annotated[float, Field(ge=0, le=2)] | None = Field(None, description="Employer match per dollar saved (0.5 is 50 cents).")
    employer_match_cap: Annotated[float, Field(ge=0, le=1)] | None = Field(None, description="The match applies up to this share of pay (0.06 is 6%).")
    children: list[ChildIn] = Field(default_factory=list, max_length=20)
    pets: list[PetIn] = Field(default_factory=list, max_length=20)
    home: HomeIn | None = None
    debts: list[DebtIn] = Field(default_factory=list, max_length=20)
    note: str | None = Field(
        None, max_length=2000,
        description="Optional free text the person added. It is only screened for requests the tools refuse; it does not change the numbers.")


# ------------------------------------------------------------------ outputs
class Assumed(BaseModel):
    field: str
    source: str = Field(description="'assumed' or 'estimate' (worked out from other answers) or 'default'.")
    note: str = ""


class PlanCheck(BaseModel):
    status: Literal["ok", "refused", "emergency"]
    message: str = Field("", description="Set when status is not ok: say this to the person.")
    headline: str | None = None
    count_on_per_year: float | None = Field(None, description="Spending the plan can pay in 90 of 100 market scenarios, dollars a year, today's dollars.")
    count_on_confidence: str | None = None
    basics_per_year: float | None = Field(None, description="Housing, food, transport and health a year.")
    basics_paid_of_100: int | None = Field(None, description="In how many of 100 scenarios the basics are paid. Under 90 means the basics are not safe.")
    verdict: Literal["works", "close", "below_goal", "falls_short"] | None = None
    verdict_words: str | None = None
    spending_goal_per_year: float | None = None
    goal_line: str | None = Field(None, description="How often the spending goal lasts, in the app's words.")
    short_of_goal_per_year: float | None = Field(None, description="Goal minus what can be counted on; 0 when the goal is covered.")
    retire_age: int | None = None
    planning_age: int | None = Field(None, description="The plan runs to this age: the age at which about 1 in 4 chance remains that anyone in the household is alive.")
    social_security_per_year: float | None = Field(None, description="Social Security the plan uses, dollars a year, at the claiming age.")
    social_security_claim_age: int | None = None
    assumptions: list[str] = Field(default_factory=list, description="The main assumptions of the plan, in the app's words.")
    assumed_inputs: list[Assumed] = Field(default_factory=list, description="Inputs the person did not give, and how each was filled.")
    starting_points: list[dict[str, Any]] = Field(default_factory=list, description="When the goal does not work on their numbers: options the app offers to try.")
    notes: list[str] = Field(default_factory=list)
    engine: str | None = None
    not_financial_advice: str = NOT_ADVICE


class SocialSecurityOut(BaseModel):
    status: Literal["ok", "refused", "emergency"] = "ok"
    claim_age: int
    per_year: float = Field(description="Benefit a year at the claiming age, today's dollars.")
    per_year_at_full_age: float = Field(description="Benefit a year at full retirement age (67).")
    years_of_work_counted: int
    by_claim_age: dict[str, float] = Field(description="Benefit a year at each claiming age, 62 to 70.")
    spousal_per_year_at_full_age: float | None = Field(None, description="Largest spousal top-up for a partner with little or no pay, if a partner pay was given.")
    basis: str
    not_financial_advice: str = NOT_ADVICE


class TaxOut(BaseModel):
    status: Literal["ok", "refused", "emergency"] = "ok"
    working: dict[str, Any] = Field(description="Tax on pay now: federal, state, payroll, child credit, after-tax pay, effective rate.")
    retired: dict[str, Any] | None = Field(None, description="Tax in a typical retirement year, when retired spending was given.")
    limits_2027: dict[str, Any]
    basis: str
    not_financial_advice: str = NOT_ADVICE


class LifeOut(BaseModel):
    status: Literal["ok", "refused", "emergency"] = "ok"
    planning_age: int
    chance_alive_at_planning_age: float = Field(description="Chance (0 to 1) that anyone in the household is alive at the planning age.")
    life_expectancy_you: float
    life_expectancy_partner: float | None = None
    chance_someone_reaches_90: float
    chance_someone_reaches_100: float
    basis: str
    not_financial_advice: str = NOT_ADVICE


class FamilyYear(BaseModel):
    year: int
    your_age: int
    total: float
    children_at_home: float
    college: float
    pets: float


class FamilyOut(BaseModel):
    status: Literal["ok", "refused", "emergency"] = "ok"
    by_year: list[FamilyYear]
    this_year: float
    total: float
    college_total: float
    ends_at_age: int | None
    moments: list[str]
    basis: str
    not_financial_advice: str = NOT_ADVICE


class Passage(BaseModel):
    id: str
    title: str
    url: str
    text: str
    score: float


class RulesOut(BaseModel):
    status: Literal["ok", "refused", "emergency"] = "ok"
    message: str = ""
    passages: list[Passage] = Field(default_factory=list)
    source: str = Field("", description="'no source' when nothing matched; otherwise the titles of the passages.")


# ------------------------------------------------------------------ safety and validation
def screen(*texts: str | None) -> tuple[str, str] | None:
    """The app's refusals, applied to free text: (status, message) when a request must be refused, else None."""
    for t in texts:
        if not t:
            continue
        if safety.is_emergency(t):
            return "emergency", safety.EMERGENCY_REPLY
        if safety.is_medicaid_hiding(t):
            return "refused", safety.MEDICAID_REPLY
        if safety.is_single_investment(t):
            return "refused", safety.STOCK_REPLY
        if safety.is_refusable(t):
            return "refused", safety.REFUSE_REPLY
    return None


def state_code(state: str | None) -> str | None:
    if state is None or not state.strip():
        return None
    s = state.strip()
    if s.upper() in pipeline.STATE_CODES:
        return s.upper()
    for code, name in STATE_NAME.items():
        if s.lower() == name.lower():
            return code
    raise ToolError(f"Unknown state '{state[:40]}'. Use a two-letter code such as OH, or a full state name.")


def health_mult(h: str | None) -> float:
    return lifetable.health_mult(h)


# ------------------------------------------------------------------ plan_check
def to_profile(h: Household) -> Profile:
    d: dict[str, Any] = {"age": h.age, "state": state_code(h.state)}
    said: list[str] = ["age"] + (["state"] if d["state"] else [])
    for src, dst in (("partner_age", "partner_age"), ("retire_age", "retire_age"), ("pay_per_year", "pay_per_year"),
                     ("partner_pay_per_year", "partner_pay_per_year"), ("spending_per_year", "spending_per_year"),
                     ("social_security_per_year", "social_security_per_year"), ("claim_age", "claim_age"),
                     ("risk", "risk"), ("health", "health"), ("sex", "sex"), ("partner_sex", "partner_sex"),
                     ("partner_health", "partner_health"), ("partner_retire_age", "partner_retire_age"),
                     ("spending_now_per_year", "spending_now_per_year")):
        v = getattr(h, src)
        if v is not None:
            d[dst] = v
            said.append(dst)
    if h.partner_age:
        d["has_partner"] = True
    parts = {k: getattr(h, "savings_" + k) for k in ("pretax", "roth", "taxable", "cash")}
    notes: dict[str, str] = {}
    sources_: dict[str, str] = {}
    if any(v is not None for v in parts.values()):
        d["savings"] = {k: (v or 0) for k, v in parts.items()}
        d["savings_known"] = True
        said.append("savings")
    elif h.savings_total is not None:
        t = h.savings_total
        d["savings"] = {"pretax": t * 0.6, "roth": t * 0.1, "taxable": t * 0.2, "cash": t * 0.1}
        d["savings_known"] = True
        sources_["savings"] = "assumed"
        notes["savings"] = "You gave the total. The split is assumed: 60% pre-tax, 10% Roth, 20% taxable and 10% cash."
    if any(v is not None for v in (h.contribution_per_year, h.partner_contribution_per_year, h.employer_match_rate, h.employer_match_cap)):
        d["saving"] = {"contrib_you": h.contribution_per_year, "contrib_partner": h.partner_contribution_per_year,
                       "match_rate": h.employer_match_rate, "match_cap": h.employer_match_cap}
        said.append("saving")
    if h.children:
        d["children"] = [Child(age=c.age, college=c.college_type != "none", college_type=c.college_type,
                               college_share=c.college_share, college_source="you said" if c.college_type else None)
                         for c in h.children]
        said.append("children")
    if h.pets:
        d["pets"] = [Pet(kind=x.kind, count=x.count) for x in h.pets]
        said.append("pets")
    if h.home is not None:
        hm = h.home
        d["home"] = {"owns": hm.owns, "value": hm.value, "mortgage_balance": hm.mortgage_balance,
                     "mortgage_payment": hm.mortgage_payment_per_month, "rent": hm.rent_per_month, "mortgage_rate": hm.mortgage_rate}
        said.append("home")
    if h.debts:
        d["debts"] = [Debt(kind=x.kind, balance=x.balance, rate=x.rate, monthly_payment=x.monthly_payment) for x in h.debts]
        said.append("debts")
    for k in said:
        sources_.setdefault(k, "you said")
    d["sources"], d["notes"] = sources_, notes
    return Profile.model_validate(d)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
async def plan_check(household: Household) -> PlanCheck:
    """Check what a household can count on in retirement, with the same engine and seed as the Enough app.

    Give what the person told you (age is the only required field). Missing inputs are estimated like the app does
    and listed in assumed_inputs; tell the person which ones were assumed. Returns the spending the plan can pay in
    90 of 100 market scenarios (count_on_per_year), how many of 100 scenarios pay the basics, a verdict, the gap to
    the spending goal, the planning age, the Social Security used and the main assumptions. Figures are in today's
    dollars. Quote the numbers as returned; do not recompute or round them differently.
    """
    hit = screen(household.note)
    if hit:
        return PlanCheck(status=hit[0], message=hit[1])  # type: ignore[arg-type]
    try:
        before = to_profile(household)
        prepared = pipeline.prepare(before)
    except pipeline.PlanError as e:
        raise ToolError(str(e)) from None
    plan, _ctx = await pipeline.tools_only_plan(prepared)
    given = {k for k, v in before.sources.items() if v == "you said"}
    assumed = [Assumed(field=k, source=v, note=prepared.notes.get(k, ""))
               for k, v in prepared.sources.items() if v != "you said" and k not in given]
    goal = float(plan.get("spending_goal") or 0)
    count_on = float(plan["count_on_per_year"])
    notes = []
    if prepared.retire_age and prepared.retire_age > 70:
        notes.append("Retirement is set past 70. Social Security claiming stops at 70, so waiting longer adds no benefit.")
    if plan.get("already_retired"):
        notes.append("The person is already at or past the retirement age, so the plan starts drawing on savings now.")
    analysis = plan.get("analysis") or {}
    return PlanCheck(
        status="ok",
        headline=plan.get("headline"),
        count_on_per_year=count_on,
        count_on_confidence="90 of 100 scenarios",
        basics_per_year=plan["needs"]["basics_per_year"],
        basics_paid_of_100=plan["needs"]["paid_of_100"],
        verdict=plan["verdict"],
        verdict_words=plan["verdict_words"],
        spending_goal_per_year=goal,
        goal_line=(plan.get("wishes") or {}).get("line"),
        short_of_goal_per_year=round(max(0.0, goal - count_on)),
        retire_age=plan.get("retire_age"),
        planning_age=plan.get("horizon_age"),
        social_security_per_year=plan.get("social_security_per_year"),
        social_security_claim_age=plan.get("claim_age"),
        assumptions=list(plan.get("assumptions") or []),
        assumed_inputs=assumed,
        starting_points=list(plan.get("starting_points") or []),
        notes=notes,
        engine=f"Enough engine, {analysis.get('paths', 2000)} market paths, seed {analysis.get('seed', 409)}; no AI model used.",
    )


# ------------------------------------------------------------------ single-question tools
@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
def social_security_estimate(
    pay_per_year: Annotated[float, Field(ge=0, le=MONEY_MAX, description="Pay now, dollars a year, as a stand-in for a career of earnings.")],
    claim_age: Annotated[int, Field(ge=62, le=70, description="Age to start the benefit, 62 to 70.")] = 67,
    retire_age: Annotated[int | None, Field(ge=30, le=100, description="Age work stops. Years of work run from about 22 to this age, at most 35. Left out: a full 35-year career.")] = None,
    partner_pay_per_year: Annotated[float | None, Field(ge=0, le=MONEY_MAX, description="Partner's pay; adds the spousal top-up figure.")] = None,
) -> SocialSecurityOut:
    """Estimate a Social Security retirement benefit, in today's dollars a year, from pay and claiming age.

    A rough estimate from the current benefit formula, not the person's own SSA statement (ssa.gov/myaccount has that).
    Returns the benefit at the chosen claiming age, at full age (67) and at every age from 62 to 70.
    """
    years = estimates.FULL_CAREER_YEARS if retire_age is None else estimates.career_years(retire_age)
    res = estimates.social_security(pay_per_year, claim_age, years)
    table = {str(a): estimates.social_security(pay_per_year, a, years)["per_year"] for a in range(62, 71)}
    spousal = None
    if partner_pay_per_year is not None:
        spousal = estimates.spouse_benefit(res["at_full_age_per_year"])
    return SocialSecurityOut(
        claim_age=res["claim_age"], per_year=res["per_year"], per_year_at_full_age=res["at_full_age_per_year"],
        years_of_work_counted=years, by_claim_age=table, spousal_per_year_at_full_age=spousal,
        basis="Current SSA benefit formula applied to today's pay; today's dollars; fewer than 35 years of work are averaged over 35.")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
def tax_estimate(
    state: Annotated[str, Field(description="US state, two-letter code or name.")],
    pay_per_year: Annotated[float, Field(ge=0, le=MONEY_MAX, description="Pay a year before tax (the person's, or the household's if partner pay is not given).")],
    partner_pay_per_year: Annotated[float, Field(ge=0, le=MONEY_MAX)] = 0,
    married: Annotated[bool, Field(description="Married filing jointly. False means single, or head of household when there are children.")] = False,
    children_under_17: Annotated[int, Field(ge=0, le=20)] = 0,
    pretax_contributions: Annotated[float, Field(ge=0, le=MONEY_MAX, description="401(k)-type saving a year; it comes off taxable pay.")] = 0,
    retired_spending_per_year: Annotated[float | None, Field(ge=0, le=MONEY_MAX, description="Also estimate a typical retirement year with this spending.")] = None,
    social_security_per_year: Annotated[float, Field(ge=0, le=MONEY_MAX, description="Social Security in that retirement year.")] = 0,
    pretax_savings: Annotated[float, Field(ge=0, le=MONEY_MAX, description="Savings mix for the retirement year (decides how much withdrawals are taxed).")] = 0,
    roth_savings: Annotated[float, Field(ge=0, le=MONEY_MAX)] = 0,
    taxable_savings: Annotated[float, Field(ge=0, le=MONEY_MAX)] = 0,
    cash_savings: Annotated[float, Field(ge=0, le=MONEY_MAX)] = 0,
    over_65_adults: Annotated[int, Field(ge=0, le=2, description="Adults aged 65 or more in the retirement year.")] = 2,
) -> TaxOut:
    """Estimate yearly tax with the app's 2027 federal brackets, standard deduction, state rates and payroll tax.

    Always returns tax on pay. When retired_spending_per_year is given it also returns a typical retirement year:
    tax on Social Security, and the extra tax on withdrawals. No itemizing and no credits beyond the child tax credit.
    """
    st = state_code(state)
    wk = tax.working_years(pay_per_year, partner_pay_per_year, st, married, children_under_17, pretax_contributions)
    ret = None
    if retired_spending_per_year is not None:
        savings = {"pretax": pretax_savings, "roth": roth_savings, "taxable": taxable_savings, "cash": cash_savings}
        ret = tax.retirement_years(retired_spending_per_year, social_security_per_year, savings, st, married,
                                   over_65_adults)
    return TaxOut(working=wk, retired=ret, limits_2027=tax.limits_2027(),
                  basis="2027 federal brackets and standard deduction; state effective rates; 85% of Social Security counted as taxable (an upper bound).")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
def life_expectancy(
    age: Age,
    sex: Annotated[Literal["male", "female"] | None, Field(description="Used for the life table. Left out: both sexes averaged.")] = None,
    health: Annotated[Literal["excellent", "good", "fair", "poor"] | None, Field(description="Self-rated health. Left out: good.")] = None,
    partner_age: Annotated[int | None, Field(ge=18, le=110)] = None,
    partner_sex: Literal["male", "female"] | None = None,
    partner_health: Literal["excellent", "good", "fair", "poor"] | None = None,
) -> LifeOut:
    """The age to plan to (the age at which about a 1 in 4 chance remains that anyone in the household is alive),
    the chance someone is alive then, life expectancy, and the chance someone reaches 90 and 100. Uses the US life
    table (SOA 2024) with a simple health adjustment. For a couple, either person being alive counts."""
    h = lifetable.horizon(age, sex, partner_age, partner_sex, mult=health_mult(health), partner_mult=health_mult(partner_health))
    return LifeOut(
        planning_age=h["horizon_age"], chance_alive_at_planning_age=h["chance_alive_at_horizon"],
        life_expectancy_you=h["life_expectancy_you"], life_expectancy_partner=h.get("life_expectancy_partner"),
        chance_someone_reaches_90=h["chance_someone_reaches_90"], chance_someone_reaches_100=h["chance_someone_reaches_100"],
        basis="US life table (SOA 2024) with improvement; health adjusts death rates (excellent x0.8, fair x1.4, poor x2.0). People with more money tend to live longer than the table says.")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
def family_costs(
    age: Annotated[int, Field(ge=18, le=100, description="Your age now; year 0 is this year.")],
    children: Annotated[list[ChildIn], Field(max_length=20, description="Children with ages and college plans.")] = [],  # noqa: B006
    pets: Annotated[list[PetIn], Field(max_length=20)] = [],  # noqa: B006
    partner_age: Annotated[int | None, Field(ge=18, le=110)] = None,
) -> FamilyOut:
    """Yearly cost of raising children (to 18), their college (public in-state or private, ages 18 to 21, family
    share) and pets, from this year on, in today's dollars, with moments such as when the youngest leaves home."""
    kids = [{"age": c.age, "college": c.college_type != "none", "college_type": c.college_type, "college_share": c.college_share}
            for c in children]
    fp = family_tools.family_path(age, kids, [{"kind": x.kind, "count": x.count} for x in pets], partner_age)
    year0 = costs.this_year()
    rows = [FamilyYear(year=year0 + t, your_age=age + t, total=fp["per_year"][t], children_at_home=fp["children_at_home_per_year"][t],
                       college=fp["college_per_year"][t], pets=fp["pets_per_year"][t]) for t in range(len(fp["per_year"]))]
    return FamilyOut(by_year=rows, this_year=fp["this_year"], total=fp["total"], college_total=fp["college_total"],
                     ends_at_age=fp["ends_at_age"], moments=fp["moments"],
                     basis="Typical US costs (USDA child-rearing, College Board), today's dollars; pets use typical yearly cost and remaining lifespan.")


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
def search_rules(
    question: Annotated[str, Field(min_length=3, max_length=500, description="A plain question about retirement accounts, Social Security, Medicare, taxes or benefit rules.")],
) -> RulesOut:
    """Find the cited public-source passages (IRS, SSA, Medicare and similar) that answer a rules question.

    Returns up to 3 passages with source title and link, or source 'no source' when nothing matches; in that case
    do not guess an answer from these tools. Refuses requests to hide assets for Medicaid or SSI, and single-stock or
    crypto picks."""
    hit = screen(question)
    if hit:
        return RulesOut(status=hit[0], message=hit[1])  # type: ignore[arg-type]
    found = sources.search(question, k=3)
    if not found:
        return RulesOut(message=NO_SOURCE, source="no source")
    return RulesOut(passages=[Passage(id=f["id"], title=f["title"], url=f["url"], text=f["text"], score=f["score"]) for f in found],
                    source="; ".join(f["title"] for f in found))


# ------------------------------------------------------------------ run
def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if "--http" in argv:
        i = argv.index("--http")
        try:
            port = int(argv[i + 1])
        except (IndexError, ValueError):
            sys.exit("Usage: python mcp_server.py [--http PORT]")
        if port in FORBIDDEN_PORTS or not (1024 <= port <= 65535):
            sys.exit(f"Port {port} is not allowed. Pick another port (not 8000, 8010 or 8020).")
        mcp.run(transport="streamable-http", host="127.0.0.1", port=port, show_banner=False)
    else:
        mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
