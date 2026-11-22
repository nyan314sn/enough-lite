"""Intake items left after the product-rules re-check (2026-11-22)."""
import re

import pytest

from tests.test_example_household import _walk, run, rows, _mortgage_asked  # noqa: F401


@pytest.mark.parametrize("yes", ["Yes, that's about right", "yes", "Yes", "ok", "That's about right", "yes that's right", "Yes."])
def test_every_yes_approves_the_estimated_mortgage_payment(yes):
    r = _walk(["That's about right"])[-1]
    assert _mortgage_asked(r)
    out = run(yes, r.profile)
    assert re.search(r"Good\. I will use \$[\d,]+ a month for your mortgage payment\.", out.reply), out.reply
    assert not _mortgage_asked(out)
    assert "still need" not in out.reply


AFFIRM_CHIP = re.compile(r"\s*(?:yes\b|that'?s about right)", re.I)


def _chip_walk():
    """The example household: at every confirm-style question, every offered 'Yes ...' / 'That's about right' chip, clicked by its exact
    label, must move the plan on, and so must the same words typed."""
    from tests.test_example_household import _start
    r = _start()
    seen = 0
    for _ in range(12):
        if not r.question:
            break
        q = r.question
        chips = [c for c in q.quick_answers if AFFIRM_CHIP.match(c)]
        for chip in chips:
            for said in (chip, chip.split(",")[0].strip(), "yes", "Yes"):
                out = run(said, r.profile)
                assert "still need this one" not in out.reply, (q.text, said, out.reply)
                assert (out.question.text if out.question else None) != q.text, (q.text, said, out.reply)
            seen += 1
        pick = chips[0] if chips else ("No other debts" if "No other debts" in q.quick_answers else q.quick_answers[0])
        r = run(pick, r.profile)
    return seen


def test_every_yes_chip_in_the_example_walk_makes_progress():
    assert _chip_walk() >= 2


# ---- R7 on page 1: a stated figure for savings, children, the mortgage or a debt changes only on a yes
FIRST = ("I'm 52, an electrician in Ohio making $96,000. My wife Maria is 50 and teaches, making $58,000. We have $510,000 saved, "
         "own our home with no mortgage, no kids, spend $6,000 a month. I want to retire at 60.")


def _ready():
    r = run(FIRST)
    for _ in range(10):
        if r.ready:
            break
        cs = r.question.quick_answers if r.question else []
        r = run(cs[0] if cs else "skip", r.profile)
    assert r.ready
    return r


def test_new_savings_total_waits_for_a_yes():
    r = _ready()
    o = run("we saved 700000", r.profile)
    assert o.question.text == "Change your savings from $510,000 to $700,000?" and o.question.quick_answers == ["Yes", "No"]
    assert sum(o.profile["savings"][k] for k in ("pretax", "roth", "taxable", "cash")) == 510000
    assert "Got it" not in o.reply
    yes = run("Yes", o.profile)
    assert sum(yes.profile["savings"][k] for k in ("pretax", "roth", "taxable", "cash")) == 700000
    no = run("No", o.profile)
    assert sum(no.profile["savings"][k] for k in ("pretax", "roth", "taxable", "cash")) == 510000 and "kept your savings at $510,000" in no.reply


def test_three_kids_waits_for_a_yes_then_asks_the_ages():
    r = _ready()
    o = run("actually we have 3 kids", r.profile)
    assert o.question.text == "Change your children from no children to 3 children?" and o.profile["children"] == []
    yes = run("Yes", o.profile)
    assert len(yes.profile["children"]) == 3 and yes.question and "How old are your children" in yes.question.text
    ages = run("5, 8 and 12", yes.profile)
    assert [c["age"] for c in ages.profile["children"]] == [5, 8, 12] and ages.profile["sources"]["children"] == "you said"
    assert run("No", o.profile).profile["children"] == []


def test_set_my_age_changes_the_person_not_the_children():
    r = _ready()
    for said in ("set my age to 60", "change my age to 60", "my age is actually 60"):
        o = run(said, r.profile)
        assert o.question.text == "Change your age from 52 to 60?" and o.profile["age"] == 52 and o.profile["children"] == []
    o = run("set my age to 60", r.profile)
    assert run("Yes", o.profile).profile["age"] == 60 and run("No", o.profile).profile["age"] == 52


def test_new_mortgage_and_debt_figures_wait_for_a_yes():
    r = _walk(["That's about right"])[-1]          # the example household: $420,000 left, payment estimated
    r = run("$2,900 a month", r.profile)
    assert r.profile["home"]["mortgage_balance"] == 420000
    o = run("my mortgage balance is now 300000", r.profile)
    assert "Change your mortgage balance from $420,000 to $300,000?" == o.question.text and o.profile["home"]["mortgage_balance"] == 420000
    assert run("Yes", o.profile).profile["home"]["mortgage_balance"] == 300000
    d = run("I owe 20000 on a car loan", r.profile)
    assert d.profile["debts"][0]["balance"] == 20000
    o2 = run("my car loan is 35000", d.profile)
    assert o2.question.text == "Change your car debt from $20,000 to $35,000?" and o2.profile["debts"][0]["balance"] == 20000
    assert run("Yes", o2.profile).profile["debts"][0]["balance"] == 35000


# ---- R4: named children and a pet inside a long message
R4 = ("I'm 41, divorced, a paralegal in Seattle, Washington making $67,000. I have two kids: Ava is 9 and Ben is 4. "
      "Ava will go to a private college and I will pay half; Ben will go to community college. I have a beagle. "
      "I owe $22,000 on student loans at 5% and $6,000 on a credit card at 22%. I rent for $1,900 a month and have $60,000 saved. "
      "I want to retire at 64.")


def test_named_children_get_their_own_college_and_the_pet_is_kept():
    p = run(R4).profile
    ava, ben = sorted(p["children"], key=lambda c: -c["age"])
    assert (ava["age"], ava["college_type"], ava["college_share"]) == (9, "private", 0.5)
    assert (ben["age"], ben["college_type"]) == (4, "public")
    assert p["pets"] == [{"kind": "dog", "count": 1}]


@pytest.mark.parametrize("text,pets", [("I have a beagle", [{"kind": "dog", "count": 1}]), ("we have two poodles", [{"kind": "dog", "count": 2}]),
                                       ("our tabby", [{"kind": "cat", "count": 1}]), ("I work in a lab", None)])
def test_a_breed_is_a_pet(text, pets):
    p = run(f"I'm 41 in Ohio. {text}.").profile
    assert (p["pets"] or None) == pets


# ---- R9: money that may come to the person is information only
@pytest.mark.parametrize("said,amount,gift", [("My aunt may leave me a house worth 200k", 200000, False), ("A $50,000 gift", 50000, True),
                                              ("I expect a $50,000 gift from my parents next year", 50000, True), ("I may inherit 300k", 300000, False)])
def test_possible_inheritance_or_gift_is_information_only(said, amount, gift):
    r = _ready()
    o = run(said, r.profile)
    p = o.profile
    assert p["inheritance"]["amount"] == amount and p["inheritance"]["count"] is False and p["inheritance"]["gift"] is gift
    assert p["goals"].get("legacy") in (None, 0) and "you want to leave" not in o.reply
    assert sum(p["savings"][k] for k in ("pretax", "roth", "taxable", "cash")) == 510000        # not savings
    row = rows(o)["inheritance"]
    assert "information only" in row.display and ("gift" in row.label.lower()) is gift


def test_leaving_money_to_kids_is_still_a_legacy_goal():
    o = run("I want to leave $200,000 to my kids", _ready().profile)
    assert o.profile["goals"]["legacy"] == 200000 and not o.profile.get("inheritance")


# ---- R1 P2 (a renter who gives no rent) and P3 (one child, "age 12")
def test_renter_with_no_rent_shows_the_states_typical_rent_as_an_estimate():
    r = run("I'm 41, a paralegal in Seattle, Washington making $67,000. I rent. I have $60,000 saved and want to retire at 64.")
    home = rows(r)["home"]
    assert re.search(r"Rent, about \$[\d,]+ a month \(estimate: the typical rent in WA, HUD\)", home.display), home.display
    typed = run("my rent is $1,900 a month", r.profile)
    assert rows(typed)["home"].display == "Rent, $1,900 a month"


def test_one_child_reads_age_not_ages():
    one = run("I'm 40 in Ohio with 1 child, age 12.")
    assert rows(one)["children"].display == "1 child, age 12"
    two = run("I'm 40 in Ohio with 2 kids, ages 12 and 9.")
    assert rows(two)["children"].display == "2 children, ages 12 and 9"
