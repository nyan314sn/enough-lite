"""Tax tool: simple federal and state income tax, and the after-tax view of retirement withdrawals.

Data: app/data/tax_rules.json (IRS Rev. Proc. 2026-35, tax year 2027) and app/data/state_tax.json (Tax Foundation 2026
state rates, as an effective rate on gross pay). A rough guide, not tax advice: the child tax credit and head of
household for single parents, 401(k) contributions before tax; no other credits, no itemizing, no local tax.
"""
from __future__ import annotations

import json
from functools import lru_cache

from ..config import DATA_DIR


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    return json.load(open(DATA_DIR / name, encoding="utf-8"))


def federal_tax(ordinary: float, filing: str = "married_joint", over_65: int = 0, gains: float = 0.0) -> float:
    r = _load("tax_rules.json")
    ded = r["standard_deduction"][filing]
    ded += over_65 * r["additional_standard_deduction_aged"]["married" if filing == "married_joint" else "unmarried"]
    taxable = max(0.0, ordinary - ded)
    tax = 0.0
    br = r["ordinary_brackets"][filing]
    for i, b in enumerate(br):
        top = br[i + 1]["threshold"] if i + 1 < len(br) else float("inf")
        if taxable > b["threshold"]:
            tax += (min(taxable, top) - b["threshold"]) * b["rate"]
    if gains > 0:  # long-term gains stacked on top of ordinary income
        lt = r["long_term_capital_gains"][filing]
        zero_room = max(0.0, lt["zero_rate_max"] - taxable)
        fifteen_room = max(0.0, lt["fifteen_rate_max"] - max(taxable, lt["zero_rate_max"]))
        g = gains
        g0 = min(g, zero_room); g -= g0
        g15 = min(g, fifteen_room); g -= g15
        tax += g15 * 0.15 + g * 0.20
    return tax


def state_rate(state: str | None, gross: float, filing: str = "married_joint") -> float:
    st = _load("state_tax.json")["states"].get((state or "").upper())
    if not st or gross <= 0:
        return 0.0
    grid = st["effective_rate_by_gross"].get(filing) or st["effective_rate_by_gross"]["single"]
    pts = sorted((float(k), v) for k, v in grid.items())
    if gross <= pts[0][0]:
        return pts[0][1] * gross / pts[0][0]
    for (g0, r0), (g1, r1) in zip(pts, pts[1:]):
        if gross <= g1:
            return r0 + (r1 - r0) * (gross - g0) / (g1 - g0)
    return pts[-1][1]


def state_exempts_ss(state: str | None, age: int | None = None) -> bool:
    """Social Security is free of state tax here: most states; also Colorado from 65 (state_tax.json exempt_from_age).
    The income limits under which some of the other seven exempt it are not modelled (see the source note)."""
    rule = _load("state_tax.json").get("taxes_social_security", {})
    st = (state or "").upper()
    if st not in set(rule.get("states", [])):
        return True
    from_age = (rule.get("exempt_from_age") or {}).get(st)
    return bool(from_age is not None and age is not None and age >= from_age)


def child_credit(children_under_17: int, tax_before: float, agi: float, earned: float, filing: str) -> float:
    """The child tax credit (tax_rules.json child_tax_credit): the part that cuts tax, plus the refundable part."""
    if children_under_17 <= 0:
        return 0.0
    c = _load("tax_rules.json")["child_tax_credit"]
    start = c["phaseout_start"]["married_joint" if filing == "married_joint" else "other"]
    full = children_under_17 * c["per_child_under_17"]
    full = max(0.0, full - c["phaseout_per_1000"] * max(0, -(-(agi - start) // 1000)))
    used = min(full, tax_before)
    refund_cap = min(children_under_17 * c["refundable_max_per_child"],
                     c["refundable_rate"] * max(0.0, earned - c["refundable_earned_income_floor"]))
    return used + min(full - used, refund_cap)


ADDL_MEDICARE_RATE, ADDL_MEDICARE_SINGLE, ADDL_MEDICARE_JOINT = 0.009, 200000.0, 250000.0   # IRS Form 8959 (not indexed)


def working_years(pay: float, partner_pay: float, state: str | None, married: bool, children_under_17: int = 0,
                  pretax_contrib: float = 0.0) -> dict:
    """Tax on pay. Single parents file as head of household; 401(k)-type contributions come off taxable income (not
    payroll tax); the child tax credit applies to children under 17. No itemizing, no other credits."""
    filing = "married_joint" if married else ("head_of_household" if children_under_17 > 0 else "single")
    gross = pay + partner_pay
    pretax = max(0.0, min(pretax_contrib, gross))
    taxable = gross - pretax
    fed0 = federal_tax(taxable, filing)
    credit = child_credit(children_under_17, fed0, taxable, gross, filing)
    fed = fed0 - credit                                  # may be below zero: the refundable part of the credit
    fica = min(pay, 192300) * 0.062 + min(partner_pay, 192300) * 0.062 + gross * 0.0145
    # the additional Medicare tax: 0.9% of wages above $200,000 (single, head of household) or $250,000 (married, joint)
    fica += ADDL_MEDICARE_RATE * max(0.0, gross - (ADDL_MEDICARE_JOINT if married else ADDL_MEDICARE_SINGLE))
    st_filing = "married_joint" if married else "single"
    st = state_rate(state, taxable, st_filing) * taxable
    total = fed + st + fica
    return {
        "gross_pay": round(gross),
        "federal_tax": round(fed), "state_tax": round(st), "payroll_tax": round(fica),
        "child_tax_credit": round(credit), "pretax_contributions": round(pretax), "filing": filing,
        "after_tax_pay": round(gross - total),
        "effective_rate_working": round(total / gross, 3) if gross else 0.0,
    }


WITHDRAWAL_REF_SHARE = 0.25   # the rate on withdrawals is measured on at least this share of spending (years before
                              # Social Security or a pension starts draw more than a typical year)
MAX_WITHDRAWAL_RATE = 0.50


def retirement_years(spending: float, social_security: float, savings: dict, state: str | None, married: bool,
                     adults_over_65: int, other_income: float = 0.0) -> dict:
    """Tax on a typical retirement year: withdraw in the order taxable, then pre-tax, then Roth.
    Taxable-account withdrawals are taken as half gain; 85% of Social Security counts as income (an upper bound).

    Each income is taxed on top of the one before: Social Security first, then pensions and part-time pay, then
    withdrawals. Each gets its own rate, so the simulation can take tax off each one. The rate on withdrawals is the
    extra tax a withdrawal adds; it is measured on a withdrawal of at least a quarter of spending, so it stays
    sensible when Social Security and a pension cover nearly everything."""
    filing = "married_joint" if married else "single"
    need = max(0.0, spending - social_security - other_income)
    total = sum(float(savings.get(k, 0) or 0) for k in ("pretax", "roth", "taxable", "cash")) or 1.0
    taxable_share = (float(savings.get("taxable", 0) or 0) + float(savings.get("cash", 0) or 0)) / total
    pretax_share = float(savings.get("pretax", 0) or 0) / total
    roth_share = float(savings.get("roth", 0) or 0) / total

    base = 0.85 * social_security
    ss_state = 0.0 if state_exempts_ss(state, 65 if adults_over_65 else None) else base     # most states do not tax Social Security

    def t(ordinary: float, gains: float = 0.0) -> float:
        # ordinary includes the taxable Social Security (base); the state taxes it only where it is not exempt
        st_income = ordinary - base + ss_state + gains
        return federal_tax(ordinary, filing, adults_over_65, gains) + state_rate(state, st_income, filing) * st_income

    ss_tax = t(base)
    oi_tax = max(0.0, t(base + other_income) - ss_tax) if other_income > 0 else 0.0
    below = base + other_income

    def wd_tax(w: float) -> float:
        # over a whole retirement, withdrawals come from each pot roughly in proportion to its size
        return max(0.0, t(below + w * pretax_share, w * taxable_share * 0.5) - t(below))

    # gross up properly: find the withdrawal W that leaves `ref` after its own tax (W - tax(W) = ref)
    ref = max(need, WITHDRAWAL_REF_SHARE * spending, 1000.0)
    w = ref
    for _ in range(30):
        w_next = ref + wd_tax(w)
        if abs(w_next - w) < 0.5:
            w = w_next
            break
        w = w_next
    rate = min(MAX_WITHDRAWAL_RATE, (w - ref) / w if w > 0 else 0.0)
    tax_wd = need * rate / (1 - rate)
    return {
        "withdrawal_order": ["taxable", "pre-tax", "Roth"],
        "tax_per_year_retired": round(ss_tax + oi_tax + tax_wd),
        "effective_rate_on_withdrawals": round(rate, 3),
        "gross_withdrawal_per_year": round(need + tax_wd),
        "social_security_tax_per_year": round(ss_tax),
        "social_security_tax_rate": round(ss_tax / social_security, 3) if social_security > 0 else 0.0,
        "other_income_tax_per_year": round(oi_tax),
        "other_income_tax_rate": round(oi_tax / other_income, 3) if other_income > 0 else 0.0,
        "shares": {"taxable_and_cash": round(taxable_share, 2), "pretax": round(pretax_share, 2), "roth": round(roth_share, 2)},
    }


def limits_2027() -> dict:
    r = _load("tax_rules.json")["retirement"]
    return {"401k_limit": r["elective_deferral"], "401k_catch_up_50_plus": r["catch_up_50_plus"],
            "401k_catch_up_60_to_63": r["catch_up_60_to_63"], "ira_limit": r["ira_limit"], "ira_catch_up_50_plus": r["ira_catch_up_50_plus"]}
