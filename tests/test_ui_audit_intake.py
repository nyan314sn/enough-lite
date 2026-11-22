"""Round-1 UI audit (docs/loop/round1_B/FINDINGS.md): the intake and plan-chat items. No live model calls."""
import asyncio

from app import ask_intent, household
from app.agents import intake, parser, turn_guard
from app.agents.turn_read import Update
from app.schemas import Profile


def run(text, prof=None):
    return asyncio.run(intake.run(text, prof or {}, use_ai=False))


COUPLE = ("I'm 71, retired, married, my wife is 69. We live in Florida. I already collect Social Security, $2,900 a month, and she gets $1,100. "
          "We have $640,000 saved and spend $6,000 a month. We own our house with no mortgage. No kids.")
AUSTIN = ("I'm 30, a software engineer in Austin Texas, I rent. I make $95,000 and my employer matches 4% of my 401k. "
          "I have $45,000 in student loans at 6.5% and $8,000 saved. Retire at 65.")


def test_p0_3_couple_social_security_keeps_both_figures():
    r = run(COUPLE)
    assert r.profile["social_security_per_year"] == 48000
    assert "$34,800" in r.reply and "$13,200" in r.reply


def test_p0_3_guard_prefers_the_household_sum():
    rule = parser.parse(COUPLE)
    g = turn_guard.check_updates([Update(field_path="social_security_per_year", value=34800, unit="per_year",
                                         evidence_quote="Social Security, $2,900 a month")], COUPLE, Profile(), None)
    assert turn_guard.merge(rule, g, COUPLE)["social_security_per_year"] == 48000


def test_p0_4_no_tiny_budget_and_no_vague_readback():
    r = run(AUSTIN)
    p = r.profile
    assert not any(v for v in p["budget"].values()), p["budget"]
    assert "is noted" not in r.reply and "spending split" not in r.reply
    assert p["pay_per_year"] == 95000 and p["job"] == "software engineer"


def test_p0_4_a_spending_figure_under_3000_a_year_is_not_stored():
    r = run("I'm 30 in Ohio. We spend $100 a year")
    assert (r.profile.get("spending_now_per_year") or 0) >= 3000 or r.profile["sources"].get("spending_now_per_year") != "you said"


def test_p1_7_stated_loan_rate_is_kept():
    for msg in (AUSTIN, "Student loans, $45,000 at 6.5%"):
        d = parser.parse(msg)["debts"][0]
        assert d["rate"] == 0.065


def test_p1_8_pension_with_amount_is_captured():
    p = run("I'm a single nurse, 58, in Ohio. I make about $78,000. I have a pension from the county hospital, about $1,500 a month at 62, "
            "and want to retire at 62.").profile
    assert p["pensions"] and p["pensions"][0]["per_year"] == 18000 and p["pensions"][0]["start_age"] == 62


def test_p1_8_pension_without_amount_is_asked():
    r = run("I'm a single nurse, 58, in Ohio. I make about $78,000. I have a pension from the county hospital and want to retire at 62.")
    assert "pension" in r.missing


def _plan():
    return {"headline": "You can count on $35,600 a year.", "needs": {"basics_per_year": 22400, "line": "Basics."},
            "wants": {"per_year": 35600.0, "above_basics_per_year": 13200.0, "line": "Wants."}, "wishes": {"line": "Wishes."},
            "actions": [{"title": "Save more", "why": "It helps."}]}


def _base():
    return household.complete(Profile(age=45, state="CT", retire_age=60, pay_per_year=90000.0, savings_known=True,
                                      sources={"age": "you said", "retire_age": "you said"}))


def test_p1_4_single_stock_tip_is_declined():
    out = asyncio.run(ask_intent.route("should I buy Tesla stock", _base(), _plan(), "s", False))
    assert out["kind"] == "answer" and "single stocks" in out["text"]


def test_p1_4_safe_spending_number_is_the_figure():
    out = asyncio.run(ask_intent.route("What is my safe spending number?", _base(), _plan(), "s", False))
    assert "$35,600" in out["text"]


def test_p2_6_editor_save_is_not_followed_by_an_unrelated_check():
    r = run("I'm 45 in Ohio, a nurse, 300k saved")
    r2 = run("Updated your pay: $80,000 a year.", r.profile)
    assert "about right" not in (r2.question.text if r2.question else "")


def test_retired_spending_is_spending_now():
    p = run(COUPLE).profile
    assert p["spending_now_per_year"] == 72000


def test_p2_10_rule_answers_keep_the_dollar_sign():
    t = ask_intent.money_signs("You can add 666 per year, and up to 23,500 in 2026; at 50 the catch-up is 7,500 a year. Use $1,000 a month.")
    assert "$666 per year" in t and "$7,500 a year" in t and "$1,000 a month" in t and "$$" not in t and "in 2026" in t
