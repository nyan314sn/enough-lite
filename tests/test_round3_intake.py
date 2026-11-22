"""Loop round 3, audit B intake fixes: one test per transcript case. Rule path only (no model calls)."""
import asyncio

import pytest

from app.agents import intake

HOUSEHOLD = ("I'm 45, a teacher in Ohio, married, my husband is 47, no kids, we have 200k saved, we own our home outright, no debts, "
             "I make $120,000, retire at 65")


def step(text, prof):
    r = asyncio.run(intake.run(text, prof, use_ai=False))
    assert r.reply.strip(), f"empty reply to {text!r}"
    return r


def play(turns, prof=None):
    prof, out = prof or {}, []
    for t in turns:
        r = step(t, prof)
        prof = r.profile
        out.append(r)
    return out


def household_at_more():
    rs = play([HOUSEHOLD])
    prof = rs[-1].profile
    for _ in range(8):
        r = rs[-1]
        if r.question and r.question.text.startswith("That is enough"):
            return r
        chip = (r.question.quick_answers[0] if r.question and r.question.quick_answers else "ok")
        rs.append(step(chip, r.profile))
    return rs[-1]


@pytest.fixture(scope="module")
def at_more():
    return household_at_more()


@pytest.mark.parametrize("answer", ["$10,000 a year", "$30,000 a year", "12000", "$20,000", "$500 a month"])
def test_saving_answers_are_accepted(at_more, answer):
    r = step("Add saving", at_more.profile)
    assert r.profile["asking"] == "saving"
    r2 = step(answer, r.profile)
    assert "catch that" not in r2.reply and "still need this one" not in r2.reply, r2.reply
    assert r2.profile["saving"]["contrib_you"] is not None
    assert r2.profile["savings"]["pretax"] == at_more.profile["savings"]["pretax"]      # the balance is untouched
    assert r2.profile["sources"].get("saving") == "you said"


def test_ten_percent_of_pay_is_a_saving_rate_not_a_pay_change(at_more):
    r = step("Add saving", at_more.profile)
    r2 = step("10% of pay", r.profile)
    assert "change your pay" not in r2.reply
    assert r2.profile["save_rate"] == pytest.approx(0.10)
    assert r2.profile["pay_per_year"] == at_more.profile["pay_per_year"]
    assert r2.profile["sources"].get("save_rate") == "you said"


def test_yearly_saving_pencil_question_names_the_total_and_its_parts(at_more):
    q = step("Add saving", at_more.profile).question
    assert "each year in all" in q.text and "401(k)" in q.text and "match" in q.text


def test_typing_a_figure_for_yearly_saving_does_not_overwrite_the_balance(at_more):
    before = at_more.profile["savings"]
    r = step("Change Yearly saving to: 30000", at_more.profile)
    assert r.profile["savings"] == before
    assert r.profile["saving"]["contrib_you"] == 30000


# ---------------------------------------------------------------- P1-1: an age cannot be guessed
@pytest.mark.parametrize("word", ["I don't know", "skip", "not sure", "dunno", "idk"])
def test_idk_on_the_age_question_says_once_that_the_plan_needs_it_and_shows_the_age_chips(word):
    r0 = step("I'm a nurse in Ohio", {})
    assert r0.profile["asking"] == "age"
    r = step(word, r0.profile)
    assert "needs it" in r.reply and "typical figure" not in r.reply and "still need this one" not in r.reply
    assert r.question.text == "How old are you?" and r.question.quick_answers == ["35", "45", "55", "65"]
    assert r.profile["age"] is None and r.profile["asking"] == "age"


def test_repeated_idk_never_alternates_between_typical_and_still_need():
    r = step("I'm a nurse in Ohio", {})
    seen = set()
    for w in ["I don't know", "skip", "I don't know", "not sure", "dunno", "idk"] * 2:
        r = step(w, r.profile)
        seen.add(r.reply)
        assert r.question.quick_answers == ["35", "45", "55", "65"]
    assert len(seen) == 1 and "typical figure" not in next(iter(seen))
    assert step("52", r.profile).profile["age"] == 52


@pytest.mark.parametrize("asking_text,skip_word", [("I'm 50", "idk"), ("I'm 50 in Ohio", "dunno")])
def test_the_other_required_questions_move_on_with_a_marked_typical_figure(asking_text, skip_word):
    r = step(asking_text, {})
    for _ in range(3):                              # whichever question is open, skipping never loops
        if r.ready:
            break
        before = r.profile["asking"]
        r = step(skip_word, r.profile)
        assert r.profile["asking"] != before or r.ready or before is None
        assert "still need this one" not in r.reply


# ---------------------------------------------------------------- P1-3: a big mortgage payment
MORT = ("I'm 45, an accountant in Illinois, married, my wife is 43. We make $160,000, have $300,000 saved, spend $8,000 a month. "
        "We own our home with a $300,000 mortgage at 4%. Retire at 62.")


def _at_mortgage_payment():
    r = step(MORT, {})
    for _ in range(6):
        if r.profile["asking"] == "mortgage":
            return r
        chip = r.question.quick_answers[0] if r.question and r.question.quick_answers else "ok"
        r = step(chip, r.profile)
    return r


def test_confirmed_huge_mortgage_payment_never_makes_retirement_spending_negative():
    r = _at_mortgage_payment()
    assert r.profile["asking"] == "mortgage"
    r = step("$12,500 a month", r.profile)
    assert "Is $12,500 a month right" in r.question.text
    r = step("yes", r.profile)
    spend = r.profile["spending_per_year"]
    assert spend is not None and spend > 0 and "$-" not in r.reply and "-$" not in r.reply
    from app import household
    from app.schemas import Profile
    full = household.complete(Profile.model_validate(r.profile))
    assert full.spending_per_year > 0


def test_retyping_the_same_mortgage_payment_is_accepted():
    r = _at_mortgage_payment()
    r = step("$12,500 a month", r.profile)
    r = step("$12,500 a month", r.profile)          # retyped while the check is open
    assert r.profile["home"]["mortgage_payment"] == 12500 and "still need this one" not in r.reply
    r = _at_mortgage_payment()
    r = step("$12,500 a month", r.profile)
    r = step("yes", r.profile)
    r = step("$12,500 a month", r.profile)          # retyped after the yes
    assert r.profile["home"]["mortgage_payment"] == 12500 and "still need this one" not in r.reply
    assert "Is $12,500 a month right" not in (r.question.text if r.question else "")


# ---------------------------------------------------------------- P1-4: a partner's pension with its start age
def test_partner_pension_with_start_age_and_the_right_person():
    r = step("Hi, I'm Maria, 43, a pediatrician in Massachusetts, married to David who's 46 and is a high school teacher. "
             "David will get a teacher pension of about $2,500 a month at 60.", {})
    pens = r.profile["pensions"]
    assert len(pens) == 1 and pens[0]["who"] == "partner" and pens[0]["per_year"] == 30000 and pens[0]["start_age"] == 60
    assert r.profile["sources"]["pensions"] == "you said"
    assert "your partner has a pension of $30,000 a year from 60" in r.reply and "you have a pension" not in r.reply
    row = next(f for f in r.fields if f.key == "pensions")
    assert "from 60" in row.display and "start at 65" not in (row.note or "")


# ---------------------------------------------------------------- P2-5: labels
def test_private_college_row_does_not_say_assumed_public():
    r = step("I'm 43, a doctor in Ohio, married, my wife is 41, we have 2 kids aged 9 and 6. We want them in private college.", {})
    row = next((f for f in r.fields if f.key.startswith("college_")), None)
    assert row is not None and "private" in row.display
    assert "Assumed public" not in (row.note or "")


def test_no_duplicate_payment_sentence_after_a_tiny_payment():
    r = _at_mortgage_payment()
    r = step("$62", r.profile)
    assert "What is the monthly payment? What is the monthly mortgage payment?" not in (r.reply + " " + r.question.text)
    assert (r.reply + " " + r.question.text).count("monthly") <= 2 or r.reply.count("What is the monthly") == 0


def test_partner_retirement_age_default_is_sensible():
    from app.schemas import Profile
    from app.tools import costs
    p = Profile(age=40, partner_age=55, has_partner=True, retire_age=57)
    assert costs.partner_retire_age(p) == 65
    p = Profile(age=60, partner_age=58, has_partner=True, retire_age=65)
    assert costs.partner_retire_age(p) == 63
    p = Profile(age=60, partner_age=40, has_partner=True, retire_age=65)
    assert costs.partner_retire_age(p) == 65


def test_retiree_costs_a_year_is_you_said_like_spending_now():
    p = {"age": 70, "has_partner": False, "state": "OH", "retire_age": 67, "pay_per_year": 0, "savings": {"pretax": 400000, "roth": 0, "taxable": 0, "cash": 50000},
         "savings_known": True, "home": {"owns": True}, "social_security_per_year": 25200, "spending_now_per_year": 48000,
         "sources": {"age": "you said", "social_security_per_year": "you said", "spending_now_per_year": "you said"}}
    from app import household
    from app.schemas import Profile
    full = household.complete(Profile.model_validate(p))
    assert full.sources["spending_now_per_year"] == "you said" and full.sources["spending_per_year"] == "you said"


# ---------------------------------------------------------------- P2-8: a panel pencil during a pending confirm
def test_pencil_during_a_pending_confirm_switches_to_that_edit():
    rs = play(["I'm 45, a nurse in Ohio, single, no kids, 300k saved, I own my home outright, no debts, I make $90,000, retire at 65, we spend $5,000 a month"])
    r = rs[-1]
    guard = 0
    while not (r.profile["asking"] or "").startswith("confirm") and guard < 8:
        r = step(r.question.quick_answers[0] if r.question and r.question.quick_answers else "ok", r.profile)
        guard += 1
    assert (r.profile["asking"] or "").startswith("confirm"), r.profile["asking"]
    r2 = step("Add saving", r.profile)
    assert "different question" not in r2.reply
    assert r2.profile["asking"] == "saving" and "each year in all" in r2.question.text


# ---------------------------------------------------------------- audit C: split, derived figures, retractions, chips
def test_savings_split_with_the_rest_zero_replaces_the_split_and_ignores_the_apps_own_figure():
    r = step("I'm 44, a nurse in Pennsylvania, single, no kids or pets. I have $150,000 saved. I make $90,000. Retire at 65. "
             "I own my home outright, no debts. I spend $61,000 a year.", {})
    r = step("And the $4,000 you put in Roth is wrong, there's no Roth at all. Please fix that so the $150,000 is pre-tax $130k, "
             "taxable $10k and cash $6k, with the rest zero.", r.profile)
    s = r.profile["savings"]
    assert (s["pretax"], s["roth"], s["taxable"], s["cash"]) == (130000, 0, 10000, 6000)
    assert "$16,000" not in r.reply and r.profile["saving"]["contrib_you"] is None


def test_a_rejected_estimate_is_not_stored_as_another_figure():
    r = step("I'm 62. I have very little saved. Retire at 67.", {})
    r = step("West Virginia.", r.profile)
    r = step("Under $50k, I think. I work at a front desk and it's about $38,000 a year before tax. "
             "Also, the $37,000 spending number is way too high. I spend about $33,000 now.", r.profile)
    p = r.profile
    assert p["spending_now_per_year"] == 33000
    assert p["spending_per_year"] != 37000 and p["sources"].get("spending_per_year") != "you said"
    assert "spending in retirement at" in r.reply          # the derived figure moved, and the reply says so


def test_retraction_removes_the_debt_and_ends_the_question():
    r = step("I'm 62, a machinist in Arizona, single, 500k saved, I own my home outright. I owe $4,000 on my truck loan at 5%.", {})
    assert r.profile["debts"]
    r = step("Wait, I need to fix that. The truck is actually paid off, so I have no debts at all. And no kids or pets.", r.profile)
    assert r.profile["debts"] == []
    assert "How much is left" not in (r.question.text if r.question else "")


def test_retired_chip_at_the_partner_pay_question_leaves_my_pay_alone():
    r = step("I'm 47, a nurse in Ohio, married, my wife is 45, I earn $88,000, 300k saved, retire at 65", {})
    guard = 0
    while r.profile["asking"] != "partner_pay_per_year" and guard < 6:
        r = step(r.question.quick_answers[0], r.profile)
        guard += 1
    assert r.profile["asking"] == "partner_pay_per_year"
    r = step("Retired", r.profile)
    assert r.profile["pay_per_year"] == 88000 and r.profile["partner_pay_per_year"] == 0
    assert r.profile["notes"].get("retired") != "yes"


def test_teacher_pension_is_not_the_savings_figure():
    from app.agents import parser_extra
    out, _ = parser_extra.parse("I'm 50, a teacher in Ohio, married, my wife is 48, 300k saved, I have a teacher pension", None, True)
    assert not out.get("pensions")
    r = step("I'm 50, a teacher in Ohio, married, my wife is 48, 300k saved, I have a teacher pension", {})
    assert not r.profile["pensions"] and r.profile["notes"].get("pension_ask") == "yes"


@pytest.mark.parametrize("chip", ["Not sure, leave it out", "Not sure, estimate it", "Estimate it for me"])
def test_skip_phrases_at_the_pay_question_are_not_a_job(chip):
    from app.agents import parser
    assert "job" not in parser.parse(chip, asking="pay_per_year")
    assert "partner_job" not in parser.parse(chip, asking="partner_pay_per_year")
