"""Estimates for things a person did not say: pay from job and state, and Social Security from pay.

Data: app/data/wages.json (BLS OEWS May 2025 pay by occupation, state pay ratio, plain job names) and
app/data/social_security.json (SSA 2027 PIA formula, wage base, early and delayed claiming rules).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from ..config import DATA_DIR


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    return json.load(open(DATA_DIR / name, encoding="utf-8"))


def is_no_pay(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in _load("wages.json")["no_pay_phrases"])


def match_job(text: str) -> tuple[str, str] | None:
    """(phrase, SOC code) for the longest known job phrase in the text."""
    t = " " + re.sub(r"[^a-z0-9 ]+", " ", text.lower()) + " "
    best = None
    for phrase, code in _load("wages.json")["phrases"].items():
        if code and f" {phrase} " in t and (best is None or len(phrase) > len(best[0])):
            best = (phrase, code)
    return best


def pay_estimate(job_text: str, state: str | None) -> dict | None:
    w = _load("wages.json")
    m = match_job(job_text)
    if not m:
        return None
    occ = w["occupations"].get(m[1])
    if not occ:
        return None
    p25, med, p75 = occ["p25_median_p75"]
    ratio = w["state_index"].get((state or "").upper(), 1.0)
    return {
        "job": m[0], "occupation": occ["title"], "soc": m[1],
        "pay_per_year": round(med * ratio, -3), "low": round(p25 * ratio, -3), "high": round(p75 * ratio, -3),
        "note": f"Typical pay for {occ['title'].lower()} (BLS, {w['release']}), adjusted for pay levels in your state.",
    }


WORK_START_AGE = 22     # assumed: work starts at about 22
FULL_CAREER_YEARS = 35  # SSA averages the 35 best years of earnings; missing years count as zeros


def career_years(retire_age: float | None) -> int:
    """Years of earnings by the time work stops: from about 22 to the retirement age, at most 35."""
    return int(max(0, min(FULL_CAREER_YEARS, (retire_age or 67) - WORK_START_AGE)))


def pia_per_year(pay_per_year: float, years_worked: int = FULL_CAREER_YEARS) -> float:
    """Benefit at full retirement age, a year, from today's pay as a stand-in for a career of earnings. Fewer than 35
    years of work are averaged over 35 (SSA counts the missing years as zeros)."""
    ss = _load("social_security.json")
    yrs = max(0, min(FULL_CAREER_YEARS, years_worked))
    aime = min(pay_per_year, ss["wage_base"]) / 12 * yrs / FULL_CAREER_YEARS
    b1, b2 = ss["bend_points_monthly"]
    f1, f2, f3 = ss["factors"]
    return 12 * (f1 * min(aime, b1) + f2 * max(0.0, min(aime, b2) - b1) + f3 * max(0.0, aime - b2))


def social_security(pay_per_year: float, claim_age: int = 67, years_worked: int = FULL_CAREER_YEARS) -> dict:
    """Yearly benefit in today's dollars, from today's pay as a stand-in for a career of earnings."""
    pia = pia_per_year(pay_per_year, years_worked) / 12
    claim_age = max(62, min(70, claim_age))
    factor = claim_factor(claim_age)
    return {"per_year": round(pia * factor * 12, -2), "at_full_age_per_year": round(pia * 12, -2), "claim_age": claim_age}


def claim_factor(claim_age: float) -> float:
    """Benefit at this claiming age as a share of the full-age benefit (SSA early reduction and delayed credits)."""
    ss = _load("social_security.json")
    fra = ss["full_retirement_age"]
    claim_age = max(62, min(70, claim_age))
    if claim_age < fra:
        months = (fra - claim_age) * 12
        return 1 - (min(36, months) * 5 / 900 + max(0, months - 36) * 5 / 1200)
    return 1 + ss["delayed_credit_per_year"] * (claim_age - fra)


def spouse_factor(claim_age: float) -> float:
    """A spousal benefit at this age as a share of its full amount: reduced before full retirement age (25/36 of 1% a
    month for 36 months, 5/12 of 1% after) and no delayed credits after it (SSA)."""
    fra = _load("social_security.json")["full_retirement_age"]
    claim_age = max(62, min(70, claim_age))
    if claim_age >= fra:
        return 1.0
    months = (fra - claim_age) * 12
    return 1 - (min(36, months) * 25 / 3600 + max(0, months - 36) * 5 / 1200)


def spouse_share() -> float:
    return float(_load("social_security.json")["spouse_max_share"])


def spouse_benefit(worker_full_age_per_year: float) -> float:
    return round(worker_full_age_per_year * _load("social_security.json")["spouse_max_share"], -2)


# Spending now, when the person gave no figure: a ceiling for high earners.
# BLS Consumer Expenditure Survey 2024 (release 2025-12-19): consumer units in the top income fifth (income before
# tax from $155,925, average about $264,510) spent $150,342 a year on average, about 57% of pay. Spending climbs
# more slowly than pay at the top, so "take-home pay less 10%" overstates it there. Below the top fifth the
# take-home rule stays (the fourth fifth spent $89,972). Past the top-fifth average, each extra dollar of pay adds
# 35 cents of spending (our judgment: high earners save most of each extra dollar).
CE_TOP_FIFTH_ENTRY_PAY = 155_925
CE_TOP_FIFTH_MEAN_PAY = 264_510
CE_TOP_FIFTH_SPEND = 150_342
CE_ENTRY_SPEND = 106_000            # about 68% of pay at the entry, what take-home less 10% gives a couple there
CE_MARGINAL_SPEND_SHARE = 0.35


def high_earner_spend_cap(household_pay: float) -> float | None:
    """The most that spending now is estimated at for this pay a year, or None below the top income fifth."""
    pay = household_pay or 0
    if pay <= CE_TOP_FIFTH_ENTRY_PAY:
        return None
    if pay <= CE_TOP_FIFTH_MEAN_PAY:
        t = (pay - CE_TOP_FIFTH_ENTRY_PAY) / (CE_TOP_FIFTH_MEAN_PAY - CE_TOP_FIFTH_ENTRY_PAY)
        return round(CE_ENTRY_SPEND + t * (CE_TOP_FIFTH_SPEND - CE_ENTRY_SPEND), -3)
    return round(CE_TOP_FIFTH_SPEND + CE_MARGINAL_SPEND_SHARE * (pay - CE_TOP_FIFTH_MEAN_PAY), -3)
