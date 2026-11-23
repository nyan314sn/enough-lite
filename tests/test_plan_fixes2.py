"""Plan fixes (2026-11-21, second pass from the 300-household eval): no duplicate action, the debt or match is not crowded
out by the goal action, a stated Social Security figure does not lose delayed credits when you retire later, and the
"Worth checking" notes (term life, disability, income annuity)."""
from __future__ import annotations

import asyncio
import copy

from app import household, pipeline
from app.agents import adviser
from app.agents.base import RunCtx
from app.schemas import Profile


def plan_for(profile):
    p = pipeline.prepare(profile)
    ctx = RunCtx(profile=p, use_ai=False)
    return asyncio.run(pipeline.run_plan(ctx)), ctx


class FakeAction:
    def __init__(self, title, why):
        self.title, self.why = title, why

    def model_dump(self):
        return {"title": self.title, "why": self.why}


GOAL = {"key": "goal", "title": "Set your spending goal nearer the safe level", "why": "gap"}
DEBT = {"key": "debt", "title": "Pay off your high-rate debt first", "why": "debt why"}
MATCH = {"key": "match", "title": "Save enough to get the full employer match", "why": "match why"}
EMERG = {"key": "emergency", "title": "Build an emergency fund of three months", "why": "emergency why"}


# ------------------------------------------------------------------ 1. no duplicate action
def test_template_goal_action_does_not_repeat_the_goal_lever():
    written = [FakeAction("Set your spending goal nearer the safe level of $30,000.", "Because."),
               FakeAction("Keep about 50% of savings in stocks now", "Mix.")]
    out = adviser.order_actions([GOAL, EMERG], written)
    titles = [a["title"] for a in out]
    assert len(out) == 3
    assert sum("spending goal" in t.lower() for t in titles) == 1
    assert len({t.lower() for t in titles}) == 3


# ------------------------------------------------------------------ 2. debt and match are not crowded out
def test_goal_debt_and_match_all_show_when_all_exist():
    written = [FakeAction("Set your spending goal nearer the safe level of $30,000.", "x"), FakeAction("Check your plan once a year", "y")]
    out = adviser.order_actions([GOAL, MATCH, DEBT, EMERG], written)
    assert [a["title"] for a in out] == [GOAL["title"], MATCH["title"], DEBT["title"]]


def test_a_debt_behind_two_other_levers_still_gets_a_slot():
    out = adviser.order_actions([GOAL, EMERG, DEBT], [FakeAction("Check your plan once a year", "y")])
    titles = [a["title"] for a in out]
    assert DEBT["title"] in titles and GOAL["title"] in titles


DEBTOR = {"age": 45, "has_partner": False, "state": "OH", "retire_age": 65, "pay_per_year": 60000, "savings_known": True,
          "savings": {"pretax": 20000, "roth": 0, "taxable": 0, "cash": 5000}, "home": {"owns": False, "rent": 1400},
          "social_security_per_year": 24000, "spending_per_year": 60000, "spending_now_per_year": 52000, "risk": "balanced",
          "debts": [{"kind": "credit_card", "balance": 9000, "rate": 0.24, "monthly_payment": 250}],
          "saving": {"contrib_you": 1800, "match_rate": 0.5, "match_cap": 0.06}}


def test_end_to_end_plan_names_the_debt_and_match_and_the_goal_once():
    plan, _ = plan_for(DEBTOR)
    titles = [a["title"].lower() for a in plan["actions"]]
    assert len(titles) == 3 and len(set(titles)) == 3
    assert sum("spending goal" in t for t in titles) <= 1
    assert any("pay off your $9,000 card debt" in t for t in titles)      # round 4: the debt and its figure
    assert any("match" in t for t in titles)


# ------------------------------------------------------------------ 3. retiring later does not lower the basics score
S033 = {"age": 57, "partner_age": 61, "has_partner": True, "state": "IL", "retire_age": 68, "pay_per_year": 39500, "partner_pay_per_year": 18500,
        "savings": {"pretax": 13600, "roth": 200, "taxable": 0, "cash": 8300}, "savings_known": True,
        "home": {"owns": True, "value": 455000, "mortgage_balance": 0, "mortgage_payment": 0, "rent": 0}, "pets": [{"kind": "dog", "count": 1}],
        "spending_per_year": 30000, "social_security_per_year": 30900, "risk": "balanced", "sex": "female", "health": "good",
        "partner_sex": "male", "partner_health": "fair", "partner_retire_age": 64,
        "debts": [{"kind": "credit_card", "balance": 2900, "rate": 0.2577, "monthly_payment": 90}],
        "saving": {"contrib_you": 0, "contrib_partner": 3500}, "insurance": {"life_kind": "none"}, "spending_now_per_year": 41500}


def test_stated_social_security_gains_delayed_credits_when_retiring_later():
    early = Profile.model_validate(S033)
    p68 = household.complete(early)
    p70 = household.complete(early.model_copy(update={"retire_age": 70}))
    a = household.stated_ss_at_claim(p68, household.claim_age(p68))
    b = household.stated_ss_at_claim(p70, household.claim_age(p70))
    assert b > a > 30900
    # a claiming age the person named keeps their figure as given
    named = household.complete(early.model_copy(update={"claim_age": 68}))
    assert household.stated_ss_at_claim(named, 68) == 30900


def test_retiring_two_years_later_does_not_cut_basics_paid():
    base, _ = plan_for(S033)
    later, _ = plan_for({**copy.deepcopy(S033), "retire_age": 70})
    assert later["needs"]["paid_of_100"] >= base["needs"]["paid_of_100"] - 3
    assert later["wants"]["per_year"] >= base["wants"]["per_year"] * 0.97


# ------------------------------------------------------------------ 5. worth checking
FAMILY = {"age": 38, "partner_age": 36, "has_partner": True, "state": "OH", "retire_age": 65, "pay_per_year": 90000, "partner_pay_per_year": 0,
          "savings_known": True, "savings": {"pretax": 60000, "roth": 0, "taxable": 10000, "cash": 15000}, "home": {"owns": False, "rent": 1800},
          "children": [{"age": 5}, {"age": 8}], "social_security_per_year": 30000, "spending_per_year": 60000, "spending_now_per_year": 70000,
          "risk": "balanced", "insurance": {"life_kind": "none", "disability": False}}
SINGLE_SAVER = {"age": 66, "has_partner": False, "state": "OH", "retire_age": 66, "pay_per_year": 0, "savings_known": True,
                "savings": {"pretax": 500000, "roth": 0, "taxable": 100000, "cash": 20000}, "home": {"owns": False, "rent": 1500},
                "social_security_per_year": 28000, "spending_per_year": 55000, "spending_now_per_year": 55000, "risk": "balanced"}


def kinds(plan):
    return {w["kind"] for w in plan["worth_checking"]}


def test_dependants_without_cover_get_term_life_and_disability_notes():
    plan, _ = plan_for(FAMILY)
    assert {"term_life", "disability"} <= kinds(plan)
    text = " ".join(w["why"] for w in plan["worth_checking"]).lower()
    assert "not a recommendation" in text and "not priced" in text and "$" not in text


def test_cover_already_held_removes_the_notes():
    held = copy.deepcopy(FAMILY)
    held["insurance"] = {"life_kind": "term", "life_face": 900000, "disability": True}
    assert kinds(plan_for(held)[0]) == set()


def test_single_saver_who_may_outlive_savings_gets_the_annuity_note_as_information():
    plan, ctx = plan_for(SINGLE_SAVER)
    m = ctx.results["markets"]
    assert ((m.get("low_at_horizon") or 0) <= 0 or m["goal_lasts_of_100"] < 100) == ("income_annuity" in kinds(plan))
    for w in plan["worth_checking"]:
        if w["kind"] == "income_annuity":
            assert "information only" in w["why"]


def test_annuity_note_not_for_couples_or_small_savings():
    couple = {**copy.deepcopy(SINGLE_SAVER), "has_partner": True, "partner_age": 64}
    assert "income_annuity" not in kinds(plan_for(couple)[0])
    poor = copy.deepcopy(SINGLE_SAVER)
    poor["savings"] = {"pretax": 20000, "roth": 0, "taxable": 0, "cash": 5000}
    assert "income_annuity" not in kinds(plan_for(poor)[0])
