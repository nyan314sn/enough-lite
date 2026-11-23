"""Seven backend fixes from the live end-to-end test: saving amounts, lever What Ifs, pending-question routing,
empty reset, the baseline wants, display strings and the empty state."""
import asyncio
import re

import pytest
from fastapi.testclient import TestClient

from app import household, main, pipeline
from app.agents import intake, parser
from app.schemas import Profile
from app.tools import costs


def run(text, profile=None, **kw):
    return asyncio.run(intake.run(text, profile or {}, use_ai=False, **kw))


def completed(**kw):
    base = dict(age=45, state="CT", pay_per_year=100000.0, retire_age=65)
    base.update(kw)
    return household.complete(Profile(**base))


# ------------------------------------------------------------------ 1. saving amounts
@pytest.mark.parametrize("q,extra", [("Save $3,000 more", 3000), ("What if I save $250 more a month?", 3000),
                                      ("what if I save an extra $500 a month", 6000), ("What if I save $1,000 more a month?", 12000)])
def test_dollar_saving_is_extra_saving_not_a_rate(q, extra):
    p = completed()
    ch = pipeline.parse_whatif(q, p)
    assert ch["_extra_per_year"] == extra
    assert abs(ch["save_rate"] - (p.save_rate + extra / 100000)) < 0.001 and ch["save_rate"] < 0.3


def test_percent_saving_is_a_rate():
    p = completed()
    assert pipeline.parse_whatif("what if I save 15%", p) == {"save_rate": 0.15}
    assert pipeline.parse_whatif("what if I save 5% more", p)["save_rate"] == pytest.approx(p.save_rate + 0.05)


def test_dollar_saving_with_given_contributions_goes_to_other_saving():
    p = completed(saving={"contrib_you": 8000.0})
    ch = pipeline.parse_whatif("what if I save $250 more a month", p)
    assert ch["saving_other_per_month"] == 250 and "save_rate" not in ch


# ------------------------------------------------------------------ 2. levers run as What Ifs
LEVER_PROFILE = {"age": 52, "has_partner": True, "partner_age": 50, "state": "OH", "retire_age": 65, "pay_per_year": 120000.0,
                 "partner_pay_per_year": 40000.0, "savings": {"pretax": 150000, "roth": 10000, "taxable": 60000, "cash": 5000}, "savings_known": True,
                 "home": {"owns": True, "value": 500000, "mortgage_balance": 150000, "mortgage_payment": 1800},
                 "children": [{"age": 15}], "debts": [{"kind": "credit_card", "balance": 8000, "rate": 0.22}],
                 "saving": {"match_rate": 0.5, "match_cap": 0.06, "contrib_you": 2000.0},
                 "insurance": {"life_kind": "none", "disability": False, "ltc": False},
                 "sources": {"age": "you said", "pay_per_year": "you said"}}


@pytest.fixture(scope="module")
def lever_plan():
    p = pipeline.prepare(LEVER_PROFILE)
    plan, _ = asyncio.run(pipeline.tools_only_plan(p))
    return plan


def test_every_lever_has_whatif_text_and_runs(lever_plan):
    keys = {x["key"] for x in lever_plan["levers"]}
    assert {"debt", "match", "emergency", "life", "disability", "ltc"} <= keys
    for lv in lever_plan["levers"]:
        assert lv["whatif_text"].startswith("What if")
        r = asyncio.run(pipeline.ask(lv["whatif_text"], LEVER_PROFILE, "t", use_ai=False))
        assert r["kind"] == "whatif", (lv["key"], r.get("text"))
        assert r["plan"] and r["profile"]


def test_pay_off_named_debt_and_emergency_months():
    r = asyncio.run(pipeline.ask("What if I pay off the credit card", LEVER_PROFILE, "t", use_ai=False))
    assert r["kind"] == "whatif" and r["profile"]["debts"] == [] and "credit card" in r["text"]
    assert r["profile"]["savings"]["cash"] == 0           # paid from cash first
    r = asyncio.run(pipeline.ask("emergency fund three months", LEVER_PROFILE, "t", use_ai=False))
    assert r["kind"] == "whatif" and r["profile"]["emergency_months"] >= 3


def test_claim_age_whatif_changes_ss_and_keeps_the_age():
    r = asyncio.run(pipeline.ask("what if I claim Social Security at 70", LEVER_PROFILE, "t", use_ai=False))
    assert r["kind"] == "whatif" and r["profile"]["claim_age"] == 70 and r["plan"]["claim_age"] == 70
    base = pipeline.prepare(LEVER_PROFILE)
    assert r["profile"]["social_security_per_year"] > base.social_security_per_year


def test_downsize_and_match_and_bad_claim_age():
    r = asyncio.run(pipeline.ask("what if we downsize our home", LEVER_PROFILE, "t", use_ai=False))
    assert r["kind"] == "whatif" and r["profile"]["home"]["mortgage_balance"] == 0 and r["profile"]["savings"]["taxable"] > 60000
    r = asyncio.run(pipeline.ask("What if I raise my 401(k) saving to the full match", LEVER_PROFILE, "t", use_ai=False))
    assert r["kind"] == "whatif" and r["profile"]["saving"]["contrib_you"] == 7200
    r = asyncio.run(pipeline.ask("what if I claim Social Security at 75", LEVER_PROFILE, "t", use_ai=False))
    assert r["kind"] == "clarify"


def test_rule_question_about_claiming_is_not_a_whatif():
    assert pipeline.parse_whatif("Can I claim Social Security at 62 while working?", completed()) == {}


# ------------------------------------------------------------------ 3. pending question routing
def to_spending_confirm():
    r = run("I'm a nurse in Ohio, I'm 50", {})
    r = run("About $750k", r.profile)
    return r


def test_debt_typed_at_a_confirm_is_a_new_fact_and_the_confirm_returns():
    r = to_spending_confirm()
    r = run("That's about right", r.profile)
    while r.profile.get("asking") != "confirm_spending_later" and r.question:
        r = run(r.question.quick_answers[0] if r.question.quick_answers else "skip", r.profile)
        if r.profile.get("asking") in ("more", None):
            break
    prof = dict(r.profile, asking="confirm_spending_later", offered=[g for g in r.profile["offered"] if g not in ("confirm_spending_later", "debts")])
    r2 = run("we owe 30k on student loans at 6%", prof)
    assert r2.profile["debts"][0]["balance"] == 30000 and r2.profile["debts"][0]["rate"] == 0.06
    assert "looks off" not in r2.reply and r2.profile.get("retire_spend_ratio") is None
    assert r2.profile["asking"] == "confirm_spending_later" and "Is that about right" in r2.question.text


def test_stray_chip_at_the_pay_question_is_not_an_amount():
    r = run("I'm 50 and live in Ohio", {})
    prof = dict(r.profile, asking="pay_per_year")
    r2 = run("Mostly in a 401(k)", prof)
    assert r2.profile.get("pay_per_year") in (None, 0) or r2.profile["sources"].get("pay_per_year") != "you said"
    assert "401" not in str([f.display for f in r2.fields if f.key == "pay_per_year"])
    assert r2.profile["asking"] == "pay_per_year" and "different question" in r2.reply


def test_product_names_are_never_amounts():
    assert parser.amounts("Mostly in a 401(k)") == [] and parser.amounts("my 403(b) and 457(b)") == []
    assert [a[0] for a in parser.amounts("my 401k has $200k")] == [200000.0]
    assert "pay_per_year" not in parser.parse("401(k)", asking="pay_per_year")


def test_question_midway_is_answered_and_the_question_is_asked_again():
    r = run("I'm 50 and live in Ohio", {})
    before = r.question.text
    r2 = run("why do you need that?", r.profile)
    assert "Your pay sets" in r2.reply and "good question" not in r2.reply and r2.question.text == before


def test_answer_in_range_still_answers():
    r = run("I'm a nurse in Ohio, I'm 50", {})
    r = run("About $750k", r.profile)
    assert r.profile["savings"]["pretax"] > 0 and r.profile["asking"] == "confirm_split"
    r2 = run("That's about right", r.profile)
    assert "confirm_split" in r2.profile["offered"]


# ------------------------------------------------------------------ 4. empty text with reset
def test_empty_text_reset_says_cleared_and_asks_next():
    r = run("I'm a nurse in Ohio, I'm 50", {})
    r = run("About $750k", r.profile)
    r2 = run("", r.profile, reset=["Saving"])
    assert r2.reply.startswith("Cleared your saving.") and "did not match" not in r2.reply
    assert r2.question is not None
    r3 = run("", r.profile, reset=["all"])
    assert r3.reply == "Cleared all your answers." and r3.question.text.startswith("How old")


# ------------------------------------------------------------------ 5. baseline wants
def test_mortgage_ending_before_retirement_is_not_a_retirement_basic():
    p = completed(home={"owns": True, "mortgage_balance": 300000, "mortgage_payment": 2800})
    assert costs.mortgage_end(p)["years_left"] < 20
    free = household.basics(p)
    with_mortgage = household.basics(completed(retire_age=50, age=45, home={"owns": True, "mortgage_balance": 300000, "mortgage_payment": 2800}))
    # Rules-audit fix (2026-11-22): for anyone still at work, retirement basics leave the mortgage out; payments that run past
    # retirement are a separate cost in the cash flow. So the basics are the same whether or not the mortgage outlives work.
    assert free["housing"] < 20000
    assert with_mortgage["housing"] == free["housing"]


def test_thin_wants_headline_reads_sensibly():
    from app.agents import adviser
    m = {"safe_spending_per_year": 50400, "wants_per_year": 0}
    h = adviser.headline(m, 50400)
    assert h.startswith("You can count on $50,400 a year, about your needs") and "Little is left for wants" in h
    assert "but your needs cost $50,400" in adviser.headline({"safe_spending_per_year": 30000, "wants_per_year": 0}, 50400)
    assert "$60,000 for needs, $30,000 for wants" in adviser.headline({"safe_spending_per_year": 90000, "wants_per_year": 90000}, 60000)


def test_plan_carries_headline_and_never_says_wants_are_zero():
    p = pipeline.prepare({"age": 60, "state": "OH", "retire_age": 62, "pay_per_year": 50000.0,
                          "savings": {"pretax": 20000, "roth": 0, "taxable": 0, "cash": 5000}, "savings_known": True, "home": {"owns": False}})
    plan, _ = asyncio.run(pipeline.tools_only_plan(p))
    assert plan["headline"] and "Wants are $0" not in plan["wants"]["line"]
    if plan["wants"]["per_year"] < 0.05 * plan["needs"]["basics_per_year"]:
        assert plan["wants"]["line"] == plan["headline"]


# ------------------------------------------------------------------ 6. display strings
RICH = {"age": 62, "has_partner": True, "partner_age": 60, "state": "CT", "retire_age": 65, "pay_per_year": 120000.0, "partner_pay_per_year": 0.0,
        "savings": {"pretax": 300000, "roth": 20000, "taxable": 50000, "cash": 30000}, "savings_known": True,
        "home": {"owns": True, "mortgage_balance": 120000, "mortgage_payment": 1500},
        "children": [{"age": 20}, {"age": 17}], "pets": [{"kind": "dog", "count": 1}],
        "pensions": [{"who": "you", "per_year": 24000.0, "start_age": 65, "inflation_adjusted": True}],
        "debts": [{"kind": "student", "balance": 20000.0, "rate": 0.06}], "saving": {"match_rate": 0.5, "match_cap": 0.06, "other_per_month": 200.0},
        "insurance": {"life_kind": "term", "life_face": 500000.0, "disability": True, "ltc": False},
        "goals": {"legacy": 100000.0, "big_costs": [{"label": "Boat", "amount": 40000.0, "year": 2030}], "parents_per_year": 6000.0, "parents_years": 5},
        "budget": {"housing": 2500.0, "food": 900.0}, "health": "fair", "emergency_months": 1.0,
        "inheritance": {"amount": 50000.0, "year": 2035}, "part_time": {"per_year": 20000.0, "until_age": 70}}


def test_pension_and_home_display_are_plain():
    r = run("", RICH)
    d = {f.key: f.display for f in r.fields}
    assert d["pensions"] == "You: $24,000 a year from 65, rises with prices, 50% goes to a surviving partner"
    h = run("", {"age": 50, "state": "OH", "home": {"owns": True, "mortgage_payment": 1500.0, "mortgage_balance": 100000.0}}).fields
    home = next(f for f in h if f.key == "home")
    assert "value not given" in home.display and "worth $0" not in home.display and home.value["value"] is None


def test_no_field_display_is_raw_or_a_zero_placeholder():
    for prof in (RICH, {"age": 40, "state": "TX"}, {}):
        r = run("", prof) if prof else run("I'm 40 in Texas", {})
        for f in r.fields:
            assert f.display, f.key
            assert "{" not in f.display and "'" not in f.display.replace("'s", "") and "None" != f.display or f.key in ("pets", "children", "big_costs", "legacy", "parents_help", "savings", "debts", "pensions")
            assert not re.search(r"(?<![\w$.,])\d+\.\d+(?![\d%]|\s*(?:months|month))", f.display), (f.key, f.display)   # a bare float
            assert "$0 " not in f.display + " " and not re.search(r"\$0\b(?!,)", f.display), (f.key, f.display)
            assert not re.search(r"\w+: [\w$]", f.display) or f.key == "pensions", (f.key, f.display)


# ------------------------------------------------------------------ 7. the empty state
def test_untouched_optional_sections_are_default_and_status_lists_them():
    r = run("I'm a nurse in Ohio, I'm 50", {})
    src = {f.key: f.source for f in r.fields}
    for k in ("debts", "pensions", "life_insurance", "disability", "ltc", "legacy", "health", "contributions", "match"):
        assert src[k] == "default", k
    st = {s["section"]: s["status"] for s in r.sections_status}
    assert list(st) == intake.intake_fields.SECTIONS
    assert st["Household"] == "added" and st["Insurance"] == st["Pensions & income"] == st["Goals"] == st["Health"] == "default"


def test_touched_section_becomes_added_and_skip_stays_default():
    r = run("I'm 50 in Ohio and we owe 30k on student loans at 6%", {})
    st = {s["section"]: s["status"] for s in r.sections_status}
    assert st["Home & debts"] == "added"
    assert next(f for f in r.fields if f.key == "debts").source == "you said"
    r2 = run("Skip, use typical", {"age": 50, "state": "OH"})
    assert next(f for f in r2.fields if f.key == "pensions").source == "default"
    assert {s["section"]: s["status"] for s in r2.sections_status}["Pensions & income"] == "default"
    r3 = run("No pension", dict(r2.profile, asking="pension", offered=[], notes={}))
    assert next(f for f in r3.fields if f.key == "pensions").source == "you said"


def test_intake_endpoint_returns_sections_status():
    c = TestClient(main.app)
    body = c.post("/api/intake", json={"text": "I'm a nurse in Ohio, I'm 50", "profile_so_far": {}}).json()
    assert isinstance(body["sections_status"], list) and {"section", "status"} == set(body["sections_status"][0])
