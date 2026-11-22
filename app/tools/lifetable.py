"""Life table tool: survival curves and a planning horizon.

Data: app/data/mortality.json (SOA U.S. population mortality 2024, copied from the full app). Rates improve over time
by the SOA Scale MP-2021 long-term rates (a simple version: the long-term rate from the base year on).
"""
from __future__ import annotations

import json
from functools import lru_cache

from ..config import DATA_DIR

THIS_YEAR = 2026


@lru_cache(maxsize=1)
def _table() -> dict:
    return json.load(open(DATA_DIR / "mortality.json", encoding="utf-8"))


def _improvement(age: int) -> float:
    pts = sorted((int(k), v) for k, v in _table()["improvement_ultimate"].items())
    if age <= pts[0][0]:
        return pts[0][1]
    for (a0, v0), (a1, v1) in zip(pts, pts[1:]):
        if age <= a1:
            return v0 + (v1 - v0) * (age - a0) / (a1 - a0)
    return pts[-1][1]


def qx(age: int, sex: str | None, year: int, mult: float = 1.0) -> float:
    t = _table()
    age = max(t["min_age"], min(t["max_age"], age))
    if sex in ("male", "female"):
        q = t[sex]["qx"][str(age)]
    else:  # not known: the average of the two tables
        q = (t["male"]["qx"][str(age)] + t["female"]["qx"][str(age)]) / 2
    if age >= t["max_age"]:
        return 1.0
    return min(1.0, mult * q * (1 - _improvement(age)) ** max(0, year - t["base_year"]))


def survival(age: int, sex: str | None = None, to_age: int = 120, mult: float = 1.0) -> list[float]:
    """Chance of being alive at each age from `age` (1.0) to `to_age`."""
    out, s = [1.0], 1.0
    for k, a in enumerate(range(age, to_age)):
        s *= 1 - qx(a, sex, THIS_YEAR + k, mult)
        out.append(s)
    return out


def life_expectancy(age: int, sex: str | None = None, mult: float = 1.0) -> float:
    s = survival(age, sex, mult=mult)
    return round(sum((s[i] + s[i + 1]) / 2 for i in range(len(s) - 1)), 1)


def horizon(age: int, sex: str | None = None, partner_age: int | None = None, partner_sex: str | None = None,
            tail: float = 0.25, mult: float = 1.0, partner_mult: float = 1.0) -> dict:
    """Planning horizon: the first age (of the first person) at which the chance that anyone in the household is
    still alive falls to `tail` or below. For a couple, either one alive counts."""
    s1 = survival(age, sex, mult=mult)
    s2 = survival(partner_age, partner_sex, mult=partner_mult) if partner_age else None
    n = len(s1)
    if s2 is not None:
        n = min(n, len(s2))
        anyone = [1 - (1 - s1[i]) * (1 - s2[i]) for i in range(n)]
    else:
        anyone = s1[:n]
    k = next((i for i, p in enumerate(anyone) if p <= tail), n - 1)
    h = age + k

    def chance(at: int) -> float:
        i = at - age
        return round(anyone[i], 2) if 0 <= i < n else 0.0

    out = {
        "horizon_age": h,
        "tail_chance": tail,
        "chance_alive_at_horizon": chance(h),
        "chance_someone_reaches_90": chance(90),
        "chance_someone_reaches_100": chance(100),
        "life_expectancy_you": life_expectancy(age, sex, mult),
        "years_to_plan": k,
    }
    if partner_age:
        out["life_expectancy_partner"] = life_expectancy(partner_age, partner_sex, partner_mult)
        out["partner_age_at_horizon"] = partner_age + k
    return out


# Health adjustment: a simple multiplier on the table's yearly death rates. This is an assumption of this app, not a
# table: self-rated poor health is linked in published studies to roughly double the death rate at older ages, and
# excellent health to a lower one. "good" is the table as it stands (the typical default).
HEALTH_MULT = {"excellent": 0.8, "good": 1.0, "fair": 1.4, "poor": 2.0}


def health_mult(health: str | None) -> float:
    return HEALTH_MULT.get(health or "good", 1.0)
