"""Social Security year by year, one person at a time.

Each person's benefit starts at their own claiming age (their own age, not their partner's) and is worked out with
their own age's factor (SSA early reduction and delayed credits). A spousal benefit tops a low own benefit up to half
of the worker's full-age benefit; it is reduced before full retirement age, earns no delayed credits, and starts only
once the worker has claimed too. After the first death the survivor keeps the larger of the two benefits.

A person is a dict: {who, age (now), pia (own benefit at full retirement age, a year), spousal_pia (half the other's
full-age benefit, or 0), claim (62 to 70), fixed (already claiming: the amount does not change), amount (when fixed),
chosen (the claiming age is the person's own choice: a strategy keeps it)}.
"""
from __future__ import annotations

from . import estimates

# The earnings test (SSA, "How Work Affects Your Benefits", 2026): before full retirement age, $1 of benefits is withheld
# for every $2 of pay above the yearly limit. SSA pays the withheld months back later by raising the benefit at full
# retirement age; the plan leaves that out, so it is a little careful here. Change the limit here when SSA updates it.
EARNINGS_TEST_LIMIT = 24480       # a year, 2026 (SSA annual exempt amount for those under full retirement age)
EARNINGS_TEST_FRA = 67


def withheld(person: dict, t: int) -> float:
    """Benefits withheld in year t for someone still at work before full retirement age."""
    a = int(person["age"]) + t
    pay = float(person.get("pay") or 0)
    if pay <= EARNINGS_TEST_LIMIT or a >= EARNINGS_TEST_FRA or a >= int(person.get("work_until") or 0):
        return 0.0
    return (pay - EARNINGS_TEST_LIMIT) / 2


def amount(person: dict, claim: int) -> tuple[float, float]:
    """(own benefit, spousal top-up) a year when claiming at `claim`."""
    if person.get("fixed"):
        return float(person.get("amount") or 0.0), 0.0
    c = max(62, min(70, int(claim)))
    own = float(person.get("pia") or 0.0) * estimates.claim_factor(c)
    top = max(0.0, float(person.get("spousal_pia") or 0.0) - float(person.get("pia") or 0.0)) * estimates.spouse_factor(c)
    return own, top


def claim_of(person: dict, claim: int | None) -> int:
    """The claiming age a strategy gives this person: their own choice is kept; otherwise the strategy's age, never
    before their own age now, 62 to 70."""
    if person.get("fixed") or person.get("chosen") or claim is None:
        return int(person["claim"])
    return int(max(62, min(70, max(int(claim), int(person["age"])))))


def schedule(people: list[dict], n: int, claim: int | None = None, first_death_t: int | None = None) -> dict:
    """Household Social Security, gross, for each of n years from now. claim: a strategy's claiming age (each person
    claims at that age of their own). first_death_t: the year index of the first death (couples), or None."""
    claims = [claim_of(x, claim) for x in people]
    starts = [0 if x.get("fixed") else max(0, c - int(x["age"])) for x, c in zip(people, claims)]
    amts = [amount(x, c) for x, c in zip(people, claims)]
    each = []
    for i, x in enumerate(people):
        own, top = amts[i]
        other = starts[1 - i] if len(people) == 2 else 0
        row = []
        for t in range(n):
            v = own if t >= starts[i] else 0.0
            if top and t >= max(starts[i], other):
                v += top
            if v > 0:
                v = max(0.0, v - withheld(x, t))      # the earnings test while still at work before 67
            row.append(v)
        each.append(row)
    by_year = [sum(r[t] for r in each) for t in range(n)]
    if first_death_t is not None and len(people) == 2:
        for t in range(max(0, first_death_t), n):
            by_year[t] = max(each[0][t], each[1][t])   # the survivor keeps the larger of the two benefits
    # benefits already being paid (someone already claiming): they also come in while the household still works
    working = [min(by_year[t], sum(r[t] for x, r in zip(people, each) if x.get("fixed"))) for t in range(n)]
    per = {x["who"]: round(sum(a), -2) for x, a in zip(people, amts)}
    total = round(sum(sum(a) for a in amts), -2)
    out = {"by_year": [round(v) for v in by_year], "working_by_year": [round(v) for v in working], "claims": {x["who"]: c for x, c in zip(people, claims)},
           "per_year": per, "total_per_year": total, "first_death_t": first_death_t,
           "already": {x["who"]: bool(x.get("fixed")) for x in people},
           "each_by_year": {x["who"]: [round(v) for v in r] for x, r in zip(people, each)}}   # before the survivor rule
    if len(people) == 2:
        out["survivor_per_year"] = round(max(sum(a) for a in amts), -2)
    return out


def from_household(ss_per_year: float, ss_age: int, age: int) -> list[dict]:
    """One person standing for the household, for callers that only know a household figure and a start age."""
    ss_age = int(ss_age)
    if ss_per_year <= 0:
        return []
    if age >= ss_age:
        return [{"who": "you", "age": age, "claim": max(62, min(70, ss_age)), "fixed": True, "amount": float(ss_per_year), "pia": 0.0}]
    c = max(62, min(70, ss_age))
    return [{"who": "you", "age": age, "claim": c, "fixed": False, "chosen": False,
             "pia": float(ss_per_year) / estimates.claim_factor(c), "spousal_pia": 0.0}]
