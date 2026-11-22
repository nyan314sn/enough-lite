"""Every 'estimate it' chip puts a number in the panel, marked estimate, and says it in the reply (rule path, no model calls)."""
import asyncio
import re

from app.agents import intake

OWN = "I'm 45, a nurse in Ohio, single, no kids, 300k saved, I own my home"


def reach(first, chip, advance="Yes"):
    r = asyncio.run(intake.run(first, {}, use_ai=False))
    for _ in range(8):
        if r.question and chip in r.question.quick_answers:
            break
        r = asyncio.run(intake.run(advance, r.profile, use_ai=False))
    assert r.question and chip in r.question.quick_answers, r.question.text if r.question else None
    return asyncio.run(intake.run(chip, r.profile, use_ai=False))


def row(r, key):
    return next(f for f in r.fields if f.key == key)


def test_mortgage_chip_stores_balance_and_payment_marked_estimate():
    r = reach(OWN, "Not sure, estimate it")
    h = r.profile["home"]
    assert h["mortgage_balance"] > 0 and h["mortgage_payment"] > 0
    assert r.profile["sources"]["home"] == "estimate"
    f = row(r, "home")
    assert f.source == "estimate" and "left on the mortgage" in f.display and "a month" in f.display
    assert f"${h['mortgage_balance']:,.0f}" in r.reply and f"${h['mortgage_payment']:,.0f}" in r.reply and "estimate" in r.reply
    assert "mortgage" not in (r.question.text.lower() if r.question and "besides" not in r.question.text else "")


def test_mortgage_estimate_uses_home_value_when_given():
    r = reach(OWN + " worth $400,000", "Not sure, estimate it")
    assert r.profile["home"]["mortgage_payment"] == 1718      # 30 years, 20% down, 5%
    assert re.search(r"\$1,718 a month", r.reply)


def test_typed_dont_know_at_mortgage_gives_the_same_estimate():
    r = asyncio.run(intake.run(OWN, {}, use_ai=False))
    for _ in range(8):
        if r.question and "mortgage" in r.question.text.lower():
            break
        r = asyncio.run(intake.run("Yes", r.profile, use_ai=False))
    r = asyncio.run(intake.run("I don't know", r.profile, use_ai=False))
    assert r.profile["home"]["mortgage_balance"] > 0 and "$" in r.reply


def test_partner_pay_chip_shows_a_figure_marked_estimate():
    r0 = asyncio.run(intake.run("I'm 45, a nurse in Ohio, married, my wife is a teacher, no kids, 300k saved, I rent", {}, use_ai=False))
    r0 = asyncio.run(intake.run("Change my partner's pay", r0.profile, use_ai=False))
    assert "Use typical for their job" in r0.question.quick_answers, r0.question.text
    r = asyncio.run(intake.run("Use typical for their job", r0.profile, use_ai=False))
    f = row(r, "partner_pay_per_year")
    assert f.source == "estimate" and "$" in f.display


def test_spending_chip_shows_a_figure_marked_estimate_and_the_reply_names_it():
    r = asyncio.run(intake.run("I'm 45, a nurse in Ohio, single, no kids, 300k saved, I rent", {}, use_ai=False))
    r = asyncio.run(intake.run("Change my spending now", r.profile, use_ai=False))
    assert "Estimate it for me" in r.question.quick_answers
    r = asyncio.run(intake.run("Estimate it for me", r.profile, use_ai=False))
    f = row(r, "spending_now_per_year")
    assert f.source == "estimate" and "$" in f.display
    assert "$" in r.reply


def test_pension_skip_says_none_is_counted_not_a_typical_figure():
    r = asyncio.run(intake.run("I'm 50, a nurse in Ohio, single, no kids, 300k saved, I earn $90k and I own my home outright. I will get a pension",
                               {}, use_ai=False))
    for _ in range(8):
        if "pension" in r.question.text.lower():
            break
        r = asyncio.run(intake.run("No other debts" if "owe" in r.question.text else "Yes", r.profile, use_ai=False))
    r = asyncio.run(intake.run("Not sure, leave it out", r.profile, use_ai=False))
    assert "no pension" in r.reply and "typical figure" not in r.reply
    assert not r.profile.get("pensions")
    assert row(r, "pensions").display == "None counted"


def test_home_and_debts_header_reads_estimated_once_the_mortgage_is_estimated():
    r = reach(OWN, "Not sure, estimate it")
    assert {s["section"]: s["status"] for s in r.sections_status}["Home & debts"] == "estimated"
