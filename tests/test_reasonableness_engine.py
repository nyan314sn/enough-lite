"""Regression tests from the reasonableness audit (eval/reasonableness/REPORT.md). Tools only, no model."""
import asyncio
import json
from pathlib import Path

import pytest

from app import pipeline
from app.agents.base import RunCtx
from app.tools import costs, simulate

CASES = Path(__file__).resolve().parents[1] / "eval" / "cases.jsonl"


def case(case_id: str) -> dict:
    for line in CASES.read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        if c["id"] == case_id:
            return c["profile"]
    raise KeyError(case_id)


def plan_of(profile, fixed=None):
    ctx = RunCtx(profile=profile, use_ai=False, options=False, fixed=fixed)
    plan = asyncio.run(pipeline.run_plan(ctx))
    return plan, ctx


def whatif(profile: dict, text: str):
    """The plan chat's own What If path (pipeline.ask without the model): parse, apply, run with the kept strategy."""
    base = pipeline._clean_profile_text(pipeline.prepare(profile))
    old_plan, old_ctx = plan_of(base)
    ch = pipeline.parse_whatif(text, base)
    newp, notes = pipeline.apply_whatif(base, ch)
    assert not notes.get("_say"), notes.get("_say")
    plan, ctx = plan_of(newp, fixed=pipeline.kept_for(ch, old_ctx))
    return old_plan, plan, newp, notes


WORKER = {"age": 45, "has_partner": False, "state": "OH", "retire_age": 65, "pay_per_year": 120000,
          "savings": {"pretax": 150000, "roth": 0, "taxable": 30000, "cash": 40000}, "savings_known": True,
          "home": {"owns": False, "rent": 1500}, "spending_per_year": 60000, "spending_now_per_year": 80000,
          "social_security_per_year": 30000, "saving": {"contrib_you": 12000},
          "debts": [{"kind": "credit_card", "balance": 20000, "rate": 0.22, "monthly_payment": 600}],
          "sources": {"spending_now_per_year": "you said", "spending_per_year": "you said", "debts": "you said"}}


def test_savings_chart_never_shows_a_negative_balance():
    # spending above take-home pay with nothing saved: the yearly saving is below zero. The years it cannot be paid are
    # counted as short before retirement; the chart and the middle path never show savings below zero
    r = simulate.simulate(age=58, retire_age=66, horizon_age=95, savings=0.0, save_per_year=-5000.0, spend_per_year=20000.0,
                          ss_per_year=18000.0, ss_age=66, save_by_year=[-5000.0] * 8)
    assert min(r["chart"]["median"]) >= 0 and min(r["chart"]["low"]) >= 0
    assert r["median_at_retirement"] >= 0
    assert r["short_before_retirement_of_100"] == 100


def test_paying_off_a_debt_at_work_saves_the_payments_that_stop():
    # the payments were part of spending now: once the debt is paid from savings, spending now falls by them (spread over
    # the working years they would still have run) and the plan saves them. Before, savings fell and nothing was saved.
    base = pipeline.prepare(WORKER)
    newp, notes = pipeline.apply_whatif(base, {"pay_off": ["credit_card"]})
    paid = sum(costs.debt_schedule(base, 20)["per_year"][:20])
    assert newp.spending_now_per_year == pytest.approx(80000 - paid / 20, abs=1)
    assert pipeline.SAVED_WHILE_WORKING in notes["after"]
    assert newp.savings.total == pytest.approx(base.savings.total - 20000, abs=1)


def test_paying_off_a_debt_once_retired_leaves_spending_alone():
    retired = {**WORKER, "age": 68, "retire_age": 65, "pay_per_year": 0, "spending_now_per_year": 60000}
    base = pipeline.prepare(retired)
    newp, notes = pipeline.apply_whatif(base, {"pay_off": ["credit_card"]})
    assert newp.spending_now_per_year == base.spending_now_per_year
    assert pipeline.SAVED_WHILE_WORKING not in notes["after"]


def test_paying_off_the_mortgage_at_work_cuts_spending_now_by_the_payment():
    owner = {**WORKER, "debts": [], "home": {"owns": True, "value": 500000, "mortgage_balance": 150000, "mortgage_payment": 1500,
                                            "mortgage_rate": 0.04},
             "savings": {"pretax": 150000, "roth": 0, "taxable": 100000, "cash": 60000}}
    base = pipeline.prepare(owner)
    mort = costs.mortgage_end(base)
    newp, notes = pipeline.apply_whatif(base, {"pay_off": ["mortgage"]})
    years = min(mort["years_left"], 20)
    assert newp.spending_now_per_year == pytest.approx(80000 - mort["drop_per_year"] * years / 20, abs=1)
    assert notes["after"] == pipeline.SAVED_WHILE_WORKING


def test_paying_off_high_rate_card_debt_never_lowers_what_you_can_count_on():
    old, new, _, _ = whatif(WORKER, "What if I pay off my credit card")
    assert new["wants"]["per_year"] >= old["wants"]["per_year"] - 300
    assert new["needs"]["paid_of_100"] >= old["needs"]["paid_of_100"] - 1


def test_a_change_that_breaks_a_safe_plan_gets_a_fresh_strategy():
    # a child added to a plan whose basics were safe: the plan's own strategy (Social Security at 70) left the basics
    # paid in 13 of 100 and $6,300 to count on; a fresh pick on the changed numbers gives about $26,100. The What If now
    # tests both and keeps the better, so it matches a plan built fresh from the changed answers.
    old, new, newp, _ = whatif(case("N01_self_employed_sched_c"), "What if we have another child")
    assert old["needs"]["paid_of_100"] >= 90
    fresh, _ = plan_of(pipeline.prepare(newp.model_dump()))
    assert new["wants"]["per_year"] == pytest.approx(fresh["wants"]["per_year"], abs=500)
    assert new["wants"]["per_year"] > 20000


COUPLE_GAP = {"age": 49, "partner_age": 50, "has_partner": True, "state": "OR", "retire_age": 70, "partner_retire_age": 65,
              "pay_per_year": 48000, "partner_pay_per_year": 37000,
              "savings": {"pretax": 40000, "roth": 0, "taxable": 0, "cash": 14600}, "savings_known": True,
              "home": {"owns": False, "rent": 1800}, "spending_per_year": 48000, "spending_now_per_year": 99400,
              "social_security_per_year": 40000,
              "sources": {"spending_now_per_year": "you said", "spending_per_year": "you said", "partner_retire_age": "you said"}}


def test_spending_above_pay_stays_a_gap_after_a_partner_stops_work():
    # the household spends more than its take-home pay. Before, the years after the partner stopped work left the gap
    # out (the yearly saving jumped from below zero to the contributions alone), so stopping work made the plan better
    p = pipeline.prepare(COUPLE_GAP)
    c = costs.contributions(p)
    gap = costs.unspent_pay(p, c)
    assert gap < 0
    assert costs.unspent_pay(p, c, partner_working=False) == gap
    stopped = pipeline.prepare({**COUPLE_GAP, "partner_retire_age": 50})
    assert costs.saving_now(stopped)["unspent_pay_per_year"] == gap


def test_a_partner_who_stops_work_never_makes_the_plan_better():
    old, new, _, _ = whatif(COUPLE_GAP, "What if my partner stops working")
    assert new["wants"]["per_year"] <= old["wants"]["per_year"] + 300
    assert new["needs"]["paid_of_100"] <= old["needs"]["paid_of_100"] + 1


def test_a_young_partner_who_stops_work_still_makes_a_valid_profile():
    # "what if my partner stops working" sets the partner's retirement age to their age now; a partner under 30 made a
    # profile that a fresh plan refused ("Some of your answers look wrong")
    young = {**COUPLE_GAP, "age": 27, "partner_age": 25, "retire_age": 65, "partner_retire_age": 65, "spending_now_per_year": 60000}
    base = pipeline.prepare(young)
    ch = pipeline.parse_whatif("What if my partner stops working", base)
    newp, notes = pipeline.apply_whatif(base, ch)
    assert newp.partner_retire_age == 25 and not notes.get("_say")
    assert pipeline.prepare(newp.model_dump()).partner_retire_age == 25


def test_when_nothing_lasts_social_security_starts_as_soon_as_it_can():
    # retired at 61 with $2,200 saved: no level of spending lasts on any strategy (the years before Social Security have
    # no income), so every candidate ties at zero. The plan claimed at 67 by the fixed order; it now claims at 62
    plan, _ = plan_of(pipeline.prepare(case("S089")))
    assert plan["wants"]["per_year"] == 0
    assert plan["claim_age"] == 62


@pytest.mark.parametrize("case_id", ["S092", "S083"])
def test_paying_off_the_mortgage_at_work_keeps_the_basics_it_already_had(case_id):
    # the budget's housing held the mortgage payment. The basics left the mortgage out (it ends before retiring, or is a
    # cost of its own), but once it was paid off they took the whole budget housing back in: S092's basics went from
    # paid in 100 of 100 to 0, S083's from 90 to 33. (S083 still loses some: its $825 payment is below the typical owner
    # costs, so the plan frees nothing when it ends, and the payoff only spends savings; see REPORT.md.)
    old, new, _, _ = whatif(case(case_id), "What if I pay off the mortgage")
    assert new["needs"]["basics_per_year"] <= old["needs"]["basics_per_year"]
    if case_id == "S092":
        assert new["needs"]["paid_of_100"] >= old["needs"]["paid_of_100"] - 5
