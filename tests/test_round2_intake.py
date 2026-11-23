"""Loop round 2 intake fixes: one test per transcript case (simulated users C, UI audit B). Rule path only (no model calls)."""
import asyncio

from app.agents import intake
from app.agents import intake_round2 as r2

BASE = "I'm 45, a nurse in Ohio, single, no kids, 300k saved"
OWNER = "I'm 45, a nurse in Ohio, single, I own my home outright, no debts, 300k saved"
MORT = "I'm 45, a nurse in Ohio, single, no kids, 300k saved, I own my home with a mortgage"


def play(turns, profile=None):
    prof, out = profile or {}, []
    for t in turns:
        r = asyncio.run(intake.run(t, prof, use_ai=False))
        prof = r.profile
        out.append(r)
        assert r.reply.strip(), f"empty reply to {t!r}"
    return out


def words(s):
    return len(s.split())


# ---------------------------------------------------------------- C P0-1 (p13)
def test_what_does_the_number_do_gets_one_answer_and_the_privacy_paragraph_comes_once():
    rs = play(["I'm 50 in Illinois, single", "skip",
               "Before I give you a savings number, tell me what the plan does with it and whether I get to see it first.",
               "Who sees my data? Is it stored?", "Who sees my data? Is it stored?"])
    use = rs[2].reply
    assert "draws on" in use and "before the plan is built" in use and "browser tab" not in use
    assert words(use) < 40
    privacy = [r for r in rs if r2.used_privacy(r.reply)]
    assert len(privacy) == 1                      # the paragraph once; later a short pointer
    assert "covered that above" in rs[4].reply


def test_third_time_the_same_question_comes_back_a_typical_figure_is_offered():
    rs = play(["I'm 50 in Illinois, single", "skip", "Why do you need that?", "Why do you need that?", "Why do you need that?"])
    chips = rs[-1].question.quick_answers
    assert chips[0].startswith("Use this: about $") and "Use this" in rs[-1].reply
    assert rs[1].question.quick_answers[0] != chips[0]
    # pressing it stores the figure as the person's own
    r = play([chips[0]], rs[-1].profile)[0]
    assert r.profile["savings_known"] and r.profile["savings"]["pretax"] > 0
    assert "typical figure" in r.reply


# ---------------------------------------------------------------- C P0-2 (p14)
def test_complaint_about_the_apps_figure_explains_it_and_stores_nothing():
    rs = play(["I'm 59, drive a bus in North Carolina, and I make about $76,000 a year. I want to retire at 64.",
               "Where did $33,600 come from? Fix it.",
               "I never said $33,600 was my savings."])
    ss = rs[0].profile["social_security_per_year"]
    assert round(ss) == 33600 and rs[0].profile["sources"].get("social_security_per_year") != "you said"
    for r in rs[1:]:
        assert "my estimate of your household Social Security" in r.reply and "Tell me the right figure" in r.reply
        assert not r.profile["savings_known"] or r.profile["savings"]["pretax"] == 0
        assert r.profile["sources"].get("social_security_per_year") != "you said"
        assert "I mean everything put away" not in r.reply
    assert rs[-1].question.text == rs[0].question.text      # the pending question stays


# ---------------------------------------------------------------- C P0-3 (h07)
def _at_spending():
    rs = play(["I'm 56, a project manager in Texas, single, no kids, I own my home outright, no debts, 400k saved, retire at 65, I make $90,000",
               "That's about right", "No other debts"])
    assert rs[-1].profile["asking"] == "spending_now_per_year", rs[-1].profile["asking"]
    return rs[-1].profile


def test_dont_know_and_estimate_phrases_approve_the_typical_figure():
    for phrase in ["I don't know", "use typical", "click the estimate one", "whatever is normal",
                   "I'm not sure, honestly. My wife does the budget. Maybe click the estimate one?"]:
        r = play([phrase], _at_spending())[0]
        assert r.profile["asking"] != "spending_now_per_year", phrase
        assert "spending_now_per_year" not in r.missing, phrase
        assert r.reply and "typical figure" in r.reply, (phrase, r.reply)


def test_spending_estimate_click_becomes_the_persons_own_figure():
    r = play(["I'm not sure. Maybe click the estimate one?"], _at_spending())[0]
    assert r.profile["sources"].get("spending_now_per_year") == "you said" and "yours to change" in r.reply
    r = play(["I don't know"], _at_spending())[0]       # "I don't know": the figure is used and named, still marked typical
    assert "$" in r.reply and "typical figure" in r.reply


def test_empty_reply_gets_the_fixed_fallback_and_the_question(monkeypatch):
    monkeypatch.setattr(intake, "_reask_line", lambda key: "")
    r = play(["I'm 50 in Illinois, single", "zzz qqq"])[-1]
    assert r.reply.startswith(r2.FALLBACK) and r.question.text in r.reply


def test_range_is_stored_at_the_middle_and_the_reply_says_so():
    r = play(["I'm 45 in Ohio, single", "$50k to $100k"])[-1]
    assert r.profile["pay_per_year"] == 75000 and "middle of that range" in r.reply and "$75,000" in r.reply
    r = play(["I'm 45, a nurse in Ohio, single", "$50k to $100k"])[-1]
    assert "middle of that range, $75,000" in r.reply
    assert round(r.profile["savings"]["pretax"] + r.profile["savings"]["roth"] + r.profile["savings"]["taxable"] + r.profile["savings"]["cash"]) == 75000


def test_range_click_echoes_the_right_midpoint_for_pay():
    rs = play(["I'm 45 in Utah, single", "UT", "$100k to $200k"])
    assert rs[-1].profile["pay_per_year"] == 150000 and "$150,000" in rs[-1].reply and "guess" in rs[-1].reply


# ---------------------------------------------------------------- C P0-6
def test_teenagers_is_age_15_with_a_stated_assumption_and_a_flag():
    rs = play([OWNER.replace("single", "single, I have 1 child"), "That's about right", "Teenagers"])
    r = rs[-1]
    assert r.profile["children"][0]["age"] == 15
    assert r.profile["sources"]["children"] == "assumed" and "assumed" in r.reply and "15" in r.reply
    f = next(x for x in r.fields if x.key == "children")
    assert f.source == "assumed"
    assert "children" not in r.missing          # no endless re-asking


def test_a_list_of_three_ages_stores_three_children():
    rs = play([OWNER, "That's about right", "I have kids", "11 9 6 k"])
    assert [c["age"] for c in rs[-1].profile["children"]] == [11, 9, 6]
    rs = play([OWNER + ", 3 kids", "That's about right", "11, 9, 6"])
    assert [c["age"] for c in rs[-1].profile["children"]] == [11, 9, 6]


def test_way_off_is_a_rejection_not_a_figure():
    rs = play(["I'm 45, a nurse in Ohio, single", "Ha, $50k is way off"])
    r = rs[-1]
    assert not r.profile["savings_known"] and "not right" in r.reply
    assert r.question.text.startswith("About how much have you saved")      # the pending question stays
    r = play(["I'm 45, a nurse in Ohio, single", "Ha, $50k is way off. I have 430k in the 401k and 70k in a brokerage"])[-1]
    assert round(r.profile["savings"]["pretax"] + r.profile["savings"]["taxable"]) == 500000
    r = play(["I'm 45, a nurse in Ohio, single", "Ha, $50k is way"])[-1]
    assert not r.profile["savings_known"]


# ---------------------------------------------------------------- B P1-6 / P1-8 / P1-9
def test_bare_number_goes_only_to_the_pending_field_and_must_be_plausible():
    rs = play([MORT, "That's about right", "62"])
    assert rs[-1].profile["age"] == 45 and "too small" in rs[-1].reply and rs[-1].profile["asking"] == "mortgage"
    r = play(["$62"], rs[-1].profile)[0]
    assert r.profile["home"]["mortgage_payment"] != 62 and "too small" in r.reply
    # a bare 62 at a question that is not about age never becomes the age
    rs = play([MORT, "That's about right", "62"])
    assert rs[-1].profile["age"] == 45


def test_huge_mortgage_payment_is_confirmed_before_it_is_kept():
    rs = play([MORT, "That's about right", "$12,500 a month, $150,000 left"])
    r = rs[-1]
    assert r.profile["home"]["mortgage_payment"] != 12500 and "Yes, $12,500 a month" in r.question.quick_answers
    yes = play(["Yes, $12,500 a month"], r.profile)[0]
    assert yes.profile["home"]["mortgage_payment"] == 12500
    no = play(["No, let me retype it"], r.profile)[0]
    assert no.profile["home"]["owns"] is True and no.profile["home"]["mortgage_balance"] == 150000 and "monthly" in no.question.text.lower()


def test_payment_over_60_percent_of_pay_is_confirmed():
    rs = play(["I'm 45, a nurse in Ohio making $60,000, single, no kids, 300k saved, I own my home with a mortgage", "That's about right",
               "$4,000 a month, $200,000 left"])
    assert "over 60% of your monthly pay" in rs[-1].reply


def test_student_loans_with_no_amount_asks_the_balance_and_takes_no_other_figure():
    rs = play([OWNER.replace("300k saved", "40k saved"), "That's about right"])
    r = play(["I have $8,000 saved and student loans"], rs[-1].profile)[0]
    assert not r.profile["debts"] and r.profile["asking"] == "debts_detail" and "How much is left" in r.question.text
    r2_ = play(["about 20k"], r.profile)[0]
    assert r2_.profile["debts"][0]["balance"] == 20000


# ---------------------------------------------------------------- C P1
def test_savings_not_asked_again_after_a_total():
    r = play(["I'm 56 in Texas, single", "I have about $500k total, $380k pretax, $50k Roth, $90k taxable, $30k cash"])[-1]
    assert "savings" not in r.missing and "saved in all" not in (r.question.text if r.question else "")


def test_home_value_is_acknowledged_and_the_rate_update_says_what_it_changes():
    r = play([MORT + ". House is worth around 330k, $45,000 left, payment about $1300 a month"])[-1]
    assert "worth about $330,000" in r.reply
    r = play([MORT, "That's about right", "$150,000 left, $1,500 a month"])[-1]
    assert "mortgage rate, which sets when the mortgage ends" in r.reply


# ---------------------------------------------------------------- B P2
def test_skip_is_accepted_on_the_investment_split_question():
    rs = play([BASE, "skip"])
    assert rs[0].profile["asking"] == "confirm_split"
    r = rs[-1]
    assert "I keep my split of your" in r.reply and "marked estimate" in r.reply and r.profile["asking"] != "confirm_split"


def test_first_reply_is_short():
    r = play(["I'm 45, a nurse in Ohio, single, I own my home with a mortgage, 300k saved. I want to retire at 62 and spend $5,000 a month."])[0]
    assert words(r.reply) <= 80, words(r.reply)
    r = play(["I'm 59, drive a bus in North Carolina, and I make about $76,000 a year. I want to retire at 64."])[0]
    assert words(r.reply) <= 80 and "marked in the panel" in r.reply


def test_widow_asking_about_a_husbands_age_gets_a_kind_plain_reply():
    r = play(["I'm 66 in Ohio, single, school secretary", "what about my husband's age? He passed three years ago"])[-1]
    assert "I am sorry about your husband" in r.reply and "only your age counts" in r.reply
    assert "If you tell me his age" not in r.reply


def test_notes_and_told_survive_the_round_trip():
    rs = play(["I'm 50 in Illinois, single", "skip"])
    assert "For the rest, I use typical figures" in rs[0].reply and "For the rest, I use typical figures" not in rs[1].reply
