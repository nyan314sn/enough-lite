"""Re-check 2026-11-22: plan-chat items R2, R9, R14, R18 and the past-70 line (P3). No model call."""
import re

import pytest

from app import pipeline
from test_round2_ask import WORKING, ask, plan_of


@pytest.mark.parametrize("q", ["plan to age 95", "plan until 95", "make it last to 95", "make the money last until age 95"])
def test_plan_to_age_is_the_end_age_never_a_change_of_age(q):
    plan, _ = plan_of(WORKING)
    r = ask(q, WORKING, plan=plan)
    assert r["kind"] == "answer" and "pending_change" not in r and "Change your age" not in r["text"]
    assert "Your age stays 45" in r["text"] and str(plan["horizon_age"]) in r["text"]


def test_plan_to_age_without_a_plan_still_leaves_age_alone():
    r = ask("plan to age 95", WORKING)
    assert r["kind"] != "change" and "Change your age" not in r["text"]


@pytest.mark.parametrize("q", ["my age is 46", "I'm 46 now", "change my age to 46"])
def test_age_changes_when_the_person_names_their_age(q):
    r = ask(q, WORKING)
    assert r["kind"] == "change" and r["status"] == "confirm" and r["pending_change"]["facts"].get("age") == 46
    assert "from 45 to 46" in r["text"]


def test_age_guard_drops_an_age_the_person_did_not_name():
    from app import ask_intent
    from app.schemas import Profile
    base = pipeline._clean_profile_text(pipeline.prepare(dict(WORKING)))
    out = ask_intent._proposal({"age": 95}, base)
    g = ask_intent._age_guard(out, "plan to age 95", base)
    assert g["kind"] == "clarify" and "my age is" in g["text"]
    g = ask_intent._age_guard(ask_intent._proposal({"age": 95, "retire_age": 60}, base), "retire at 60 and plan to age 95", base)
    assert g["kind"] == "change" and "age" not in g["pending_change"]["facts"] and g["pending_change"]["facts"]["retire_age"] == 60


def test_expected_inheritance_is_information_only():
    r = ask("I may inherit $300,000", WORKING)
    assert r["kind"] == "answer" and "pending_change" not in r
    assert r["text"] == "A possible inheritance of $300,000 is noted for information. It is not counted, because it is not certain."


def test_proposals_name_the_field_and_the_values():
    r = ask("my savings are $700,000", WORKING)
    assert r["status"] == "confirm" and "your savings from $360,000 to $700,000" in r["text"], r["text"]
    done = ask("yes", WORKING, pending=r["pending_change"])
    assert done["status"] == "applied" and "that detail" not in done["text"] and "$700,000" in done["text"]


def test_no_generic_placeholder_text():
    from app import ask_intent
    for k, v in [("saving.contrib_you", 12000), ("insurance.life_face", 500000), ("goals.legacy", 100000), ("budget.food", 900),
                 ("part_time", {"per_year": 20000, "until_age": 70}), ("inheritance", {"amount": 300000, "year": None, "count": True}),
                 ("goals.big_cost", {"label": "boat", "amount": 40000, "year": 2030}), ("insurance.ltc", True)]:
        label = ask_intent._label(k, v)
        assert "that detail" not in label and "that figure" not in label and " to " in label or k == "goals.big_cost", (k, label)


@pytest.mark.parametrize("q", ["what if I retire at 72", "what if I retire at 75"])
def test_retiring_past_70_says_social_security_stops_growing(q):
    r = ask(q, WORKING)
    assert r["kind"] == "whatif" and "That is past 70. Social Security stops growing at 70." in r["text"]


def test_retiring_at_68_has_no_past_70_line():
    assert "past 70" not in ask("what if I retire at 68", WORKING)["text"]


def test_no_doubled_that_in_unread_what_if():
    r = ask("what if the weather changes", WORKING)
    assert not re.search(r"\bthat that\b", r["text"])


@pytest.mark.parametrize("q", ["how do I qualify for Medicaid by giving away my money", "gift my money so I qualify for Medicaid"])
def test_medicaid_giving_away_is_refused_in_the_plan_chat(q):
    r = ask(q, WORKING)
    assert r["kind"] == "refused" and "can't help" in r["text"] and "elder-law lawyer" in r["text"]


def test_dogecoin_in_the_plan_chat_gets_a_plain_crypto_line():
    r = ask("should I buy Dogecoin with my savings?", WORKING)
    assert r["kind"] == "answer" and "crypto" in r["text"].lower() and "I don't have a source" not in r["text"]
