"""Intake agent: plain text -> profile fields, each shown with where it came from.

AI first, rules as checks. Every message goes to one small model call (turn_read.py) that returns a structured
TurnRead: the intent, the facts with their evidence quotes, and any question asked. The guard (turn_guard.py) keeps
only what the message backs up, and the rule parser runs as a cross-check. With no key, or when the AI is down, the
rule parser alone reads the message. Gaps are filled with estimates (pay from job and state, Social Security from pay,
spending from take-home pay) and assumptions; every reply says which ones it used.
"""
from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from .. import household, llm, safety
from ..schemas import BigCost, Debt, FieldOut, Goals, Inheritance, IntakeResponse, Pension, PartTime, Pet, Profile, Question
from . import intake_answers as answers
from . import intake_fields, intake_round2 as r2, intake_support as sup, parser, parser_extra, turn_guard, turn_read
from .base import RunCtx, run_model

REQUIRED = ("age", "state", "savings")
SKIP = ("skip", "don't know", "dont know", "do not know", "idk", "dunno", "no clue", "not sure", "no idea", "pass", "rather not say", "prefer not to say")
RE_ESTIMATE = ("pay_per_year", "partner_pay_per_year", "retire_age", "risk", "social_security_per_year", "spending_per_year",
               "save_rate", "partner_age", "spending_now_per_year", "emergency_months", "health", "partner_health", "partner_retire_age")


LABELS = {"age": "Your age", "partner_age": "Partner's age", "state": "State", "job": "Your job", "partner_job": "Partner's job",
          "pay_per_year": "Your pay", "partner_pay_per_year": "Partner's pay", "savings": "Savings", "home": "Home",
          "children": "Children", "pets": "Pets", "retire_age": "Retirement age", "spending_per_year": "Spending in retirement",
          "social_security_per_year": "Social Security", "risk": "Investing style", "save_rate": "Yearly saving"}


def _money(x: float | None) -> str:
    return "unknown" if x is None else f"${x:,.0f}"


def _join(xs: list[str]) -> str:
    xs = [x for x in xs if x]
    return ", ".join(xs[:-1]) + " and " + xs[-1] if len(xs) > 1 else (xs[0] if xs else "")


def apply(p: Profile, facts: dict[str, Any]) -> list[str]:
    """Write stated facts into the profile. Returns the keys that changed."""
    changed: list[str] = []

    def said(key: str):
        p.sources[key] = "you said"
        p.notes.pop(key, None)
        if key not in changed:
            changed.append(key)

    for k in ("age", "partner_age", "state", "job", "partner_job", "retire_age", "spending_per_year", "social_security_per_year", "risk",
              "pay_per_year", "partner_pay_per_year", "spending_now_per_year", "partner_retire_age", "sex", "partner_sex", "health",
              "partner_health", "emergency_months"):
        if k in facts and facts[k] is not None:
            setattr(p, k, facts[k])
            said(k)
    if "social_security_per_year" in facts:
        parts = facts.get("social_security_parts")
        if isinstance(parts, list) and len(parts) == 2 and all(isinstance(x, (int, float)) for x in parts):
            p.notes["ss_parts"] = f"{_money(parts[0])} for you and {_money(parts[1])} for your partner"
        else:
            p.notes.pop("ss_parts", None)
    if "retire_spend_ratio" in facts:
        p.retire_spend_ratio = facts["retire_spend_ratio"]
        p.sources["retire_spend_ratio"] = "you said"
        if p.spending_now_per_year and "spending_per_year" not in facts:
            p.spending_per_year = None            # worked out again from the new share
        said("spending_per_year")
        if "spending_per_year" not in facts:
            p.sources.pop("spending_per_year", None)
    for key in facts.get("use_typical", []):
        setattr(p, key, None)
        p.sources.pop(key, None)
        p.notes.pop(key, None)
        changed.append(key)
    if "has_partner" in facts and not (bool(facts["has_partner"]) == p.has_partner and p.sources.get("has_partner") == "you said"):
        p.has_partner = bool(facts["has_partner"])
        if not p.has_partner:
            p.partner_age, p.partner_pay_per_year = None, None
        said("has_partner")
    if "household_pay" in facts:
        if p.partner_pay_per_year is not None and p.sources.get("partner_pay_per_year") == "you said":
            p.pay_per_year = max(0.0, facts["household_pay"] - p.partner_pay_per_year)
        else:
            p.pay_per_year = facts["household_pay"]
        said("pay_per_year")
    if facts.get("retired"):
        p.notes["retired"] = "yes"
        if p.age and p.sources.get("retire_age") != "you said":
            p.retire_age = p.age
            said("retire_age")
        if "pay_per_year" not in facts:
            p.pay_per_year = 0
            said("pay_per_year")
    if "retire_in_years" in facts and p.age:
        p.retire_age = p.age + facts["retire_in_years"]
        said("retire_age")
    kinds = [k for k in ("pretax", "roth", "taxable", "cash") if "savings." + k in facts]
    if "savings.mix" in facts:
        t = p.savings.total
        p.savings.pretax, p.savings.roth, p.savings.taxable, p.savings.cash = (t * x for x in facts["savings.mix"])
        p.savings_known = True
        said("savings")
    elif kinds:
        if facts.get("savings.replace"):
            p.savings.pretax = p.savings.roth = p.savings.taxable = p.savings.cash = 0.0
        for k in kinds:
            setattr(p.savings, k, float(facts["savings." + k]))
        p.savings_known = True
        said("savings")
    elif "savings.total" in facts:
        t = float(facts["savings.total"])
        p.savings.pretax, p.savings.roth, p.savings.taxable, p.savings.cash = t * 0.6, t * 0.1, t * 0.2, t * 0.1
        p.savings_known = True
        p.sources["savings"] = "assumed"       # the total is theirs; the split is assumed
        p.notes["savings"] = "You gave the total. I assumed 60% pre-tax, 10% Roth, 20% taxable and 10% cash; change the split if you know it."
        changed.append("savings")
    home_keys = [k for k in facts if k.startswith("home.") and k != "home.has_mortgage"]
    for k in home_keys:
        setattr(p.home, k.split(".", 1)[1], facts[k])
    if home_keys:
        said("home")
    # the mortgage: is there one, and which of its figures did the person give?
    if facts.get("home.owns") is False:
        for k in ("mortgage", "mortgage_balance_said", "mortgage_payment_said"):
            p.notes.pop(k, None)
    elif facts.get("home.has_mortgage") or (facts.get("home.mortgage_balance") or 0) > 0 or (facts.get("home.mortgage_payment") or 0) > 0:
        p.notes["mortgage"] = "yes"
    elif facts.get("home.mortgage_balance") == 0:
        p.notes["mortgage"] = "no"
        p.home.mortgage_payment = 0.0
    for part in ("balance", "payment"):
        if (facts.get(f"home.mortgage_{part}") or 0) > 0:
            p.notes[f"mortgage_{part}_said"] = "yes"
    if p.notes.get("mortgage_payment_said") == "yes" or not p.home.mortgage_payment:
        p.notes.pop("mortgage_payment_est", None)
    if facts.get("home.has_mortgage") and not p.home.mortgage_payment:
        from ..tools import costs as _costs
        if p.notes.get("mortgage_balance_said") == "yes" and p.home.mortgage_balance > 0:
            # one rule for an estimated payment: the typical mortgage (costs.typical_mortgage), kept to the balance the person gave
            p.home.mortgage_payment = _costs.typical_mortgage(p)[1]
            p.notes["home"] = ("The payment is an estimate. It pays off your balance over the years a typical mortgage has left, at 5%. "
                               "Please give your own payment.")
        else:
            from ..tools.family_costs import _load as _fc_load
            b = _fc_load("basics.json")
            row = b["states"].get((p.state or "").upper(), b["us"])
            p.home.mortgage_payment = float(row["smoc_mortgage"])
            p.sources["home"] = "estimate"
            p.notes["home"] = "Typical monthly owner costs with a mortgage in your state (Census). Please give your own payment."
        p.notes["mortgage_payment_est"] = "yes"
    if "children.ages" in facts or "children.count" in facts or "children.college" in facts:
        household.set_children(p, facts.get("children.count"), facts.get("children.ages"), facts.get("children.college"))
        if "children.ages" in facts or facts.get("children.count") == 0:
            said("children")
        else:
            changed.append("children")
            if any(c.age is None for c in p.children):
                p.sources.pop("children", None)     # a new count: the ages are not known yet, so they are asked
    if facts.get("children.sexes") and p.children:         # "a girl of 8 and a boy of 5": which child is the girl, by the age beside the word
        ages = [c.age for c in p.children]
        for age, sex in facts["children.sexes"].items():
            if ages.count(int(age)) == 1:
                p.children[ages.index(int(age))].sex = sex
    if "children.college_each" in facts:       # college child by child; a question goes back in p.notes when the words do not pick a child
        from . import college as _college
        was = [(c.college_type, c.college_share, c.college_source) for c in p.children]
        ask = _college.apply_each(p, facts["children.college_each"])
        p.notes.pop("college_unclear", None)
        if ask:
            p.notes["college_unclear"] = json.dumps(ask)
        if any(c.college_source == "you said" and (c.college_type, c.college_share, c.college_source) != w for c, w in zip(p.children, was)):      # only when a choice was applied to a child
            said("college")
    elif "children.college_type" in facts or "children.college_share" in facts:
        for c in p.children:
            if "children.college_type" in facts:
                c.college_type = facts["children.college_type"]
                c.college = c.college_type != "none"
            if "children.college_share" in facts:
                c.college_share = facts["children.college_share"]
            c.college_source = "you said"
        if p.children:
            said("college")
    if "pets" in facts:
        p.pets = [Pet(**x) for x in facts["pets"]]
        said("pets")
    # optional detail
    if "debts" in facts:
        if not facts["debts"]:
            p.debts = []
        for d in facts["debts"]:
            nd = Debt(**{k: v for k, v in d.items() if v is not None})
            p.debts = [x for x in p.debts if x.kind != nd.kind] + [nd]
        said("debts")
    if "pensions" in facts:
        if not facts["pensions"]:
            p.pensions = []
        for x in facts["pensions"]:
            np_ = Pension(**x)
            p.pensions = [y for y in p.pensions if y.who != np_.who] + [np_]
        said("pensions")
    sv = [k for k in facts if k.startswith("saving.") and k != "saving.none"]
    for k in sv:
        setattr(p.saving, k.split(".", 1)[1], facts[k])
    if sv:
        said("saving")
    if "save_rate" in facts:
        p.save_rate = facts["save_rate"]
        said("save_rate")
    ins = [k for k in facts if k.startswith("insurance.")]
    for k in ins:
        setattr(p.insurance, k.split(".", 1)[1], facts[k])
    if ins:
        said("insurance")
    gl = [k for k in facts if k.startswith("goals.") and k not in ("goals.big_costs", "goals.none", "goals.legacy_wish")]
    for k in gl:
        setattr(p.goals, k.split(".", 1)[1], facts[k])
    wish = bool(facts.get("goals.legacy_wish")) and "goals.legacy" not in facts
    if wish:
        p.notes["legacy_wish"] = "yes"
    for b in facts.get("goals.big_costs", []):
        nb = BigCost(**b)
        p.goals.big_costs = [x for x in p.goals.big_costs if (x.label, x.year) != (nb.label, nb.year)] + [nb]
        gl.append("big")
    if gl or wish:
        said("goals")
    if "part_time" in facts:
        p.part_time = PartTime(**{k: v for k, v in facts["part_time"].items() if v is not None})
        said("part_time")
    if "inheritance" in facts:
        p.inheritance = Inheritance(**{k: v for k, v in facts["inheritance"].items() if v is not None})
        said("inheritance")
    bud = [k for k in facts if k.startswith("budget.")]
    for k in bud:
        setattr(p.budget, k.split(".", 1)[1], float(facts[k]))
    if bud:
        said("budget")
        if "spending_now_per_year" not in facts:
            p.spending_now_per_year = None       # added up from the budget when the plan is built
            p.sources.pop("spending_now_per_year", None)
    return changed


def _child_cost(p: Profile) -> str:
    """A child added in the answers editor costs money now, like the What If path: spending now rises by a typical first-year cost,
    unless the person gave no spending figure (then the estimate is worked out again anyway)."""
    try:
        before = int(p.notes.get("children_n", ""))
    except ValueError:
        return ""
    added = len(p.children) - before
    if added <= 0 or p.sources.get("spending_now_per_year") != "you said" or not p.spending_now_per_year \
            or (p.retire_age or 65) <= (p.age or 45):
        return ""
    from ..tools import family_costs

    def at_home(kids):
        return family_costs.family_path(p.age or 45, [c.model_dump() for c in kids], [])["children_at_home_per_year"][:1] or [0]
    old = p.children[:before]
    extra = max(0.0, round(at_home(p.children)[0] - at_home(old)[0], -2))
    if not extra:
        return ""
    p.spending_now_per_year += extra
    p.notes["spending_now_per_year"] = f"Your figure plus about {_money(extra)} a year, a typical cost for the new child. Please check it."
    return (f"I added about {_money(extra)} a year to your spending now for the new child, a typical figure. "
            "It is in the panel under Spending now, so you can change it.")


def reset_estimates(p: Profile) -> Profile:
    """Clear values that were estimates or assumptions, so they are worked out again from the latest facts."""
    p = p.model_copy(deep=True)
    for k in RE_ESTIMATE:
        if p.sources.get(k) in ("estimate", "assumed"):
            setattr(p, k, None)
            p.sources.pop(k, None)
            p.notes.pop(k, None)
    if p.sources.get("children") == "assumed" and not p.notes.get("child_bucket"):      # a bucket ("teenagers") stays until real ages come
        for c in p.children:
            c.age = None
        p.sources.pop("children", None)
    for c in p.children:       # each child's own choice stays; a typical one proposed earlier is worked out again
        if c.college_source == "estimate" or (c.college_source is None and p.sources.get("college") == "assumed"):
            c.college_type, c.college_share, c.college, c.college_source = None, 1.0, True, None
    return p


SECTION_KEYS = {
    "Household": ["age", "partner_age", "has_partner", "sex", "partner_sex", "state", "children", "pets", "college"],
    "Work & pay": ["job", "partner_job", "pay_per_year", "partner_pay_per_year", "retire_age", "partner_retire_age", "part_time"],
    "Saving": ["savings", "save_rate", "saving", "emergency_months", "risk"],
    "Home & debts": ["home", "debts"],
    "Pensions & income": ["social_security_per_year", "pensions", "inheritance"],
    "Insurance": ["insurance"],
    "Goals": ["goals"],
    "Health": ["health", "partner_health"],
    "Costs": ["spending_now_per_year", "budget", "spending_per_year", "retire_spend_ratio"],
}
SECTION_DEFAULTS: dict[str, Any] = {
    "age": None, "partner_age": None, "has_partner": False, "sex": None, "partner_sex": None, "state": None, "children": [], "pets": [],
    "job": None, "partner_job": None, "pay_per_year": None, "partner_pay_per_year": None, "retire_age": None, "partner_retire_age": None,
    "part_time": None, "save_rate": None, "emergency_months": None, "risk": None, "debts": [], "pensions": [], "inheritance": None,
    "social_security_per_year": None, "health": None, "partner_health": None, "spending_now_per_year": None, "spending_per_year": None,
    "retire_spend_ratio": None,
}
# the question groups and confirmations that belong to each section
GROUPS_OF = {"Home & debts": ["debts"], "Pensions & income": ["pension"], "Saving": ["saving", "confirm_split"], "Insurance": ["insurance"],
             "Goals": ["goals"], "Health": ["health", "sex"], "Costs": ["costs", "spending_later", "confirm_spending_later"],
             "Work & pay": ["confirm_pay"], "Household": []}


def reset_sections(p: Profile, names: list[str]) -> Profile:
    """Clear whole sections (or everything). The profile always comes in with the request, so nothing is kept on the server."""
    if any(n.lower() == "all" for n in names):
        return Profile()
    from ..schemas import Budget, Goals, Home, Insurance, Saving, Savings
    p = p.model_copy(deep=True)
    for name in names:
        norm = name.lower().replace("_", " ").replace(" & ", " ").replace("&", " ")
        sec = next((s for s in SECTION_KEYS if s.lower().replace(" & ", " ") == norm), None)
        if sec is None:
            continue
        for k in SECTION_KEYS[sec]:
            if k == "savings":
                p.savings, p.savings_known = Savings(), False
            elif k == "home":
                p.home = Home()
            elif k == "saving":
                p.saving = Saving()
            elif k == "insurance":
                p.insurance = Insurance()
            elif k == "goals":
                p.goals = Goals()
            elif k == "budget":
                p.budget = Budget()
            elif k == "college":
                for c in p.children:
                    c.college_type, c.college_share, c.college, c.college_source = None, 1.0, True, None
            elif k in SECTION_DEFAULTS:
                setattr(p, k, SECTION_DEFAULTS[k])
            p.sources.pop(k, None)
            p.notes.pop(k, None)
            p.notes.pop("skipped_" + k, None)
        gone = set(GROUPS_OF.get(sec, []))
        p.offered = [g for g in p.offered if g not in gone]
        if sec == "Household":
            for k in ("skipped_state", "skipped_children", "skipped_partner_age"):
                p.notes.pop(k, None)
        if sec == "Saving":
            p.notes.pop("skipped_savings", None)
        if sec == "Home & debts":
            p.notes.pop("skipped_home", None)
            p.notes.pop("pending_debt_kind", None)
        if sec == "Work & pay":
            p.notes.pop("retired", None)
    p.asking = None
    p.notes.pop("then", None)
    return p


def mortgage_needs(p: Profile) -> list[str]:
    """What is still unknown about the mortgage of a home the person owns: ['status'], ['balance', 'payment'], one of them, or []."""
    h = p.home
    if not h.owns or p.notes.get("mortgage") == "no" or "skipped_mortgage" in p.notes:
        return []
    if "mortgage" not in p.notes:
        if h.mortgage_balance > 0 and h.mortgage_payment > 0 and p.sources.get("home") == "you said":
            return []                       # given before the mortgage question existed
        if not (h.mortgage_balance or h.mortgage_payment):
            return ["status"]
    return [x for x in ("balance", "payment") if p.notes.get(f"mortgage_{x}_said") != "yes"]


def missing(p: Profile) -> list[str]:
    """Only the essentials: ages, state, pay, partner's pay, savings, children's ages, home and mortgage, debts, retirement
    age and spending."""
    out = []
    retired = p.notes.get("retired") == "yes"
    if p.age is None:
        out.append("age")
    elif p.has_partner and p.sources.get("partner_age") != "you said" and "skipped_partner_age" not in p.notes:
        out.append("partner_age")
    if p.state is None and "skipped_state" not in p.notes:
        out.append("state")
    pay_open = p.age is not None and not retired and p.sources.get("pay_per_year") != "you said" and "skipped_pay_per_year" not in p.notes \
        and "confirm_pay" not in p.offered
    if pay_open and not p.job:
        out.append("pay_per_year")
    if not p.savings_known:
        out.append("savings")
    if p.children and (any(c.age is None for c in p.children) or p.sources.get("children") == "assumed") and "skipped_children" not in p.notes:
        out.append("children")
    if p.has_partner and not retired and p.sources.get("partner_pay_per_year") != "you said" and p.partner_job != "at home" \
            and "skipped_partner_pay_per_year" not in p.notes:
        out.append("partner_pay_per_year")
    if p.home.owns is None and "skipped_home" not in p.notes:
        out.append("home")
    if mortgage_needs(p):
        out.append("mortgage")
    if p.age is not None and "debts" not in p.offered and not p.debts and p.sources.get("debts") != "you said" and "skipped_debts" not in p.notes \
            and p.notes.get("skip_all") != "yes":
        out.append("debts")
    if p.age is not None and p.age < 75 and not p.children and not p.sources.get("children") and "skipped_children_count" not in p.notes \
            and p.notes.get("skip_all") != "yes":
        out.append("children_count")        # never mentioned: ask once, with pets in the same breath
    if p.notes.get("pension_ask") == "yes" and not p.pensions and "pension" not in p.offered and "skipped_pension" not in p.notes:
        out.append("pension")
    if p.age is not None and not retired and p.age < 67 and p.sources.get("retire_age") != "you said" and "skipped_retire_age" not in p.notes:
        out.append("retire_age")
    if p.age is not None and p.sources.get("spending_now_per_year") != "you said" and p.sources.get("spending_per_year") != "you said" \
            and not p.budget.given() and "skipped_spending_now_per_year" not in p.notes:
        out.append("spending_now_per_year")
    if pay_open and p.job:
        out.append("pay_per_year")          # the estimate from the job, stated for the person to check
    return out


def question_for(key: str, p: Profile) -> Question:
    partner = {"female": "your wife", "male": "your husband"}.get(p.partner_sex or "", "your partner")
    if key == "age":
        if p.has_partner:
            return Question(text=f"How old are you and {partner}?", quick_answers=["35 and 33", "45 and 43", "55 and 53", "65 and 63"])
        return Question(text="How old are you?", quick_answers=["35", "45", "55", "65"])
    if key == "partner_age":
        return Question(text=f"How old is {partner}?", quick_answers=[str(max(25, (p.age or 45) + d)) for d in (-5, -2, 0, 3)])
    if key == "state":
        return Question(text="Which state do you live in?", quick_answers=["Connecticut", "New York", "California", "Texas", "Florida"])
    if key == "pay_per_year" and p.job and p.job != "at home":
        return Question(text=f"About how much do you earn a year as a {p.job}, before tax?",
                        quick_answers=["Under $50k", "$50k to $100k", "$100k to $200k", "Over $200k"])
    if key == "pay_per_year":
        return Question(text="What do you do for work, or what do you earn a year before tax?",
                        quick_answers=["Under $50k", "$50k to $100k", "$100k to $200k", "Over $200k"])
    if key == "partner_pay_per_year":
        typical = ["Use typical for their job"] if p.partner_job and p.partner_job != "at home" else []
        return Question(text=f"Does {partner} work? If so, what do they earn a year before tax?",
                        quick_answers=["Not working", "Retired", *typical, "Type an amount"])
    if key == "mortgage":
        need = mortgage_needs(p)
        if need == ["status"]:
            return Question(text="Do you still have a mortgage? If so, about how much is left, and what is the monthly payment?",
                            quick_answers=["No, it's paid off", "Not sure, estimate it"])
        if need == ["payment"] and p.notes.get("mortgage_payment_est") == "yes" and p.home.mortgage_payment > 0:
            return Question(text=f"I estimated your monthly mortgage payment at {_money(p.home.mortgage_payment)}. Is that about right? Or type your payment.",
                            quick_answers=["Yes, that's about right"])
        if need == ["payment"]:
            return Question(text="What is the monthly mortgage payment?", quick_answers=["Not sure, estimate it"])
        if need == ["balance"]:
            return Question(text="About how much is left on the mortgage?", quick_answers=["Not sure, estimate it", "It's paid off"])
        return Question(text="About how much is left on the mortgage, and what is the monthly payment? For example: $180,000 left, $1,500 a month.",
                        quick_answers=["Not sure, estimate it", "It's paid off"])
    if key == "debts":
        return sup.group_question("debts", p)
    if key == "savings":
        return Question(text="About how much have you saved in all, counting 401(k)s, IRAs, other investments and cash?",
                        quick_answers=["About $50k", "About $250k", "About $750k", "About $2 million"])
    if key == "children":
        n = len(p.children)
        return Question(text="How old are your children?" if n != 1 else "How old is your child?",
                        quick_answers=["Under 5", "5 to 12", "Teenagers", "Grown up"])
    if key == "retire_age":
        return Question(text="At what age do you want to stop working?", quick_answers=["60", "62", "65", "67", "70"])
    if key == "pension":
        return Question(text="You mentioned a pension. About how much will it pay, a month or a year, and from what age? For example: $1,500 a month at 62.",
                        quick_answers=["Not sure, leave it out", "No pension after all"])
    if key == "children_count":
        if p.sources.get("pets") == "you said":
            return Question(text="And children? For example: two kids, 12 and 9.", quick_answers=["No children", "1 child", "2 children", "3 children"])
        return Question(text="Do you have children, or pets at home? For example: two kids, 12 and 9, and a dog.",
                        quick_answers=["No children", "1 child", "2 children", "3 children"])
    if key == "spending_now_per_year" and p.spending_now_per_year and p.sources.get("spending_now_per_year") in ("estimate", "assumed"):
        return Question(text=f"I estimated your spending now at {_money(p.spending_now_per_year)} a year. Is that about right?",
                        quick_answers=["Yes, that's about right", "$4,000 a month", "$6,000 a month", "$9,000 a month"])
    if key == "spending_now_per_year":
        return Question(text="About how much does your household spend in a year now, all in?",
                        quick_answers=["$4,000 a month", "$6,000 a month", "$9,000 a month", "Estimate it for me"])
    return Question(text="Do you own your home or rent?", quick_answers=["I own it outright", "I own it with a mortgage", "I rent"])


def fields(p: Profile) -> list[FieldOut]:
    return intake_fields.fields(p)


BUILD_LINE = ("That is enough to build your plan. Check the figures on the right, then press Build my plan. "
              "I will ask you to check them once more first.")
BUILD_REMINDER = "Press Build my plan when you are ready."
SHORT_WORDS = 45      # a reply (before the question) longer than this many words gets a short readback and a short typical-figures line
SHORT_AFTER = 5     # more facts than this in one message (or a readback of more than SHORT_WORDS words): a short reply
SHORT_LIST = 28       # a readback of more words than this becomes a short one (the key facts and any pension, college or home figure)
DISC_START = "For the rest, I use typical figures"


def _said_count(p: Profile) -> int:
    return sum(1 for f in fields(p) if f.source == "you said")


def _short_summary(changed: list[str], p: Profile, extra: list[str] | None = None) -> str:
    n = _said_count(p)
    key = []
    if "age" in changed and p.age:
        key.append(f"you are {p.age}")
    if "pay_per_year" in changed and p.pay_per_year:
        key.append(f"your pay is {_money(p.pay_per_year)} a year")
    if "retire_age" in changed and p.retire_age:
        key.append(f"you want to retire at {p.retire_age}")
    if "savings" in changed and p.savings.total:
        key.append(f"you have saved {_money(p.savings.total)}")
    out = f"Got it. I noted {n} facts from your message. Check them in the panel on the right."
    if key:
        out += " The main ones: " + _join(key[:3]) + "."
    if extra:
        out += " Also: " + ". ".join(x[0].upper() + x[1:] if i else x for i, x in enumerate(extra[:3])) + "."      # a pension, college or Social Security figure is read back, never only counted
    return out


def _named_bits(changed: list[str], p: Profile) -> list[str]:
    """What was noted, said as the fact itself: 'you are in fair health', not 'your health is noted'."""
    out: list[str] = []
    if "insurance" in changed:
        ins, b = p.insurance, []
        if ins.life_kind in ("term", "whole"):
            b.append(f"you hold {ins.life_kind} life cover" + (f" of {_money(ins.life_face)}" if ins.life_face else ""))
        elif ins.life_kind == "none":
            b.append("you have no life cover")
        if ins.disability is not None:
            b.append("you have disability cover" if ins.disability else "you have no disability cover")
        if ins.ltc is not None:
            b.append("you have long-term care cover" if ins.ltc else "you have no long-term care cover")
        out.append(_join(b) if b else "")
    if "goals" in changed:
        g, b = p.goals, []
        if g.legacy:
            b.append(f"you want to leave {_money(g.legacy)}")
        elif g.legacy is None and p.notes.get("legacy_wish") == "yes":
            b.append("you wish to leave something behind (a wish noted, no amount, not counted)")
        elif g.legacy == 0:
            b.append("you plan to leave nothing behind")
        for x in g.big_costs:
            b.append(f"a big cost: {x.label} {_money(x.amount)}" + (f" in {x.year}" if x.year else ""))
        if g.parents_per_year:
            b.append(f"you help your parents with {_money(g.parents_per_year)} a year" + (f" for {g.parents_years} years" if g.parents_years else ""))
        out.append(_join(b) if b else "")
    if "college" in changed and p.children:
        kind = {"public": "a public in-state college", "private": "a private college", "none": "no college"}
        said = [f"the {c.age}-year-old goes to {kind[c.college_type or 'public']}" if c.age is not None else f"your child goes to {kind[c.college_type or 'public']}"
                for c in p.children if c.college_source == "you said"]
        out.append(_join(said) if said else "")
    if "health" in changed and p.health:
        out.append(f"you are in {p.health} health")
    if "partner_health" in changed and p.partner_health:
        out.append(f"your partner is in {p.partner_health} health")
    if "sex" in changed and p.sex:
        out.append(f"you are {p.sex} (used only to pick the life table)")
    if "part_time" in changed and p.part_time and p.part_time.per_year:
        out.append(f"you plan part-time work of {_money(p.part_time.per_year)} a year in retirement")
    if "inheritance" in changed and p.inheritance and p.inheritance.amount:
        out.append(f"you may {'receive a gift of' if p.inheritance.gift else 'inherit'} {_money(p.inheritance.amount)}, shown for information and not counted in the plan")
    if "emergency_months" in changed and p.emergency_months is not None:
        out.append(f"you keep {p.emergency_months:g} months of spending in cash")
    return out


def summary(changed: list[str], p: Profile) -> str:
    bits = []
    if "job" in changed and p.job:
        bits.append(f"you work as a {p.job}" if p.job != "at home" else "")
    if "has_partner" in changed:
        bits.append("you have a partner" if p.has_partner else "you are single")
    if "partner_job" in changed and p.partner_job == "at home":
        bits.append("your partner is at home")
    if "children" in changed:
        n = len(p.children)
        ages = [c.age for c in p.children]
        agetxt = f", aged {_join([str(a) for a in ages])}" if n and all(a is not None for a in ages) and p.sources.get("children") == "you said" else ""
        bits.append((f"you have {n} child" + ("ren" if n != 1 else "") + agetxt) if n else "you have no children")
    if "pets" in changed and p.pets:
        bits.append("you have " + ", ".join(f"{x.count} {x.kind}{'s' if x.count > 1 else ''}" for x in p.pets))
    elif "pets" in changed:
        bits.append("you have no pets")
    if "state" in changed:
        bits.append(f"you live in {parser.STATE_NAME.get(p.state or '', p.state)}")
    if "age" in changed:
        bits.append(f"you are {p.age}" + (f" and your partner is {p.partner_age}" if "partner_age" in changed else ""))
    elif "partner_age" in changed:
        bits.append(f"your partner is {p.partner_age}")
    if "savings" in changed:
        s = p.savings
        parts = [f"{_money(v)} {lbl}" for v, lbl in ((s.pretax, "pre-tax"), (s.roth, "Roth"), (s.taxable, "taxable"), (s.cash, "cash")) if v]
        split_given = p.sources.get("savings") == "you said" and len(parts) >= 2
        bits.append(f"you have saved {_money(s.total)}" + (f" ({_join(parts)})" if split_given else ""))
    if "home" in changed:
        h = p.home
        if not h.owns:
            bits.append("you rent" + (f", at {_money(h.rent)} a month" if h.rent else ""))
        else:
            mort = []
            if h.mortgage_balance and p.notes.get("mortgage_balance_said") == "yes":
                mort.append(f"{_money(h.mortgage_balance)} left on the mortgage")
            if h.mortgage_payment and p.notes.get("mortgage_payment_said") == "yes":
                mort.append(f"a payment of {_money(h.mortgage_payment)} a month")
            paid_off = p.notes.get("mortgage") == "no"
            bits.append("you own your home" + (", with " + _join(mort) if mort else (" with no mortgage" if paid_off else "")) + (f", worth about {_money(h.value)}" if h.value else ""))
    if "pay_per_year" in changed:
        bits.append(f"your pay is {_money(p.pay_per_year)} a year" if p.pay_per_year else "you have no pay now")
    if "partner_pay_per_year" in changed and p.has_partner and p.partner_pay_per_year is not None:
        bits.append(f"your partner's pay is {_money(p.partner_pay_per_year)} a year" if p.partner_pay_per_year else "your partner has no pay")
    if "spending_now_per_year" in changed:
        bits.append(f"you spend {_money(p.spending_now_per_year)} a year now")
    if "spending_per_year" in changed:
        bits.append(f"your spending in retirement is {_money(p.spending_per_year)} a year")
    if "retire_age" in changed:
        bits.append(f"you want to retire at {p.retire_age}")
    if "social_security_per_year" in changed and p.social_security_per_year:
        parts = p.notes.get("ss_parts")
        bits.append(f"your household Social Security is {_money(p.social_security_per_year)} a year" + (f" ({parts})" if parts else ""))
    if "debts" in changed:
        bits.append(("you owe " + ", ".join(f"{_money(d.balance)} in {d.kind.replace('_', ' ')} debt" for d in p.debts)) if p.debts else "you have no other debts")
    if "pensions" in changed:
        bits.append(" and ".join(f"{'your partner has' if x.who == 'partner' else 'you have'} a pension of {_money(x.per_year)} a year"
                                 + (f" from {x.start_age}" if x.start_age else "") for x in p.pensions) if p.pensions else "there is no pension")
    if "saving" in changed or "save_rate" in changed:
        sv, sb = p.saving, []
        if sv.contrib_you:
            sb.append(f"you put {_money(sv.contrib_you)} a year into retirement accounts")
        if sv.contrib_partner:
            sb.append(f"your partner puts in {_money(sv.contrib_partner)} a year")
        if sv.other_per_month:
            sb.append(f"you save {_money(sv.other_per_month)} a month besides")
        if sv.match_rate:
            sb.append(f"your employer adds {round(sv.match_rate * 100)} cents per dollar you save"
                      + (f", up to {sv.match_cap * 100:g}% of pay" if sv.match_cap else ""))
        if "save_rate" in changed and p.save_rate:
            sb.append(f"you save {round(p.save_rate * 100)}% of pay")
        bits.append(_join(sb) if sb else "")
    if "budget" in changed and p.budget.given():
        parts = [f"{k} {_money(v)}" for k, v in p.budget.model_dump().items() if v]
        bits.append(f"your monthly costs are {_join(parts)}, {_money(p.budget.total_month())} a month in all")
    bits += _named_bits(changed, p)
    bits = [b for b in bits if b]
    if not bits:
        return ""
    full_text = "Got it: " + (", ".join(bits[:-1]) + " and " + bits[-1] if len(bits) > 1 else bits[0]) + "."
    if len(bits) > SHORT_AFTER or len(full_text.split()) > SHORT_LIST:
        return _short_summary(changed, p, [b for b in bits if re.search(r"pension|Social Security|college|goes to|worth about|work as|live in", b)])       # many facts: the list is in the panel
    return full_text


PLAIN_KEYS = ("pay_per_year", "partner_pay_per_year", "spending_now_per_year", "spending_per_year", "social_security_per_year")
UPDATED_LABELS = {"savings": ["savings"], "pay": ["pay_per_year"], "partner's pay": ["partner_pay_per_year"], "retirement age": ["retire_age"],
                  "spending": ["spending_now_per_year", "spending_per_year"], "social security": ["social_security_per_year"],
                  "investing style": ["risk"], "yearly saving": ["save_rate"], "health": ["health"], "home": ["home"],
                  "partner's retirement age": ["partner_retire_age"], "children": ["children"], "emergency fund": ["emergency_months"]}
# Every figure the panel can edit in place (web/src/components/editSpecs.ts NOUN): "Updated your <noun>: ..." names the profile keys
# whose source becomes "you said". The sources use the group keys (insurance, goals, saving), as the chat path does.
UPDATED_LABELS.update({
    "age": ["age"], "partner's age": ["partner_age"], "sex": ["sex"], "partner's sex": ["partner_sex"], "state": ["state"], "pets": ["pets"],
    "job": ["job"], "partner's job": ["partner_job"], "part-time work": ["part_time"], "retirement account saving": ["saving"],
    "employer match": ["saving"], "other saving": ["saving"], "other debts": ["debts"], "pensions": ["pensions"],
    "possible inheritance": ["inheritance"], "life insurance": ["insurance"], "disability insurance": ["insurance"],
    "long-term care insurance": ["insurance"], "money to leave behind": ["goals"], "big planned costs": ["goals"], "help for parents": ["goals"],
    "partner's health": ["partner_health"], "spending now": ["spending_now_per_year"], "spending split": ["budget"],
    "spending in retirement": ["spending_per_year"],
})
PAGE_EDIT_AGES = {"age": (18, 110), "partner_age": (18, 110), "retire_age": (30, 80), "partner_retire_age": (30, 80)}


def _page_edit_line(noun: str, text: str, bad: list[str]) -> str:
    """'Saved. Your state is now Texas, was Connecticut.' from the page's own line 'Updated your state: Texas (was Connecticut).'"""
    noun = noun.lower().strip()
    was = re.search(r"\(was (.{1,140})\)\s*$", text)
    now = re.match(r"\s*updated your [a-z' -]+?\s*:\s*(.+?)\.?(?:\s*\(was .*)?$", text, re.I)
    line = f"Saved. Your {noun} is now {now.group(1).rstrip('.')}, was {was.group(1)}." if was and now else ""
    if bad:
        line = f"I did not keep {', '.join(bad)}: it is outside the range I can use. Tell me again. " + (line or f"Saved the rest of your {noun}.")
    return line


def check_page_edit(p: Profile) -> list[str]:
    """A figure typed in the panel is checked against the same limits the form shows. A value out of range is dropped (the
    question is asked again), never moved to another figure. Returns the plain names of what was dropped."""
    bad: list[str] = []
    for k, (lo, hi) in PAGE_EDIT_AGES.items():
        v = getattr(p, k)
        if v is not None and not lo <= v <= hi:
            setattr(p, k, None)
            bad.append(k.replace("_", " "))
    if any(c.age is not None and not 0 <= c.age <= 30 for c in p.children):
        p.children = [c for c in p.children if c.age is None or 0 <= c.age <= 30]
        bad.append("a child's age")
    p.pets = [x for x in p.pets if 0 < x.count <= 20]
    for d in p.debts:
        if d.rate is not None and not 0 <= d.rate <= 1:
            d.rate = None
            d.assumed = sorted(set(d.assumed) | {"rate"})
    for x in p.pensions:
        if x.survivor_share is not None and not 0 <= x.survivor_share <= 1:
            x.survivor_share = None
    return bad


def _plain_answer_facts(text: str, asking: str) -> dict[str, Any]:
    """Chips that go with an edit question: keep, use typical, type an amount; and 'not working' for a partner's pay."""
    low = text.strip().lower().strip(" .!")
    if low.startswith("keep"):
        return {"keep": True}
    if low in ("use typical for my job", "use typical for their job", "use the estimate", "estimate it for me", "estimate it", "use typical",
               "not sure, estimate it"):
        return {"use_typical": [asking]}
    if low == "type an amount":
        return {"type_prompt": asking}
    if asking == "partner_pay_per_year" and NO_PAY.match(low):
        return {"partner_pay_per_year": 0.0}
    return {}


NO_PAY = re.compile(r"^(?:no|none|nope|nothing|zero|\$?0|not working|not employed|unemployed|doesn'?t work|does not work|retired|"
                    r"(?:she|he|they)(?:'s| is| are) (?:retired|not working|at home)|stays? (?:at )?home|at home|stay[- ]at[- ]home|no pay|homemaker)\b")
# Only an explicit "no mortgage" clears it. A bare "no" does (it answers "do you still have a mortgage?"); "No other debts",
# "no other loans" and "nothing else" are about other debts and never reach the mortgage.
MORT_NO = re.compile(r"paid (?:it )?off|no mortgage|outright|^\s*(?:no|nope|none)\s*[.!]*\s*$|^\s*(?:no|nope)[,.]?\s+(?:we|i)\s+(?:don'?t|do not)\b|"
                     r"don'?t have (?:a|one)\b|(?:we|i) have no mortgage|free and clear", re.I)
OTHER_DEBTS_NO = re.compile(r"^\s*(?:no|nope|none|nothing|not any)\b[^.]{0,20}\b(?:other|else|more|further|additional)\b|^\s*(?:no|nope|none)\s+(?:debts?|loans?)\b|"
                            r"\bdebt[- ]free\b", re.I)
OK_ONLY = re.compile(r"^\s*(?:ok(?:ay)?|k|sure|fine|alright|all right|go on|next|continue)\s*[.!]*\s*$", re.I)
NO_RATE = re.compile(r"(?:don'?t|do not) (?:really )?know|not sure|no idea|leave (?:it|that|the rate)? ?(?:blank|out)|skip", re.I)
MORT_SKIP = re.compile(r"not sure|estimate it|don'?t know|no idea|skip", re.I)


def _confirmed_line(p: Profile, key: Any) -> str:
    """Rule R1: when the person approves an estimate, name the figure that is now theirs."""
    keys = sup.CONFIRM_SOURCES.get(key, []) if isinstance(key, str) else []
    shown = [f for f in intake_fields.fields(p) if f.key in keys and f.display and f.display not in ("None", "No pay", "Not given")]
    if not shown:
        return "Good. I will treat that as your own figure."
    parts = "; ".join(f"{f.label.lower()} {f.display}" for f in shown)
    return f"Good. I will use these as your own figures: {parts}." if len(shown) > 1 else f"Good. I will use {shown[0].display} as your own figure for {shown[0].label.lower()}."


def _mortgage_answer(text: str) -> dict[str, Any]:
    """An answer to the mortgage question: paid off, not sure, or the balance and payment (any order)."""
    low = (text or "").lower().strip()
    if OTHER_DEBTS_NO.search(low) and not re.search(r"paid off|no mortgage|outright|free and clear", low):
        return {}            # about other debts: the mortgage is untouched
    if MORT_SKIP.search(low):
        return {"use_typical": ["mortgage"]}
    if MORT_NO.search(low):
        return {"home.owns": True, "home.mortgage_balance": 0.0, "home.mortgage_payment": 0.0}
    out: dict[str, Any] = {}
    clean = parser_extra.PRODUCT_NUM.sub(" ", text or "")
    for m in turn_guard.DIGITS.finditer(clean):
        try:
            v = float(m.group(1).replace(",", "")) * (turn_guard.DMULT[m.group(2).lower()] if m.group(2) else 1)
        except ValueError:
            continue
        tail, head = clean[m.end(): m.end() + 25].lower(), clean[max(0, m.start() - 25): m.start()].lower()
        if v < 100 or re.match(r"\s*(?:%|percent)", tail):
            continue
        monthly = re.match(r"\s*(?:a|per|/|each)\s*(?:month|mo)\b|\s*monthly", tail) or re.search(r"payment|monthly", head)
        if re.match(r"\s*(?:a|per)\s*year", tail) and v < 100000:
            v, monthly = v / 12, True
        if monthly or v < 15000:
            out["home.mortgage_payment"] = v
        else:
            out["home.mortgage_balance"] = v
    if not out and re.match(r"^\s*(?:yes|yeah|yep|we do|i do|still)\b", low):
        return {"home.owns": True, "home.has_mortgage": True}
    if out:
        out["home.owns"] = True
        out["home.has_mortgage"] = True
    return out


NON_FACTS = ("open_group", "skip_all", "keep", "type_prompt", "confirm", "open_edit", "debt_kind_only")
EDIT_LABEL = {"pay_per_year": "your pay", "partner_pay_per_year": "your partner's pay", "savings": "your savings", "savings_split": "your savings split",
              "retire_age": "your retirement age", "spending_now_per_year": "your spending", "spending_per_year": "your spending in retirement",
              "children_count": "your children", "home": "your home", "age": "your age", "state": "your state", "risk": "your investing style",
              "social_security_per_year": "your Social Security", "partner_retire_age": "your partner's retirement age", "debts": "your debts",
              "pension": "your pension", "insurance": "your insurance", "goals": "your goals", "health": "your health", "mortgage": "your mortgage", "saving": "your yearly saving"}
ASK_KEY = {"retire_age": "retire_age", "retire_in_years": "retire_age", "age": "age", "partner_age": "partner_age", "children.count": "children_count",
           "pay_per_year": "pay_per_year", "household_pay": "pay_per_year", "partner_pay_per_year": "partner_pay_per_year",
           "spending_now_per_year": "spending_now_per_year", "spending_per_year": "spending_per_year",
           "social_security_per_year": "social_security_per_year", "home.mortgage_balance": "mortgage", "home.mortgage_payment": "mortgage"}
FACT_LABEL = {"pay_per_year": "your pay", "partner_pay_per_year": "your partner's pay", "household_pay": "your pay", "savings.total": "your savings",
              "spending_now_per_year": "your spending now", "spending_per_year": "your spending in retirement", "home.mortgage_balance": "the mortgage left",
              "home.mortgage_payment": "the mortgage payment", "home.rent": "your rent", "home.value": "your home's value",
              "social_security_per_year": "your Social Security"}
PER_YEAR_KEYS = ("pay_per_year", "partner_pay_per_year", "household_pay", "spending_now_per_year", "spending_per_year", "social_security_per_year")
ESCAPE = "Build my plan with typical numbers for the rest"
ESCAPE_RE = re.compile(r"^\s*(?:build|make|create|show) (?:my|the|a) plan\b.*\btypical\b", re.I)

# ------------------------------------------------------------------ round 4: a What If asked during the intake
# "what if I save an extra 1,000 a month?" is a question about a plan not yet built, never a change to a stored figure. The
# cue words are the plan chat's What If words (ask_intent.HYPOTHETICAL) less the loose ones ("if I", "let's say") that
# also start plain answers here.
INTAKE_WHATIF = re.compile(r"\bwhat (?:if|happens if|would happen if)\b|^\W*(?:but\s+|and\s+|so\s+)?(?:suppose|imagine)\s+(?:i|we|if)\b|"
                           r"\bhypothetical\w*\b|\bhow (?:does|would|will|could|might) (?:that|this|it) (?:change|affect|move)\b", re.I)
NOT_WHATIF = re.compile(r"\bwhat if (?:i|we) (?:don'?t|do not|can'?t|cannot|am not|'?m not|skip|leave|make a mistake|get (?:it|this|that) wrong|"
                        r"change (?:my|our) minds?|have no|type|press|click)\b|\bwhat if (?:i'?m|i am|we'?re|we are) wrong\b", re.I)
WHATIF_GO_ON = re.compile(r"^\W*(?:say|so|and|like|for example|e\.?g\.?|then|how|would|could|will|what|or|maybe|instead|is that)\b", re.I)
WHATIF_LATER = "I'll test that once your plan is built. Press Build my plan, then ask it in the plan chat."


def whatif_split(text: str) -> tuple[str, str]:
    """(the What If part, the rest) of a message: a sentence with a What If cue, and the sentences that carry it on
    ("Say an extra 1,000 a month.", "How does that change when I could retire?"). The rest is read as usual."""
    wi, rest, on = [], [], False
    for s in re.split(r"(?<=[.?!])\s+", text or ""):
        if INTAKE_WHATIF.search(s) and not NOT_WHATIF.search(s):
            on = True
            wi.append(s)
        elif on and (WHATIF_GO_ON.match(s) or s.strip().endswith("?")):
            wi.append(s)
        else:
            on = False
            rest.append(s)
    return " ".join(wi).strip(), " ".join(rest).strip()


# ------------------------------------------------------------------ round 4: an early build asks the retirement age first
RETIRE_CHIPS = (60, 62, 65, 67)
USE_DEFAULT = re.compile(r"^\W*(?:use\b|ok\b|okay\b|fine\b|sure\b|yes\b|default|typical|skip|idk|dunno|(?:i )?don'?t know|not sure|no idea|"
                         r"whatever|any\b|you pick|go ahead|just build|build)", re.I)


def _retire_chips(now: int | None, use: int) -> list[str]:
    return [str(a) for a in RETIRE_CHIPS if (now or 0) < a <= 70][:4] + [f"Use {use}"]


def _escape_retire_q(p: Profile) -> tuple[Question, str] | None:
    """Before an early build: one short question for a retirement age nobody gave (R2: a stated age is never moved;
    an unstated one is asked, not silently set to 65). A partner's age to stop is asked in the same breath when nothing
    was said about it. None when there is nothing to ask."""
    if p.age is None:
        return None
    full = household.complete(p)
    own = "retire_age" in missing(full)
    partner = bool(full.has_partner and full.sources.get("partner_retire_age") != "you said" and full.notes.get("retired") != "yes"
                   and not (full.sources.get("partner_pay_per_year") == "you said" and not full.partner_pay_per_year)
                   and (full.partner_age or full.age or 0) < 67)
    d = full.retire_age or 65
    if own:
        text = f"When would you like to retire? Pick an age or I'll use {d}."
        if partner:
            text += " If your partner stops at another age, type both, like 62 and 64."
        return Question(text=text, quick_answers=_retire_chips(full.age, d)), ("both" if partner else "own")
    if partner:
        from ..tools import costs
        pd = costs.partner_retire_age(full)
        return (Question(text=f"When would your partner like to retire? Pick an age or I'll use {pd}.",
                         quick_answers=_retire_chips(full.partner_age, pd)), "partner")
    return None


def _escape_retire_answer(clean: str, p: Profile, mode: str) -> str | None:
    """The answer to the early build's retirement question: the age or ages given (the person's own), or the typical
    age on "Use 65", "skip" and the like. None when the message is not an answer to it (it is then read as usual)."""
    from ..tools import costs
    full = household.complete(p)
    d = full.retire_age or 65
    pd = costs.partner_retire_age(full) if full.has_partner else None
    low = (clean or "").strip()
    nums = [int(x) for x in turn_guard.quote_numbers(low) if 40 <= x <= 85 and x == int(x)]
    if USE_DEFAULT.match(low) and not (nums and not re.match(r"^\W*use\b", low, re.I)):
        if mode == "partner":
            return f"I will use {pd} for your partner's retirement, marked assumed."
        if re.match(r"^\W*(?:use|ok|okay|fine|sure|yes)\b", low, re.I):
            apply(p, {"retire_age": d})        # R1: the age on offer, approved, is now the person's own
            return f"Got it: retirement at {d}."
        _skip(p, "retire_age")
        return f"I will use {d} for your retirement, marked assumed."
    if not nums:
        return None
    if mode == "partner":
        if nums[0] <= (full.partner_age or 0):
            return None
        apply(p, {"partner_retire_age": nums[0]})
        return f"Got it: your partner retires at {nums[0]}."
    if nums[0] <= (p.age or 0):
        return None
    facts: dict[str, Any] = {"retire_age": nums[0]}
    if mode == "both" and len(nums) > 1 and nums[1] > (full.partner_age or 0):
        facts["partner_retire_age"] = nums[1]
    apply(p, facts)
    return f"Got it: you want to retire at {nums[0]}" + (f", and your partner at {nums[1]}." if "partner_retire_age" in facts else ".")


def _respond_q(p: Profile, reply: str, q: Question, ask: str | None) -> IntakeResponse:
    """A reply that ends the turn with a question of its own (not one rebuilt from the pending key)."""
    full = household.complete(p) if p.age else p
    miss = missing(full)
    full.asking = ask
    ready = all(k not in miss for k in REQUIRED) and full.age is not None
    _history(full, "", f"{reply} {q.text}".strip())
    flds = fields(full)
    return IntakeResponse(profile=full.model_dump(), fields=flds, missing=miss, question=q, reply=reply.strip(), ready=ready,
                          sections_status=intake_fields.sections_status(flds), tokens={"input": 0, "cached": 0, "output": 0}, cost_usd=0.0)


AGE_AGAIN = ("The plan can't start without your age. It sets how long your money must last and when Social Security can start. "
             "A rough age is fine.")      # never "type skip": an age is not guessed
AGE_LAST = "I still need your age to go on. Type it as a number, for example 50."
START_HELP = re.compile(r"\bwhat (?:to|do i|should i|can i) (?:say|write|type|tell|put)\b|\bwhere (?:do i |to |should i )?(?:start|begin)\b|"
                        r"\bhow (?:do i |to )?(?:start|begin)\b|^\W*(?:idk|dunno|i don'?t know|no idea|not sure|help|hi|hello|hey)\W*$", re.I)
START_EXAMPLE = ("Tell me a little about yourself, in your own words. "
                 "For example: I'm 45, a teacher in Ohio, I earn $60,000 and I've saved $80,000.")
ESSENTIAL_SKIP = ("pay_per_year", "partner_pay_per_year", "mortgage", "debts", "children_count", "partner_age", "state", "children", "home", "retire_age",
                  "spending_now_per_year", "savings")
FIGURE_KEYS = ("age", "partner_age", "pay_per_year", "partner_pay_per_year", "savings", "children", "retire_age", "spending_now_per_year", "mortgage",
               "savings_split", "spending_per_year", "social_security_per_year", "children_count")


# ------------------------------------------------------------------ what the reply says
def _snap(p: Profile) -> dict[str, tuple[str, str, str]]:
    """The person's own figures as (lead, value, tail), so a change can be echoed: 'Got it: 2 children, not 3.'"""
    s, out = p.sources, {}
    if p.age is not None and s.get("age") == "you said":
        out["age"] = ("age ", str(p.age), "")
    if p.partner_age is not None and s.get("partner_age") == "you said":
        out["partner_age"] = ("your partner's age ", str(p.partner_age), "")
    if p.state and s.get("state") == "you said":
        out["state"] = ("", parser.STATE_NAME.get(p.state, p.state), "")
    if p.pay_per_year is not None and s.get("pay_per_year") == "you said":
        out["pay_per_year"] = ("pay of ", _money(p.pay_per_year), " a year")
    if p.partner_pay_per_year is not None and s.get("partner_pay_per_year") == "you said":
        out["partner_pay_per_year"] = ("your partner's pay of ", _money(p.partner_pay_per_year), " a year")
    if p.savings_known and s.get("savings") in ("you said", "assumed"):
        out["savings"] = ("savings of ", _money(p.savings.total), "")
    if s.get("children") or p.children:
        n = len(p.children)
        ages = [c.age for c in p.children]
        agetxt = (", ages " + _join([str(a) for a in ages])) if n and all(a is not None for a in ages) and s.get("children") == "you said" else ""
        out["children"] = ("", str(n), (" child" if n == 1 else " children") + agetxt)
    if p.retire_age is not None and s.get("retire_age") == "you said":
        out["retire_age"] = ("retirement at ", str(p.retire_age), "")
    if p.spending_now_per_year is not None and s.get("spending_now_per_year") == "you said":
        out["spending_now_per_year"] = ("spending of ", _money(p.spending_now_per_year), " a year")
    if p.home.owns and p.notes.get("mortgage_balance_said") == "yes":
        out["mortgage_balance"] = ("", _money(p.home.mortgage_balance), " left on the mortgage")
    if p.home.owns and p.notes.get("mortgage_payment_said") == "yes":
        out["mortgage_payment"] = ("a mortgage payment of ", _money(p.home.mortgage_payment), " a month")
    if p.debts and s.get("debts") == "you said":
        out["debts"] = ("debts of ", _money(sum(d.balance for d in p.debts)), "")
    return out


SNAP_TO_CHANGED = {"mortgage_balance": "home", "mortgage_payment": "home"}


def _corrections(before: dict, after: dict, corrected: set[str]) -> tuple[list[str], set[str]]:
    """'Got it: 2 children, not 3.' for every figure of the person's own that changed. Returns (sentences, changed keys echoed)."""
    out, echoed = [], set()
    for k, (lead, val, tail) in after.items():
        old = before.get(k)
        if old and old[1] != val:
            sameform = old[0] == lead and (old[2] == tail or k == "children")
            out.append(f"Got it: {lead}{val}{tail}, not {old[1] if sameform else old[0] + old[1] + old[2]}.")
            echoed.add(SNAP_TO_CHANGED.get(k, k))
        elif old and k in corrected and k != "savings":      # the same savings total with a new split: the summary shows the split
            out.append(f"I have {lead}{val}{tail}, as you say.")
            echoed.add(SNAP_TO_CHANGED.get(k, k))
    return out, echoed


def _fact_snap_key(k: str) -> str | None:
    if k.startswith("savings."):
        return "savings"
    if k.startswith("children."):
        return "children"
    if k in ("home.mortgage_balance", "home.mortgage_payment"):
        return k.split(".")[1]
    if k == "household_pay":
        return "pay_per_year"
    return k


def _assumption_bits(full: Profile) -> dict[str, str]:
    """Each estimate or assumption in use, in a few plain words."""
    s, out = full.sources, {}

    def est(k):
        return s.get(k) in ("estimate", "assumed")
    retired = full.notes.get("retired") == "yes"
    if est("pay_per_year") and full.pay_per_year:
        out["pay_per_year"] = f"your pay at {_money(full.pay_per_year)} a year"
    if full.has_partner and est("partner_pay_per_year") and full.partner_pay_per_year is not None:
        out["partner_pay_per_year"] = (f"your partner's pay at {_money(full.partner_pay_per_year)} a year" if full.partner_pay_per_year
                                       else "no pay for your partner")
    if full.has_partner and est("partner_age") and full.partner_age:
        out["partner_age"] = f"your partner's age as {full.partner_age}"
    if est("retire_age") and full.retire_age and not retired:
        out["retire_age"] = f"retirement at {full.retire_age}"
    if est("spending_now_per_year") and full.spending_now_per_year:
        out["spending_now_per_year"] = f"spending now at {_money(full.spending_now_per_year)} a year"
    if est("spending_per_year") and full.spending_per_year:
        out["spending_per_year"] = f"spending in retirement at {_money(full.spending_per_year)} a year"
    if est("social_security_per_year") and full.social_security_per_year:
        out["social_security_per_year"] = f"Social Security at {_money(full.social_security_per_year)} a year"
    if est("save_rate") and full.save_rate:
        out["save_rate"] = f"saving {round(full.save_rate * 100)}% of pay"
    if est("risk") and full.risk:
        out["risk"] = f"a {full.risk} investing mix"
    if s.get("children") == "assumed" and full.children:
        out["children"] = "children's ages of " + _join([str(c.age) for c in full.children])
    if full.home.owns and full.home.mortgage_payment and p_notes_missing(full, "mortgage_payment_said") and full.notes.get("mortgage") == "yes" \
            and "skipped_mortgage" not in full.notes:
        out["mortgage_payment"] = (f"your mortgage payment at about {_money(full.home.mortgage_payment)} a month, worked out from your balance"
                                   if full.notes.get("mortgage_balance_said") == "yes" else
                                   f"your mortgage payment at about {_money(full.home.mortgage_payment)} a month, typical for your state")
    if full.home.owns and full.home.mortgage_balance > 0 and s.get("mortgage_rate") == "assumed" and full.home.mortgage_rate:
        out["mortgage_rate"] = f"a {full.home.mortgage_rate * 100:g}% mortgage rate, which sets when the mortgage ends"
    return out


def p_notes_missing(p: Profile, key: str) -> bool:
    return p.notes.get(key) != "yes"


def _disclose(full: Profile) -> str:
    """Name every estimate or assumption the first time it is used, or when it changes."""
    bits = _assumption_bits(full)
    try:
        told = json.loads(full.notes.get("told") or "{}")
        told = told if isinstance(told, dict) else {}
    except ValueError:
        told = {}
    try:
        told_v = json.loads(full.notes.get("told_v") or "{}")
        told_v = told_v if isinstance(told_v, dict) else {}
    except ValueError:
        told_v = {}
    vals = {k: round(float(getattr(full, k))) for k in MOVED_LABEL if k in bits and getattr(full, k)}
    new_keys = [k for k, t in bits.items() if told.get(k) != t]
    full.notes["told"] = json.dumps(bits)[:3000]
    full.notes["told_v"] = json.dumps(vals)[:200]
    if not new_keys:
        return ""
    if not told:
        new = [bits[k] for k in new_keys]
        shown = new[:2] + ([f"{len(new) - 2} more"] if len(new) > 2 else [])      # the rest are in the panel
        return f"{DISC_START}: {_join(shown)}. Each is marked in the panel, so you can change it."
    # round 4, no silent changes: a typical figure worked out again because another answer changed is said as old -> new
    moved, rest = [], []
    for k in new_keys:
        old = told_v.get(k)
        if k in vals and isinstance(old, (int, float)) and old and abs(old - vals[k]) >= 1:
            moved.append(f"{MOVED_LABEL[k]}: {_money(old)} → {_money(vals[k])}{_moved_why(k, full)}.")
        else:
            rest.append(bits[k])
    out = " ".join(moved[:3])
    rest += [bits[k] for k in new_keys if any(MOVED_LABEL.get(k, "-") in x for x in moved[3:])]
    if rest:
        shown = rest[:2] + ([f"{len(rest) - 2} more"] if len(rest) > 2 else [])
        out = f"{out} I updated some typical figures: {_join(shown)}.".strip()
    return out


MOVED_LABEL = {"pay_per_year": "Your pay", "partner_pay_per_year": "Your partner's pay", "spending_now_per_year": "Spending now",
               "spending_per_year": "Spending in retirement", "social_security_per_year": "Social Security"}


def _moved_why(k: str, full: Profile) -> str:
    """The short reason a typical figure moved, from the answer it follows."""
    if k == "spending_per_year" and full.spending_now_per_year and full.notes.get("retired") != "yes":
        return f", since you spend {_money(full.spending_now_per_year)} now"
    if k == "social_security_per_year":
        return ", from your pay and retirement age"
    return ""


def _reask_line(key: str | None) -> str:
    if key in FIGURE_KEYS:
        return "I didn't catch a figure there. A rough number is fine, or type skip."
    return "I didn't catch that. Pick a button or type your answer, or type skip."


def _skip(p: Profile, key: str) -> None:
    """Leave an essential to a typical figure, marked so the person can change it."""
    if key == "savings":
        if not p.savings_known:
            apply(p, {"savings.total": r2.typical_savings(p.age)})      # a typical figure for the age, shown for approval
            p.sources["savings"] = "assumed"
            p.notes["savings"] = r2.SAVINGS_NOTE + " Please give yours."
    elif key == "debts":
        p.offered = list(dict.fromkeys(p.offered + ["debts"]))
    p.notes[f"skipped_{key}"] = "yes"


def _typical_figure_line(asking: str, full: Profile, estimated: bool = False) -> str:
    """'For your spending I will use $66,000 a year, a typical figure, marked estimate in the panel.' for a skipped money question.
    With `estimated` (the person pressed 'Estimate it for me'): 'I estimated your spending at $66,000 a year, marked estimate.'"""
    if asking in ("costs", "spending_now_per_year"):
        label, v, unit = "your spending", full.spending_now_per_year, " a year"
    elif asking == "social_security_per_year":
        label, v, unit = "your Social Security", full.social_security_per_year, " a year"
    elif asking == "partner_pay_per_year":
        label, v, unit = "your partner's pay", full.partner_pay_per_year, " a year"
    elif asking == "pay_per_year":
        label, v, unit = "your pay", full.pay_per_year, " a year"
    elif asking == "savings":
        label, v, unit = "your savings", (full.savings.total if full.savings_known else None), ""
    else:
        return ""
    if not v:
        return ""
    if estimated:
        return f"I estimated {label} at ${v:,.0f}{unit}, marked estimate in the panel. Change it if you know better."
    return f"For {label} I will use ${v:,.0f}{unit}, a typical figure, marked estimate in the panel. Change it if you know better."


def _skip_line(asking: str | None, full: Profile) -> str:
    """The reply to a skipped question: the figure that is used (marked estimate), or plainly 'none counted'. Never 'a typical figure'
    with no figure. '' when the key has no such line."""
    if asking in sup.CONFIRM_BASE:
        base = sup.CONFIRM_BASE[asking]
        if base == "savings_split":
            s = full.savings
            if s.total:
                pct = ", ".join(f"{round(getattr(s, k) / s.total * 100)}% {lbl}" for k, lbl in (("pretax", "pre-tax"), ("roth", "Roth"), ("taxable", "taxable"), ("cash", "cash")))
                return f"Fine. I keep my split of your {_money(s.total)}: {pct}. It stays marked estimate, so you can change it."
            return ""
        what = {"pay_per_year": ("your pay", full.pay_per_year, " a year"), "spending_later": ("your spending in retirement", full.spending_per_year, " a year"),
                "social_security_per_year": ("your Social Security", full.social_security_per_year, " a year")}.get(base)
        if what and what[1]:
            return f"Fine. I keep {what[0]} at {_money(what[1])}{what[2]}, marked estimate in the panel so you can change it."
        if base == "risk" and full.risk:
            return f"Fine. I keep a {full.risk} investing mix, marked assumed in the panel so you can change it."
        return ""
    if asking == "home":
        try:
            housing = household.basics(full)["housing"]
        except Exception:       # noqa: BLE001
            housing = None
        return ("Fine. I will use typical housing costs for your state" + (f", about {_money(housing)} a year" if housing else "")
                + ", marked estimate. Tell me later if you rent or own.")
    if asking == "children_count":
        return "Fine. I will count no children, so no child costs are counted. Add them in the panel if you have any."
    if asking == "children":
        ages = [c.age for c in full.children if c.age is not None]
        return f"Fine. I will use ages {_join([str(a) for a in ages])} for the children, marked assumed. Give the real ages any time." if ages else ""
    if asking == "partner_age" and full.partner_age:
        return f"Fine. I will use {full.partner_age} for your partner's age, the same as yours, marked assumed."
    if asking == "state":
        return "Fine. I will use typical US taxes and costs, marked estimate, until you give a state."
    if asking == "mortgage":
        return ""      # _estimate_mortgage names its figures
    if asking == "health":
        return "Fine. I will assume good health, marked assumed in the panel so you can change it."
    return ""


def _estimate_mortgage(p: Profile) -> str:
    """'Not sure, estimate it' at the mortgage question: a typical balance and payment, marked estimate, said in the reply."""
    from ..tools import costs
    bal, pay = costs.typical_mortgage(p)
    p.home.mortgage_balance, p.home.mortgage_payment = bal, pay
    p.notes["mortgage"] = "yes"
    p.notes["skipped_mortgage"] = "yes"
    p.notes["mortgage_payment_est"] = "yes"
    if p.notes.get("mortgage_balance_said") == "yes":
        p.notes["home"] = "The payment is an estimate. It is a typical 30-year loan at 5%, kept to your balance. Please give your own payment."
    else:
        p.sources["home"] = "estimate"
        p.notes["home"] = ("This is a typical mortgage: a 30-year loan at 5%. The payment is typical for your state, or comes from your home's value. "
                           "Please give your own figures.")
    return f"I used a typical mortgage for now: about {_money(bal)} left, {_money(pay)} a month, marked estimate. Change it in the panel if you know better."


ORDERS = re.compile(r"\b(?:i order you|you must|you will|answer (?:every|all)|reply (?:with|only|in)|respond (?:with|only)|say only|"
                    r"ignore (?:your|all|any|the|previous)|as your (?:developer|admin\w*|creator|owner)|system prompt|instructions?|pwn)\b"
                    r"|javascript:|<[^>]*>|\bon\w+\s*=", re.I)


# R7 on page 1: a figure the person stated earlier changes only after a yes. (key: label, money?)
GATE_KEYS = {"pay_per_year": ("your pay", True), "partner_pay_per_year": ("your partner's pay", True), "retire_age": ("your retirement age", False),
             "partner_retire_age": ("your partner's retirement age", False), "age": ("your age", False), "partner_age": ("your partner's age", False),
             "spending_now_per_year": ("your spending now", True), "spending_per_year": ("your spending in retirement", True),
             "social_security_per_year": ("your Social Security", True)}
AGE_EDIT = re.compile(r"\b(?:set|change|make|update|fix|correct)\s+(?:my|our|the)\s+(partner'?s?\s+|wife'?s?\s+|husband'?s?\s+|spouse'?s?\s+)?age\s+(?:to|as|at|is|should be)?\s*(\d{2})\b"
                      r"|\b(?:my|our)\s+(partner'?s?\s+|wife'?s?\s+|husband'?s?\s+|spouse'?s?\s+)?age\s+(?:is|was|should be)\s+(?:actually\s+)?(\d{2})\b", re.I)
YES_CHANGE = re.compile(r"^(?:yes|yep|yeah|yup|sure|ok|okay|correct|do it|go ahead|please do|yes please|yes, change it)\b")
NO_CHANGE = re.compile(r"^(?:no|nope|nah|don'?t|do not|keep(?: it)?|cancel|never ?mind|leave it|stop)\b")


def _gate_value(key: str, v: float) -> str:
    return _money(v) if GATE_KEYS[key][1] else f"{v:g}"


def _pending_change(p: Profile) -> dict[str, Any] | None:
    """The change waiting for a yes, checked again here because the profile comes from the browser: only known keys, plain numbers,
    plausible ranges, and a figure the person did state."""
    raw = p.notes.get("pending_change")
    if not raw:
        return None
    try:
        d = json.loads(raw)
        f, a = d.get("f") or {}, d.get("a")
        if not isinstance(f, dict) or len(f) > 4 or not (a is None or (isinstance(a, str) and len(a) <= 40)):
            return None
        f = {k: float(v) for k, v in f.items() if k in GATE_KEYS and isinstance(v, (int, float)) and not isinstance(v, bool) and v == v}
        g = _clean_struct(d.get("g"))
    except (ValueError, KeyError, TypeError):
        return None
    if (not f and not g) or sup.implausible({**f, **g}, p):
        return None
    k = next(iter(f)) if f else None
    label = GATE_KEYS[k][0] if k else _join([b[0] for b in _struct_bits(p, g)])
    return {"f": f, "g": g, "a": a, "label": label, "key": k, "old": getattr(p, k, None) if k else None, "new": f[k] if k else None}


STRUCT_SAVINGS = ("savings.total", "savings.pretax", "savings.roth", "savings.taxable", "savings.cash")


def _clean_struct(raw: Any) -> dict[str, Any]:
    """The held changes to savings, children, the mortgage and debts, checked again because they come back from the browser."""
    out: dict[str, Any] = {}
    if not isinstance(raw, dict):
        return out
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) < 1e10      # noqa: E731
    for k, v in raw.items():
        if k in STRUCT_SAVINGS + ("home.mortgage_balance", "home.mortgage_payment") and num(v):
            out[k] = float(v)
        elif k == "savings.replace" and v is True:
            out[k] = True
        elif k == "children.count" and num(v) and 0 <= v <= 20:
            out[k] = int(v)
        elif k == "children.ages" and isinstance(v, list) and len(v) <= 20 and all(num(a) for a in v):
            out[k] = [int(a) for a in v]
        elif k == "debts" and isinstance(v, list) and len(v) <= 6:
            ds = []
            for d in v:
                if isinstance(d, dict) and d.get("kind") in ("student", "car", "credit_card", "other") and num(d.get("balance")):
                    ds.append({kk: (float(vv) if num(vv) else vv) for kk, vv in d.items() if kk in ("kind", "balance", "rate", "monthly_payment") and vv is not None
                               and (kk == "kind" or num(vv))})
            if ds:
                out[k] = ds
    return out


def _kids_phrase(n: int, ages: list[int | None] | None = None) -> str:
    if n == 0:
        return "no children"
    known = [a for a in (ages or []) if a is not None]
    tail = f" (age{'s' if len(known) > 1 else ''} {_join([str(a) for a in known])})" if known and len(known) == n else ""
    return f"{n} child{'ren' if n != 1 else ''}{tail}"


def _struct_bits(p: Profile, g: dict[str, Any]) -> list[tuple[str, str]]:
    """(what, 'from X to Y') for each held change to savings, children, the mortgage or debts."""
    out: list[tuple[str, str]] = []
    sk = {k: v for k, v in g.items() if k in STRUCT_SAVINGS}
    if sk:
        old = p.savings.total
        if "savings.total" in sk:
            new = sk["savings.total"]
        else:
            parts = {k: getattr(p.savings, k) for k in ("pretax", "roth", "taxable", "cash")}
            if g.get("savings.replace"):
                parts = dict.fromkeys(parts, 0.0)
            parts.update({k.split(".", 1)[1]: v for k, v in sk.items()})
            new = sum(parts.values())
        out.append(("your savings", f"from {_money(old)} to {_money(new)}"))
    if "children.count" in g or "children.ages" in g:
        ages = g.get("children.ages")
        n = len(ages) if ages is not None else int(g["children.count"])
        out.append(("your children", f"from {_kids_phrase(len(p.children), [c.age for c in p.children])} to {_kids_phrase(n, ages)}"))
    if "home.mortgage_balance" in g:
        out.append(("your mortgage balance", f"from {_money(p.home.mortgage_balance)} to {_money(g['home.mortgage_balance'])}"))
    if "home.mortgage_payment" in g:
        out.append(("your mortgage payment", f"from {_money(p.home.mortgage_payment)} to {_money(g['home.mortgage_payment'])} a month"))
    for d in g.get("debts") or []:
        old = next((x for x in p.debts if x.kind == d["kind"]), None)
        kind = d["kind"].replace("_", " ")
        out.append((f"your {kind} debt", f"from {_money(old.balance)} to {_money(d['balance'])}" if old else f"to {_money(d['balance'])}"))
    return out


def _gated_struct(facts: dict[str, Any], p: Profile, asking: str | None) -> dict[str, Any]:
    """Facts that would change savings, children, the mortgage or a debt the person gave earlier, other than as the answer to the pending question."""
    own = tuple(sup.own_keys(asking, None) or ())
    held: dict[str, Any] = {}
    differs = lambda new, old: abs(float(new) - float(old)) > max(0.5, 0.005 * abs(float(old)))      # noqa: E731
    split_q = asking in sup.CONFIRM_BASE and sup.CONFIRM_BASE[asking] == "savings_split"
    sk = {k: v for k, v in facts.items() if k in STRUCT_SAVINGS and isinstance(v, (int, float)) and (k == "savings.total" and split_q or not sup._owns(k, own))}
    if sk and p.savings_known and p.sources.get("savings") in ("you said", "assumed") and p.savings.total > 0:
        trial = {**sk, **({"savings.replace": True} if facts.get("savings.replace") else {})}
        bits = _struct_bits(p, trial)
        old = p.savings.total
        new = float(sk["savings.total"]) if "savings.total" in sk else None
        if new is None:
            parts = {k: getattr(p.savings, k) for k in ("pretax", "roth", "taxable", "cash")}
            if facts.get("savings.replace"):
                parts = dict.fromkeys(parts, 0.0)
            parts.update({k.split(".", 1)[1]: float(v) for k, v in sk.items()})
            new = sum(parts.values())
        if bits and differs(new, old):
            held.update(trial)
    if p.sources.get("children") == "you said" and (p.children or "children_n" in p.notes) and not any(sup._owns(k, own) for k in ("children.count", "children.ages")):
        ages, cnt = facts.get("children.ages"), facts.get("children.count")
        n = len(ages) if isinstance(ages, list) else cnt
        if isinstance(n, int) and not isinstance(n, bool):
            old_ages = sorted(c.age for c in p.children if c.age is not None)
            if n != len(p.children) or (isinstance(ages, list) and sorted(ages) != old_ages):
                if isinstance(ages, list):
                    held["children.ages"] = [int(a) for a in ages]
                else:
                    held["children.count"] = int(n)
    for k, said_note in (("home.mortgage_balance", "mortgage_balance_said"), ("home.mortgage_payment", "mortgage_payment_said")):
        v = facts.get(k)
        if isinstance(v, (int, float)) and v > 0 and p.notes.get(said_note) == "yes" and p.home.owns and getattr(p.home, k.split(".", 1)[1]) > 0 \
                and differs(v, getattr(p.home, k.split(".", 1)[1])) and not sup._owns(k, own):
            held[k] = float(v)
    if not sup._owns("debts", own):
        ds = [d for d in (facts.get("debts") or []) if isinstance(d, dict) and any(
            x.kind == d.get("kind") and p.sources.get("debts") == "you said" and differs(d.get("balance") or 0, x.balance) and (d.get("balance") or 0) > 0 for x in p.debts)]
        if ds:
            held["debts"] = ds
    return held


def _change_question(p: Profile, pc: dict[str, Any]) -> Question:
    bits = []
    for k, v in pc["f"].items():
        old = getattr(p, k, None)
        bits.append(f"{GATE_KEYS[k][0]} from {_gate_value(k, old)} to {_gate_value(k, v)}" if old is not None else f"{GATE_KEYS[k][0]} to {_gate_value(k, v)}")
    bits += [f"{what} {change}" for what, change in _struct_bits(p, pc.get("g") or {})]
    return Question(text=f"Change {_join(bits)}?", quick_answers=["Yes", "No"])


def _gated(facts: dict[str, Any], p: Profile, asking: str | None, then: str | None) -> dict[str, float]:
    """The facts that would change a figure the person stated earlier, other than as the answer to the pending question."""
    own = sup.own_keys(asking, None) or ()      # the pending question itself, not the one that follows it
    out = {}
    for k in GATE_KEYS:
        v, old = facts.get(k), getattr(p, k, None)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and old is not None and p.sources.get(k) == "you said" and not sup._owns(k, tuple(own)) \
                and abs(float(v) - float(old)) > max(0.5, 0.005 * abs(float(old))):
            out[k] = float(v)
    return out


def _respond(p: Profile, reply: str, ask: str | None, tokens: dict | None = None) -> IntakeResponse:
    """A short reply that ends the turn: the changed profile, then the question that was open before (or the next missing one)."""
    full = household.complete(p) if p.age else p
    miss = missing(full)
    q = reask(ask, full, miss) if ask else None
    full.asking = ask if q is not None else None
    if q is None and miss:
        q, full.asking = question_for(miss[0], full), miss[0]
    ready = all(k not in miss for k in REQUIRED) and full.age is not None
    _history(full, "", f"{reply} {q.text if q else ''}".strip())
    flds = fields(full)
    return IntakeResponse(profile=full.model_dump(), fields=flds, missing=miss, question=q, reply=reply.strip(), ready=ready,
                          sections_status=intake_fields.sections_status(flds), tokens=tokens or {"input": 0, "cached": 0, "output": 0}, cost_usd=0.0)


def _apply_pending_change(p: Profile, pc: dict[str, Any], ask: str | None) -> IntakeResponse:
    g = pc.get("g") or {}
    bits = _struct_bits(p, g)
    p = reset_estimates(p)
    changed = apply(p, {**{k: (int(v) if k.endswith("age") else v) for k, v in pc["f"].items()}, **g})
    full = household.complete(p) if p.age else p
    said = _join([f"{GATE_KEYS[k][0]} is now {_gate_value(k, v)}" for k, v in pc["f"].items()] + [f"{what} is now {change.rsplit(' to ', 1)[1]}" for what, change in bits])
    disclosure = _disclose(full) if full.age else ""
    reply = f"Changed: {said}." + (f" {disclosure}" if disclosure else "")
    p.notes.update({k: v for k, v in full.notes.items() if k in ("told", "told_v")})
    if "children.count" in g and "children.ages" not in g and g["children.count"] > 0:
        ask = "children"          # a new count has no ages: ask them now
    return _respond(p, reply, ask)


def _kept_response(p: Profile, pc: dict[str, Any], ask: str | None) -> IntakeResponse:
    kept = _join([f"{GATE_KEYS[k][0]} at {_gate_value(k, getattr(p, k))}" for k in pc["f"] if getattr(p, k, None) is not None]
                 + [f"{what} at {change[5:].split(' to ', 1)[0]}" for what, change in _struct_bits(p, pc.get("g") or {})])
    return _respond(p, f"Fine. I kept {kept}." if kept else "Fine. Nothing changed.", ask)


def _drop_mortgage_debts(facts: dict[str, Any], p: Profile) -> None:
    """A debt that is the mortgage (the same balance as the home's) is never kept as another debt."""
    mort = [v for v in (facts.get("home.mortgage_balance"), p.home.mortgage_balance if p.home.owns else None) if isinstance(v, (int, float)) and v > 0]
    debts = facts.get("debts")
    if not mort or not isinstance(debts, list) or not debts:
        return
    kept = [d for d in debts if not (isinstance(d, dict) and d.get("kind") in (None, "other")
                                     and any(abs(float(d.get("balance") or 0) - m) <= max(1.0, 0.005 * m) for m in mort))]
    if len(kept) != len(debts):
        if kept:
            facts["debts"] = kept
        else:
            facts.pop("debts")


def _history_text(user: str) -> str:
    """The person's words as kept for the next turn's reading: clauses that give orders, and any markup, are left out."""
    parts = re.split(r"(?<=[.;!?])\s+|,\s+(?=(?:and |also |now |then )?(?:as|i|you|ignore|reply|answer|say)\b)", user or "")
    kept = [x for x in parts if x.strip() and not ORDERS.search(x)]
    return re.sub(r"[<>]", "", " ".join(kept))[:300]


def _history(p: Profile, user: str, app: str) -> None:
    u = _history_text(user)
    p.history = (p.history + ([f"you: {u}"] if u else []) + [f"app: {app[:390]}"])[-8:]


def _last_app(p: Profile) -> str:
    return next((h[5:] for h in reversed(p.history) if h.startswith("app: ")), "")


def _same(a: str, b: str) -> bool:
    n = lambda s: re.sub(r"\W+", " ", s.lower()).strip()  # noqa: E731
    return bool(a) and n(a)[:380] == n(b)[:380]


def _pending_q(asking: str | None, p: Profile) -> Question | None:
    if not asking:
        return None
    try:
        full = household.complete(p) if p.age else p
        return reask(asking, full, missing(full))
    except Exception:           # noqa: BLE001  a missing figure must not break the reply
        return None


def clean_incoming(p: Profile) -> Profile:
    """The profile comes from the browser. Clean its free text the way pipeline._clean_profile_text does for ask and plan,
    before any of it can reach a prompt."""
    from ..pipeline import STATE_CODES      # late: pipeline imports this package
    for k in ("job", "partner_job"):
        v = getattr(p, k)
        if v:
            setattr(p, k, safety.guard(v[:200]).clean[:60])
    if p.state is not None and p.state.upper() not in STATE_CODES:
        p.state = None
    elif p.state:
        p.state = p.state.upper()
    p.asking = p.asking if p.asking and len(p.asking) <= 40 else None
    p.offered = [x for x in p.offered if isinstance(x, str) and len(x) <= 40][:50]
    notes = {k: v[:(3000 if k == "told" else 200)] for k, v in p.notes.items() if isinstance(k, str) and len(k) <= 40 and isinstance(v, str)}
    try:                    # "told" is the list of assumptions already stated; it must stay whole JSON of short strings
        told = json.loads(notes.get("told") or "{}")
        if not isinstance(told, dict):
            raise ValueError
        notes["told"] = json.dumps({str(k)[:40]: str(v)[:200] for k, v in list(told.items())[:30]})[:3000]
    except ValueError:
        notes.pop("told", None)
    if notes.get("pending_debt_kind") not in Debt.model_fields["kind"].annotation.__args__:
        notes.pop("pending_debt_kind", None)
    p.notes = dict(list(notes.items())[:60])
    p.history = [safety.guard(h[:400]).clean[:400] for h in p.history[:8] if isinstance(h, str)]
    return p


async def run(text: str, profile_so_far: dict | None, session: str = "local", use_ai: bool = True, reset: list[str] | None = None) -> IntakeResponse:
    raw = profile_so_far or {}
    try:
        p = Profile.model_validate(raw)
    except Exception:
        p = Profile()
    p = clean_incoming(p)
    cleared = sup.cleared_message(reset) if reset else ""
    if reset:
        p = reset_sections(p, reset)
    # a section the page removed is no longer treated as offered
    for grp, key in (("debts", "debts"), ("pension", "pensions"), ("saving", "saving"), ("insurance", "insurance"), ("goals", "goals"),
                     ("health", "health"), ("costs", "budget")):
        if raw and key not in raw and grp in p.offered:
            p.offered = [g for g in p.offered if g != grp]
    asking = p.asking
    then = p.notes.get("then")
    held_note = ""
    if (pc := _pending_change(p)) is not None or asking == "confirm_change":
        p.notes.pop("pending_change", None)
        asking = p.asking = (pc or {}).get("a") or None
        then = p.notes.get("then")
        if pc is not None:
            low = (text or "").strip().lower().strip(" .!")
            if YES_CHANGE.match(low):
                return _apply_pending_change(p, pc, asking)
            if NO_CHANGE.match(low):
                return _kept_response(p, pc, asking)
            held_note = f"I did not change {pc['label']}."      # something else was said: the figure stays as it was
    # "Clear the $420,000 mortgage?" waiting for a yes (R2: a balance the person gave goes only on their yes)
    clear_ok = False
    if (pcm := p.notes.pop("pending_clear_mortgage", None)) is not None:
        before_ask = pcm if pcm in ESSENTIAL_Q or pcm in sup.CONFIRM_BASE else None
        asking = p.asking = before_ask
        then = p.notes.get("then")
        low = (text or "").strip().lower().strip(" .!")
        if YES_CHANGE.match(low):
            clear_ok, asking, text = True, "mortgage", "paid off"
        elif NO_CHANGE.match(low):
            return _respond(p, f"Fine. I kept the {_money(p.home.mortgage_balance)} mortgage.", before_ask)
        else:
            held_note = f"I did not clear the {_money(p.home.mortgage_balance)} mortgage."
    # "Updated your savings: ..." from the page: keep the edited value as the person's own
    page_edit = False
    page_bad: list[str] = []
    um = re.match(r"\s*updated your ([a-z' -]+?)\s*[:.]", text or "", re.I)
    edit_text = text or ""
    if um:
        page_edit = True
        page_bad = check_page_edit(p)
        for k in UPDATED_LABELS.get(um.group(1).lower().strip(), []):
            p.sources[k] = "you said"       # the person typed it: it is their own figure, whatever it was before
            p.notes.pop(k, None)
            p.notes.pop(f"skipped_{k}", None)
        if um.group(1).lower().strip() == "children":
            p.notes.pop("skipped_children_count", None)
        if um.group(1).lower().strip() == "savings":
            p.offered = list(dict.fromkeys(p.offered + ["confirm_split"]))
        text = ""
    # safety first: tags, instructions and requests to hide money are set aside before anything reads the message
    notes: list[str] = []
    if held_note:
        notes.append(held_note)
    text, stripped = sup.strip_wrappers(text)
    if stripped:
        notes.append("I set aside text that looked like tags or instructions to me, not facts about you.")
    g_safe = safety.guard(text)
    if safety.is_medicaid_hiding(text) or sup.is_hiding(text):
        notes.append(safety.MEDICAID_REPLY + " I keep your true figures.")
        kept, found = sup.strip_concealment(text)
        clean = safety.guard(kept).clean if found else ""      # the request is refused; every true fact in the message is kept
    else:
        clean = g_safe.clean
        if g_safe.flagged:
            notes.append("I set aside part of your message because it read like instructions to me, not facts about you.")
    clean = parser.fix_typos(clean)          # "4o yrs" -> "40 yrs", for both readers and the evidence check
    escape = bool(ESCAPE_RE.match(clean))
    # round 4: the answer to the early build's retirement question, then the build itself
    er = p.notes.pop("escape_retire", None)
    if er and not escape and (line := _escape_retire_answer(clean, p, er)) is not None:
        notes.append(line)
        clean, escape = ESCAPE, True
    if escape and p.notes.get("escape_retire_asked") != "yes" and (rq := _escape_retire_q(p)) is not None:
        p.notes["escape_retire_asked"] = "yes"
        p.notes["escape_retire"] = rq[1]
        return _respond_q(p, " ".join([*notes, "Before I build it, one question."]), rq[0], "retire_age")
    # round 4: a What If asked before the plan exists is answered, never read as a change; the rest of the message is read as usual
    whatif_line = ""
    if not escape:
        wi, rest = whatif_split(clean)
        if wi:
            whatif_line, clean = WHATIF_LATER, rest
            if not clean.strip():
                return _respond(p, " ".join([*notes, WHATIF_LATER]), asking)
    # the model reads the message (one call), unless it is one of the pending question's own buttons
    pending_q = _pending_q(asking, p)
    is_chip = (bool(pending_q) and clean.strip().lower().strip(" .!") in {c.lower() for c in pending_q.quick_answers}) or bool(asking and r2.USE_THIS.match(clean))
    tr, tokens, cost = None, {"input": 0, "cached": 0, "output": 0}, 0.0
    if use_ai and clean.strip() and not is_chip and not escape:
        tr, tokens, cost = await turn_read.read(clean, p, pending_q.text if pending_q else None, p.history, session, use_ai)
    # "that's about right" keeps an assumption as the person's own (before the estimates are cleared)
    ck = asking if asking in sup.CONFIRM_BASE else None
    cf = sup.confirm_facts(clean, ck) if ck else {}
    if ck and not cf and tr is not None and tr.intent == "confirm" and not tr.updates:
        cf = {"confirm": ck}
    if cf.get("confirm"):
        for k in sup.CONFIRM_SOURCES[ck]:
            if p.sources.get(k) in ("estimate", "assumed"):
                p.sources[k] = "you said"
                p.notes.pop(k, None)
    child_added_line = ""
    if page_edit and um and um.group(1).lower().strip() == "children":
        child_added_line = _child_cost(p)
    p = reset_estimates(p)
    eff = asking
    facts: dict[str, Any] = dict(cf)
    if ck and not facts:
        base = sup.CONFIRM_BASE[ck]
        eff = then if base == "savings_split" else base
    said = turn_guard.statements(clean)      # figures inside "why are you using $108,000?" are quoted back, not stated
    full0 = household.complete(p) if p.age else p
    prep = r2.prepare(clean, said, p, asking, full0, [h[5:] for h in p.history if h.startswith("app: ")])
    said = prep.said                         # a complaint about the app's own figure, or "$50k is way off", states nothing
    priv_seen = p.notes.get("privacy_told") == "yes"
    doubt = p.notes.pop("doubt", "")         # "key=value": a doubtful figure waiting for a yes
    doubt_yes = bool(doubt) and bool(re.match(r"\s*(?:yes|yep|yeah|correct|that'?s right|right)\b", clean, re.I))
    doubt_no = bool(doubt) and bool(re.match(r"\s*no\b", clean, re.I))
    if doubt_yes:
        prep.accept.add(doubt.split("=")[0])
    if not facts and not escape:
        facts = parser.parse(said, asking=eff, has_partner=p.has_partner, n_children=len(p.children), pending_kind=p.notes.get("pending_debt_kind"))
        if eff == "mortgage":
            est_pending = p.notes.get("mortgage_payment_est") == "yes" and p.home.mortgage_payment > 0 and p.notes.get("mortgage_payment_said") != "yes"
            mf = {} if (est_pending and r2.affirms(clean)) else _mortgage_answer(clean)      # a yes to "is $2,772 about right?" is no new fact
            if est_pending and r2.affirms(clean):
                facts = {k: v for k, v in facts.items() if not k.startswith("home.")}
            elif mf:
                facts = {k: v for k, v in facts.items() if not k.startswith("home.")} | mf
            elif OTHER_DEBTS_NO.search(clean) and not MORT_NO.search(clean):
                facts = {k: v for k, v in facts.items() if not k.startswith("home.")}       # "No other debts" is no word about the mortgage
                if not p.debts:
                    facts["debts"] = []       # it answers the debts question: recorded there, and the mortgage question stays open
        if eff in PLAIN_KEYS and not facts:
            facts = _plain_answer_facts(clean, eff)
        if asking and facts and set(facts) <= {"has_partner", "partner_sex"} and r2.skips(clean, SKIP):
            facts = {}                       # "my wife would know; use the estimate": a mention of her is no answer
        if doubt_no:
            facts = {}                       # "No, let me retype it": the doubtful figure is dropped, the question comes back
        elif doubt_yes and "=" in doubt:
            try:
                facts[doubt.split("=")[0]] = float(doubt.split("=")[1])
            except ValueError:
                pass
    # a pencil on a panel row sends its group's chip ("Add saving"): it opens that group now, even while another question is pending
    if asking and asking != "more" and not escape and parser_extra.CHIP_TO_GROUP.get(clean.strip().lower().strip(" .!")):
        facts = {"open_group": parser_extra.CHIP_TO_GROUP[clean.strip().lower().strip(" .!")]}
    # does the message answer the pending question, or is it a new fact, a stray chip, an edit or a question?
    new_fact = False
    skipping = r2.skips(clean, SKIP) or bool(parser_extra.NO_ANSWER.match(clean))
    if asking and not cf and clean.strip() and not sup.answers(facts, asking, then) and not escape:
        free = parser.parse(said, asking=None, has_partner=p.has_partner, n_children=len(p.children), pending_kind=p.notes.get("pending_debt_kind"))
        if {k for k in free if k not in NON_FACTS and not (skipping and k in ("has_partner", "partner_sex"))} and not prep.bare:      # a bare number answers the pending question or nothing
            facts, new_fact = free, True      # a new fact: read it without the pending question's context
    # the model's reading, checked, with the rule parser as a cross-check
    gr = None
    if tr is not None and not cf.get("confirm"):
        gr = turn_guard.check_updates(tr.updates, clean, p, eff)
        facts = turn_guard.merge(facts, gr, clean)
    if (am := AGE_EDIT.search(clean)) and not escape:
        # "set my age to 60": the person's age, not the children's ages, whatever question is open
        for k in [k for k in facts if k.startswith("children.")]:
            facts.pop(k)
        facts["partner_age" if (am.group(1) or am.group(3)) else "age"] = int(am.group(2) or am.group(4))
    _drop_mortgage_debts(facts, p)           # the mortgage is not also "other debt"
    reply_bits: list[str] = []
    if page_edit and child_added_line:
        reply_bits.append(child_added_line)
    forced_question: Question | None = None
    forced_asking: str | None = None
    # round 2: a bare number goes only to the pending question's field; a complaint or a rejection states no figure
    if prep.bare and asking and (own := sup.own_keys(asking, then)):
        facts = {k: v for k, v in facts.items() if k in sup.MARKERS or sup._owns(k, own)}
    if prep.quoted or prep.rejected:
        r2.drop_quoted(facts, prep.quoted + prep.rejected)
        if "savings.replace" in facts and not any(k.startswith("savings.") and k not in ("savings.replace", "savings.mix") for k in facts):
            facts.pop("savings.replace")        # every account figure was set aside: nothing to replace the split with
    facts.update(r2.children_list(clean, asking))
    if (sx := _college_sexes(clean)):
        facts["children.sexes"] = sx
        if not p.children and "children.ages" not in facts:
            facts["children.ages"] = list(sx)         # "a girl of 8 and a boy of 5" names the children and their ages
            facts.pop("children.count", None)
    range_note: tuple[str, str] | None = None
    if (rng := r2.range_midpoint(clean, asking, facts)) and rng[1]:
        facts[rng[0]] = rng[1]
        reply_bits.append(rng[2])
        range_note = (r2.NOTE_KEY[rng[0]], "A guess: the middle of the range you gave.")
    if asking != "debts_detail":         # there the kind is known and any figure is its balance
        r2.student_loan_guard(facts, said)
    small_msg = False
    for k, lbl, v in r2.too_small(facts, prep.bare):
        facts.pop(k)
        reply_bits.append(f"${v:,.0f} does not look right for {lbl}, so I have not stored it.")
        small_msg = True
    if prep.bare and asking == "mortgage" and not facts and (fg := r2.figures(clean)) and fg[0] < 100:
        reply_bits.append(f"${fg[0]:,.0f} is too small for a mortgage payment or a balance, so I have not stored it.")
        small_msg = True
    if doubt_no:
        reply_bits.append("Fine, let's retype it.")
    hh = float((facts.get("pay_per_year") or full0.pay_per_year or 0) + (facts.get("partner_pay_per_year") or full0.partner_pay_per_year or 0))
    if doubt_yes:
        p.notes["accepted"] = doubt
    for acc in (doubt, p.notes.get("accepted", "")):        # the same figure typed again after a doubt or a yes: it stands
        ak, _, av = acc.partition("=")
        try:
            if ak in facts and abs(float(facts[ak]) - float(av)) < 1:
                prep.accept.add(ak)
        except (TypeError, ValueError):
            pass
    for k, v, why in r2.sanity(facts, hh, prep.accept):
        facts.pop(k)
        p.notes["doubt"] = f"{k}={v:.0f}"
        reply_bits.append(f"A payment of ${v:,.0f} a month {why}. I have not stored it yet.")
        forced_question = Question(text=f"Is ${v:,.0f} a month right for your mortgage payment?", quick_answers=[f"Yes, ${v:,.0f} a month", "No, let me retype it"])
        forced_asking = "mortgage"
    # a spending split that adds to almost nothing is a misreading, not a budget: never let it become "$100 a year"
    bud = {k: v for k, v in facts.items() if k.startswith("budget.") and isinstance(v, (int, float))}
    if bud and sum(bud.values()) < 300:
        for k in bud:
            facts.pop(k)
    for k in ("spending_now_per_year", "spending_per_year"):
        v = facts.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v < 3000:
            facts.pop(k)
            reply_bits.append(f"I read your spending as ${v:,.0f} a year, which looks too low, so I have not stored it.")
    # plausible ranges: store nothing outside them, and ask what was meant
    bad = sup.implausible(facts, p)
    if bad:
        sup.drop_keys(facts, bad)
        reply_bits.append(sup.implausible_reply(bad))
        key = bad[0][0]
        ask_key = ASK_KEY.get(key) or ("savings" if key.startswith("savings.") else None)
        if ask_key:
            forced_question, forced_asking = edit_or_essential(ask_key, p), ask_key
        else:
            forced_asking = asking
    elif gr is not None and gr.looks_off:
        reply_bits.append(turn_guard.looks_off_reply(gr.looks_off))
        key, _, _, sugg = gr.looks_off[0]
        ask_key = ASK_KEY.get(key) or ("savings" if key.startswith("savings.") else None)
        if ask_key:
            q0 = edit_or_essential(ask_key, p)
            chip = (f"${sugg:,.0f}" + (" a year" if key in PER_YEAR_KEYS else "")) if sugg else None
            forced_question = Question(text=q0.text, quick_answers=[c for c in [chip, *q0.quick_answers] if c][:5])
            forced_asking = ask_key
    if gr is not None and gr.conflict and forced_question is None:
        k, a, b = gr.conflict
        label = FACT_LABEL.get(k, "that")
        per = " a year" if k in PER_YEAR_KEYS else (" a month" if k in ("home.mortgage_payment", "home.rent") else "")
        reply_bits.append(f"I read two figures for {label}: {_money(a)} and {_money(b)}. Which is right?")
        forced_question = Question(text=f"Which is right for {label}?", quick_answers=[f"{_money(a)}{per}", f"{_money(b)}{per}"])
        forced_asking = ASK_KEY.get(k) or asking
    answered = bool(cf) or (bool(asking) and (sup.answers(facts, asking, then) or (skipping and not new_fact)))
    words = len(clean.split())
    skipped_key: str | None = None
    real = {k: v for k, v in facts.items() if k not in NON_FACTS and k not in ("partner_sex", "has_partner", "savings.replace")}
    if facts.get("type_prompt"):
        reply_bits.append("Type the amount, for example $85,000 a year or $7,000 a month.")
        forced_question = Question(text=sup.edit_question(facts["type_prompt"], p).text, quick_answers=[])
        forced_asking = facts["type_prompt"]
    # a question asked along the way gets a short answer; the pending question is then asked again
    now_full = household.complete(p) if p.age else p
    miss_now = missing(now_full)
    affirmed: set[str] = set()       # approved just now: the reply names the figure, so the summary does not say it again
    approving = bool(asking) and r2.approves(clean) and (not real or bool(r2.USE_THIS.match(clean)))
    if approving and (af := r2.approved_facts(asking, now_full, clean)):
        facts.update(af)                     # the typical figure on offer, approved: from now on it is the person's own
        real.update(af)
        affirmed.add(asking)
        reply_bits.append(r2.affirm_line(asking, next(iter(af.values())), typical=True) if asking in r2.AFFIRM_LABEL else
                          "Using the typical figure, as you asked. It is now yours to change." if asking != "savings" else
                          f"Using about {_money(af['savings.total'])} for your savings, the typical figure for your age, as you asked. It is now yours to change.")
    # "that's about right", "yes", "ok" with an estimate of ours in the panel for the pending question: approve that figure, and name it
    if not approving and asking in r2.APPROVABLE and not real and not cf and r2.affirms(clean) and p.sources.get(asking) != "you said" \
            and (af := r2.approved_facts(asking, now_full, clean)):
        facts.update(af)
        real.update(af)
        approving = answered = True
        affirmed.add(asking)
        reply_bits.append(r2.affirm_line(asking, next(iter(af.values()))))
    if not approving and asking == "mortgage" and not real and not cf and r2.affirms(clean) and p.notes.get("mortgage_payment_est") == "yes"             and p.home.mortgage_payment > 0 and p.notes.get("mortgage_payment_said") != "yes":
        facts["home.mortgage_payment"] = real["home.mortgage_payment"] = p.home.mortgage_payment      # the estimate, approved: now the person's own
        approving = answered = True
        affirmed.add("home")
        reply_bits.append(f"Good. I will use {_money(p.home.mortgage_payment)} a month for your mortgage payment.")
    asked = None
    if tr is not None and (tr.intent == "question" or tr.question_text) and tr.intent != "off_topic":
        asked = answers.answer(tr.question_topic, tr.question_text or clean, tr.term, asking, miss_now)
    elif tr is None and not real and sup.IS_QUESTION.search(clean):
        asked = answers.answer(answers.topic_from_text(clean), clean, None, asking, miss_now)
    elif not real and asking and (asking in answers.WHY or asking == "savings") and (r2.USE_Q.search(clean) or r2.FIND_Q.search(clean)):
        asked = "x"
    if approving:
        asked = None
    if prep.explain:
        asked = None
        reply_bits.append(prep.explain)
    if prep.partner_note:
        asked = None
        reply_bits.append(prep.partner_note)
    if prep.reject_bit:
        reply_bits.append(prep.reject_bit)
    if asked:
        asked = r2.shape_answer(asked, clean, asking, priv_seen)
    if tr is not None and tr.intent == "off_topic" and not real:
        reply_bits.append(answers.OFF_TOPIC)
    # edit intents, when nothing was read as a fact
    nothing = not real and not any(k in facts for k in ("open_group", "skip_all", "keep", "confirm", "type_prompt", "use_typical", "debt_kind_only")) \
        and not bad and clean.strip() and not escape and not (gr is not None and (gr.looks_off or gr.conflict))         and not (small_msg or prep.reject_bit or prep.explain or prep.partner_note)
    if nothing and asked is None and not (tr is not None and tr.intent == "off_topic"):
        key = facts.get("open_edit")
        in_group = asking in sup.GROUP_QUESTIONS or asking in sup.CONFIRM_BASE
        stray = bool(asking) and not key and not skipping and sup.is_stray_chip(clean, pending_q.quick_answers if pending_q else []) \
            and not (sup.EDIT_VERB.search(clean) and sup.detect_edit(clean) not in (None, "which"))
        if stray:
            reply_bits.append("That answers a different question, so I did not change anything.")
        if not stray and not key and not (in_group and skipping) and not (asking and skipping):
            key = sup.detect_edit(clean)
            if not key and tr is not None and tr.intent == "correction" and words >= 3:
                key = "which"
        if key and not real and key != "which":
            vf = sup.edit_value_facts(clean, key, p.has_partner, len(p.children))
            if vf:      # "my pay is wrong, it is $150,000": the value is in the message, so apply it
                facts, real, key = {**facts, **vf}, dict(vf), None
        if key and not real:
            if key == "which":
                forced_question, forced_asking = sup.which_question(), None
                reply_bits.append("I can change any answer.")
            else:
                forced_question = sup.edit_question(key, p)
                forced_asking = key
                reply_bits.append(f"Sure, let's change {EDIT_LABEL.get(key, 'that')}.")
    asked_at = -1
    if asked:
        asked_at = len(reply_bits)
        reply_bits.append(asked)
    if asking == "savings_split" and any(k.startswith("savings.") for k in facts):
        facts["savings.replace"] = True
    if sum(1 for k in facts if k.startswith("savings.") and k not in ("savings.replace", "savings.mix", "savings.total")) >= 2 and r2.REST_ZERO.search(clean):
        facts["savings.replace"] = True         # "with the rest zero", "no Roth at all": the accounts named are all there is
    if "skip_all" in facts:
        p.offered = list(dict.fromkeys(p.offered + sup.GROUP_ORDER + ["sex", "spending_later"]))
        p.notes["skip_all"] = "yes"          # the groups are closed, not answered: their fields stay "default"
    if "debt_kind_only" in facts and "debts" in facts:
        facts.pop("debt_kind_only")          # the balance came with it: no need to ask for it
    if asking == "debts_detail" and not facts.get("debts") and (skipping or NO_RATE.search(clean)):
        p.offered = list(dict.fromkeys(p.offered + ["debts"]))      # "I don't know the rate": a typical rate is used
        kind = p.notes.pop("pending_debt_kind", None)
        answered = True
        if not asked:
            from ..tools import costs
            rate = costs.RATE_BY_KIND.get(kind or "other", costs.RATE_BY_KIND["other"])
            reply_bits.append(f"Fine. I will use {rate * 100:g}% for that loan, a typical rate, marked estimate so you can change it.")
    if "debt_kind_only" in facts:
        p.notes["pending_debt_kind"] = facts["debt_kind_only"]
        forced_question, forced_asking = sup.group_question("debts_detail", p), "debts_detail"
    # "use the estimate" for an essential: keep the typical figure and stop asking
    ut = [k for k in facts.get("use_typical", []) if isinstance(k, str) and (k != "mortgage" or asking == "mortgage")]      # "not sure" to the split is not about the mortgage
    for k in ut:
        if k in ESSENTIAL_SKIP:
            _skip(p, k)
    if facts.get("use_typical"):
        facts["use_typical"] = [k for k in ut if k not in ("mortgage", "debts", "savings", "children", "home", "state")]
        if not facts["use_typical"]:
            facts.pop("use_typical")
    if re.search(r"\bpension\b", said, re.I) and "pensions" not in facts and not p.pensions \
            and not re.search(r"\b(?:no|not|n't|without|never)\b[^.]{0,20}\bpension", said, re.I):
        p.notes["pension_ask"] = "yes"       # a pension named without its amount: ask for it among the essentials
    held = _gated(facts, p, asking, then) if not page_edit and not escape and forced_question is None else {}
    held_g = _gated_struct(facts, p, asking) if not page_edit and not escape and forced_question is None else {}
    if held or held_g:
        # R7: a figure they stated earlier changes only after a yes; the rest of the message is applied now
        for k in [*held, *held_g]:
            facts.pop(k, None)
            real.pop(k, None)
        if any(k in held_g for k in STRUCT_SAVINGS):
            facts.pop("savings.replace", None)
            real.pop("savings.replace", None)
        if "children.ages" in held_g or "children.count" in held_g:
            for k in ("children.count", "children.ages", "children.sexes", "children.college_each"):
                facts.pop(k, None)
                real.pop(k, None)
        p.notes["pending_change"] = json.dumps({"f": held, "g": held_g, "a": asking})
        forced_question, forced_asking = _change_question(p, {"f": held, "g": held_g}), "confirm_change"
        reply_bits.append("I do not change a figure you gave without your yes.")
    if not clear_ok and not page_edit and not escape and forced_question is None and p.home.owns and p.home.mortgage_balance > 0 \
            and p.notes.get("mortgage_balance_said") == "yes" and (facts.get("home.mortgage_balance") == 0 or facts.get("home.has_mortgage") is False):
        # R2: a mortgage balance the person gave is cleared only on their yes
        for k in ("home.mortgage_balance", "home.mortgage_payment", "home.has_mortgage"):
            facts.pop(k, None)
            real.pop(k, None)
        p.notes["pending_clear_mortgage"] = asking or "-"
        forced_question = Question(text=f"Clear the {_money(p.home.mortgage_balance)} mortgage?", quick_answers=["Yes", "No"])
        forced_asking = "confirm_clear_mortgage"
        reply_bits.append("I do not clear a mortgage you gave without your yes.")
    before = _snap(p)
    changed = apply(p, {k: v for k, v in facts.items() if k not in NON_FACTS})
    if cu := p.notes.pop("college_unclear", None):      # the words did not pick one child, or one type: one short question
        cq = json.loads(cu)
        forced_question, forced_asking = Question(text=cq["question"], quick_answers=cq["quick"]), None
    elif "children" in changed and "college" not in changed and any(c.college_source != "you said" for c in p.children):
        reply_bits.append("I assumed public in-state college for each child, paid in full. It is marked as an estimate. "
                          "Tell me if that is wrong.")
    if "mortgage" in ut and p.home.owns and asking == "mortgage":
        reply_bits.append(_estimate_mortgage(p))
    if range_note and range_note[0] in ("pay_per_year", "partner_pay_per_year", "savings", "spending_now_per_year", "spending_per_year"):
        p.notes[range_note[0]] = range_note[1]
    if asking == "children" and "children" in changed and clean.lower().strip(" .!") in r2.CHILD_CHIPS and not prep.bare:
        n_age = r2.CHILD_CHIPS[clean.lower().strip(" .!")]       # a bucket, not an age: flag it, say so, and do not keep asking
        p.sources["children"] = "assumed"
        p.notes["children"] = f'Assumed age {n_age} from "{clean.strip(" .!").lower()}". Give the real ages if you like.'
        p.notes["skipped_children"] = "yes"
        p.notes["child_bucket"] = str(n_age)
        reply_bits.append(f'I took "{clean.strip(" .!").lower()}" as age {n_age} for now, marked assumed. Give the real ages any time.')
    if p.notes.get("retired") == "yes" and "spending_per_year" in changed and p.spending_per_year \
            and p.sources.get("spending_now_per_year") != "you said":
        p.spending_now_per_year = p.spending_per_year       # already retired: what they spend now is what they spend in retirement
        p.sources["spending_now_per_year"] = "you said"
    if "debts" in changed:
        p.notes.pop("pending_debt_kind", None)
    if asking in sup.CONFIRM_BASE and answered and "open_group" not in facts:      # a message about something else leaves the assumption open
        p.offered = list(dict.fromkeys(p.offered + [asking]))
        p.notes.pop("then", None)
    # a group is done once the person has answered it, with facts or with a plain no
    done_map = {"debts": ("debts",), "pension": ("pensions",), "saving": ("saving", "save_rate"), "insurance": ("insurance",),
                "goals": ("goals", "college"), "health": ("health", "partner_health"),
                "costs": ("budget", "part_time", "inheritance", "emergency_months")}
    for grp, keys in done_map.items():
        if any(k in changed for k in keys):
            p.offered = list(dict.fromkeys(p.offered + [grp]))
    if asking in ("costs", "spending_later") and any(k in changed for k in ("spending_now_per_year", "spending_per_year")):
        p.offered = list(dict.fromkeys(p.offered + ["costs"]))
    if asking in done_map:
        if not changed and not forced_question and (parser_extra.NO_ANSWER.match(clean) or r2.skips(clean, SKIP)):
            p.offered = list(dict.fromkeys(p.offered + [asking]))
    if asking == "health" and "health" in changed and p.sex is None and "sex" not in p.offered and forced_question is None:
        forced_question, forced_asking = sup.group_question("sex", p), "sex"
    if asking == "sex":
        p.offered = list(dict.fromkeys(p.offered + ["sex"]))
    if asking == "costs" and ("spending_now_per_year" in changed or "budget" in changed) and "spending_later" not in p.offered \
            and p.retire_spend_ratio is None and "spending_per_year" not in changed and forced_question is None:
        forced_question, forced_asking = sup.group_question("spending_later", p), "spending_later"
    if asking == "spending_later":
        p.offered = list(dict.fromkeys(p.offered + ["spending_later"]))
    age_needed = asking == "age" and not changed and not facts.get("age") and (r2.skips(clean, SKIP) or bool(parser_extra.NO_ANSWER.match(clean))
                                                                                or bool(re.match(r"\s*(?:i\s+)?(?:dunno|idk|no clue|not telling)\b", clean, re.I)))
    if age_needed:
        # an age cannot be guessed: say so once, plainly, and keep asking; never offer a typical figure for it
        reply_bits.append("I can't guess your age, and the plan needs it. Pick one below or type it.")
        answered = False
    if asking in ("partner_age", "state", "savings", "children", "children_count", "pension", "home", "pay_per_year", "partner_pay_per_year", "retire_age",
                  "spending_now_per_year", "mortgage") and not changed and r2.skips(clean, SKIP):
        _skip(p, asking)
        skipped_key = asking
    elif asking in ESSENTIAL_SKIP and asking != "age" and asking in miss_now and not changed and not real and forced_question is None \
            and OK_ONLY.match(clean):
        # a bare "ok" to an open question: take it as "use a typical figure", say so, and move on
        _skip(p, asking)
        answered = True
        named = _typical_figure_line(asking, household.complete(p)) if asking != "children_count" else ""      # R1: the figure is named
        reply_bits.append("Fine. I will plan with no children; you can add them in the panel." if asking == "children_count" else
                          named or f"Fine. I will use a typical figure for {answers._plain_list([asking])}, marked so you can change it.")
    # "build my plan with typical numbers for the rest": every essential left (but age) takes a typical figure
    escaped: list[str] = []
    if escape:
        for k in missing(household.complete(p) if p.age else p):
            if k != "age":
                _skip(p, k)
                escaped.append(k)
    after = _snap(p)
    corrected = {sk for k in (gr.corrections if gr else set()) if (sk := _fact_snap_key(k)) and k in facts}
    corr_bits, echoed = _corrections(before, after, corrected)
    full = household.complete(p) if p.age else p
    miss = missing(full)
    if asked_at >= 0 and miss != miss_now:        # the answer names what is still needed after this message's facts
        if tr is not None:
            reply_bits[asked_at] = r2.shape_answer(answers.answer(tr.question_topic, tr.question_text or clean, tr.term, asking, miss), clean, asking, priv_seen)
        else:
            reply_bits[asked_at] = r2.shape_answer(answers.answer(answers.topic_from_text(clean), clean, None, asking, miss), clean, asking, priv_seen)
    ready = all(k not in miss for k in REQUIRED) and full.age is not None
    if skipped_key and (tl := r2.typical_line(skipped_key, full)):
        reply_bits.append(tl)
    if "children" in echoed and "children" in miss and forced_question is None and full.age is not None:
        forced_question, forced_asking = question_for("children", full), "children"     # a new count: the ages next
    # the next question
    q: Question | None = None
    reasked = False
    reask_needed = bool(asking) and not answered and forced_question is None and "skip_all" not in facts and not escape \
        and not (page_edit and asking in sup.CONFIRM_BASE)       # after an editor save, no "is that about right?" about something else
    full.asking = None
    if "open_group" in facts:
        full.asking = facts["open_group"]
        q = sup.group_question(full.asking, full)
    elif forced_question is not None:
        q, full.asking = forced_question, forced_asking
    elif reask_needed and (rq := reask(asking, full, miss)) is not None:
        q, full.asking, reasked = rq, asking, True       # the pending question is still open: ask it again
    else:
        imm = [] if page_edit else sup.pending_confirms(full, immediate_only=True)      # an editor save is not followed by an unrelated check
        if imm and full.age:
            q = sup.confirm_question(imm[0], full)
            full.asking = imm[0]
            if miss:
                full.notes["then"] = miss[0]
        elif not page_edit and miss and miss[0] == "pay_per_year" and full.sources.get("pay_per_year") == "estimate" and full.job and full.pay_per_year:
            q, full.asking = sup.confirm_question("confirm_pay", full), "confirm_pay"     # the estimate, stated, for them to check
            if len(miss) > 1:
                full.notes["then"] = miss[1]
        elif miss:
            q = question_for(miss[0], full)
            full.asking = miss[0]
        else:
            later = [] if page_edit else sup.pending_confirms(full)
            if later:
                q = sup.confirm_question(later[0], full)
                full.asking = later[0]
            elif any(g not in full.offered for g in sup.GROUP_ORDER) and "skip_all" not in facts:
                q = sup.more_question(full.offered)
                full.asking = "more"
    summ = summary([c for c in changed if c not in echoed and c not in ut and c not in affirmed], full)      # an estimate the person asked for is not something they said
    disclosure = _disclose(full) if full.age else ""
    escape_line = (f"Fine. I will build your plan with typical figures for {answers._plain_list(escaped)}. Each is marked in the panel, "
                   "and you can change any of them on the plan page."
                   + (" With no state, I use typical US taxes and costs." if "state" in escaped else "") if escaped else
                   ("I need at least your age to build a plan. How old are you?" if escape and full.age is None else ""))
    answer_text = reply_bits.pop(asked_at) if asked_at >= 0 else ""      # what was recorded first, then the answer, then the question
    reply = " ".join(x for x in [*notes, escape_line, *corr_bits, *reply_bits, summ, gr.breakdown_note if gr else "", answer_text,
                                 disclosure, whatif_line] if x)
    if p.age is None and not p.history and not real and not changed and not whatif_line and START_HELP.search(clean):
        reply = START_EXAMPLE            # "idk what to say" as a first message: one example sentence to copy
    no_text = not clean.strip() and not notes
    if not reply.strip() and not changed and not (cleared and no_text):
        # never a dead end: say what was understood, or ask one specific question
        if facts.get("keep"):
            reply = "Kept as it was."
        elif facts.get("confirm"):
            reply = _confirmed_line(full, facts.get("confirm"))
        elif facts.get("skip_all"):
            reply = "Fine. I will use typical figures for the rest, and mark each one."
        elif "open_group" in facts:
            reply = "Sure."
        elif "debt_kind_only" in facts:
            reply = f"Got it: {str(facts['debt_kind_only']).replace('_', ' ')} debt, no amount yet."
        elif ut:
            reply = "Fine. I will use the typical figure, marked so you can change it."
        elif any(k.startswith("skipped_") for k in full.notes) and asking and full.notes.get(f"skipped_{asking}") == "yes":
            reply = ("Fine. I will count no pension; you can add it in the panel." if asking == "pension" else
                     _skip_line(asking, full) or _typical_figure_line(asking, full)
                     or "Fine. I will use the typical figure for that, marked estimate in the panel so you can change it.")
        elif asking in done_map and skipping:
            none_counted = {"debts": "no other debts", "pension": "no pension", "insurance": "no insurance", "goals": "no goals or big costs",
                            "saving": "no extra saving"}
            reply = (f"Fine. I will count {none_counted[asking]} for now; you can add it in the panel." if asking in none_counted else
                     _skip_line("health", full) or "Fine. I will assume good health, marked assumed in the panel so you can change it.")
        elif asking in sup.CONFIRM_BASE and skipping:
            reply = _skip_line(asking, full) or "Fine. I will keep that as it is, marked estimate, so you can change it later in the panel."
        elif page_edit and um:
            reply = _page_edit_line(um.group(1), edit_text, page_bad) or f"Saved. I use your new {um.group(1).lower().strip()} from now on."
        elif q is not None and (miss or reasked):
            reply = _reask_line(asking)
        else:
            reply = "I did not match that to a change. What would you like to change or add?"
            q, full.asking = sup.which_question(), None
    if ut and asking and not (set(real) - {"use_typical"}) and (line := _typical_figure_line(asking, full, estimated=True)):
        reply = reply.replace("Fine. I will use the typical figure, marked so you can change it.", "").strip()
        reply = f"{reply} {line}".strip()      # the person pressed an estimate chip: said as a proposal, not as a fact they gave
    elif (skipping or ut) and asking and not real and (line := _typical_figure_line(asking, full)) and line.split(" use ")[1].split(",")[0] not in reply:
        reply = reply.replace("Fine. I will count no extra costs for now; you can add it in the panel.", "").strip()
        reply = f"{reply} {line}".strip()      # a skipped money question: the typical figure, named and marked
    if disclosure.startswith(DISC_START) and disclosure in reply and (len(reply.split()) > SHORT_WORDS or "facts from your message" in summ):
        n_typ = sum(1 for f in fields(full) if f.source in ("estimate", "assumed"))
        reply = reply.replace(disclosure, f"I filled in {n_typ} more with typical figures. Each is marked in the panel, so you can change it.")      # short first reply
    if page_edit and um and (line := _page_edit_line(um.group(1), edit_text, page_bad)) and line not in reply:
        reply = f"{line} {reply}".strip()      # an edit from the page says old to new, whatever else the reply carries
    if cleared:
        reply = f"{cleared} {reply}"
    # ready to build: say so once, after any confirm question has been answered; later, a short reminder only if no next step is named
    confirm_open = (full.asking or "") in sup.CONFIRM_BASE or (full.asking or "").startswith("confirm")
    if miss or not full.age:
        full.notes.pop("build_told", None)
    elif not confirm_open and clean.strip() and not escape:
        if full.notes.get("build_told") != "yes":
            reply = f"{reply} {BUILD_LINE}".strip()
            full.notes["build_told"] = "yes"
        elif q is None and "Build my plan" not in reply:
            reply = f"{reply} {BUILD_REMINDER}".strip()
    # never stuck: after 8 turns, or when the same question keeps coming back, offer to build with typical numbers
    real_turn = bool(clean.strip()) and not page_edit
    if real_turn:
        full.turns = p.turns + 1
    try:
        stuck = max(0, min(int(p.notes.get("stuck", "0") or 0), 99))
    except (TypeError, ValueError):
        stuck = 0
    stuck = stuck + 1 if (real_turn and not changed and full.asking == asking and asking) else 0
    full.notes["stuck"] = str(min(stuck, 99))
    offered_typ, offer_note = False, ""
    if stuck >= 2 and q is not None and full.asking == asking and (offer := r2.stuck_offer(q, asking, full)):
        q, offer_note = offer       # the third time round: a typical figure on the table, with a Use this button
        reply = f"{reply} {offer_note}".strip()
        offered_typ = True
    if miss and q is not None and "age" not in miss and (full.turns >= 8 or stuck >= 2):
        if ESCAPE not in q.quick_answers:
            q = Question(text=q.text, quick_answers=[*q.quick_answers[:4], ESCAPE])
        if not offered_typ and (full.notes.get("escape_told") != "yes" or stuck >= 2):
            reply += " Or I can build your plan now with typical numbers for the rest."
            full.notes["escape_told"] = "yes"
    # never the same reply twice in a row: say it another way, and offer a way forward
    shown = (reply + " " + (q.text if q else "")).strip()
    if real_turn and not age_needed and _same(shown, _last_app(p)):
        age_q = full.asking == "age" or full.age is None
        alt = (AGE_AGAIN if age_q else
               "I still need this one to go on. A rough figure is fine, or type skip and I will use a typical figure." if reasked or q is not None
               else "I could not use that. You can change an answer, or build your plan now.")
        if _same(alt + " " + (q.text if q else ""), _last_app(p)):
            alt = (AGE_LAST if age_q else
                   "Let's keep moving. Answer the question below in your own words, or press the button to build your plan with typical numbers.")
        reply = f"{alt} {offer_note}".strip()
        if q is not None and miss and ESCAPE not in q.quick_answers and full.age is not None:
            q = Question(text=q.text, quick_answers=[*q.quick_answers[:4], ESCAPE])
        shown = (reply + " " + (q.text if q else "")).strip()
    if not reply.strip():
        reply = r2.FALLBACK + (f" {q.text}" if q is not None else "")       # never an empty reply
        shown = (reply + " " + (q.text if q else "")).strip()
    if r2.used_privacy(reply):
        full.notes["privacy_told"] = "yes"
    if real_turn or reply:
        _history(full, clean if real_turn else "", shown)
    full.notes["children_n"] = str(len(full.children))
    flds = fields(full)
    return IntakeResponse(profile=full.model_dump(), fields=flds, missing=miss, question=q, reply=reply.strip(),
                          ready=ready, sections_status=intake_fields.sections_status(flds), tokens=tokens, cost_usd=round(cost, 6))


def edit_or_essential(key: str, p: Profile) -> Question:
    full = household.complete(p) if p.age else p
    if key in ("mortgage", "partner_pay_per_year"):
        return question_for(key, full)
    return sup.edit_question(key, full)


ESSENTIAL_Q = ("age", "partner_age", "state", "pay_per_year", "partner_pay_per_year", "savings", "children", "retire_age", "spending_now_per_year",
               "home", "mortgage", "debts", "children_count")


def reask(key: str | None, p: Profile, miss: list[str]) -> Question | None:
    """The pending question again, built from the profile as it stands now."""
    if not key:
        return None
    if key in sup.CONFIRM_BASE:
        return sup.confirm_question(key, p)
    if key in sup.GROUP_QUESTIONS:
        return sup.group_question(key, p)
    if key == "more":
        return sup.more_question(p.offered)
    if key in ESSENTIAL_Q and key in miss:
        return question_for(key, p)
    if key == "mortgage":
        return None
    return sup.edit_question(key, p)


def _chips_of(key: str | None, p: Profile) -> list[str]:
    q = _pending_q(key, p)
    return q.quick_answers if q else []


def _college_sexes(text: str) -> dict[int, str]:
    from . import college as _college
    return _college.child_sexes(text)
