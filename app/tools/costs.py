"""Costs tool: what the household spends now and later, year by year, and the money flows the plan needs.

Pure Python, no model. Two halves, used by two agents:
  family_side(): costs by year (college by child, big costs, parents, mortgage end, debts, health care by age) and the
                 costs timeline (plan.costs_by_age) with labelled events.
  money_side():  saving by year (contributions + employer match), pension and part-time income, an inheritance if counted,
                 and the legacy that must remain.
All in today's dollars (real), like the simulation. Assumptions are named constants below, each labelled.
"""
from __future__ import annotations

import datetime
import math

from .. import config
from ..schemas import Profile
from . import family_costs, lifetable, tax
from .family_costs import _load

N_YEARS = 100                # arrays run from this year for 100 years, past any plan horizon (an 18-year-old plans to about 100)
INFLATION = 0.025
# Assumptions of this app (not tables). Round figures; change them here.
RATE_BY_KIND = {"student": 0.06, "car": 0.07, "credit_card": 0.22, "other": 0.08}   # a year; typical rates, assumed
TERM_YEARS = {"student": 10, "car": 5, "credit_card": 5, "other": 5}               # standard payoff term, assumed
HIGH_RATE = config.HIGH_RATE_DEBT   # debt at or above this rate is "high rate" (7%, set in config)
DEBT_NAME = {"student": "student loan", "car": "car loan", "credit_card": "credit card", "other": "other debt"}
DEBT_SHORT = {"student": "student loan", "car": "car loan", "credit_card": "card debt", "other": "high-rate debt"}     # in action titles
DEFAULT_MORTGAGE_RATE = 0.05
DEFAULT_MATCH_CAP = 0.06    # employer match cap, share of pay, when only the match rate is known
PRE_MEDICARE_PREMIUM = 10000  # a person a year, before Medicare at 65: a round figure for a marketplace plan around age 60. Assumed.
LIFE_COVER_YEARS = 10       # a common rule of thumb: life cover of 10 years of pay when others depend on it
EMERGENCY_MIN_MONTHS = 3
EMERGENCY_TYPICAL_MONTHS = 6
HEALTH_NOTE_85 = "Out-of-pocket health costs rise again from 85 (CMS)."
MEDICARE_AGE = 65


def this_year() -> int:
    return datetime.date.today().year


# ------------------------------------------------------------------ debts and mortgage
def months_to_payoff(balance: float, annual_rate: float, payment: float) -> int | None:
    """Months to pay a loan off at a fixed monthly payment. None when the payment does not cover the interest."""
    if balance <= 0:
        return 0
    if payment <= 0:
        return None
    r = annual_rate / 12
    if r <= 0:
        return math.ceil(balance / payment)
    if payment <= balance * r + 1e-9:
        return None
    return math.ceil(-math.log(1 - balance * r / payment) / math.log(1 + r))


def standard_payment(balance: float, annual_rate: float, years: int) -> float:
    """The monthly payment that pays a loan off in `years`."""
    n, r = years * 12, annual_rate / 12
    if r <= 0:
        return balance / n
    return balance * r / (1 - (1 + r) ** -n)


def fill_debt(d) -> None:
    """Fill a missing rate or payment with a typical one and record what was assumed."""
    if d.rate is None:
        d.rate = RATE_BY_KIND.get(d.kind, 0.08)
        if "rate" not in d.assumed:
            d.assumed.append("rate")
    if d.monthly_payment is None:
        d.monthly_payment = round(standard_payment(d.balance, d.rate, TERM_YEARS.get(d.kind, 5)), 2)
        if "monthly_payment" not in d.assumed:
            d.assumed.append("monthly_payment")


def debt_schedule(p: Profile, n: int = N_YEARS) -> dict:
    per_year = [0.0] * n
    rows = []
    total_bal = total_pay = interest = 0.0
    high_bal = high_int = 0.0
    high_rate = 0.0
    last_year_idx = -1
    for d in p.debts:
        if d.balance <= 0:
            continue
        rate = d.rate if d.rate is not None else RATE_BY_KIND.get(d.kind, 0.08)
        pay = d.monthly_payment if d.monthly_payment is not None else standard_payment(d.balance, rate, TERM_YEARS.get(d.kind, 5))
        months = months_to_payoff(d.balance, rate, pay)
        never = months is None
        m = 12 * 40 if never else months
        for t in range(n):
            left = m - 12 * t
            if left <= 0:
                break
            per_year[t] += pay * min(12, left)
        last_year_idx = max(last_year_idx, min(n - 1, math.ceil(m / 12) - 1))
        total_bal += d.balance
        total_pay += pay * 12
        interest += d.balance * rate
        if rate >= HIGH_RATE:
            high_bal += d.balance
            high_int += d.balance * rate
            high_rate = max(high_rate, rate)
        rows.append({"kind": d.kind, "balance": d.balance, "rate": rate, "monthly_payment": round(pay, 2), "months": months,
                     "never_paid_off": never})
    return {"per_year": [round(x) for x in per_year], "rows": rows, "total_balance": round(total_bal),
            "payment_per_year": round(total_pay), "interest_per_year": round(interest),
            "high_rate_balance": round(high_bal), "high_rate_interest_per_year": round(high_int), "high_rate": round(high_rate, 3),
            "free_index": last_year_idx if rows else None}


# A typical mortgage, for "not sure, estimate it". Assumed round figures: a 30-year loan taken out at about 35 with 20% down,
# at DEFAULT_MORTGAGE_RATE. The payment is the Census owner cost with a mortgage for the state (what the plan already uses
# for housing) unless the home's value is known; the balance is what that payment still owes over the years left.
MORTGAGE_TERM_YEARS = 30
MORTGAGE_BUY_AGE = 35
MORTGAGE_DOWN = 0.20
MORTGAGE_MIN_YEARS_LEFT = 5


def typical_mortgage(p: Profile) -> tuple[float, float]:
    """(balance, monthly payment) for a typical mortgage, keeping any one figure the person gave."""
    r = DEFAULT_MORTGAGE_RATE / 12
    years = max(MORTGAGE_MIN_YEARS_LEFT, min(MORTGAGE_TERM_YEARS, MORTGAGE_TERM_YEARS - ((p.age or 45) - MORTGAGE_BUY_AGE)))
    n = years * 12
    h = p.home
    pv = (1 - (1 + r) ** -n) / r             # what one dollar a month still owes over the years left
    if p.notes.get("mortgage_balance_said") == "yes" and h.mortgage_balance > 0:
        return h.mortgage_balance, h.mortgage_payment if p.notes.get("mortgage_payment_said") == "yes" else round(h.mortgage_balance / pv)
    if p.notes.get("mortgage_payment_said") == "yes" and h.mortgage_payment > 0:
        return round(h.mortgage_payment * pv, -3), h.mortgage_payment
    if h.value:
        full = MORTGAGE_TERM_YEARS * 12
        pay = round(h.value * (1 - MORTGAGE_DOWN) * r / (1 - (1 + r) ** -full))
    else:
        row = _load("basics.json")
        pay = float(row["states"].get((p.state or "").upper(), row["us"])["smoc_mortgage"])
    return round(pay * pv, -3), pay


def mortgage_end(p: Profile) -> dict | None:
    """When the mortgage ends and how much yearly cost falls then. Needs a balance and a payment."""
    h = p.home
    if not (h.owns and h.mortgage_balance > 0 and h.mortgage_payment > 0):
        return None
    rate = h.mortgage_rate if h.mortgage_rate is not None else DEFAULT_MORTGAGE_RATE
    months = months_to_payoff(h.mortgage_balance, rate, h.mortgage_payment)
    if months is None:
        return None
    b = _load("basics.json")
    row = b["states"].get((p.state or "").upper(), b["us"])
    drop = max(0.0, h.mortgage_payment * 12 - row["smoc_free"] * 12)
    idx = math.ceil(months / 12)
    return {"years_left": idx, "end_year": this_year() + idx, "drop_per_year": round(drop, -2), "rate": rate}


def mortgage_separate(p: Profile) -> bool:
    """True when the plan keeps the mortgage out of retirement spending and the basics, and counts any payments left
    after retiring as a cost of their own: for someone still at work who has a mortgage. Then what you can count on is
    the same kind of figure at every retirement age (audit R12: retiring at 63 gave more than at 64, because at 63 the
    figure held a mortgage that ended a year later)."""
    return bool(mortgage_end(p)) and (p.retire_age or 65) > (p.age or 45)


# ------------------------------------------------------------------ health care by age
def health_extra(a: int) -> float:
    """Extra yearly health cost for one person at age a, over the Medicare-era figure the basics already hold
    (out-of-pocket at 65-84 plus Part B and D premiums). Before 65 a retired person buys their own cover (assumed premium
    plus CMS out-of-pocket at 45-64). From 85 out-of-pocket costs rise (CMS)."""
    h = _load("basics.json")["health"]
    oop = h["out_of_pocket_per_person"]
    medicare_basis = oop["65-84"] + (h["part_b_premium_monthly_2027"] + h["part_d_premium_monthly"]) * 12
    if a < MEDICARE_AGE:
        return PRE_MEDICARE_PREMIUM + oop["45-64"] - medicare_basis
    if a >= 85:
        return oop["85+"] - oop["65-84"]
    return 0.0


def partner_retire_age(p: Profile) -> int:
    if p.partner_retire_age is not None:
        return p.partner_retire_age
    age, pa = p.age or 45, p.partner_age or p.age or 45
    if abs(pa - age) <= 5:
        return min(max(pa, 70), pa + max(0, (p.retire_age or 65) - age))      # about the same time as you, never past 70
    return max(pa, 65)                                                          # far apart in age: the usual 65


def health_extra_by_year(p: Profile, n: int = N_YEARS) -> list[float]:
    age, ra = p.age or 45, p.retire_age or 65
    out = []
    for t in range(n):
        x = 0.0
        if age + t >= ra or age + t >= 65:
            x += health_extra(age + t)
        if p.has_partner and p.partner_age:
            pa = p.partner_age + t
            if pa >= partner_retire_age(p) or pa >= 65:
                x += health_extra(pa)
        out.append(round(x))
    return out


def ltc_facts() -> dict:
    pc = _load("life_costs.json")["parent_care"]
    return {"nursing_home_per_year": pc["nursing_home"]["typical"], "typical_years": pc["duration_years"]["typical"]}


# ------------------------------------------------------------------ the family side: costs by year and the timeline
def _year_index(year: int | None, n: int) -> int | None:
    if year is None:
        return None
    t = year - this_year()
    return t if 0 <= t < n else None


def family_side(p: Profile, fam: dict, n: int = N_YEARS) -> dict:
    """fam: the family_path() result. Returns arrays by year (index 0 = this year) and the timeline."""
    age, ra = p.age or 45, p.retire_age or 65
    yr0 = this_year()

    def pad(xs):
        xs = list(xs)[:n]
        return xs + [0.0] * (n - len(xs))

    college = pad(fam.get("college_per_year", []))
    homepets = [a - b for a, b in zip(pad(fam.get("per_year", [])), college)]
    big = [0.0] * n
    for b in p.goals.big_costs:
        t = _year_index(b.year, n)
        if t is not None:
            big[t] += b.amount
    parents = [0.0] * n
    if p.goals.parents_per_year and p.goals.parents_years:
        for t in range(min(n, int(p.goals.parents_years))):
            parents[t] = p.goals.parents_per_year
    debts = debt_schedule(p, n)
    mort = mortgage_end(p)
    drop = [0.0] * n
    if mort:
        for t in range(n):
            if t >= mort["years_left"]:
                drop[t] = mort["drop_per_year"]
    ends_after_retirement = bool(mort) and yr0 + mort["years_left"] > yr0 + max(0, ra - age)
    # Someone still at work plans retirement spending without the mortgage (household.complete takes it out of the
    # goal and the basics), and any mortgage years left after retiring are a cost on top, like a debt. So what you can
    # count on means the same thing whatever the retirement age, and retiring a year later never makes it jump (audit
    # R12). Someone already retired keeps the spending they gave, mortgage in it, and it falls when the mortgage ends.
    separate = mortgage_separate(p)
    left_after = [0.0] * n
    if mort and separate:
        for t in range(n):
            if t < mort["years_left"]:
                left_after[t] = mort["drop_per_year"]
    health = health_extra_by_year(p, n)

    # what the simulation withdraws on top of the spending goal, by year
    extra = []
    for t in range(n):
        retired = age + t >= ra
        x = college[t] + big[t] + parents[t] + health[t]
        if retired:
            x += homepets[t] + debts["per_year"][t]
            if separate:
                x += left_after[t]
            elif ends_after_retirement:
                x -= drop[t]
        extra.append(round(x))

    # the costs timeline
    spend_now = p.spending_now_per_year or p.spending_per_year or 0
    core_now = max(0.0, spend_now - homepets[0] - college[0] - debts["per_year"][0])
    if fam.get("basics"):
        basics0 = fam["basics"]["basics_per_year"]      # the plan's own basics (household.basics)
        mort_in_basics = ends_after_retirement and not separate     # a mortgage that ends earlier, or is a cost of its own, is left out
    else:
        basics0 = family_costs.basics_per_year(p.state, p.adults(), max(ra, 65), p.home.model_dump())["basics_per_year"]
        mort_in_basics = True
    total, basics = [], []
    for t in range(n):
        retired = age + t >= ra
        if retired:
            x = max(0.0, (p.spending_per_year or 0) - (drop[t] if (ends_after_retirement and not separate) else 0))
            x += homepets[t] + health[t] + college[t] + big[t] + parents[t] + debts["per_year"][t] + left_after[t]
        else:
            x = core_now - drop[t] + homepets[t] + college[t] + big[t] + parents[t] + debts["per_year"][t] + health[t]
        b_t = round(max(0.0, basics0 - (drop[t] if mort_in_basics else 0.0) + (left_after[t] if retired else 0.0) + health[t]), -2)
        if not retired and t > 0:
            x = max(x, b_t)      # spending while at work never shows below the basics (children leaving frees money, not the basics)
        total.append(round(max(0.0, x)))
        basics.append(b_t)
    in_line = [mort_in_basics or (left_after[t] > 0 and age + t >= ra) for t in range(n)]     # years the basics line holds the mortgage
    parts = cost_parts(p, fam, total, basics, college, homepets, health, debts["per_year"], big, parents, mort, in_line, n)

    events: list[dict] = []

    def ev(t: int, label: str, change: float | None, **kw):
        events.append({"age": age + t, "year": yr0 + t, "label": label.replace("{year}", str(yr0 + t)), "change_per_year": change, **kw})

    if ra > age:
        ev(ra - age, f"You retire at {ra}", None)
    if p.has_partner and p.partner_age and partner_retire_age(p) != p.partner_age + (ra - age) and p.partner_pay_per_year:
        t = partner_retire_age(p) - p.partner_age
        if 0 < t < n:
            ev(t, f"Your partner retires at {partner_retire_age(p)}", None)
    if mort and mort["years_left"] < n:
        ev(mort["years_left"], "Mortgage paid off {year}", -mort["drop_per_year"])
    home = [a for a in fam.get("children_at_home_per_year", [])]
    if home and any(home):
        last = max(t for t, v in enumerate(home) if v > 0)
        ev(last + 1, "Children's costs end {year}", -home[last])
    cs = [t for t, v in enumerate(college) if v > 0]
    kids_col = [b for b in fam.get("college_by_child", []) if b["first"] < n]
    if len(kids_col) > 1:       # each child's own years and own cost (type and share)
        for b in kids_col:
            ev(b["first"], f"College, {b['age']}-year-old, {yr0 + b['first']}-{yr0 + b['last']}", b["per_year"])
    elif cs:
        ev(cs[0], f"College {yr0 + cs[0]}-{yr0 + cs[-1]}", max(college))
    if debts["free_index"] is not None and debts["total_balance"] > 0:
        t = debts["free_index"] + 1
        if t < n:
            ev(t, "Debts paid off {year}", -max(debts["per_year"]))
    for b in p.goals.big_costs:
        t = _year_index(b.year, n)
        if t is not None:
            ev(t, f"{b.label} {b.year}", b.amount, one_off=True)
    if p.goals.parents_per_year and p.goals.parents_years:
        t = min(n - 1, int(p.goals.parents_years))
        ev(t, "Helping your parents ends {year}", -p.goals.parents_per_year)
    if age < MEDICARE_AGE:
        t = MEDICARE_AGE - age
        pre = health_extra(MEDICARE_AGE - 1) if ra < MEDICARE_AGE else 0
        ev(t, "Medicare starts for you {year}", -round(pre) if pre else None)
    if age < 85 <= age + n:
        ev(85 - age, "Health costs rise again at 85 ({year})", round(health_extra(85)))
    events.sort(key=lambda e: (e["age"], e["label"]))

    ltc = ltc_facts()
    return {
        "college": [round(x) for x in college], "home_pets": [round(x) for x in homepets], "big": [round(x) for x in big],
        "parents": [round(x) for x in parents], "health_extra": health, "mortgage_drop": drop, "debt_pay": debts["per_year"],
        "extra_by_year": extra, "debts": debts, "mortgage": mort, "ltc": ltc,
        "timeline": {"ages": [age + t for t in range(n)], "total": total, "basics": basics, "events": events, "parts": parts},
    }


PART_LABELS = {
    "basics": "Needs: home, food, transport, care",
    "mortgage": "Mortgage payments",
    "children": "Children and college",
    "pets": "Pets",
    "health_cover": "Health cover before Medicare",
    "health_late": "More health care from 85",
    "debts": "Debt payments",
    "big": "Big costs you named",
    "parents": "Help for your parents",
    "other": "Other spending",
}


def _health_split(p: Profile, n: int) -> tuple[list[float], list[float]]:
    """health_extra_by_year in two parts: cover bought before Medicare, and the rise in care from 85."""
    age, ra = p.age or 45, p.retire_age or 65
    pre, late = [0.0] * n, [0.0] * n
    people = [(age, ra)]
    if p.has_partner and p.partner_age:
        people.append((p.partner_age, partner_retire_age(p)))
    for t in range(n):
        for a0, r in people:
            a = a0 + t
            if a >= r or a >= MEDICARE_AGE:
                x = health_extra(a)
                if a < MEDICARE_AGE:
                    pre[t] += x
                else:
                    late[t] += x
    return pre, late


def cost_parts(p: Profile, fam: dict, total: list, basics: list, college: list, homepets: list, health: list, debt_pay: list,
               big: list, parents: list, mort: dict | None, mort_in_basics: list[bool], n: int) -> list[dict]:
    """Each year's total cost in parts that add up to it exactly: the named costs first (debts, the mortgage, children
    and college, pets, health on top of the basics, big costs, help for parents), then the basics without those, then
    the rest as other spending. A part never goes below zero; when the total is smaller than the named costs (spending
    now set low), the later parts get what is left."""
    kids_home = list(fam.get("children_at_home_per_year", []))[:n]
    kids_home += [0.0] * (n - len(kids_home))
    pre, late = _health_split(p, n)
    keys = ["debts", "mortgage", "children", "pets", "health_cover", "health_late", "big", "parents", "basics", "other"]
    rows = {k: [0] * n for k in keys}
    for t in range(n):
        mort_t = mort["drop_per_year"] if (mort and t < mort["years_left"]) else 0.0
        kids = min(homepets[t], kids_home[t])
        h_pre = round(pre[t]) if health[t] else 0
        h_late = max(0, round(health[t]) - h_pre)
        core = max(0.0, basics[t] - round(health[t]) - (mort_t if mort_in_basics[t] else 0.0))
        want = {"debts": debt_pay[t], "mortgage": mort_t, "children": kids + college[t], "pets": homepets[t] - kids,
                "health_cover": h_pre, "health_late": h_late, "big": big[t], "parents": parents[t], "basics": core}
        left = int(total[t])
        for k in keys[:-1]:
            v = int(min(left, max(0, round(want[k]))))
            rows[k][t] = v
            left -= v
        rows["other"][t] = left
    return [{"key": k, "label": PART_LABELS[k], "values": rows[k]} for k in keys if any(rows[k])]


def trim_timeline(tl: dict, horizon_age: int) -> dict:
    k = max(1, horizon_age - tl["ages"][0] + 1)
    return {"ages": tl["ages"][:k], "total": tl["total"][:k], "basics": tl["basics"][:k],
            "events": [e for e in tl["events"] if e["age"] <= horizon_age],
            "parts": [{**x, "values": x["values"][:k]} for x in tl.get("parts", []) if any(x["values"][:k])]}


# ------------------------------------------------------------------ the money side: saving, income, legacy
def match_info(p: Profile) -> dict:
    """The employer match, for the earner it applies to (you, else your partner). Contributions are yearly."""
    s = p.saving
    rate = s.match_rate
    if rate is None:
        return {"rate": None}
    cap = s.match_cap if s.match_cap is not None else DEFAULT_MATCH_CAP
    you_pays = (p.pay_per_year or 0) > 0
    pay = (p.pay_per_year or 0) if you_pays else (p.partner_pay_per_year or 0)
    contrib = contributions(p)["you" if you_pays else "partner"]
    full_contrib = cap * pay
    got = min(contrib, full_contrib) * rate
    full = full_contrib * rate
    return {"rate": rate, "cap": cap, "pay": pay, "contribution": round(contrib), "full_contribution": round(full_contrib),
            "match": round(got), "full_match": round(full), "missed": round(max(0.0, full - got))}


def contributions(p: Profile) -> dict:
    """Yearly 401(k)/IRA contributions for each person: what they said, else the assumed saving rate times pay."""
    rate = p.save_rate if p.save_rate is not None else 0.0
    you = p.saving.contrib_you if p.saving.contrib_you is not None else rate * (p.pay_per_year or 0)
    partner = p.saving.contrib_partner if p.saving.contrib_partner is not None else rate * (p.partner_pay_per_year or 0)
    return {"you": you, "partner": partner, "other": (p.saving.other_per_month or 0) * 12}


CHILD_CREDIT_AGE = 17       # the child tax credit is for children under 17


def work_tax(p: Profile, c: dict | None = None) -> dict:
    """tax.working_years for this household: children under 17 for the credit (and head of household when single),
    and the 401(k) or IRA saving each earner puts in before tax (at most the yearly limit)."""
    c = c or contributions(p)
    lim = tax.limits_2027()

    def cap(a: int | None) -> float:
        # the catch-up: from 50, and the larger one from 60 to 63 (SECURE 2.0)
        extra = lim["401k_catch_up_60_to_63"] if 60 <= (a or 0) <= 63 else lim["401k_catch_up_50_plus"] if (a or 0) >= 50 else 0
        return lim["401k_limit"] + extra
    pre = min(c["you"], cap(p.age)) if (p.pay_per_year or 0) > 0 else 0.0
    if p.has_partner and (p.partner_pay_per_year or 0) > 0:
        pre += min(c["partner"], cap(p.partner_age))
    kids = sum(1 for k in p.children if k.age is not None and k.age < CHILD_CREDIT_AGE)
    return tax.working_years(p.pay_per_year or 0, p.partner_pay_per_year or 0, p.state, p.has_partner, kids, pre)


def unspent_pay(p: Profile, c: dict | None = None, partner_working: bool = True) -> float:
    """Take-home pay left each year after spending now and saving. Money earned and not spent is saved. When the
    saving is more than spending now leaves, the result is negative: the saving is cut to what is left, and spending
    above take-home pay is drawn from savings (the plan's yearly saving is then below zero).

    partner_working False: the years a partner with pay has stopped work and you still work. The plan assumes the
    household then lives on what is left, so pay left over is no longer saved; but spending above take-home pay does not
    stop when a partner stops work, so a gap stays a gap (before, it was dropped, and a partner who stopped work made
    the plan better; reasonableness audit)."""
    if not partner_working and p.has_partner and (p.partner_pay_per_year or 0) > 0:
        return min(0.0, unspent_pay(p, c))
    pay = p.household_pay()
    if pay <= 0 or not p.spending_now_per_year:
        return 0.0
    c = c or contributions(p)
    after = work_tax(p, c)["after_tax_pay"]
    saved = c["you"] + c["partner"] + c["other"]
    left = after - p.spending_now_per_year - saved
    return round(left)          # the saving is cut first; past zero the gap is drawn from savings (audit 2A)


def saving_now(p: Profile) -> dict:
    """The yearly saving the plan uses this year (money_side's first year), in its parts: 401(k) or IRA saving, other
    saving, the employer match and the take-home pay left after spending (negative when spending leaves less than
    the assumed saving). The answers panel and the plan both show this figure."""
    age, ra = p.age or 45, p.retire_age or 65
    zero = {"per_year": 0, "accounts_per_year": 0, "other_per_year": 0, "match_per_year": 0, "unspent_pay_per_year": 0}
    if ra <= age:
        return zero
    c = contributions(p)
    m = match_info(p)
    partner_works = bool(p.has_partner and p.partner_age and p.partner_age < partner_retire_age(p) and (p.partner_pay_per_year or 0) > 0)
    unspent = unspent_pay(p, c, partner_works or not (p.partner_pay_per_year or 0))
    x = c["you"] + c["other"] + (m.get("match") or 0) + (c["partner"] if partner_works else 0) + unspent
    return {"per_year": round(x), "accounts_per_year": round(c["you"] + (c["partner"] if partner_works else 0)),
            "other_per_year": round(c["other"]), "match_per_year": round(m.get("match") or 0), "unspent_pay_per_year": round(unspent)}


def money_side(p: Profile, other_tax_rate: float, partner_net_pay: float, life_expectancy_you: float | None,
               life_expectancy_partner: float | None, family: dict, n: int = N_YEARS) -> dict:
    """Arrays by year for the simulation. other_tax_rate: tax on pension and part-time income (from the tax tool)."""
    age, ra = p.age or 45, p.retire_age or 65
    yr0 = this_year()
    c = contributions(p)
    m = match_info(p)
    exact = p.saving.given()
    partner_ra = partner_retire_age(p)
    unspent = unspent_pay(p, c)
    unspent_alone = unspent_pay(p, c, partner_working=False)      # after a partner with pay stops work
    save = [0.0] * n
    cash_left = [0.0] * n       # the take-home pay left after spending now that save[] holds (below zero: drawn from savings)
    income = [0.0] * n
    lump = [0.0] * n
    work = [0.0] * n            # a partner's pay after you stop, and part-time work, after tax
    pension = [0.0] * n         # pensions after tax
    pension_fixed = [0.0] * n   # the part with no cost-of-living rise
    for t in range(n):
        a = age + t
        pa = (p.partner_age + t) if (p.has_partner and p.partner_age) else None
        partner_works = pa is not None and pa < partner_ra and (p.partner_pay_per_year or 0) > 0
        if a < ra:
            # debt payments are part of spending now, so they do not also cut the saving
            x = c["you"] + c["other"] + (m.get("match") or 0)
            if partner_works:
                x += c["partner"]
            # pay left after spending and saving: both pays while every earner works, then yours alone
            left = unspent if (partner_works or not (p.partner_pay_per_year or 0)) else unspent_alone
            x += left
            cash_left[t] = left
            save[t] = x                     # below zero: spending now above take-home pay, drawn from savings
        elif partner_works:
            income[t] += partner_net_pay          # a partner still at work after you stop
            work[t] += partner_net_pay
    pen_total_now = 0.0
    pen_rows = []
    for pen in p.pensions:
        who_age0 = (p.partner_age if pen.who == "partner" and p.partner_age else age)
        start = pen.start_age if pen.start_age is not None else 65
        adj = bool(pen.inflation_adjusted)
        surv = pen.survivor_share if pen.survivor_share is not None else 0.5
        le = (life_expectancy_partner if pen.who == "partner" else life_expectancy_you) or 85
        death_age = who_age0 + le
        for t in range(n):
            pa = who_age0 + t
            if pa < start:
                continue
            amt = pen.per_year * (1.0 if adj else (1 - INFLATION) ** (pa - start))
            if p.has_partner and pa > death_age:
                amt *= surv
            income[t] += amt * (1 - other_tax_rate)
            pension[t] += amt * (1 - other_tax_rate)
            if not adj:
                pension_fixed[t] += amt * (1 - other_tax_rate)
        pen_total_now += pen.per_year
        pen_rows.append({"who": pen.who, "per_year": pen.per_year, "start_age": start})
    pt = p.part_time
    if pt and pt.per_year > 0:
        until = pt.until_age if pt.until_age is not None else 70
        for t in range(n):
            if ra <= age + t < until:
                income[t] += pt.per_year * (1 - other_tax_rate)
                work[t] += pt.per_year * (1 - other_tax_rate)
    inh = p.inheritance
    inh_counted = bool(inh and inh.count and inh.amount > 0)
    if inh_counted:
        t = _year_index(inh.year, n)
        lump[t if t is not None else 0] += inh.amount
    # pension income in the first year you are retired, after tax, for the figures
    t_ret = max(0, ra - age)
    return {
        "save_by_year": [round(x) for x in save], "income_by_year": [round(x) for x in income], "lump_by_year": lump,
        "legacy": p.goals.legacy or 0.0, "contributions": {k: round(v) for k, v in c.items()}, "match": m,
        "save_now": round(save[0]), "pension_per_year": round(pen_total_now), "pension_rows": pen_rows,
        "income_at_retirement": round(income[min(t_ret, n - 1)]), "inheritance_counted": inh_counted,
        "inheritance_amount": inh.amount if inh else 0, "exact_saving": exact, "unspent_pay_per_year": round(cash_left[0] if ra > age else unspent),
        "flows": {"work_by_year": work, "pension_by_year": pension, "pension_fixed_by_year": pension_fixed,
                  "pay_left_by_year": [round(x) for x in cash_left]},
    }


# ------------------------------------------------------------------ levers: actions the inputs point to
def levers(p: Profile, debts: dict, match: dict, spend_now: float, cash: float) -> list[dict]:
    """Specific actions the person's own inputs call for, most useful first. 'numbers' holds the figures each uses."""
    out: list[dict] = []
    pay = p.household_pay()
    if debts["high_rate_balance"] > 0:
        hi = [r["kind"] for r in debts["rows"] if r["rate"] >= HIGH_RATE]
        one = hi[0] if len(set(hi)) == 1 else None
        # titles are actions with the figure (round 4): "Pay off your $8,000 card debt first"
        out.append({"key": "debt", "title": f"Pay off your ${debts['high_rate_balance']:,.0f} {DEBT_SHORT.get(one, 'high-rate debt')} first",
                    "whatif_text": "What if I pay off my " + (DEBT_NAME[one] if one else "high-rate debts"),
                    "numbers": {"high_rate_debt_balance": debts["high_rate_balance"], "high_rate_debt_rate": debts["high_rate"],
                                "high_rate_debt_interest_per_year": debts["high_rate_interest_per_year"]},
                    "why": f"You owe ${debts['high_rate_balance']:,.0f} at up to {round(debts['high_rate'] * 100)}%. "
                           f"Interest costs about ${debts['high_rate_interest_per_year']:,.0f} a year."})
    years_left = (p.retire_age or 65) - (p.age or 45)
    if match.get("rate") is not None and match.get("missed", 0) > 0 and years_left >= config.MATCH_MIN_YEARS_LEFT:
        out.append({"key": "match", "title": f"Get the full employer match: ${match['missed']:,.0f} a year",
                    "whatif_text": "What if I raise my 401(k) saving to the full match",
                    "numbers": {"match_full_contribution": match["full_contribution"], "match_missed_per_year": match["missed"]},
                    "why": f"Save ${match['full_contribution']:,.0f} a year in your 401(k) to get the full match. "
                           f"You now miss about ${match['missed']:,.0f} a year."})
    working = (p.retire_age or 65) > (p.age or 45)
    monthly = spend_now / 12 if spend_now else 0
    held_months = p.emergency_months if p.emergency_months is not None else (cash / monthly if monthly else None)
    if monthly and held_months is not None and held_months < EMERGENCY_MIN_MONTHS:
        held = cash if (cash and abs(cash / monthly - held_months) < 0.06) else held_months * monthly   # exact, not from rounded months
        short = round(max(0.0, EMERGENCY_MIN_MONTHS * monthly - held))
        out.append({"key": "emergency", "title": f"Keep {EMERGENCY_MIN_MONTHS} months of spending in cash",
                    "whatif_text": f"What if I build an emergency fund of {EMERGENCY_MIN_MONTHS} months",
                    "numbers": {"emergency_shortfall": short, "emergency_target_months": EMERGENCY_MIN_MONTHS,
                                "emergency_months_now": round(held_months, 1)},
                    "why": f"You hold about {held_months:.1f} months of spending in cash. Three months is "
                           f"${EMERGENCY_MIN_MONTHS * monthly:,.0f}, so you are ${short:,.0f} short."})
    ins = p.insurance
    dependents = any((c.age or 0) < 22 for c in p.children) or (p.has_partner and (p.partner_pay_per_year or 0) == 0 and (p.pay_per_year or 0) > 0)
    if dependents and ins.life_kind is not None:
        earner = max(p.pay_per_year or 0, p.partner_pay_per_year or 0)
        need = LIFE_COVER_YEARS * earner
        have = (ins.life_face or 0) if ins.life_kind != "none" else 0
        if need > have and earner > 0:
            out.append({"key": "life", "title": f"Add ${need - have:,.0f} of life cover",
                        "whatif_text": "What if I get life insurance",
                        "numbers": {"life_cover_needed": round(need), "life_cover_have": round(have), "life_cover_gap": round(need - have)},
                        "why": f"Ten years of pay is about ${need:,.0f}. You have ${have:,.0f}, a gap of ${need - have:,.0f}."})
    if working and ins.disability is False and pay > 0:
        out.append({"key": "disability", "title": "Get disability cover while you work",
                    "whatif_text": "What if I get disability insurance",
                    "numbers": {}, "why": "Your pay is your biggest asset. This cover protects it if you cannot work."})
    if ins.ltc is False and (p.age or 0) >= 50:
        lt = ltc_facts()
        out.append({"key": "ltc", "title": "Look into long-term care cover",
                    "whatif_text": "What if I get long-term care insurance",
                    "numbers": {"ltc_nursing_home_per_year": lt["nursing_home_per_year"], "ltc_typical_years": lt["typical_years"]},
                    "why": f"A nursing home room costs about ${lt['nursing_home_per_year']:,.0f} a year. You have no cover for it."})
    return out
