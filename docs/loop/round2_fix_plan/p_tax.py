"""Patch (audit A P2): additional Medicare tax, 401(k) catch-up at 60 to 63, Colorado's Social Security exemption at 65,
the tax agent's withdrawal order, status-line actions. Usage: p_tax.py"""
import json
from pathlib import Path

L = Path(__file__).resolve().parents[3]


def sub(rel, old, new):
    f = L / rel
    s = f.read_text(encoding="utf-8")
    assert s.count(old) == 1, (rel, old[:60], s.count(old))
    f.write_text(s.replace(old, new), encoding="utf-8")


T = "app/tools/tax.py"
sub(T, '''def state_exempts_ss(state: str | None) -> bool:
    return (state or "").upper() not in set(_load("state_tax.json").get("taxes_social_security", {}).get("states", []))''',
    '''def state_exempts_ss(state: str | None, age: int | None = None) -> bool:
    """Social Security is free of state tax here: most states; also Colorado from 65 (state_tax.json exempt_from_age).
    The income limits under which some of the other seven exempt it are not modelled (see the source note)."""
    rule = _load("state_tax.json").get("taxes_social_security", {})
    st = (state or "").upper()
    if st not in set(rule.get("states", [])):
        return True
    from_age = (rule.get("exempt_from_age") or {}).get(st)
    return bool(from_age is not None and age is not None and age >= from_age)''')
sub(T, '''    ss_state = 0.0 if state_exempts_ss(state) else base     # most states do not tax Social Security''',
    '''    ss_state = 0.0 if state_exempts_ss(state, 65 if adults_over_65 else None) else base     # most states do not tax Social Security''')
sub(T, '''    fica = min(pay, 192300) * 0.062 + min(partner_pay, 192300) * 0.062 + gross * 0.0145''',
    '''    fica = min(pay, 192300) * 0.062 + min(partner_pay, 192300) * 0.062 + gross * 0.0145
    # the additional Medicare tax: 0.9% of wages above $200,000 (single, head of household) or $250,000 (married, joint)
    fica += ADDL_MEDICARE_RATE * max(0.0, gross - (ADDL_MEDICARE_JOINT if married else ADDL_MEDICARE_SINGLE))''')
sub(T, '''def working_years(pay: float,''', '''ADDL_MEDICARE_RATE, ADDL_MEDICARE_SINGLE, ADDL_MEDICARE_JOINT = 0.009, 200000.0, 250000.0   # IRS Form 8959 (not indexed)


def working_years(pay: float,''')

C = "app/tools/costs.py"
sub(C, '''    def cap(a: int | None) -> float:
        return lim["401k_limit"] + (lim["401k_catch_up_50_plus"] if (a or 0) >= 50 else 0)''',
    '''    def cap(a: int | None) -> float:
        # the catch-up: from 50, and the larger one from 60 to 63 (SECURE 2.0)
        extra = lim["401k_catch_up_60_to_63"] if 60 <= (a or 0) <= 63 else lim["401k_catch_up_50_plus"] if (a or 0) >= 50 else 0
        return lim["401k_limit"] + extra''')

A = "app/agents/adviser.py"
sub(A, '''    state_ss = "" if tax_mod.state_exempts_ss(p.state) else " Your state taxes part of it too."''',
    '''    state_ss = "" if tax_mod.state_exempts_ss(p.state, max(age, ra)) else " Your state taxes part of it too."''')
sub(A, '''STATUS_RE = re.compile(r"^\\s*(?:keep (?:your spending|saving|spending|going|on)|continue|stay)\\b", re.I)''',
    '''STATUS_RE = re.compile(r"^\\s*(?:keep\\b(?! about \\d)|continue|stay|stick|maintain|remain|plan for your money to last)\\b", re.I)''')

X = "app/agents/tax.py"
sub(X, '''"of income goes to tax now and in retirement, and which accounts to draw on first. This is a rough guide, "
                    "not tax advice.")''', '''"of income goes to tax now and in retirement, and which accounts to draw on first: taxable savings first, then "
                    "pre-tax accounts such as a 401(k), and Roth accounts last (the order the tool uses). This is a rough guide, "
                    "not tax advice.")''')

f = L / "app/data/state_tax.json"
d = json.loads(f.read_text(encoding="utf-8"))
r = d["taxes_social_security"]
r["exempt_from_age"] = {"CO": 65}
r["note"] = ("States that tax some Social Security benefits in 2026 (West Virginia finished its phase-out in 2026). All other states "
             "exempt it. Colorado exempts it in full from 65 (modelled). The others exempt it below an income limit, not modelled: "
             "CT (AGI under $75,000 single, $100,000 joint), MN (a subtraction that phases out above about $82,000 single, $105,000 "
             "joint), MT (taxed like the federal rules, with a senior deduction), NM (under $100,000 single, $150,000 joint), RI (from "
             "full retirement age, under about $104,000 single, $130,000 joint), UT (a credit that phases out above $45,000 single, "
             "$75,000 joint), VT (under $50,000 single, $65,000 joint). So the plan may overstate state tax on Social Security there. "
             "Source: Tax Foundation, 'Does Your State Tax Social Security Benefits?' (2025) and state revenue pages; limits rounded.")
f.write_text(json.dumps(d, indent=1), encoding="utf-8")
print("ok")
