"""The example household on the first screen, the long version with a match, the match phrasings, the reply length (R18),
the partner's retirement row, and the two intake dead ends (R13, child cost)."""
import asyncio
import re
from pathlib import Path

import pytest

from app.agents import intake, parser_extra

LONG = (
    "I'm 45, a doctor in Connecticut, and I earn $310,000 a year. My wife is 43 and stays home with our 3 kids, ages 13, 10 and 6. "
    "We have 2 dogs. We own our home, worth about $850,000, with $420,000 left on the mortgage at 3.5%, and we pay $3,600 a month. "
    "We spend about $12,000 a month in all. We have $640,000 in my 401(k), $90,000 in Roth IRAs, $150,000 in a brokerage account and $40,000 in cash. "
    "I put $23,000 a year into my 401(k), and the hospital matches 4% of pay. We owe $18,000 on a car loan at 6%. "
    "The oldest will go to a state school, the middle one to a private college with us paying half, and the youngest won't go to college. "
    "I'd like to retire at 62.")


def run(text, profile=None):
    return asyncio.run(intake.run(text, profile or {}, use_ai=False))


def example_text():
    src = (Path(__file__).resolve().parents[1] / "web" / "src" / "examples.ts").read_text(encoding="utf-8")
    return "".join(re.findall(r'"([^"]*)"', src.split("EXAMPLE_TEXT", 1)[1]))


def rows(r):
    return {f.key: f for f in r.fields}


def test_long_example_reads_every_figure_including_the_match():
    r = run(LONG)
    p = r.profile
    assert (p["age"], p["partner_age"], p["pay_per_year"], p["retire_age"], p["state"]) == (45, 43, 310000, 62, "CT")
    assert p["partner_pay_per_year"] == 0
    assert p["savings"]["pretax"] == 640000 and p["savings"]["roth"] == 90000 and p["savings"]["taxable"] == 150000 and p["savings"]["cash"] == 40000
    assert [c["age"] for c in p["children"]] == [13, 10, 6]
    assert p["pets"] == [{"kind": "dog", "count": 2}]
    assert p["saving"]["contrib_you"] == 23000 and p["saving"]["match_cap"] == 0.04 and p["saving"]["match_rate"] == 1.0
    assert p["debts"][0]["balance"] == 18000
    assert rows(r)["match"].source == "you said"


def test_long_reply_is_short_and_still_discloses_assumptions():
    r = run(LONG)
    assert len(r.reply.split()) <= 80, r.reply
    assert re.search(r"I noted \d+ facts from your message", r.reply)
    assert "in the panel on the right" in r.reply
    for want in ("you are 45", "$310,000", "retire at 62"):
        assert want in r.reply
    assert re.search(r"typical figures", r.reply) and re.search(r"\d+ more", r.reply)      # R1: the disclosure stays, with its count
    assert r.question is not None


def test_short_messages_keep_the_full_readback():
    r = run("I'm 45, a doctor in Ohio, with 2 kids, 12 and 9")
    assert "facts from your message" not in r.reply
    assert "you are 45" in r.reply


def test_short_example_reads_figures_and_names_each_estimate():
    r = run(example_text())
    p = r.profile
    assert (p["age"], p["partner_age"], p["pay_per_year"], p["retire_age"], p["state"]) == (45, 43, 310000, 62, "CT")
    assert sum(p["savings"][k] for k in ("pretax", "roth", "taxable", "cash")) == 920000
    assert p["home"]["value"] == 850000 and p["home"]["mortgage_balance"] == 420000
    assert len(r.reply.split()) <= 80, r.reply
    f = rows(r)
    for key in ("spending_now_per_year", "savings"):       # spending and the split: proposed and marked
        assert f[key].source in ("estimate", "assumed"), key
    assert f["spending_now_per_year"].display or f["spending_now_per_year"].value
    assert not any(x.value in (None, "") and x.source == "you said" for x in f.values())


@pytest.mark.parametrize("text,rate,cap", [
    ("I earn $100,000. I put $10,000 a year into my 401(k) and the hospital matches 4% of pay.", 1.0, 0.04),
    ("My employer matches 4% of pay.", 1.0, 0.04),
    ("The company matches 3% of my pay.", 1.0, 0.03),
    ("I get a 4% match.", 1.0, 0.04),
    ("They match 50% up to 6%.", 0.5, 0.06),
    ("My employer matches dollar for dollar up to 5%.", 1.0, 0.05),
])
def test_match_phrasings(text, rate, cap):
    s = parser_extra.parse_saving(text, False)
    assert s["saving.match_rate"] == rate and s["saving.match_cap"] == cap


def test_partner_with_no_pay_shows_no_retirement_age_row():
    r = run(LONG)
    assert "partner_retire_age" not in rows(r)
    r2 = run("I'm 45, earn $90,000. My wife is 43 and works, she makes $60,000.")
    assert "partner_retire_age" in rows(r2) or r2.profile["partner_retire_age"] is None


def test_no_pets_is_recorded_and_only_children_are_asked_next():
    r = run("I'm 50, single, in Ohio, earn $90,000, rent, retire at 65, have $300,000 saved, no debts")
    for _ in range(6):
        if r.question and "children" in r.question.text:
            break
        r = run("skip", r.profile)
    assert r.question and "children" in r.question.text
    r = run("No pets", r.profile)
    assert "no pets" in r.reply
    assert r.question.text.startswith("And children?") and "pets" not in r.question.text
    r = run("No children", r.profile)
    assert r.question is None or "children" not in r.question.text


def test_child_added_in_the_editor_adds_a_typical_cost():
    r = run("I'm 40, earn $90,000, own a home, we spend $4,000 a month, 1 child aged 5, retire at 65, $200,000 saved")
    p = r.profile
    assert p["sources"].get("spending_now_per_year") == "you said" and len(p["children"]) == 1
    before = p["spending_now_per_year"]
    p["children"].append({"age": 0, "college": True})
    r2 = run("Updated your children: 2 children, aged 5 and 0", p)
    assert r2.profile["spending_now_per_year"] > before
    assert "I added about" in r2.reply and "new child" in r2.reply
    assert "spending_now_per_year" in r2.profile["notes"]


def test_build_line_once_when_ready_and_after_confirm_questions():
    r = run("I'm 50, single, in Ohio, earn $90,000, rent, retire at 65, have $300,000 saved, no debts, no kids, no pets, we spend $4,000 a month")
    p = r.profile
    for _ in range(8):
        if "Build my plan" in r.reply:
            break
        if not r.question:
            break
        r = run("yes" if r.profile.get("asking", "").startswith("confirm") else "skip", r.profile)
    assert "Build my plan" in r.reply and "check the figures on the right".lower() in r.reply.lower()
    assert "ask you to check the figures once before building" in r.reply and "once more" not in r.reply
    assert not (r.profile.get("asking") or "").startswith("confirm")     # a confirm question is asked first, the build line follows
    again = run("I also have a dog", r.profile)
    assert "That's enough to build your plan" not in again.reply         # said once


# ---- the example household through follow-up turns (mortgage kept, estimates approved, figures named)
def _start():
    """The example as the app has it after its first read. The rule parser alone misses the kids, the wife's pay and the mortgage, which the
    model's read supplies in the app, so those three are added here the way the model would give them."""
    r = run(example_text())
    p = intake.Profile.model_validate(r.profile)
    intake.apply(p, {"children.ages": [13, 10, 6], "partner_pay_per_year": 0.0, "home.has_mortgage": True})
    return intake._respond(p, "x", p.asking)


def _walk(turns):
    r = _start()
    out = [r]
    for t in turns:
        r = run(t, r.profile)
        out.append(r)
    return out


def _mortgage_asked(r):
    return bool(r.question) and "mortgage payment" in r.question.text


@pytest.mark.parametrize("answer", ["No other debts", "no other loans", "Nothing else", "none other", "No other debts, thanks", "nope, nothing else"])
def test_other_debts_never_clear_the_mortgage(answer):
    r = _walk(["That's about right", answer])[-1]
    h = r.profile["home"]
    assert h["mortgage_balance"] == 420000 and h["mortgage_payment"] > 0 and h["value"] == 850000
    assert "not $420,000" not in r.reply and "$0 left" not in r.reply
    assert _mortgage_asked(r)                            # the pending question is kept, not dropped
    assert "debts" not in r.missing                      # and the answer was recorded for the debts question


@pytest.mark.parametrize("answer", ["No mortgage", "it's paid off", "we own it outright", "No, it's paid off"])
def test_clearing_a_stated_mortgage_needs_a_yes(answer):
    r = _walk(["That's about right"])[-1]
    asked = run(answer, r.profile)
    assert asked.profile["home"]["mortgage_balance"] == 420000      # not cleared yet
    assert asked.question and asked.question.text == "Clear the $420,000 mortgage?"
    yes = run("Yes", asked.profile)
    assert yes.profile["home"]["mortgage_balance"] == 0 and yes.profile["home"]["mortgage_payment"] == 0
    no = run("No", asked.profile)
    assert no.profile["home"]["mortgage_balance"] == 420000 and "kept" in no.reply
    assert _mortgage_asked(no)
    other = run("No other debts", asked.profile)                     # something else: still not cleared
    assert other.profile["home"]["mortgage_balance"] == 420000


def test_bare_no_to_an_unstated_mortgage_still_means_paid_off():
    r = run("I'm 45 in Ohio, earn $90,000, own my home, no kids, retire at 65, $200,000 saved")
    for _ in range(4):
        if r.question and "mortgage" in r.question.text.lower():
            break
        r = run("That's about right", r.profile)
    assert r.question and "mortgage" in r.question.text.lower()
    r2 = run("No", r.profile)
    assert r2.profile["home"]["mortgage_balance"] == 0


@pytest.mark.parametrize("yes", ["That's about right", "yes", "ok", "fine", "sounds right", "Yes, that's about right"])
def test_yes_approves_the_spending_estimate_and_names_it(yes):
    rs = _walk(["That's about right", "No other debts", "That's about right"])
    r = rs[-1]
    assert r.question and "spend" in r.question.text and "$166,000" in r.question.text      # the estimate is in the question
    out = run(yes, r.profile)
    assert "Good. I will use $166,000 a year for your spending now." in out.reply
    assert "different question" not in out.reply
    assert out.profile["sources"]["spending_now_per_year"] == "you said" and out.profile["spending_now_per_year"] == 166000
    assert "spending_now_per_year" not in out.missing


def test_a_bare_ok_names_the_figure():
    r = _walk(["That's about right", "No other debts", "That's about right"])[-1]
    out = run("ok", r.profile)
    assert "$166,000" in out.reply and "a typical figure for your" not in out.reply


def test_an_estimated_payment_follows_the_one_mortgage_rule():
    from app.tools import costs
    r = _start()
    h = r.profile["home"]
    bal, pay = costs.typical_mortgage(intake.Profile.model_validate(r.profile))
    assert h["mortgage_balance"] == 420000 == bal and h["mortgage_payment"] == pay
    end = rows(r)["mortgage_end"].value
    assert 19 <= end["years_left"] <= 21              # about 20 years left at 45, not 30


def test_home_row_marks_only_the_estimated_part():
    r = _start()
    home = rows(r)["home"]
    assert home.source == "you said"                  # the value and balance were stated
    assert "(estimate)" in home.display and home.display.count("(estimate)") == 1
    assert "$850,000" in home.display and "$420,000 left on the mortgage" in home.display.replace("(estimate)", "")
    assert "payment is an estimate" in home.note.lower()
    typed = run("$3,100 a month", _walk(["That's about right"])[-1].profile)
    assert "(estimate)" not in rows(typed)["home"].display and typed.profile["home"]["mortgage_payment"] == 3100


def test_yes_approves_the_estimated_mortgage_payment():
    r = _walk(["That's about right"])[-1]
    assert _mortgage_asked(r) and "estimated" in r.question.text
    out = run("That's about right", r.profile)
    assert re.search(r"Good\. I will use \$[\d,]+ a month for your mortgage payment\.", out.reply)
    assert "(estimate)" not in rows(out)["home"].display and out.profile["home"]["mortgage_balance"] == 420000


def test_full_example_walk_ends_ready_with_everything_intact():
    rs = _walk(["That's about right", "No other debts", "That's about right", "That's about right", "ok"])
    for r in rs[1:]:
        assert "different question" not in r.reply, r.reply
        assert "a typical figure for your" not in r.reply, r.reply
        p = r.profile
        assert p["home"]["mortgage_balance"] == 420000 and p["home"]["value"] == 850000
        assert [c["age"] for c in p["children"]] == [13, 10, 6] and p["partner_pay_per_year"] == 0
    last = rs[-1]
    p = last.profile
    assert last.ready and last.missing == [] and p["spending_now_per_year"] == 166000
    assert p["sources"]["spending_now_per_year"] == "you said" and p["pay_per_year"] == 310000


@pytest.mark.parametrize("yes", ["Yes, that's about right", "yes", "Yes", "ok", "Yes."])
def test_every_yes_form_approves_the_estimated_mortgage_payment(yes):
    r = _walk(["That's about right"])[-1]
    out = run(yes, r.profile)
    assert re.search(r"Good\. I will use \$[\d,]+ a month for your mortgage payment\.", out.reply), out.reply
    assert "still need this one" not in out.reply and not _mortgage_asked(out)
