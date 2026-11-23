"""The 'What we have so far' rows: each field has a section, a display string, a source and an editor hint.

Sections: Household, Work & pay, Saving, Home & debts, Pensions & income, Insurance, Goals, Health, Costs.
Works on a profile that has not been completed (a missing value is skipped or shown as not given).
"""
from __future__ import annotations

from typing import Any

from ..schemas import FieldOut, Profile
from ..tools import costs

SECTIONS = ["Household", "Work & pay", "Saving", "Home & debts", "Pensions & income", "Insurance", "Goals", "Health", "Costs"]


def _m(x: float | None) -> str:
    return "unknown" if x is None else f"${x:,.0f}"


def _ss_display(p: Profile) -> str:
    """'$33,000 a year at 67': the age the figure is read at, so it can be matched with the plan, which may start it at
    another age (the plan's assumptions give both)."""
    base = f"{_m(p.social_security_per_year)} a year"
    if p.age is None or not p.social_security_per_year:
        return base
    from .. import household
    est = p.sources.get("social_security_per_year") == "estimate"
    at = p.claim_age if p.claim_age is not None else (household.claim_age(p) if est else household.FRA)
    if p.age >= at or p.age >= household.claim_age(p):      # already claiming: the figure as given
        return base
    return base + f" at {at}" + (" (each at their own age)" if est and p.has_partner and p.partner_age else "")


def _saving_display(p: Profile) -> str:
    """'Yearly saving' as the plan uses it (costs.saving_now): the total and its parts, the assumed part marked."""
    if p.age is None or p.retire_age is None or p.retire_age <= p.age:
        return f"{round((p.save_rate or 0) * 100)}% of pay" if p.save_rate else "None: you are retired"
    try:
        sv = costs.saving_now(p)
    except Exception:       # an unfinished profile: the simple form
        return f"{round(p.save_rate * 100)}% of pay, about {_m(p.save_rate * p.household_pay())} a year"
    assumed = p.sources.get("save_rate") != "you said" and not p.saving.given()
    parts = []
    if sv["accounts_per_year"]:
        parts.append(f"{_m(sv['accounts_per_year'])} into a 401(k) or IRA" + (f", an assumed {round(p.save_rate * 100)}% of pay" if assumed else ""))
    if sv["match_per_year"]:
        parts.append(f"{_m(sv['match_per_year'])} employer match")
    if sv["other_per_year"]:
        parts.append(f"{_m(sv['other_per_year'])} other saving")
    if sv["unspent_pay_per_year"] > 0:
        parts.append(f"{_m(sv['unspent_pay_per_year'])} of take-home pay left after spending")
    if sv["per_year"] < 0:
        return f"None, as spending now is {_m(-sv['per_year'])} a year above take-home pay (taken from savings)"
    if sv["unspent_pay_per_year"] < 0:
        return f"About {_m(sv['per_year'])} a year, what take-home pay leaves after spending" + (", less than the 10% of pay assumed" if assumed else "") + (f", plus a {_m(sv['match_per_year'])} employer match" if sv["match_per_year"] else "")
    return f"About {_m(sv['per_year'])} a year" + (" (" + "; ".join(parts) + ")" if parts else "")


def _pct(x: float) -> str:
    return f"{x * 100:g}%"


def _src(p: Profile, key: str, default: str = "you said") -> str:
    return p.sources.get(key, default)


def _number(ask: str, lo: int, hi: int) -> dict:
    return {"kind": "number", "ask": ask, "min": lo, "max": hi}


def _money(ask: str, per: str = "year") -> dict:
    return {"kind": "money", "ask": ask, "per": per}


def _group(ask: str) -> dict:
    return {"kind": "group", "ask": ask}


def _choice(ask: str, options: list[str]) -> dict:
    return {"kind": "choice", "ask": ask, "options": options}


DEBT_LABEL = {"student": "Student loan", "car": "Car loan", "credit_card": "Credit card", "other": "Other debt"}


def _debt_line(d) -> str:
    bits = [DEBT_LABEL.get(d.kind, "Debt"), _m(d.balance)]
    if d.rate is not None:
        bits.append(f"at {_pct(d.rate)}" + (" (assumed)" if "rate" in d.assumed else ""))
    if d.monthly_payment:
        bits.append(f"{_m(d.monthly_payment)} a month" + (" (assumed)" if "monthly_payment" in d.assumed else ""))
    return " ".join(bits[:2]) + "".join(", " + b for b in bits[2:])


def _pension_line(x, has_partner: bool = False) -> str:
    """'You: $24,000 a year from 65, rises with prices'"""
    who = "You" if x.who == "you" else "Partner"
    text = f"{who}: {_m(x.per_year)} a year"
    if x.start_age is not None:
        text += f" from {x.start_age}" + (" (assumed)" if "start_age" in x.assumed else "")
    if x.inflation_adjusted is not None:
        text += ", rises with prices" if x.inflation_adjusted else ", does not rise with prices"
    if has_partner and x.survivor_share is not None:
        text += f", {_pct(x.survivor_share)} goes to a surviving partner"
    return text


def typical_rent(p: Profile) -> tuple[float, str]:
    """The rent the plan uses when a renter gives none: the state's HUD one-bedroom rent (a couple: a quarter more), and where it comes from."""
    from ..tools.family_costs import _load
    b = _load("basics.json")
    row = b["states"].get((p.state or "").upper(), b["us"])
    return float(row["rent_1br"]) * (1.25 if p.has_partner else 1.0), (f"the typical rent in {p.state.upper()}" if p.state and p.state.upper() in b["states"] else "the typical US rent")


def _home_line(h, pay_est: bool = False, typical: tuple[float, str] | None = None) -> str:
    if not h.owns:
        if h.rent:
            return f"Rent, {_m(h.rent)} a month"
        return f"Rent, about {_m(typical[0])} a month (estimate: {typical[1]}, HUD)" if typical else "Rent, amount not given"
    if h.mortgage_balance > 0 and h.mortgage_payment > 0:
        mort = f"{_m(h.mortgage_balance)} left on the mortgage, {_m(h.mortgage_payment)} a month" + (" (estimate)" if pay_est else "")
    elif h.mortgage_payment > 0:
        mort = f"mortgage payment {_m(h.mortgage_payment)} a month"
    elif h.mortgage_balance > 0:
        mort = f"{_m(h.mortgage_balance)} left on the mortgage"
    else:
        mort = "no mortgage"
    return f"Own, {mort}, " + (f"worth {_m(h.value)}" if h.value else "value not given")


# optional groups: a field in a group the person has not touched is a typical figure ("default"), not an assumption they are checking
FIELD_GROUP = {"debts": "debts", "pensions": "pension", "contributions": "saving", "match": "saving", "other_saving": "saving", "save_rate": "saving",
               "life_insurance": "insurance", "disability": "insurance", "ltc": "insurance", "legacy": "goals", "big_costs": "goals",
               "parents_help": "goals", "college": "goals", "health": "health", "partner_health": "health", "sex": "health", "partner_sex": "health",
               "part_time": "costs", "inheritance": "costs", "budget": "costs", "emergency_months": "costs"}
GROUP_DATA = {"debts": ("debts",), "pension": ("pensions",), "saving": ("saving", "save_rate"), "insurance": ("insurance",),
              "goals": ("goals", "college"), "health": ("health", "partner_health", "sex", "partner_sex"),
              "costs": ("budget", "part_time", "inheritance", "emergency_months")}


def touched(p: Profile, group: str) -> bool:
    """The person gave data for this group, or answered it (a plain no counts). 'Skip, use typical' does not."""
    if any(p.sources.get(k) == "you said" for k in GROUP_DATA.get(group, ())):
        return True
    return group in p.offered and p.notes.get("skip_all") != "yes"


def _row(r, k):
    return getattr(r, k, None) if not isinstance(r, dict) else r.get(k)


def _section_note(sec: str, mine: list) -> str:
    """For a section the person has not filled in: the figure the plan uses, marked as an estimate, or 'None counted'.
    The panel shows it beside the section's name, so a skipped answer shows its figure without opening the section."""
    by = {_row(r, "key"): r for r in mine}

    def est(k):
        r = by.get(k)
        return r if r is not None and _row(r, "source") != "you said" else None
    parts: list[str] = []
    if sec == "Saving" and (r := est("savings")) is not None and isinstance(_row(r, "value"), dict):
        parts.append(f"Estimate: {_m(sum(float(v or 0) for v in _row(r, 'value').values()))} saved")
    elif sec == "Home & debts":
        if (r := est("home")) is not None:
            parts.append("Estimate: " + str(_row(r, "display")))
        d = by.get("debts")
        if d is not None and str(_row(d, "display")).startswith("None"):
            parts.append("no other debts counted")
        elif d is not None:
            parts.append("Estimate: " + str(_row(d, "display")))
    elif sec == "Pensions & income":
        if (r := est("social_security_per_year")) is not None:
            parts.append(f"Estimate: Social Security {_row(r, 'display')}")
        pn = by.get("pensions")
        if pn is not None and str(_row(pn, "display")).startswith("None"):
            parts.append("no pension counted")
    elif sec in ("Insurance", "Goals") and mine and all(str(_row(r, "display")).startswith("None") for r in mine):
        parts.append("None counted")
    elif sec == "Health" and (r := est("health")) is not None:
        parts.append(f"Estimate: {str(_row(r, 'display')).lower()} health")
    elif sec == "Costs" and (r := est("spending_now_per_year")) is not None:
        parts.append("Estimate: " + str(_row(r, "display")).split(", about")[0])
    return "; ".join(parts)


def sections_status(rows_: list) -> list[dict[str, str]]:
    """[{section, status, note}]: added when any field in the section is the person's own word, else default. A section that is
    not filled in carries a note with its estimated figure, or 'None counted'."""
    out = []
    for sec in SECTIONS:
        mine = [r for r in rows_ if _row(r, "section") == sec]
        added = any(_row(r, "source") == "you said" for r in mine)
        est = not added and any(_row(r, "source") == "estimate" for r in mine)
        item = {"section": sec, "status": "added" if added else ("estimated" if est and sec == "Home & debts" else "default")}
        if not added and (note := _section_note(sec, mine)):
            item["note"] = note
        out.append(item)
    return out


def rows(p: Profile, offered_none: bool = True) -> list[dict[str, Any]]:
    """Plain dicts: key, label, section, value, display, source, note, editable."""
    out: list[dict[str, Any]] = []
    done = set(p.offered)

    def add(key, label, section, value, display, source, note="", editable=None):
        out.append({"key": key, "label": label, "section": section, "value": value, "display": display, "source": source,
                    "note": note, "editable": editable})

    # Household
    if p.age is not None:
        add("age", "Your age", "Household", p.age, str(p.age), _src(p, "age"), p.notes.get("age", ""), _number("age", 18, 110))
    if p.has_partner and p.partner_age is not None:
        add("partner_age", "Partner's age", "Household", p.partner_age, str(p.partner_age), _src(p, "partner_age"), p.notes.get("partner_age", ""), _number("partner_age", 18, 110))
    if p.age is not None:
        add("sex", "Your sex (life table only)", "Household", p.sex, p.sex.title() if p.sex else "Not given, the average of the two tables",
            "you said" if p.sex else "assumed", "Only used to pick the right life table.", _choice("sex", ["male", "female"]))
    if p.has_partner:
        add("partner_sex", "Partner's sex (life table only)", "Household", p.partner_sex,
            p.partner_sex.title() if p.partner_sex else "Not given, the average of the two tables", "you said" if p.partner_sex or p.sources.get("partner_sex") == "you said" else "assumed", "",
            _choice("partner_sex", ["male", "female"]))
    if p.state:
        from . import parser
        add("state", "State", "Household", p.state, parser.STATE_NAME.get(p.state, p.state), _src(p, "state"), "", {"kind": "text", "ask": "state"})
    elif p.age is not None and (p.notes.get("skipped_state") == "yes" or p.notes.get("skip_all") == "yes"):
        # round 4: an assumed state is shown, not left out
        add("state", "State", "Household", None, "Not given: typical US taxes and costs", "assumed",
            "You did not say. Give your state for its taxes and costs.", {"kind": "text", "ask": "state"})
    if not (p.sources.get("children") or p.children) and p.notes.get("skipped_children_count") == "yes":
        add("children", "Children", "Household", [], "None counted", "assumed", "You did not say. No children are counted; add them if you have any.", _group("children"))
    if p.sources.get("children") or p.children:
        ages = [str(c.age) for c in p.children if c.age is not None]
        n = len(p.children)
        agetxt = ((", ages " if len(ages) > 1 else ", age ") + (", ".join(ages[:-1]) + " and " + ages[-1] if len(ages) > 1 else ages[0])) if ages else ", ages not given"
        disp = "None" if not n else f"{n} {'child' if n == 1 else 'children'}{agetxt}"
        add("children", "Children", "Household", [c.model_dump() for c in p.children], disp, _src(p, "children"), p.notes.get("children", ""), _group("children"))
    if p.children:
        from . import college as _college
        for i, c in enumerate(p.children):        # one row per child: that child's own type and share, and its own note
            label, disp = _college.line(i, c)
            said = c.college_source == "you said" or (c.college_source is None and c.college_type is not None and p.sources.get("college") != "assumed")
            add(f"college_{i}", label, "Household", c.model_dump(), disp, "you said" if said else "estimate",
                "" if said else _college.estimate_note(c), {"kind": "college", "ask": "college", "child": i, "options": ["public", "private", "none"]})
    if p.pets or p.sources.get("pets"):
        add("pets", "Pets", "Household", [x.model_dump() for x in p.pets], ", ".join(f"{x.count} {x.kind}{'s' if x.count > 1 else ''}" for x in p.pets) or "None",
            _src(p, "pets"), "", _group("pets"))

    # Work & pay
    if p.job:
        add("job", "Your job", "Work & pay", p.job, p.job, _src(p, "job"), "", {"kind": "text", "ask": "job"})
    if p.has_partner and p.partner_job:
        add("partner_job", "Partner's job", "Work & pay", p.partner_job, p.partner_job, _src(p, "partner_job"), "", {"kind": "text", "ask": "partner_job"})
    if p.pay_per_year is not None:
        add("pay_per_year", "Your pay", "Work & pay", p.pay_per_year, (f"{_m(p.pay_per_year)} a year" if p.pay_per_year else "No pay"), _src(p, "pay_per_year"), p.notes.get("pay_per_year", ""), _money("pay_per_year"))
    if p.has_partner and p.partner_pay_per_year is not None:
        add("partner_pay_per_year", "Partner's pay", "Work & pay", p.partner_pay_per_year, (f"{_m(p.partner_pay_per_year)} a year" if p.partner_pay_per_year else "No pay"),
            _src(p, "partner_pay_per_year"), p.notes.get("partner_pay_per_year", ""), _money("partner_pay_per_year"))
    if p.retire_age is not None:
        add("retire_age", "Retirement age", "Work & pay", p.retire_age, str(p.retire_age), _src(p, "retire_age"), p.notes.get("retire_age", ""), _number("retire_age", 30, 80))
    if p.has_partner and p.partner_retire_age is not None and not (p.partner_pay_per_year == 0 and _src(p, "partner_retire_age", "assumed") != "you said"):     # a partner with no pay has no retirement age to show
        add("partner_retire_age", "Partner's retirement age", "Work & pay", p.partner_retire_age, str(p.partner_retire_age),
            _src(p, "partner_retire_age", "assumed"), p.notes.get("partner_retire_age", ""), _number("partner_retire_age", 30, 80))
    if p.part_time and p.part_time.per_year:
        add("part_time", "Part-time work in retirement", "Work & pay", p.part_time.model_dump(),
            f"{_m(p.part_time.per_year)} a year until {p.part_time.until_age or 70}", _src(p, "part_time"), p.notes.get("part_time", ""), _group("costs"))

    # Saving
    if p.savings_known:
        s = p.savings
        parts = [f"{_m(v)} {lbl}" for v, lbl in ((s.pretax, "pre-tax (401(k) or IRA)"), (s.roth, "Roth"), (s.taxable, "taxable"), (s.cash, "cash")) if v]
        add("savings", "Savings", "Saving", s.model_dump(), ", ".join(parts) if parts else "None", _src(p, "savings"), p.notes.get("savings", ""),
            {"kind": "split", "ask": "savings_split", "parts": ["pretax", "roth", "taxable", "cash"]})
    if p.save_rate is not None:
        # the full yearly saving the plan uses (costs.saving_now), in its parts, so the panel and the plan show one figure;
        # the pen opens the saving questions (401(k) or IRA saving and the match), the part a person sets
        add("save_rate", "Yearly saving", "Saving", p.save_rate, _saving_display(p), _src(p, "save_rate"), p.notes.get("save_rate", ""),
            _group("saving"))
    sv = p.saving
    c = costs.contributions(p) if p.age is not None else None
    if sv.contrib_you is not None or sv.contrib_partner is not None:
        parts = []
        if sv.contrib_you is not None:
            parts.append(f"you {_m(sv.contrib_you)}")
        if sv.contrib_partner is not None:
            parts.append(f"partner {_m(sv.contrib_partner)}")
        add("contributions", "401(k) or IRA saving a year", "Saving", sv.model_dump(), ", ".join(parts) + " a year", _src(p, "saving"), "", _group("saving"))
    elif p.age is not None:
        add("contributions", "401(k) or IRA saving a year", "Saving", None, f"Not given, {round((p.save_rate or 0) * 100)}% of pay assumed", "assumed", "", _group("saving"))
    if sv.match_rate is not None:
        cap = sv.match_cap if sv.match_cap is not None else costs.DEFAULT_MATCH_CAP
        add("match", "Employer match", "Saving", {"rate": sv.match_rate, "cap": cap},
            f"{_pct(sv.match_rate)} of what you save, up to {_pct(cap)} of pay" + ("" if sv.match_cap is not None else " (cap assumed)"), _src(p, "saving"), "", _group("saving"))
    elif p.age is not None:
        add("match", "Employer match", "Saving", None, "None given", "assumed" if "saving" not in done else "you said", "", _group("saving"))
    if sv.other_per_month is not None:
        add("other_saving", "Other saving", "Saving", sv.other_per_month, f"{_m(sv.other_per_month)} a month", _src(p, "saving"), "", _group("saving"))
    if p.emergency_months is not None:
        add("emergency_months", "Emergency fund", "Saving", p.emergency_months, f"{p.emergency_months:g} {'month' if p.emergency_months == 1 else 'months'} of spending in cash",
            _src(p, "emergency_months", "estimate"), p.notes.get("emergency_months", ""), {"kind": "number", "ask": "costs", "min": 0, "max": 60})
    if p.risk:
        add("risk", "Investing style", "Saving", p.risk, p.risk.title(), _src(p, "risk"), p.notes.get("risk", ""), _choice("risk", ["careful", "balanced", "growth"]))

    # Home & debts
    if p.home.owns is not None:
        h = p.home
        rent_typ = typical_rent(p) if h.owns is False and not h.rent else None
        disp = _home_line(h, p.notes.get("mortgage_payment_est") == "yes", rent_typ)
        hv = h.model_dump()
        if not h.value:
            hv["value"] = None
        note = p.notes.get("home", "") or ("You gave no rent. The plan uses this typical figure until you give yours." if rent_typ else "")
        add("home", "Home", "Home & debts", hv, disp, _src(p, "home"), note,_choice("home", ["own outright", "own with a mortgage", "rent"]))
        if h.owns and h.mortgage_balance > 0 and h.mortgage_payment > 0:
            m = costs.mortgage_end(p)
            if m:
                add("mortgage_end", "Mortgage paid off", "Home & debts", m, f"Paid off in {m['end_year']}, costs fall by about {_m(m['drop_per_year'])} a year",
                    "estimate", f"Worked out from the balance, payment and a {_pct(m['rate'])} rate" + (" (assumed)" if h.mortgage_rate is None or p.sources.get("mortgage_rate") == "assumed" else "") + ".", None)
    elif p.age is not None and p.notes.get("skipped_home") == "yes":
        from .. import household
        try:
            housing = household.basics(household.complete(p))["housing"]
        except Exception:       # noqa: BLE001  an unfinished profile: say it without the figure
            housing = None
        add("home", "Home", "Home & debts", None,
            "Not given. Typical housing costs used" + (f": about {_m(housing)} a year" if housing else ""), "estimate",
            "You skipped this. The plan uses the typical housing cost for your state (Census). Tell me if you rent or own.",
            _choice("home", ["own outright", "own with a mortgage", "rent"]))
    if p.debts or p.age is not None:
        if p.debts:
            add("debts", "Other debts", "Home & debts", [d.model_dump() for d in p.debts], "; ".join(_debt_line(d) for d in p.debts), _src(p, "debts"),
                p.notes.get("debts", ""), _group("debts"))
        else:
            add("debts", "Other debts", "Home & debts", [], "None counted", "you said" if "debts" in done else "assumed", "", _group("debts"))

    # Pensions & income
    if p.social_security_per_year is not None:
        add("social_security_per_year", "Social Security", "Pensions & income", p.social_security_per_year, _ss_display(p),
            _src(p, "social_security_per_year"), p.notes.get("social_security_per_year", ""), _money("social_security_per_year"))
    if p.pensions:
        add("pensions", "Pensions", "Pensions & income", [x.model_dump() for x in p.pensions], "; ".join(_pension_line(x, p.has_partner) for x in p.pensions),
            _src(p, "pensions"), p.notes.get("pensions", ""), _group("pension"))
    elif p.age is not None:
        add("pensions", "Pensions", "Pensions & income", [], "None counted", "you said" if "pension" in done else "assumed", "", _group("pension"))
    if p.inheritance and p.inheritance.amount:
        i = p.inheritance
        add("inheritance", "Possible gift" if i.gift else "Possible inheritance", "Pensions & income", i.model_dump(),
            f"{_m(i.amount)}" + (f" in {i.year}" if i.year else "") + (", counted in the plan" if i.count else ", not counted (information only)"),
            _src(p, "inheritance"), "Counted only if you say to count it.", _group("costs"))

    # Insurance
    ins = p.insurance
    if p.age is not None:
        life = {"none": "None", "term": "Term life", "whole": "Whole life", None: "None counted"}[ins.life_kind]
        if ins.life_kind in ("term", "whole"):
            life += f", {_m(ins.life_face)} cover" if ins.life_face else ""
            life += f", premium {_m(ins.life_premium)} a year" if ins.life_premium else ""
        add("life_insurance", "Life insurance", "Insurance", {"kind": ins.life_kind, "face": ins.life_face, "premium": ins.life_premium}, life,
            _src(p, "insurance") if ins.life_kind else "assumed", "", _group("insurance"))
        add("disability", "Disability insurance", "Insurance", ins.disability, {True: "Yes", False: "No", None: "None counted"}[ins.disability],
            _src(p, "insurance") if ins.disability is not None else "assumed", "", _group("insurance"))
        add("ltc", "Long-term care insurance", "Insurance", ins.ltc, {True: "Yes", False: "No", None: "None counted"}[ins.ltc],
            _src(p, "insurance") if ins.ltc is not None else "assumed", "", _group("insurance"))

    # Goals
    g = p.goals
    if p.age is not None:
        wish = g.legacy is None and p.notes.get("legacy_wish") == "yes"       # "leave something to our daughter": a wish, no amount
        add("legacy", "Money to leave behind", "Goals", g.legacy, "A wish noted, no amount" if wish else (_m(g.legacy) if g.legacy else "None"),
            "you said" if wish else (_src(p, "goals") if g.legacy is not None else "assumed"), "Not counted in the plan. Give an amount if you want one." if wish else "",
            _group("goals"))
        add("big_costs", "Big planned costs", "Goals", [b.model_dump() for b in g.big_costs],
            "; ".join(f"{b.label} {_m(b.amount)}" + (f" in {b.year}" if b.year else "") for b in g.big_costs) or "None",
            _src(p, "goals") if g.big_costs else "assumed", "", _group("goals"))
        add("parents_help", "Helping parents", "Goals", {"per_year": g.parents_per_year, "years": g.parents_years},
            f"{_m(g.parents_per_year)} a year for {g.parents_years} years" if g.parents_per_year else "None", _src(p, "goals") if g.parents_per_year else "assumed", "", _group("goals"))

    # Health
    if p.age is not None:
        add("health", "Your health", "Health", p.health, (p.health or "good").title(), _src(p, "health", "assumed") if p.health else "assumed",
            p.notes.get("health", "Assumed good health, which leaves the life table as it is."), _choice("health", ["excellent", "good", "fair", "poor"]))
    if p.has_partner:
        add("partner_health", "Partner's health", "Health", p.partner_health, (p.partner_health or "good").title(),
            _src(p, "partner_health", "assumed") if p.partner_health else "assumed", "", _choice("partner_health", ["excellent", "good", "fair", "poor"]))

    # Costs now and later
    if p.spending_now_per_year is not None:
        add("spending_now_per_year", "Spending now", "Costs", p.spending_now_per_year, f"{_m(p.spending_now_per_year)} a year, about {_m(p.spending_now_per_year / 12)} a month",
            _src(p, "spending_now_per_year"), p.notes.get("spending_now_per_year", ""), _money("spending_now_per_year"))
    if p.budget.given():
        b = p.budget
        add("budget", "Spending split, a month", "Costs", b.model_dump(),
            ", ".join(f"{k} {_m(v)} a month" for k, v in b.model_dump().items() if v), _src(p, "budget"), "", _group("costs"))
    if p.spending_per_year is not None:
        add("spending_per_year", "Spending in retirement", "Costs", p.spending_per_year, f"{_m(p.spending_per_year)} a year",
            _src(p, "spending_per_year"), p.notes.get("spending_per_year", ""), _money("spending_per_year"))
    return out


def fields(p: Profile) -> list[FieldOut]:
    out = []
    for r in rows(p):
        grp = FIELD_GROUP.get(r["key"])
        if grp and not touched(p, grp):
            r["source"] = "default"
            if r["display"] in ("None", "None given", "Not given", "No") and r["key"] not in ("health", "partner_health"):
                r["display"] = "None counted"       # the plan counts nothing here until the person adds it
        if not r["display"]:
            r["display"] = "Not given"
        out.append(FieldOut(**r))
    return out
