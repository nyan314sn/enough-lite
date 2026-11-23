"""Everyday words for the same input (eval/phrasing_inputs/probe.py found these against the live app)."""
from datetime import date
from types import SimpleNamespace

import pytest

from app.agents import intake_round2 as r2
from app.agents import parser, turn_guard
from app.schemas import Profile

YEAR = date.today().year


def _upd(fp, v, quote, unit="text"):
    return SimpleNamespace(field_path=fp, value=v, unit=unit, evidence_quote=quote, is_correction=False)


def _guard(fp, v, msg, p=None, asking=None):
    return turn_guard.check_updates([_upd(fp, v, msg)], msg, p or Profile(age=55, has_partner=True, partner_age=53), asking).facts


# ---- the rule reader
def test_hourly_pay_full_time():
    assert parser.parse("I earn $45 an hour full time")["pay_per_year"] == pytest.approx(93600)


def test_hourly_pay_part_time():
    assert parser.parse("I make 20 dollars per hour part-time")["pay_per_year"] == pytest.approx(20800)


def test_born_year_is_age():
    assert parser.parse("I was born in 1968")["age"] == YEAR - 1968


def test_partner_born_year():
    assert parser.parse("my wife was born in March 1970")["partner_age"] == YEAR - 1970


@pytest.mark.parametrize("text, key, want", [
    ("Make my retirement age 67", "retire_age", 67),
    ("my retirement age is 62", "retire_age", 62),
])
def test_retirement_age_is_not_age(text, key, want):
    out = parser.parse(text)
    assert out.get(key) == want
    assert "age" not in out and "children.ages" not in out


# ---- the check on the model's reading
@pytest.mark.parametrize("fp, said, msg, want", [
    ("risk", "low", "I don't like risk", "careful"),
    ("risk", "aggressive", "I can stomach big swings for higher returns", "growth"),
    ("risk", "moderate", "Moderate risk is fine", "balanced"),
    ("health", "so-so", "My health is so-so", "fair"),
    ("health", "great", "I'm in great health", "excellent"),
])
def test_choice_words(fp, said, msg, want):
    assert _guard(fp, said, msg)[fp] == want


def test_half_a_million():
    assert _guard("savings.total", 500000.0, "We've got half a million saved")["savings.total"] == pytest.approx(500000)


def test_retire_words():
    assert _guard("retire_age", 60.0, "I want out of work by 60").get("retire_age") == 60


def test_born_year_from_model():
    assert _guard("age", 57.0, "I was born in 1968")["age"] == YEAR - 1968


def test_job_in_other_words():
    assert _guard("job", "high school teacher", "I teach high school").get("job") == "high school teacher"


def test_job_still_checked():
    assert "job" not in _guard("job", "astronaut", "I teach high school")


def test_hourly_from_model():
    assert _guard("pay_per_year", 45.0, "I earn $45 an hour")["pay_per_year"] == pytest.approx(93600)


def test_rent_bare_at_other_question():
    p = Profile(age=55, has_partner=True, partner_age=53)
    assert _guard("home.rent", 1800.0, "We're renters, $1,800/mo", p, asking="confirm_split").get("home.rent") == pytest.approx(1800)


# ---- the later steps
def test_medical_bills_keep_their_amount():
    facts = {"debts": [{"kind": "other", "balance": 3000.0}]}
    r2.student_loan_guard(facts, "We have $3k in medical bills")
    assert facts.get("debts") == [{"kind": "other", "balance": 3000.0}]


def test_tiny_pay_never_stored():
    assert [k for k, _, _ in r2.too_small({"pay_per_year": 45.0}, bare=False)] == ["pay_per_year"]


@pytest.mark.parametrize("text, code", [("We're in the Bay Area", "CA"), ("We're in Jersey", "NJ"), ("we live in Philly", "PA")])
def test_regions_name_a_state(text, code):
    assert parser.find_state(text) == code


def test_car_note_left():
    facts = {"debts": [{"kind": "car", "balance": 18000.0}]}
    r2.student_loan_guard(facts, "My car note has 18k left")
    assert facts.get("debts") == [{"kind": "car", "balance": 18000.0}]


def test_spending_to_live_is_now():
    out = _guard("spending_per_year", 60000.0, "We need around 5 grand a month to live")
    assert "spending_per_year" not in out and out["spending_now_per_year"] == pytest.approx(60000)


def test_spending_in_retirement_stays_later():
    out = _guard("spending_per_year", 50000.0, "In retirement we'd want to spend $50k a year")
    assert out["spending_per_year"] == pytest.approx(50000)


def test_ups_and_downs_is_growth():
    assert _guard("risk", "comfortable with ups and downs", "I'm comfortable with ups and downs")["risk"] == "growth"
