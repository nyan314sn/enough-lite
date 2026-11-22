"""Loop round 2: the plan chat (/api/ask) cases from the simulated-user and UI audits.

Each case is a turn from the transcripts (simusers/round2/analysis.txt, docs/loop/round2_B and round2_C): What Ifs typed
sloppily, "spend less", bare numbers, where a figure came from, run-out age, privacy, bitcoin, pets, starting points.
No model call: every turn runs on rules and tools.
"""
import asyncio
import copy
import re

import pytest

from app import ask_plan, pipeline

RETIRED = {"age": 71, "has_partner": True, "partner_age": 69, "state": "OH", "retire_age": 71, "pay_per_year": 0,
           "savings": {"pretax": 600000, "roth": 0, "taxable": 100000, "cash": 50000}, "savings_known": True,
           "home": {"owns": True}, "social_security_per_year": 38000, "spending_per_year": 72000, "risk": "balanced",
           "pets": [{"kind": "dog", "count": 1}],
           "sources": {"age": "you said", "social_security_per_year": "you said", "spending_per_year": "you said", "retire_age": "you said"}}
WORKING = {"age": 45, "has_partner": True, "partner_age": 43, "state": "OH", "retire_age": 65, "pay_per_year": 120000, "partner_pay_per_year": 60000,
           "savings": {"pretax": 250000, "roth": 20000, "taxable": 60000, "cash": 30000}, "savings_known": True,
           "home": {"owns": True}, "children": [{"age": 5}, {"age": 8}], "risk": "balanced",
           "sources": {"age": "you said", "retire_age": "you said", "pay_per_year": "you said", "partner_pay_per_year": "you said"}}
SHORT = {"age": 58, "has_partner": False, "state": "OH", "retire_age": 62, "pay_per_year": 38000,
         "savings": {"pretax": 20000, "roth": 0, "taxable": 0, "cash": 5000}, "savings_known": True, "home": {"owns": False},
         "sources": {"age": "you said", "retire_age": "you said", "pay_per_year": "you said"}}


def ask(q, profile, pending=None, plan=None):
    return asyncio.run(pipeline.ask(q, copy.deepcopy(profile), "t", use_ai=False, pending=pending, plan_so_far=plan))


def plan_of(profile):
    base = pipeline._clean_profile_text(pipeline.prepare(copy.deepcopy(profile)))
    plan, ctx = asyncio.run(pipeline.tools_only_plan(base))
    return plan, ctx.results


# ---------------------------------------------------------------- 1. What Ifs typed naturally (C P0-4, P1)
@pytest.mark.parametrize("q,age", [
    ("if I stop at 62", 62), ("wat if retir 62", 62), ("retire at sixty two", 62), ("retire at 55", 55),
    ("what if we both stop at 55 instead of 62?", 55), ("what if I work until 66?", 66), ("What if I retire at sixty-seven", 67),
    ("what if I quit working at 63", 63)])
def test_retire_age_forms_run_a_what_if(q, age):
    r = ask(q, WORKING)
    assert r["kind"] == "whatif", r["text"]
    assert r["changes"]["retire_age"] == age
    assert "From the source" not in r["text"]


def test_retire_in_years_and_more_years():
    assert ask("what if I retire in 12 years", WORKING)["changes"]["retire_age"] == 57
    assert ask("what if I work 3 more years", WORKING)["changes"]["retire_age"] == 68


def test_saving_forms():
    r = ask("what if I save 500 more per month", WORKING)
    assert r["kind"] == "whatif" and "$6,000 more a year" in r["text"]
    r = ask("wat if i sav 500 more per mnth", WORKING)
    assert r["kind"] == "whatif" and "$6,000 more a year" in r["text"]
    r = ask("put 300 a month into college savings", WORKING)
    assert r["kind"] == "whatif" and "$3,600 more a year" in r["text"] and "college" in r["text"]
    r = ask("What happens if I put 300 a month into college savings for the kids", WORKING)
    assert r["kind"] == "whatif" and "$3,600" in r["text"]


def test_spending_to_a_figure_and_claiming():
    r = ask("what if i cut spendin to 50k", WORKING)
    assert r["kind"] == "whatif" and r["changes"]["spending_per_year"] == 50000
    r = ask("what if I wait until 68 to claim", WORKING)
    assert r["kind"] == "whatif" and r["changes"]["claim_age"] == 68


def test_part_time_with_an_amount_runs():
    r = ask("what if I earn $20,000 a year part time until 68", WORKING)
    assert r["kind"] == "whatif" and r["changes"]["part_time"] == {"per_year": 20000, "until_age": 68}
    r = ask("what if I work part time making 1500 a month until 66", WORKING)
    assert r["changes"]["part_time"]["per_year"] == 18000


def test_part_time_without_an_amount_says_so_in_one_sentence_and_offers_a_run():
    r = ask("what if I work part time until 68", WORKING)
    assert r["kind"] == "clarify"
    assert len(re.findall(r"[.?!](?:\s|$)", r["text"])) == 1
    assert "can't run it" in r["text"] and "retiring at 68" in r["text"]
    assert "What if I retire at 68" in r["quick_answers"]
    assert ask(r["quick_answers"][0], WORKING)["kind"] == "whatif"       # the button runs
    assert ask(r["quick_answers"][1], WORKING)["kind"] == "whatif"


def test_a_what_if_never_gets_a_source_quote():
    for q in ("what if we buy a boat", "what if I retire early", "what if I get a 3 percent lower return", "wat if we go on vacation more"):
        r = ask(q, WORKING)
        assert r["kind"] == "clarify", (q, r["text"])
        assert "From the source" not in r["text"] and r["quick_answers"]
    assert ask("what if I miss my Medicare enrollment?", WORKING)["kind"] == "answer"      # a rule question keeps its source


def test_partner_retirement_is_the_partners():
    r = ask("what if my wife retires at 60", WORKING)
    assert r["kind"] == "whatif" and r["changes"] == {"partner_retire_age": 60}


# ---------------------------------------------------------------- 2. spend less (B P0-1)
@pytest.mark.parametrize("q", ["spend $500 less a month", "what if I spend $6,000 a year less", "cut my spending by $500 a month", "spend 500 less per month"])
def test_spend_less_is_a_cut_of_the_goal(q):
    r = ask(q, RETIRED)
    assert r["kind"] == "whatif", r["text"]
    assert r["changes"]["spending_per_year"] == 66000
    assert "If you spend $6,000 a year less ($66,000)," in r["text"]
    base_lasts = plan_of(RETIRED)[1]["markets"]["goal_lasts_of_100"]
    new_lasts = r["plan"]["spending_goal"]
    assert new_lasts == 66000
    assert f"(baseline plan: {base_lasts} of 100)" in r["text"]      # round 3: "of 100" (B P2-7)
    assert r["plan"]["spending_goal"] != 72000


def test_spend_less_result_changes():
    r = ask("spend $500 less a month", RETIRED)
    lasts_before = plan_of(RETIRED)[1]["markets"]["goal_lasts_of_100"]
    m = re.search(r"goal lasts in (\d+) of 100", r["text"])
    assert m and int(m.group(1)) != lasts_before
    assert "(now $" not in r["text"] and "(baseline plan: $" in r["text"]


def test_spend_less_without_an_amount_asks_how_much():
    r = ask("what if I spend less", RETIRED)
    assert r["kind"] == "clarify" and "How much less" in r["text"] and "What if I spend $500 less a month" in r["quick_answers"]


def test_spend_less_by_a_share():
    r = ask("what if I spend 10% less", RETIRED)
    assert r["changes"]["spending_per_year"] == 64800


# ---------------------------------------------------------------- 3. bare numbers (C P0-5, B P1-6)
def test_a_bare_number_with_nothing_pending_asks_which_figure():
    for q in ("65", "62"):          # round 3: a bare age asks "Do you mean retiring at N?"
        r = ask(q, WORKING)
        assert r["kind"] == "clarify", (q, r)
        assert f"Do you mean retiring at {q}?" in r["text"] and r.get("status") != "confirm"
    r = ask("$90,000", WORKING)
    assert r["kind"] == "clarify" and "Which figure" in r["text"] and r.get("status") != "confirm"


def test_a_bare_number_is_not_an_age_when_the_question_was_money():
    r = ask("62", WORKING, pending={"ask": "spending_now_per_year"})
    assert r["kind"] == "clarify" and "does not look like your spending" in r["text"]
    r = ask("62", WORKING, pending={"ask": "pay_per_year"})
    assert r["kind"] == "clarify"


def test_a_bare_number_fits_its_own_question():
    r = ask("62", WORKING, pending={"ask": "retire_age"})
    assert r["kind"] == "change" and r["status"] == "confirm" and "retirement age" in r["text"]
    assert "age to 62" not in r["text"].replace("retirement age to 62", "")
    r = ask("85000", WORKING, pending={"ask": "pay_per_year"})
    assert r["kind"] == "change" and r["status"] == "confirm"


def test_a_bare_number_with_a_confirm_waiting_keeps_the_confirm():
    r = ask("65", WORKING, pending={"facts": {"pay_per_year": 150000}})
    assert r["kind"] == "clarify" and r["quick_answers"][:2] == ["Yes, rebuild", "No"]


# ---------------------------------------------------------------- 4. starting points, past ages, another child
def test_every_starting_point_parses_to_a_what_if():
    plan, _ = plan_of(SHORT)
    pts = plan["starting_points"]
    assert pts, "the short profile should have starting points"
    for x in pts:
        assert x["whatif_text"], x
        r = ask(x["whatif_text"], SHORT)
        assert r["kind"] == "whatif", (x["whatif_text"], r["text"])


def test_spend_now_starting_point_is_worded_and_runs():
    r = ask("What if I spend $5,000 a year less now and save it", SHORT)
    assert r["kind"] == "whatif" and "less now and save it" in r["text"]
    assert r["plan"]["spending_goal"] != plan_of(SHORT)[0]["spending_goal"] or "spending_per_year" not in r["changes"]


def test_no_past_retirement_age_for_someone_retired():
    r = ask("retire at 60", RETIRED)
    assert r["kind"] == "clarify" and "already 71" in r["text"]
    r = ask("What if I retire at 62", {**WORKING, "age": 66, "retire_age": 70})
    assert r["kind"] == "clarify" and "already 66" in r["text"]
    plan, _ = plan_of(RETIRED)
    assert not [x for x in plan["levers"] if re.search(r"retire at", x["whatif_text"].lower())]


def test_another_child_for_a_retired_person():
    r = ask("what if we have another child", RETIRED)
    assert r["kind"] == "clarify" and "retired" in r["text"]
    assert ask("what if we have another child", WORKING)["kind"] == "whatif"


def test_action_one_has_no_starting_points_tail():
    plan, _ = plan_of(SHORT)
    assert all("Starting points:" not in a["why"] for a in plan["actions"])


# ---------------------------------------------------------------- 5. run-out age, labels, the 100 and 90 question
def test_when_does_my_money_run_out_gives_an_age():
    r = ask("when does my money run out", RETIRED)
    assert r["kind"] == "answer" and "From the source" not in r["text"]
    assert re.search(r"age \d\d", r["text"])
    assert re.search(r"\d+ of 100", r["text"])


def test_run_out_for_money_that_lasts_says_so():
    rich = {**RETIRED, "savings": {"pretax": 3000000, "roth": 0, "taxable": 500000, "cash": 100000}, "spending_per_year": 60000}
    r = ask("how long will my money last?", rich)
    assert "lasts through age" in r["text"] and "of 100" in r["text"]


def test_whatif_labels_say_your_plan():
    r = ask("retire at 70", WORKING)
    assert "(baseline plan: $" in r["text"] and "(now $" not in r["text"]


def test_same_figure_100_then_90_is_explained():
    r = ask("why does it say 100 of 100 and then 90 of 100?", RETIRED)
    assert r["kind"] == "answer" and "different things" in r["text"] and "basics" in r["text"].lower()


# ---------------------------------------------------------------- 6. where did a figure come from (C P0-4)
def test_where_did_a_figure_come_from_uses_the_plans_fields():
    r = ask("where did $72,000 come from?", RETIRED)
    assert r["kind"] == "answer" and "From the source" not in r["text"]
    assert "$72,000" in r["text"] and "your own answer" in r["text"] and "spending" in r["text"]
    r = ask("Where did the $38,000 for Social Security come from?", RETIRED)
    assert "Social Security" in r["text"] and "your own answer" in r["text"]


def test_where_did_an_estimate_come_from_says_estimate():
    plan, _ = plan_of({**RETIRED, "social_security_per_year": None, "sources": {"age": "you said"}})
    ss = int(plan["social_security_per_year"])
    r = ask(f"where did ${ss:,} come from", {**RETIRED, "social_security_per_year": None, "sources": {"age": "you said"}}, plan=plan)
    assert "estimate" in r["text"] or "assumption" in r["text"]


def test_a_plan_figure_is_traced_to_the_plan():
    plan, _ = plan_of(RETIRED)
    per = int(plan["wants"]["per_year"])
    r = ask(f"where did ${per:,} come from?", RETIRED, plan=plan)
    assert "90 of 100" in r["text"] and "not a figure you gave" in r["text"]


def test_an_untraceable_figure_is_said_plainly():
    r = ask("where did $56,000 and 8% come from?", RETIRED)
    assert r["kind"] == "answer" and "can't trace" in r["text"] and "From the source" not in r["text"]


def test_what_was_assumed_lists_the_guesses():
    r = ask("why did you assume that?", WORKING)
    assert r["kind"] == "answer" and "you said" in r["text"]


# ---------------------------------------------------------------- 7. privacy, "can I rely on this", crypto, pets
def test_privacy_and_rely_get_short_plain_answers():
    r = ask("is my data private?", RETIRED)
    assert r["kind"] == "answer" and "browser tab" in r["text"]
    assert ask("who sees my answers", RETIRED)["text"] == r["text"]
    r = ask("can I rely on this?", RETIRED)
    assert r["kind"] == "answer" and "guide" in r["text"] and "not as advice" in r["text"]
    assert "I don't have a source" not in r["text"]


def test_bitcoin_has_its_own_line_and_the_crypto_refusal_is_not_doubled():
    r = ask("what about bitcoin?", RETIRED)
    assert r["kind"] == "answer" and "Bitcoin" in r["text"] and "include it in your savings" in r["text"]
    r = ask("which crypto should I buy", RETIRED)
    assert r["kind"] == "refused"
    assert not r["text"].startswith("I can't help with that") and r["text"].count("help with that") == 0
    assert "crypto" in r["text"].lower()
    r = ask("which stock should I buy", RETIRED)
    assert r["kind"] == "refused"


def test_get_a_second_dog_is_a_what_if():
    r = ask("get a second dog", RETIRED)
    assert r["kind"] == "whatif"
    assert r["changes"]["pets"] == [{"kind": "dog", "count": 2}]
    assert "another dog" in r["text"] and "a year" in r["text"]
    r = ask("what if we adopt a cat", WORKING)
    assert r["kind"] == "whatif" and r["changes"]["pets"] == [{"kind": "cat", "count": 1}]
    r = ask("what if we get two dogs", WORKING)
    assert r["changes"]["pets"] == [{"kind": "dog", "count": 2}]


# ---------------------------------------------------------------- follow-up: a widow, and "what does the plan assume"
def test_a_widow_asking_about_her_husbands_age_is_answered_kindly():
    single = {**RETIRED, "has_partner": False, "partner_age": None}
    r = ask("what about my husband's age? he passed away", single)
    assert r["kind"] == "answer" and r["text"].startswith("I am sorry about your husband.") and "only your age counts" in r["text"]
    assert "If you tell me" not in r["text"]
    r = ask("what age is my husband in the plan?", single)
    assert "only your age counts" in r["text"] and "sorry" not in r["text"]


def test_what_does_the_plan_assume_is_answered_from_the_plan():
    r = ask("What does the plan assume about me? Like what age I'll live to, or how much my pay goes up each year?", WORKING)
    assert r["kind"] == "answer" and "From the source" not in r["text"] and "Pay stays" in r["text"]
