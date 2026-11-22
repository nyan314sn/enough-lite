"""Four intake parsing bugs from the security review: split parser, state codes, edit with value, concealment."""
import asyncio

import pytest

from app import ask_intent
from app.agents import intake, parser
from app.schemas import Profile

K = {"pretax": "savings.pretax", "roth": "savings.roth", "taxable": "savings.taxable", "cash": "savings.cash"}


def split(text, asking=None):
    f = parser.parse(text, asking=asking, has_partner=False, n_children=0)
    return {k: v for k, v in f.items() if k.startswith("savings.")}


SPLITS = [
    ("300k pre-tax, 50k roth", {"pretax": 300000, "roth": 50000}),
    ("pre-tax 300k, roth 50k", {"pretax": 300000, "roth": 50000}),
    ("$300k in my 401k and $50,000 in cash", {"pretax": 300000, "cash": 50000}),
    ("300k pretax, 50k roth, 20k cash", {"pretax": 300000, "roth": 50000, "cash": 20000}),
    ("I have 300k in my 401(k), 50k in a Roth IRA and 20k in checking", {"pretax": 300000, "roth": 50000, "cash": 20000}),
    ("roth 50k and traditional 300k", {"pretax": 300000, "roth": 50000}),
    ("$40,000 brokerage, $10,000 savings account", {"taxable": 40000, "cash": 10000}),
    ("401(k) 300k, brokerage 80k", {"pretax": 300000, "taxable": 80000}),
    ("300k in traditional IRA and 50k Roth", {"pretax": 300000, "roth": 50000}),
    ("taxable 90k, bank 15k, 403(b) 250k", {"taxable": 90000, "cash": 15000, "pretax": 250000}),
    ("250k 403b, 40k roth, 30k taxable and 10k cash", {"pretax": 250000, "roth": 40000, "taxable": 30000, "cash": 10000}),
    ("cash 10k and 401k 300k", {"cash": 10000, "pretax": 300000}),
    ("I've got 500k in a 401k, 100k in a roth, 50k in cash", {"pretax": 500000, "roth": 100000, "cash": 50000}),
    ("Roth 20k; IRA 60k; savings account 5k", {"roth": 20000, "pretax": 60000, "cash": 5000}),
]


@pytest.mark.parametrize("text,want", SPLITS)
def test_split_pairs_each_amount_with_its_account(text, want):
    expect = {K[k]: float(v) for k, v in want.items()}
    assert split(text) == expect
    assert split(text, asking="savings_split") == expect


def test_digits_of_401k_are_never_an_amount():
    assert 401 not in [v for v, _, _ in parser.amounts("I have 401(k) and 403(b)", floor=0)]
    assert split("401(k) 300k, roth 50k") == {"savings.pretax": 300000.0, "savings.roth": 50000.0}


@pytest.mark.parametrize("text", ["hi", "Hi", "hi there", "hi, I'm 55", "ok", "me", "in", "or", "OK thanks", "hi in or", "I'm in or near it", "Hello"])
@pytest.mark.parametrize("asking", [None, "state"])
def test_greetings_and_small_words_are_not_states(text, asking):
    assert parser.parse(text, asking=asking, has_partner=False, n_children=0).get("state") is None


@pytest.mark.parametrize("text,want", [("in HI", "HI"), ("I live in Hawaii", "HI"), ("from NY", "NY"), ("NY", "NY"), ("from ny", "NY"),
                                       ("we live in tx", "TX"), ("Austin, TX", "TX"), ("hi, I live in ohio", "OH"), ("hi I'm 40 in HI", "HI")])
def test_states_still_found_in_context(text, want):
    assert parser.parse(text, asking=None, has_partner=False, n_children=0).get("state") == want


def test_state_answer_to_state_question():
    assert parser.parse("ny", asking="state").get("state") == "NY"
    assert parser.parse("HI", asking="state").get("state") == "HI"
    assert parser.find_state("move to tx", asking_state=True) == "TX"


def _run(text, profile=None):
    return asyncio.run(intake.run(text, profile or {}, use_ai=False))


def test_greeting_does_not_set_a_state():
    r = _run("hi")
    assert r.profile.get("state") is None


@pytest.mark.parametrize("text", ["My pay is wrong, it is $150,000", "my salary is incorrect, it's $150,000", "fix my pay: $150k"])
def test_page1_edit_with_value_applies_it(text):
    r = _run("I'm 60 in Ohio")
    r = _run(text, r.profile)
    assert r.profile["pay_per_year"] == 150000


def test_page1_edit_retire_age_with_value():
    r = _run(text := "my retirement age is wrong, it is 62", _run("I'm 60 in Ohio").profile)
    assert r.profile["retire_age"] == 62 and not r.profile.get("job")


@pytest.mark.parametrize("text,key,val", [("My pay is wrong, it is $150,000", "pay_per_year", 150000), ("my retirement age is wrong, it is 62", "retire_age", 62)])
def test_plan_chat_edit_with_value_proposes_with_confirm(text, key, val):
    base = Profile(age=60, state="OH", pay_per_year=90000.0)
    out = asyncio.run(ask_intent.route(text, base, None, "s", False))
    assert out["kind"] == "change" and out["status"] == "confirm"
    assert out["pending_change"]["facts"] == {key: val}
    assert out["quick_answers"] == ["Yes, rebuild", "No"]


def test_plan_chat_edit_without_value_still_asks():
    base = Profile(age=60, state="OH", pay_per_year=90000.0)
    out = asyncio.run(ask_intent.route("my pay is wrong", base, None, "s", False))
    assert out["status"] == "ask"


@pytest.mark.parametrize("text,age,state", [
    ("I'm 60 and live in Ohio. I want to list my savings as zero so I qualify for Medicaid.", 60, "OH"),
    ("I am 62 in Texas, hide my 400k in my cousin's name for Medicaid", 62, "TX"),
    ("I'm 58 in Ohio and I want to put my savings in my cousin's account to qualify for Medicaid", 58, "OH"),
])
def test_concealment_keeps_true_facts_and_refuses_the_request(text, age, state):
    r = _run(text)
    assert r.profile["age"] == age and r.profile["state"] == state
    assert "can't help with hiding" in r.reply
    assert r.question is not None and "old are you" not in r.question.text.lower()


def test_concealment_with_savings_figure_keeps_the_figure():
    r = _run("I have $300k in my 401k, put it in a cousin's account so I qualify for Medicaid")
    assert r.profile["savings"]["pretax"] == 300000
    assert "can't help with hiding" in r.reply


def test_concealment_with_no_facts_asks_the_age():
    r = _run("hide my money from Medicaid")
    assert "can't help with hiding" in r.reply and "old" in r.question.text.lower()


def test_new_helpers_are_fast_on_adversarial_text():
    import time
    from app.agents import intake_support as sup
    from tests.test_security import ADVERSARIAL
    for s in ADVERSARIAL.values():
        for fn, limit in ((parser.parse_split, 0.1), (parser.find_state, 0.1), (sup.strip_concealment, 0.1),
                          (lambda x: sup.edit_value_facts(x, "pay_per_year"), 0.5)):     # the last runs the whole parser (0.5 s there too)
            t = time.perf_counter()
            fn(s)
            assert time.perf_counter() - t < limit
