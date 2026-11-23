"""The intake failures from the live product-rules audit (docs/loop/rules_audit/: out_idk, out_long, out_parent, out_t_edit, out_t_misc).

Rule path (no model) for the journeys; the long message is also run with the model's reading faked (the wrong reading the live run
produced), so the guards are tested too."""
import asyncio
import re

from app import household, pipeline
from app.agents import college, intake, parser, turn_guard, turn_read
from app.schemas import Profile


def run(text, profile=None, use_ai=False):
    return asyncio.run(intake.run(text, profile or {}, use_ai=use_ai))


def row(r, key):
    return next((f for f in r.fields if f.key == key), None)


def note(r, section):
    return next(s.get("note", "") for s in r.sections_status if s["section"] == section)


# ------------------------------------------------------------------ item 1 (R1): every skipped input shows and names its figure
def test_r1_skip_everything_names_a_figure_or_says_none_counted():
    r = run("I'm 50, I live in Georgia")
    replies = []
    for ans in ["I don't know", "skip", "I don't know", "skip", "I don't know", "skip", "I don't know"]:
        asked = r.profile.get("asking")
        r = run(ans, r.profile)
        replies.append((asked, r.reply))
    for asked, reply in replies:
        assert "a typical figure for that" not in reply and "the typical figure for that" not in reply, (asked, reply)
        assert re.search(r"\$\d|age \d|none|no children|no other debts|no pension|typical US taxes|ages \d|same as yours", reply, re.I), (asked, reply)
    by = dict(replies)
    assert "$115,000" in by["savings"]
    assert re.search(r"typical housing costs.*\$[\d,]+ a year", by["home"])
    assert "no children" in by["children_count"] and "none are counted" in by["children_count"].replace("no child costs are counted", "none are counted") or "no child costs are counted" in by["children_count"]


def test_r1_panel_shows_the_savings_figure_as_an_estimate():
    r = run("I'm 50, I live in Georgia")
    r = run("skip", r.profile)           # pay
    r = run("skip", r.profile)           # savings
    f = row(r, "savings")
    assert f.source in ("assumed", "estimate") and "$69,000" in f.display
    assert "$115,000" in note(r, "Saving") and "Estimate" in note(r, "Saving")


def test_r1_panel_shows_a_skipped_home_and_children_and_none_counted_groups():
    r = run("I'm 50, I live in Georgia")
    for _ in range(7):
        r = run("skip", r.profile)
    home = row(r, "home")
    assert home is not None and home.source == "estimate" and re.search(r"\$[\d,]+ a year", home.display)
    kids = row(r, "children")
    assert kids is not None and kids.display == "None counted"
    r = run("Add a pension", r.profile)
    r = run("skip", r.profile)
    assert row(r, "pensions").display == "None counted" and "no pension" in r.reply
    for chip in ("Add insurance", "Add goals"):
        r = run(chip, r.profile)
        r = run("skip", r.profile)
    assert row(r, "life_insurance").display.startswith("None") and row(r, "legacy").display.startswith("None")
    assert "typical figure" not in r.reply


def test_r1_estimate_chip_is_a_proposal_not_something_the_person_said():
    r = run("I'm 45, a nurse in Ohio, single, no kids, 300k saved, I rent")
    r = run("Change my spending now", r.profile)
    r = run("Estimate it for me", r.profile)
    assert re.search(r"I estimated your spending at \$[\d,]+ a year, marked estimate", r.reply), r.reply
    assert "I noted that you spend" not in r.reply
    assert row(r, "spending_now_per_year").source == "estimate"


# ------------------------------------------------------------------ item 2 (R4/R2): the long message
LONG = ("My name is not important but I am 47, my husband is 49. We live in Portland, Oregon with our daughter who is 12 and our cat. I'm a dental hygienist making $88,000, he is a carpenter making $71,000. "
        "We have $330,000 in 401(k)s, $45,000 in a savings account and about $20,000 in an IRA. Our house is worth $620,000 and we owe $310,000 at 3.1% with payments of $2,150 a month. "
        "We have a car loan of $14,000 at 5%. We spend about $7,000 a month. I want to retire at 62, he wants to retire at 65. He will get a union pension of about $1,800 a month at 65. "
        "We want our daughter to go to a state university. My mother lives with us part of the year and we help her with about $400 a month. We also want to leave something to our daughter.")


def test_long_message_rule_path_keeps_stated_figures():
    r = run(LONG)
    s = r.profile["savings"]
    assert (s["pretax"], s["cash"], s["taxable"]) == (350000, 45000, 0)           # 401(k)s and the IRA are pre-tax; nothing is made up
    h = r.profile["home"]
    assert (h["mortgage_balance"], h["mortgage_payment"], h["value"]) == (310000, 2150, 620000)
    assert [(d["kind"], d["balance"]) for d in r.profile["debts"]] == [("car", 14000)]      # the mortgage is not also a debt
    assert not any(r.profile["budget"].get(k) for k in ("transport", "debt", "housing"))   # a loan balance is never monthly spending
    assert row(r, "budget") is None
    leave = row(r, "legacy")
    assert leave.display == "A wish noted, no amount" and "None" not in leave.display
    assert r.profile["goals"]["legacy"] is None
    assert "is noted" not in r.reply


def _update(path, value, unit, quote):
    return turn_read.Update(field_path=path, value=value, unit=unit, evidence_quote=quote)


def test_long_message_with_the_models_wrong_reading_is_corrected_by_the_guards(monkeypatch):
    """The live run: the model gave the IRA and the savings account, a total, and the mortgage as 'other debt'."""
    q401 = "$330,000 in 401(k)s, $45,000 in a savings account and about $20,000 in an IRA"
    tr = turn_read.TurnRead(intent="new_facts", updates=[
        _update("age", 47, "age", "I am 47"),
        _update("savings.pretax", 20000, "dollars", "about $20,000 in an IRA"),
        _update("savings.cash", 45000, "dollars", "$45,000 in a savings account"),
        _update("savings.total", 395000, "dollars", q401),
        _update("home.value", 620000, "dollars", "Our house is worth $620,000"),
        _update("home.mortgage_balance", 310000, "dollars", "we owe $310,000 at 3.1%"),
        _update("debts.other", 310000, "dollars", "we owe $310,000 at 3.1%"),
        _update("spending_now_per_year", 84000, "per_year", "We spend about $7,000 a month"),
    ])

    async def fake(clean, p, pending, history, session, use_ai, *a, **k):
        return tr, {"input": 0, "cached": 0, "output": 0}, 0.0
    monkeypatch.setattr(intake.turn_read, "read", fake)
    r = run(LONG, use_ai=True)
    s = r.profile["savings"]
    assert (s["pretax"], s["cash"], s["taxable"]) == (350000, 45000, 0), s
    assert "taxable" not in r.reply
    assert [d["kind"] for d in r.profile["debts"]] == ["car"], r.profile["debts"]
    assert r.profile["home"]["mortgage_balance"] == 310000
    assert not any(r.profile["budget"].get(k) for k in ("transport", "debt"))
    assert r.profile["spending_now_per_year"] == 84000


def test_a_balance_is_never_read_as_monthly_spending():
    for text in ("We have a car loan of $14,000 at 5%.", "I have a car loan of $14,000 and a student loan of $20,000",
                 "Our mortgage is $200,000 and we owe $9,000 on a credit card"):
        assert not [k for k in parser.parse(text, asking=None) if k.startswith("budget.")], text
    assert parser.parse("housing 2000, food 800, transport 500", asking="budget").get("budget.housing") == 2000


def test_mortgage_figure_is_not_kept_as_other_debt_in_either_reader():
    f = parser.parse("Our house is worth $620,000 and we owe $310,000 at 3.1% with payments of $2,150 a month.")
    assert f["home.mortgage_balance"] == 310000 and f["home.mortgage_rate"] == 0.031 and f["home.mortgage_payment"] == 2150
    assert "debts" not in f
    facts = {"debts": [{"kind": "other", "balance": 310000.0}, {"kind": "car", "balance": 14000.0}], "home.mortgage_balance": 310000.0}
    intake._drop_mortgage_debts(facts, Profile())
    assert [d["kind"] for d in facts["debts"]] == ["car"]


def test_guard_pairs_accounts_to_figures_when_they_add_to_the_stated_total():
    p = Profile(age=47)
    q = "$330,000 in 401(k)s, $45,000 in a savings account and about $20,000 in an IRA"
    g = turn_guard.check_updates([
        _update("savings.pretax", 20000, "dollars", "about $20,000 in an IRA"),
        _update("savings.cash", 45000, "dollars", "$45,000 in a savings account"),
        _update("savings.total", 395000, "dollars", q)], q, p)
    assert g.facts["savings.pretax"] == 350000 and g.facts["savings.cash"] == 45000
    assert "savings.taxable" not in g.facts


# ------------------------------------------------------------------ item 3 (R4): per-child college by sex
def _children(r):
    return {c["age"]: c["college_type"] for c in r.profile["children"]}


def test_girl_and_boy_are_linked_to_ages_when_the_sentence_gives_them():
    r = run("I'm a single mom, 38, a nurse in Denver, Colorado earning $92,000. I have two kids, a girl of 8 and a boy of 5. I rent for $2,300 a month "
            "and have $48,000 saved. I want the girl to go to a state college and the boy to a private one. I'd like to retire at 63.")
    assert _children(r) == {8: "public", 5: "private"}
    assert [c["sex"] for c in r.profile["children"]] == ["female", "male"]
    assert "8-year-old goes to a public in-state college" in r.reply and "5-year-old goes to a private college" in r.reply
    assert "is noted" not in r.reply


def test_girl_and_boy_without_a_link_are_asked_and_not_called_noted():
    r = run("I'm a single mom, 38, a nurse in Denver, Colorado earning $92,000. I have two kids, 8 and 5. I rent for $2,300 a month and have $48,000 saved. "
            "I want the girl to go to a state college and the boy to a private one.")
    assert r.question and "Which child" in r.question.text and "8-year-old" in r.question.text and "5-year-old" in r.question.text
    assert "college" not in r.reply.lower().split("filled in")[0].split("i noted that")[-1]       # the choice was not applied, so it is not claimed
    assert all(row(r, f"college_{i}").source == "estimate" for i in range(2))


def test_daughter_who_is_12_links_the_word_to_the_age():
    assert college.child_sexes("our daughter who is 12 and our son (9)") == {12: "female", 9: "male"}
    assert college.child_sexes("a girl of 8 and a boy of 5") == {8: "female", 5: "male"}
    assert college.child_sexes("I want the girl to go to a state college and the boy to a private one") == {}
    assert college.child_sexes("my son is 2 and my daughter is 2") == {}        # twins of one age and two words: not guessed


def test_sex_is_kept_for_a_later_college_message():
    r = run("I'm a single mom, 38, a nurse in Denver, Colorado. I have a girl of 8 and a boy of 5.")
    assert [c["sex"] for c in r.profile["children"]] == ["female", "male"]
    r = run("the boy goes to a private college", r.profile)
    assert _children(r)[5] == "private"


# ------------------------------------------------------------------ item 4 (R7): a stated figure changes only after a yes
def _ready_household():
    r = run("I'm 45, a lawyer in Ohio making $400,000, single, no kids, $900k saved, own with no mortgage, spend $90,000 a year, retire at 60")
    for t in ("No other debts", "Skip, use typical"):
        if r.question and r.question.quick_answers:
            r = run(t if t in r.question.quick_answers else r.question.quick_answers[0], r.profile)
    return r


def _asked_to_change_pay():
    r = _ready_household()
    assert r.profile["pay_per_year"] == 400000
    r = run("change my pay to 90000", r.profile)
    assert r.question.text == "Change your pay from $400,000 to $90,000?" and r.question.quick_answers == ["Yes", "No"]
    assert r.profile["pay_per_year"] == 400000
    assert "Got it" not in r.reply
    return r


def test_changing_a_stated_pay_asks_first_and_applies_nothing():
    _asked_to_change_pay()


def test_yes_applies_the_change_and_no_keeps_the_figure():
    r = _asked_to_change_pay()
    yes = run("Yes", r.profile)
    assert yes.profile["pay_per_year"] == 90000 and "Changed: your pay is now $90,000" in yes.reply
    assert "pending_change" not in yes.profile["notes"]
    no = run("No", r.profile)
    assert no.profile["pay_per_year"] == 400000 and "kept your pay at $400,000" in no.reply
    other = run("I rent actually", r.profile)          # something else: the figure stays, and it is said
    assert other.profile["pay_per_year"] == 400000 and "I did not change your pay" in other.reply


def test_a_retirement_age_correction_also_asks():
    r = _ready_household()
    r = run("actually I retire at 66", r.profile)
    assert r.question.text == "Change your retirement age from 60 to 66?"
    assert r.profile["retire_age"] == 60


def test_a_forged_pending_change_is_ignored():
    r = _ready_household()
    prof = dict(r.profile, asking="confirm_change")
    prof["notes"] = dict(prof["notes"], pending_change='{"f":{"pay_per_year":1e99,"state":"x"},"a":null}')
    out = run("Yes", prof)
    assert out.profile["pay_per_year"] == 400000


def test_the_answer_to_the_pending_question_needs_no_confirm():
    r = run("I'm 45, a nurse in Ohio, single, no kids, 300k saved, I rent")
    r = run("Change my retirement age", r.profile)
    r = run("62", r.profile)
    assert r.profile["retire_age"] == 62 and not (r.question and r.question.quick_answers == ["Yes", "No"])


# ------------------------------------------------------------------ item 5 (R9) and 6 (R18): wording
def test_possible_inheritance_is_shown_as_information_only():
    r = run("I'm 45, a nurse in Ohio, single, no kids, 300k saved, I rent")
    r = run("I may inherit $300,000", r.profile)
    f = row(r, "inheritance")
    assert f.label == "Possible inheritance" and "$300,000" in f.display and "not counted" in f.display
    assert "you may inherit $300,000" in r.reply and "not counted" in r.reply
    assert "is noted" not in r.reply
    p = household.complete(Profile(**r.profile))
    assert not p.inheritance.count


def test_health_is_named_and_nothing_says_is_noted_is_noted():
    r = run("I'm 45, a nurse in Ohio, single, no kids, 300k saved, I rent")
    r = run("my health is fair", r.profile)
    assert "you are in fair health" in r.reply and "is noted" not in r.reply


def test_no_pay_reads_as_you_have_no_pay():
    from app import ask_self
    base = household.complete(Profile(age=70, retire_age=65, pay_per_year=0, sources={"pay_per_year": "you said", "retire_age": "you said"}))
    out = ask_self.assumes("what does the plan assume", base, {})
    assert out and "you have no pay" in out["text"] and "your pay is No pay" not in out["text"]


# ------------------------------------------------------------------ item 7: smaller items
def test_saved_editor_edit_is_not_called_unmatched():
    r = _ready_household()
    prof = dict(r.profile, pay_per_year=310000)
    out = run("Updated your pay: $310,000.", prof)
    assert "did not match" not in out.reply and out.reply.strip() and ("Saved" in out.reply or "updated some typical figures" in out.reply or "→" in out.reply)


def test_retier_typo_works_for_the_plan_chat_and_for_intake():
    assert parser.fix_words("what if i retier at 67") == "what if i retire at 67"
    assert parser.fix_words("my retirment is at 65") == "my retirement is at 65"
    assert parser.fix_words("I retired in 2020 and my retiree club") == "I retired in 2020 and my retiree club"
    p = household.complete(Profile(age=50, state="CT", pay_per_year=100000.0, retire_age=65))
    assert pipeline.parse_whatif(parser.fix_words("what if i retier at 67"), p) == {"retire_age": 67}
    r = _ready_household()
    r = run("I'd like to retier at 66", r.profile)
    assert r.question.text == "Change your retirement age from 60 to 66?"


def test_an_ira_named_without_roth_is_pre_tax_and_adds_to_the_401ks():
    p = Profile(age=47)
    msg = "We have $330,000 in 401(k)s, $45,000 in a savings account and about $20,000 in an IRA."
    g = turn_guard.check_updates([
        _update("savings.pretax", 330000, "dollars", "$330,000 in 401(k)s"),
        _update("savings.roth", 20000, "dollars", "about $20,000 in an IRA"),
        _update("savings.cash", 45000, "dollars", "$45,000 in a savings account"),
        _update("savings.total", 395000, "dollars", msg.rstrip("."))], msg, p)
    assert g.facts["savings.pretax"] == 350000 and g.facts["savings.cash"] == 45000
    assert not g.facts.get("savings.roth") and not g.facts.get("savings.taxable")
