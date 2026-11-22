"""Plan and engine fixes (2026-11-21, from the 300-household eval and the UX review): realistic wants, monotone results,
claiming ages, verdict, the 7% debt line, stable strategy choice, no late match advice, market-shock What Ifs, plan
invariants, action order and the run deadline."""
from __future__ import annotations

import asyncio
import copy
import time

import pytest

from app import config, pipeline
from app.agents import adviser
from app.agents.base import RunCtx, run_model
from app.tools import costs, neighbors, tax

NOISE = 0.03     # Monte Carlo noise allowed on "must not fall"


def plan_for(profile, shock=None):
    p = pipeline.prepare(profile)
    ctx = RunCtx(profile=p, use_ai=False, shock=shock)
    plan = asyncio.run(pipeline.run_plan(ctx))
    return plan, ctx


def count_on(profile):
    return plan_for(profile)[0]["wants"]["per_year"]


# S111 from the eval: a retired couple, 63 and 64, renting in Utah, with a small debt and a budget
S111 = {"age": 63, "partner_age": 64, "has_partner": True, "state": "UT", "retire_age": 63, "pay_per_year": 0, "partner_pay_per_year": 0,
        "savings": {"pretax": 106100, "roth": 70200, "taxable": 69700, "cash": 27600}, "savings_known": True,
        "home": {"owns": False, "rent": 980}, "spending_per_year": 42000, "social_security_per_year": 38000, "risk": "balanced",
        "partner_retire_age": 64, "debts": [{"kind": "credit_card", "balance": 1900, "rate": 0.2233, "monthly_payment": 55}],
        "budget": {"housing": 1155, "transport": 1030, "food": 395, "health": 305, "other": 485, "debt": 55},
        "spending_now_per_year": 41100}
WORKER = {"age": 50, "has_partner": False, "state": "OH", "retire_age": 63, "pay_per_year": 90000, "savings_known": True,
          "savings": {"pretax": 200000, "roth": 20000, "taxable": 20000, "cash": 15000}, "home": {"owns": False, "rent": 1300},
          "social_security_per_year": 26000, "spending_per_year": 50000, "spending_now_per_year": 60000, "risk": "balanced"}


def with_(base, **kw):
    p = copy.deepcopy(base)
    p.update(kw)
    return p


# ------------------------------------------------------------------ 1. wants is not floored at zero by mistake
def test_tax_rate_on_withdrawals_stays_sensible_when_income_covers_spending():
    r = tax.retirement_years(14000, 23700, {"pretax": 5000, "cash": 1300}, "MA", False, 1)
    assert r["effective_rate_on_withdrawals"] < 0.5          # it was 1.0, which made every withdrawal cost 20 times over
    r = tax.retirement_years(42000, 38000, {"pretax": 100000, "roth": 70000, "taxable": 70000}, "UT", True, 1, other_income=24000)
    assert r["effective_rate_on_withdrawals"] < 0.5 and r["other_income_tax_rate"] < 0.3


def test_basics_use_the_budget_and_never_exceed_the_goal():
    plan, ctx = plan_for(S111)
    b = ctx.results["family"]["basics"]
    assert b["housing"] == 1155 * 12 and b["food"] == 395 * 12
    assert plan["needs"]["basics_per_year"] <= 42000
    low_goal = with_(S111, spending_per_year=14000)
    assert plan_for(low_goal)[0]["needs"]["basics_per_year"] <= 14000


def test_unspent_pay_is_saved():
    p = pipeline.prepare(with_(WORKER, saving={"contrib_you": 0}))
    assert costs.unspent_pay(p) > 0


def test_count_on_is_zero_only_when_nothing_can_be_counted_on():
    assert count_on(S111) > 30000
    nothing = with_(WORKER, savings={"pretax": 0, "roth": 0, "taxable": 0, "cash": 0}, social_security_per_year=0, pay_per_year=0,
                    retire_age=50, spending_now_per_year=None)
    assert count_on(nothing) == 0


# ------------------------------------------------------------------ 2. monotone: more never lowers what you can count on
@pytest.mark.parametrize("start", [65, 63, 70])
def test_a_pension_never_lowers_count_on(start):
    base = count_on(S111)
    more = count_on(with_(S111, pensions=[{"who": "you", "per_year": 24000, "start_age": start}]))
    assert more >= base * (1 - NOISE)
    assert more > base                      # $24,000 a year more income must show


def test_more_savings_more_pay_and_later_retirement_never_lower_count_on():
    base = count_on(WORKER)
    sv = dict(WORKER["savings"])
    sv["pretax"] *= 1.2
    assert count_on(with_(WORKER, savings=sv)) >= base * (1 - NOISE)
    assert count_on(with_(WORKER, pay_per_year=110000)) >= base * (1 - NOISE)
    assert count_on(with_(WORKER, retire_age=65)) >= base * (1 - NOISE)
    assert count_on(with_(WORKER, social_security_per_year=30000)) >= base * (1 - NOISE)


# ------------------------------------------------------------------ 3. claiming ages
def test_claim_ages_are_62_to_70_and_the_partners_own():
    old = with_(S111, age=77, partner_age=73, retire_age=77, partner_retire_age=73)
    plan = plan_for(old)[0]
    assert plan["claim_age"] == 70 and plan["partner_claim_age"] == 70 and plan["already_claiming"]
    p = pipeline.prepare(with_(S111, age=60, partner_age=66, retire_age=67, pay_per_year=50000))
    you, partner = adviser.claim_ages(p, 67)
    assert you == 67 and 62 <= partner <= 70 and partner >= 66


# ------------------------------------------------------------------ 4. the verdict agrees with the needs
def test_verdict_falls_short_when_basics_are_not_safe():
    m = {"spending_goal_per_year": 14000, "safe_spending_per_year": 19000, "basics_paid_of_100": 40}
    assert adviser.verdict(m) == "falls_short"
    m["basics_paid_of_100"] = 95
    assert adviser.verdict(m) == "works"


# ------------------------------------------------------------------ 5. the 7% line
def test_high_rate_line_is_7_percent_and_set_in_config():
    assert config.HIGH_RATE_DEBT == 0.07 and costs.HIGH_RATE == 0.07
    plan = plan_for(with_(WORKER, debts=[{"kind": "car", "balance": 30000, "rate": 0.07}]))[0]
    assert any(x["key"] == "debt" for x in plan["levers"])


# ------------------------------------------------------------------ 6. stable strategy choice
def test_pick_breaks_ties_within_noise_the_same_way():
    a = [{"source": "S9-full", "basics_paid_of_100": 100, "safe_spending_per_year": 50300},
         {"source": "rule", "basics_paid_of_100": 100, "safe_spending_per_year": 50000},
         {"source": "S2-full", "basics_paid_of_100": 100, "safe_spending_per_year": 50100}]
    assert neighbors.pick(a)["source"] == "rule"
    assert neighbors.pick(list(reversed(a)))["source"] == "rule"
    a[0]["safe_spending_per_year"] = 60000                  # a clear winner still wins
    assert neighbors.pick(a)["source"] == "S9-full"


# ------------------------------------------------------------------ 7. no match advice when work is about to stop
def test_no_match_lever_with_under_two_working_years():
    late = with_(WORKER, age=75, retire_age=76, saving={"contrib_you": 0, "match_rate": 0.5, "match_cap": 0.06})
    plan = plan_for(late)[0]
    assert not any(x["key"] == "match" for x in plan["levers"])
    assert not any("match" in a["title"].lower() for a in plan["actions"])
    early = with_(WORKER, saving={"contrib_you": 0, "match_rate": 0.5, "match_cap": 0.06})
    assert any(x["key"] == "match" for x in plan_for(early)[0]["levers"])


# ------------------------------------------------------------------ 8. market-shock What Ifs
@pytest.mark.parametrize("q,kind", [("Markets fall 30%", "fall"), ("what if stocks crash 40% when I retire", "fall"),
                                    ("What if inflation stays high for a decade?", "inflation"),
                                    ("what if I have a bad first decade", "bad_decade")])
def test_shock_whatifs_parse(q, kind):
    ch = pipeline.parse_whatif(q, pipeline.prepare(WORKER))
    assert ch["shock"]["kind"] == kind
    if "40%" in q:
        assert ch["shock"]["size"] == 0.40 and ch["shock"]["when"] == "retirement"


def test_markets_fall_chip_returns_a_whatif_that_lowers_the_figures():
    r = asyncio.run(pipeline.ask("Markets fall 30%", WORKER, "t-shock", use_ai=False))
    assert r["kind"] == "whatif" and "fall 30%" in r["text"]
    base = count_on(WORKER)
    for s in ({"kind": "fall", "size": 0.3, "when": "now"}, {"kind": "fall", "size": 0.3, "when": "retirement"},
              {"kind": "inflation"}, {"kind": "bad_decade"}):
        assert plan_for(WORKER, shock=s)[0]["wants"]["per_year"] < base


# ------------------------------------------------------------------ 10. plan invariants
@pytest.mark.parametrize("profile", [S111, WORKER, with_(WORKER, retire_age=60, spending_per_year=90000)])
def test_plan_invariants(profile):
    plan, ctx = plan_for(profile)
    m = ctx.results["markets"]
    w = plan["wants"]["per_year"]
    assert w >= 0 and w == plan["count_on_per_year"] == m["safe_spending_per_year"]
    assert f"${w:,.0f}" in plan["headline"]                         # the headline quotes wants
    assert plan["wants"]["above_basics_per_year"] == max(0, round(w - plan["needs"]["basics_per_year"], -2))
    if plan["verdict"] != "falls_short":
        assert plan["needs"]["paid_of_100"] >= adviser.BASICS_SAFE


def test_safe_spending_at_least_guaranteed_income_after_tax():
    # retired, Social Security from now: you can always count on at least it after tax
    p = {"age": 68, "has_partner": False, "state": "OH", "retire_age": 68, "pay_per_year": 0, "savings_known": True,
         "savings": {"pretax": 20000, "roth": 0, "taxable": 0, "cash": 5000}, "home": {"owns": True},
         "social_security_per_year": 40000, "spending_per_year": 30000, "risk": "balanced"}
    plan, ctx = plan_for(p)
    after_tax = 40000 * (1 - ctx.results["tax"]["social_security_tax_rate"])
    # less the largest yearly cost on top of spending (health costs rise from 85), which the savings must cover
    gaps = max(ctx.results["family"]["costs"]["extra_by_year"][: plan["horizon_age"] - 68])
    assert after_tax - gaps - 100 <= plan["wants"]["per_year"]
    assert plan["wants"]["per_year"] > 30000 and plan["verdict"] == "works"


def test_whatif_baseline_equals_the_plan():
    base_plan = plan_for(WORKER)[0]
    old_plan, _ = asyncio.run(pipeline.tools_only_plan(pipeline.prepare(WORKER)))
    assert old_plan["wants"]["per_year"] == base_plan["wants"]["per_year"]
    assert old_plan["needs"] == base_plan["needs"]


# ------------------------------------------------------------------ 11. actions by dollar impact
def test_goal_gap_leads_then_debt_and_no_lever_repeats_the_plan():
    p = with_(WORKER, spending_per_year=120000, debts=[{"kind": "credit_card", "balance": 9000, "rate": 0.22}],
              savings={"pretax": 200000, "roth": 0, "taxable": 0, "cash": 1000})
    plan = plan_for(p)[0]
    keys = [x["key"] for x in plan["levers"]]
    assert keys[0] == "goal" and keys.index("debt") < keys.index("emergency")
    assert plan["actions"][0]["title"].startswith("Set your spending goal")
    assert not any(f"retire at {plan['retire_age']}" in (x["whatif_text"] or "").lower() for x in plan["levers"])


# ------------------------------------------------------------------ 12. the run deadline
def test_no_model_call_starts_after_the_deadline(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    ctx = RunCtx(profile=pipeline.prepare(WORKER), use_ai=True, deadline=time.monotonic() - 1)

    def boom():
        raise AssertionError("a model was built after the deadline")
    out, tokens, cost = asyncio.run(run_model(ctx, "tax", boom, "hi", __import__("app.llm", fromlist=["SIMPLE"]).SIMPLE))
    assert out is None and cost == 0 and ctx.ai_down is None
