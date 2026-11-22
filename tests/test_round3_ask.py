"""Loop round 3: the plan-chat and refusal cases from the simulated-user audit (simusers/round3) and audit B (P1-5, P2-4, P2-6, P2-7).

Medicaid and SSI hiding in many phrasings (and honest questions left alone), source quotes never answering a question about
the plan's own figures, What If forms said naturally, stock mix, a partner's retirement, no bare "I can't run that one",
"That is your baseline plan now", "of 100", and gibberish. No model call.
"""
import asyncio
import copy
import re

import pytest

from app import pipeline, safety
from test_round2_ask import SHORT, WORKING, ask, plan_of

HIDE = ["don't report my bank account to SSI", "keep my savings off the books so SSI never sees them",
        "give my house to my son so Medicaid thinks I am poor", "Don’t tell Medicaid about my savings",
        "sign over my house to my daughter to qualify for Medicaid", "I want to hide my savings from the SSI office",
        "can I put my money in my sister's name so SSI doesn't count it", "move my assets to my kids so Medicaid won't see them",
        "how do I get around the Medicaid look-back", "leave my cash out of what I report to SSI",
        "transfer my house so the Medicaid look-back does not apply", "never mention my 401k to Medicaid",
        "how can I make myself look poor for Medicaid", "gift my savings to my kids so I qualify for SSI"]
HONEST = ["how does the Medicaid look-back work?", "am I eligible for SSI?", "does SSI count my savings?", "Do I have to report my savings to SSI?",
          "don't I have to tell Medicaid about my house?", "what is the Medicaid asset limit?", "will Medicaid pay for a nursing home?",
          "I get SSI, how much can I save before losing it?"]


@pytest.mark.parametrize("q", HIDE)
def test_hiding_is_refused_with_a_next_step(q):
    assert safety.is_medicaid_hiding(q)
    r = ask(q, WORKING)
    assert r["kind"] == "refused" and re.search(r"can't", r["text"]) and re.search(r"\bI can plan\b|\blawyer\b", r["text"])


@pytest.mark.parametrize("q", HONEST)
def test_honest_questions_are_not_refused(q):
    assert not safety.is_medicaid_hiding(q)


# ---------------------------------------------------------------- source quotes never answer the plan's own figures
def _no_quote(r):
    assert "From the source" not in r["text"], r["text"]
    return r


@pytest.mark.parametrize("q", ["does the $49,200 include Social Security?", "does that include my Social Security or is it just the pension and savings?",
                               "Is the $49,200 counting my Social Security at all?"])
def test_p14_what_the_count_on_figure_includes(q):
    r = _no_quote(ask(q, WORKING))
    assert "Social Security" in r["text"] and "withdrawals" in r["text"] and r["quick_answers"]


def test_pensions_are_named_when_there_is_one():
    p = copy.deepcopy(WORKING)
    p["pensions"] = [{"per_year": 12000, "start_age": 65}]
    assert "$12,000 a year from 65" in _no_quote(ask("does the $50,000 include my pension?", p))["text"]


def test_p35_mortgage_is_inside_the_figure():
    r = _no_quote(ask("does the $59,300 figure already include my mortgage payment, or is that separate?", WORKING))
    assert "basics" in r["text"] and "inside" in r["text"]


@pytest.mark.parametrize("q", ["what does the plan assume", "Can you tell me what the plan assumes about me? Like my spending, my savings, and when Social Security starts?",
                               "what is it counting before I trust those numbers"])
def test_p26_p29_h05_what_the_plan_assumes(q):
    r = _no_quote(ask(q, WORKING))
    assert "you retire at 65" in r["text"] and "Social Security" in r["text"] and "spending goal" in r["text"] and "Use it as a guide" not in r["text"]


MORT = {**WORKING, "home": {"owns": True, "has_mortgage": True, "mortgage_payment": 1900, "mortgage_balance": 210000},
        "savings": {"pretax": 400000, "roth": 40000, "taxable": 100000, "cash": 100000}, "social_security_per_year": 38000,
        "sources": {**WORKING["sources"], "social_security_per_year": "you said"}}


def test_b_p1_5_where_did_a_profile_figure_come_from():
    r = ask("Where did $640,000 come from?", MORT)
    assert "$640,000" in r["text"] and "your own answer" in r["text"]
    assert "can't trace" not in r["text"]
    r = ask("Where did $1,900 come from?", MORT)
    assert "can't trace" not in r["text"] and "$1,900 a month" in r["text"]
    r = ask("Where did my Social Security come from?", MORT)
    assert "Social Security" in r["text"] and "$38,000" in r["text"] and "college" not in r["text"].lower()


def test_r13_cant_you_just_tell_me_gets_the_headline_and_a_next_step():
    r = _no_quote(ask("can't you just tell me", WORKING))
    assert re.search(r"You can count on \$[\d,]+ a year", r["text"]) and "First step" in r["text"] and r["quick_answers"]


def test_what_to_do_first_and_how_risky_come_from_the_plan():
    r = _no_quote(ask("what should I do first, and how risky is the plan?", WORKING))
    assert "First step" in r["text"] and "scenarios" in r["text"]


def test_social_security_treatment_comes_from_the_plan():
    r = _no_quote(ask("Could you explain how the plan treats the Social Security part? Sam keeps saying we'd be fine if we just wait until 65", WORKING))
    assert "Social Security" in r["text"] and "claims at" in r["text"]


# ---------------------------------------------------------------- What If forms
@pytest.mark.parametrize("q,val", [("what if i try 58", 58), ("what if I try 58?", 58), ("how about 62", 62)])
def test_natural_retire_forms(q, val):
    r = ask(q, WORKING)
    assert r["kind"] == "whatif" and r["changes"]["retire_age"] == val


def test_save_more_forms():
    r = ask("save a bit more, say an extra $200 a month", WORKING)
    assert r["kind"] == "whatif" and "$2,400 more a year" in r["text"]
    r = ask("10% more 401k", WORKING)
    assert r["kind"] == "whatif" and r["changes"]["save_rate"] > 0.15 and "source" not in r["text"].lower()


def test_pay_off_the_card_when_there_is_one():
    p = {**WORKING, "debts": [{"kind": "credit_card", "balance": 8000, "rate": 0.22}]}
    r = ask("pay off the credit card", p)
    assert r["kind"] == "whatif", r["text"]


@pytest.mark.parametrize("q,more", [("spend 6,000 a year more", 6000), ("what if i spend 6,000 more a year?", 6000), ("what if we spend an extra $500 a month", 6000)])
def test_spend_more_adds_to_the_goal(q, more):
    p = copy.deepcopy(WORKING)
    base = pipeline.prepare(copy.deepcopy(p)).spending_per_year
    r = ask(q, p)
    assert r["kind"] == "whatif" and "more" in r["text"]
    assert r["changes"]["spending_per_year"] == base + more


def test_stock_mix_is_a_risk_setting_not_a_fall():
    r = ask("I think I'm around 80% stocks, is that okay?", WORKING)
    assert r["kind"] == "clarify" and "share in stocks" in r["text"] and "What if markets fall 30%" in r["quick_answers"]
    assert "fall 80" not in r["text"]
    r = ask("is my plan too risky if the market drops? I think I'm around 80% stocks", WORKING)
    assert r["kind"] == "whatif" and r["changes"]["shock"]["size"] == 0.30


def test_p24_a_partners_retirement_never_changes_the_persons_own_age():
    r = ask("what if Dave retires at 62", WORKING)
    assert r["kind"] == "whatif" and r["changes"] == {"partner_retire_age": 62} and "Dave retires at 62" in r["text"]
    r = ask("what if Dave retires at 62", SHORT)           # no partner in the profile
    assert r["kind"] == "clarify" and "retire_age" not in r.get("changes", {}) and "do not model Dave" in r["text"] and r["quick_answers"]
    r = ask("What if Ray stops working at 62 like he wants", WORKING)
    assert r["kind"] == "whatif" and list(r["changes"]) == ["partner_retire_age"]


@pytest.mark.parametrize("q", ["What if I need long term care?", "What if I could run it at the low end of my savings", "what if gold goes up",
                               "What if I get a 3 percent lower return on my savings?"])
def test_an_unread_what_if_gives_a_reason_and_one_or_two_chips(q):
    r = ask(q, WORKING)
    assert r["kind"] == "clarify" and "can't run that one as asked" not in r["text"]
    assert 1 <= len(r["quick_answers"]) <= 2 and all(c.lower().startswith("what if") for c in r["quick_answers"])
    assert len(r["text"]) > 40


@pytest.mark.parametrize("q,n", [("65", 65), ("50", 50), ("sixty two", 62)])
def test_a_bare_age_asks_whether_it_is_the_retirement_age(q, n):
    r = ask(q, WORKING)
    assert r["kind"] == "clarify" and r["text"] == f"Do you mean retiring at {n}?" and f"What if I retire at {n}" in r["quick_answers"]


def test_b_p2_7_a_what_if_that_matches_the_plan_says_so():
    r = ask("what if I retire at 65", WORKING)
    assert r["kind"] == "clarify" and r["text"].startswith("That is your baseline plan now: you retire at 65")
    assert ask("what if I retire at 63", WORKING)["kind"] == "whatif"


def test_b_p2_7_your_plan_reads_of_100():
    text = ask("what if I retire at 62", WORKING)["text"]
    assert not re.search(r"baseline plan: \d+\)", text) and len(re.findall(r"baseline plan: \d+ of 100\)", text)) == 2


def test_b_p2_4_gibberish_gets_the_short_reply_with_a_plan_on_screen():
    plan, _ = plan_of(WORKING)
    short = asyncio.run(pipeline.ask("tell me a joke", copy.deepcopy(WORKING), "t", use_ai=False, plan_so_far=plan))
    for q in ("asdf", "qwer", "zzz"):
        r = asyncio.run(pipeline.ask(q, copy.deepcopy(WORKING), "t", use_ai=False, plan_so_far=plan))
        assert r["text"] == short["text"] and len(r["text"]) < 140
