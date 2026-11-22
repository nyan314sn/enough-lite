"""Family tool: children, college and pets by year; and the typical basics of a retired household.

Data: app/data/life_costs.json (USDA child costs restated to 2026 dollars, College Board 2026-27 budgets, Rover pet
costs, Banfield pet lifespans) and app/data/basics.json (HUD rents, Census owner costs, USDA food plans, FHWA miles,
IRS mileage rate, CMS health costs). All in today's dollars.
"""
from __future__ import annotations

import json
from functools import lru_cache

from ..config import DATA_DIR


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    return json.load(open(DATA_DIR / name, encoding="utf-8"))


def _band(age: int) -> str | None:
    for key in _load("life_costs.json")["child_rearing"]:
        lo, hi = (int(x) for x in key.split("-"))
        if lo <= age <= hi:
            return key
    return None


def child_cost(age: int, n_children: int) -> float:
    lc = _load("life_costs.json")
    band = _band(age)
    if band is None:
        return 0.0
    base = lc["child_rearing"][band]["typical"]
    mult = lc["child"]["only_child_multiplier"] if n_children == 1 else (lc["child"]["three_plus_multiplier"] if n_children >= 3 else 1.0)
    return base * mult


def pet_cost(kind: str) -> tuple[float, float]:
    """(typical yearly cost, years left for a pet of unknown age = half its typical lifespan)."""
    pets = _load("life_costs.json")["pets"]
    p = pets.get(kind, pets["dog"] if kind == "dog" else pets["cat"])
    return float(p["annual"]["typical"]), round(p["lifespan"]["typical"] / 2)


def family_path(age: int, children: list[dict], pets: list[dict], partner_age: int | None = None,
                college: str = "in_state") -> dict:
    """Yearly family costs from now (index 0 = this year, your age `age`) until they end."""
    lc = _load("life_costs.json")
    n = len(children)
    col = lc["college"][college]["typical"]
    start, years = lc["child"]["college_start_age"], lc["child"]["college_years"]
    indep = lc["child"]["independence_age"]
    horizon = 40
    home = [0.0] * horizon
    college_cost = [0.0] * horizon
    pet = [0.0] * horizon
    moments: list[str] = []
    by_child: list[dict] = []        # each child's own college: its type and share, in the years that child is of college age
    for i, c in enumerate(children):
        ca = c.get("age")
        if ca is None:
            continue
        in_college = c.get("college", True) and c.get("college_type") != "none"
        kind = {"private": "private"}.get(c.get("college_type"), "in_state") if c.get("college_type") else college
        amount = lc["college"][kind]["typical"] * float(c.get("college_share", 1.0) or 0)
        ts = []
        for t in range(horizon):
            a = ca + t
            if a < indep:
                home[t] += child_cost(a, n)
            if in_college and start <= a < start + years:
                college_cost[t] += amount
                ts.append(t)
        if ts and amount > 0:
            by_child.append({"child": i + 1, "age": ca, "type": c.get("college_type") or "public", "share": float(c.get("college_share", 1.0) or 0),
                             "per_year": round(amount), "first": ts[0], "last": ts[-1]})
    ages = [c["age"] for c in children if c.get("age") is not None]
    if ages:
        youngest = min(ages)
        oldest = max(ages)
        if youngest < indep:
            moments.append(f"Your youngest child leaves home when you are about {age + indep - youngest}.")
        for b in by_child:
            kind = "private" if b["type"] == "private" else "public in-state"
            share = "" if b["share"] == 1 else f", your share {b['share'] * 100:g}%"
            moments.append(f"College for the {b['age']}-year-old ({kind}{share}): about ${b['per_year']:,.0f} a year, when you are {age + b['first']} to {age + b['last']}.")
        if oldest < indep and n > 1:
            moments.append(f"Your oldest child turns {indep} when you are about {age + indep - oldest}.")
    for p in pets:
        cost, left = pet_cost(p.get("kind", "dog"))
        cnt = int(p.get("count", 1))
        for t in range(min(horizon, int(left))):
            pet[t] += cost * cnt
        word = p.get("kind", "pet") + ("s" if cnt > 1 else "")
        moments.append(f"Your {word} cost about ${cost * cnt:,.0f} a year, for about {int(left)} more years.")
    if partner_age is not None and partner_age >= 65 > age:
        moments.append("Your partner reaches Medicare age before you do.")
    total = [home[t] + college_cost[t] + pet[t] for t in range(horizon)]
    last = max((t for t in range(horizon) if total[t] > 0), default=-1)
    return {
        "per_year": [round(x) for x in total[: last + 1]],
        "children_at_home_per_year": [round(x) for x in home[: last + 1]],
        "college_per_year": [round(x) for x in college_cost[: last + 1]],
        "pets_per_year": [round(x) for x in pet[: last + 1]],
        "this_year": round(total[0]) if total else 0,
        "total": round(sum(total)),
        "college_total": round(sum(college_cost)),
        "ends_at_age": age + last if last >= 0 else None,
        "college_cost_per_year": max((b["per_year"] for b in by_child), default=col),
        "college_by_child": by_child,
        "moments": moments,
    }


def medicare_premiums_per_year() -> float:
    """Part B and Part D premiums for one person, a year (CMS 2027, KFF 2026)."""
    h = _load("basics.json")["health"]
    return (h["part_b_premium_monthly_2027"] + h["part_d_premium_monthly"]) * 12


def basics_per_year(state: str | None, adults: int, age: int, home: dict) -> dict:
    """Typical basics for the household once retired: housing, food, transport and health care, a year."""
    b = _load("basics.json")
    row = b["states"].get((state or "").upper(), b["us"])
    owns, payment, rent = home.get("owns"), float(home.get("mortgage_payment") or 0), float(home.get("rent") or 0)
    if owns is True and float(home.get("mortgage_balance") or 0) <= 0 and payment <= 0:
        housing, how = row["smoc_free"] * 12, "owner costs without a mortgage (Census)"
    elif owns is True:
        housing, how = (payment if payment > 0 else row["smoc_mortgage"]) * 12, "mortgage and owner costs"
    elif rent > 0:
        housing, how = rent * 12, "your rent"
    else:
        housing, how = row["rent_1br"] * 12 * (1.25 if adults > 1 else 1.0), "typical rent (HUD)"
    band = "71+" if age >= 71 else "51-70"
    f = b["food"]
    food_person = (f["monthly_individual"]["male"][band] + f["monthly_individual"]["female"][band]) / 2 * 12
    food = food_person * adults * f["household_adjust"]["2" if adults > 1 else "1"]
    tr = b["transport"]
    miles = (tr["miles_65_plus"]["male"] + tr["miles_65_plus"]["female"]) / 2
    transport = miles * tr["rate_per_mile"] * adults
    h = b["health"]
    health = (h["out_of_pocket_per_person"]["65-84"] + (h["part_b_premium_monthly_2027"] + h["part_d_premium_monthly"]) * 12) * adults
    total = housing + food + transport + health
    return {
        "basics_per_year": round(total, -2),
        "housing": round(housing), "housing_basis": how,
        "food": round(food), "transport": round(transport), "health": round(health),
        "place": row.get("name", "the United States"),
    }
