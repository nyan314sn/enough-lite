"""Spending now when the person gave no figure: take-home less saving, capped for high earners by BLS CE 2024."""
import asyncio

from app import household, schemas
from app.agents import intake
from app.tools import costs, estimates

EXAMPLE = ("I'm 45, a doctor in Connecticut earning $310,000. My wife, 43, stays home with our kids, 13, 10 and 6, and our 2 dogs. "
           "We have $920,000 saved and owe $420,000 on our $850,000 home. The oldest will go to a state school, the middle one private. "
           "I'd like to retire at 62.")


def done(text):
    r = asyncio.run(intake.run(text, {}, use_ai=False))
    return household.complete(schemas.Profile(**r.profile))


def test_cap_is_none_below_top_fifth_and_rises_with_pay():
    assert estimates.high_earner_spend_cap(120_000) is None
    assert estimates.high_earner_spend_cap(estimates.CE_TOP_FIFTH_MEAN_PAY) == round(estimates.CE_TOP_FIFTH_SPEND, -3)
    caps = [estimates.high_earner_spend_cap(x) for x in (160_000, 200_000, 264_510, 310_000, 500_000, 900_000)]
    assert caps == sorted(caps) and len(set(caps)) == len(caps)
    assert all(c < 0.7 * x for c, x in zip(caps, (160_000, 200_000, 264_510, 310_000, 500_000, 900_000)))


def test_example_household_leaves_a_sensible_saving():
    p = done(EXAMPLE)
    assert p.sources["spending_now_per_year"] == "estimate"          # R1: proposed, marked estimate
    assert p.notes["spending_now_per_year"]
    after = costs.work_tax(p)["after_tax_pay"]
    assert 150_000 <= p.spending_now_per_year <= 185_000
    assert p.spending_now_per_year <= 0.75 * after                   # saves a fifth or more of take-home pay
    assert p.spending_per_year <= p.spending_now_per_year


def test_500k_earner_not_spending_most_of_take_home():
    p = done("I'm 42, a lawyer in New York earning $500,000. I'm single and rent. I have $600,000 saved. I'd like to retire at 60.")
    after = costs.work_tax(p)["after_tax_pay"]
    assert p.spending_now_per_year <= 0.75 * after


def test_middle_incomes_keep_the_take_home_rule():
    p = done("We're 40 and 38, married, in Texas with two kids, 8 and 5. Combined we earn $120,000. We have $80,000 saved and own our "
             "home worth $300,000 with $200,000 left on the mortgage. We'd like to retire at 65.")
    c = costs.contributions(p)
    after = costs.work_tax(p)["after_tax_pay"]
    assert abs(p.spending_now_per_year - round(after - (c["you"] + c["partner"] + c["other"]), -3)) <= 1000
    assert "take-home" in p.notes["spending_now_per_year"]


def test_stated_spending_is_never_changed():
    r = asyncio.run(intake.run(EXAMPLE + " We spend $240,000 a year.", {}, use_ai=False))
    p = household.complete(schemas.Profile(**r.profile))
    assert p.spending_now_per_year == 240_000 and p.sources["spending_now_per_year"] == "you said"
