"""Intake helpers: wrapper tags, concealment, plausible ranges, edit intents, and the questions that go with them.

Kept apart from intake.py so each piece can be tested alone. No model calls here.
"""
from __future__ import annotations

import re
from typing import Any

from ..schemas import Profile, Question
from . import parser, parser_extra

# ------------------------------------------------------------------ wrapper tags (DI-03)
USER_TAGS = r"(?:user_text|user|untrusted\w*|message|human|input)"
ROLE_TAGS = r"(?:system|assistant|developer|instructions?|prompt|admin|tool\w*|im_start|im_end)"


def strip_wrappers(text: str) -> tuple[str, bool]:
    """Remove text that pretends to sit outside the person's message: everything after a closing user tag, and the
    content of system-like tags. No figure inside them is ever read. Returns (text, removed_something)."""
    t = text or ""
    original = t
    m = re.search(rf"</\s*{USER_TAGS}\s*>", t, re.I)
    if m:
        t = t[:m.start()]
    t = re.sub(rf"<\s*({ROLE_TAGS})\b[^>]*>.*?(?:</\s*\1\s*>|$)", " ", t, flags=re.I | re.S)
    t = re.sub(r"<\|[^|>]*\|>.*$|\[/?INST\].*$", " ", t, flags=re.I | re.S)
    t = re.sub(rf"</?\s*(?:{USER_TAGS}|{ROLE_TAGS})[^>]*>", " ", t, flags=re.I)
    plain = re.sub(rf"</?\s*(?:{USER_TAGS}|{ROLE_TAGS})[^>]*>", " ", original, flags=re.I)
    removed = re.sub(r"\s+", " ", plain).strip() != re.sub(r"\s+", " ", t).strip()
    return re.sub(r"[ \t]+", " ", t).strip(), removed


# ------------------------------------------------------------------ concealment (HA-04)
HIDE_VERB = r"(?:list|report|record|show|enter|write|put|count|leave out|leave off|omit|exclude|keep off|hide|register|call|treat)"
HIDE_WHAT = (r"(?:as (?:zero|\$?0|nothing|none)\b|off the books|out of the (?:plan|total|numbers)|a safe\b|someone else'?s? (?:name|account)|"
             r"(?:cousin|friend|sister|brother|relative|uncle|aunt|neighbor)'?s? (?:account|name|house)|in (?:a |my )?(?:cousin|friend|relative)'?s?)")
HIDE_CONTEXT = r"(?:medicaid|\bssi\b|supplemental security|benefits?|qualif\w+|eligib\w+|nursing home|means[- ]test|asset test)"


def is_hiding(text: str) -> bool:
    """Asking to list money as zero or park it with someone else so that benefits are not lost."""
    from .. import safety     # late: keeps the import order of this module as it was
    low = safety.invisible_free(text).lower()
    return bool(re.search(HIDE_CONTEXT, low) and re.search(HIDE_VERB + r"\b[^.?!]{0,80}" + HIDE_WHAT, low))


# ------------------------------------------------------------------ plausible ranges (DP-04)
RANGES: dict[str, tuple[float, float, str]] = {
    "age": (18, 110, "your age"), "partner_age": (18, 110, "your partner's age"),
    "retire_age": (30, 80, "your retirement age"), "partner_retire_age": (30, 80, "your partner's retirement age"),
    "children.count": (0, 15, "the number of children"),
    "pay_per_year": (0, 5e6, "your pay"), "partner_pay_per_year": (0, 5e6, "your partner's pay"), "household_pay": (0, 1e7, "your pay"),
    "spending_per_year": (0, 3e6, "your spending"), "spending_now_per_year": (0, 3e6, "your spending now"),
    "social_security_per_year": (0, 120000, "your Social Security"),
    "savings.pretax": (0, 5e7, "your pre-tax savings"), "savings.roth": (0, 5e7, "your Roth savings"),
    "savings.taxable": (0, 5e7, "your taxable savings"), "savings.cash": (0, 5e7, "your cash"), "savings.total": (0, 5e7, "your savings"),
    "home.value": (0, 1e8, "your home value"), "home.mortgage_payment": (0, 100000, "your mortgage payment"),
    "home.rent": (0, 100000, "your rent"), "home.mortgage_balance": (0, 2e7, "your mortgage balance"),
    "saving.contrib_you": (0, 500000, "your 401(k) or IRA saving"), "saving.contrib_partner": (0, 500000, "your partner's saving"),
    "saving.other_per_month": (0, 200000, "your other saving"), "saving.match_rate": (0, 2, "the employer match"),
    "saving.match_cap": (0, 1, "the match cap"), "goals.legacy": (0, 1e8, "the amount to leave"),
    "goals.parents_per_year": (0, 500000, "the help for your parents"), "goals.parents_years": (0, 60, "the years of help"),
    "emergency_months": (0, 60, "your emergency fund"), "retire_spend_ratio": (0.1, 3, "your retirement spending share"),
    "insurance.life_face": (0, 1e8, "your life cover"), "insurance.life_premium": (0, 200000, "your life premium"),
}


def _bad(key: str, v: Any) -> tuple[str, Any] | None:
    r = RANGES.get(key)
    if r is None or not isinstance(v, (int, float)) or isinstance(v, bool):
        return None
    return (r[2], v) if not (r[0] <= v <= r[1]) else None


def implausible(facts: dict[str, Any], p: Profile) -> list[tuple[str, str, Any]]:
    """(key, label, value) for each figure outside a plausible range."""
    out = []
    for k, v in list(facts.items()):
        b = _bad(k, v)
        if b:
            out.append((k, b[0], b[1]))
    ages = facts.get("children.ages")
    if ages and any(not (0 <= a <= 50) for a in ages):
        out.append(("children.ages", "your children's ages", [a for a in ages if not (0 <= a <= 50)][0]))
    if "retire_in_years" in facts:
        y, age = facts["retire_in_years"], p.age or facts.get("age")
        if y < 0 or (age and not (30 <= age + y <= 80)):
            out.append(("retire_in_years", "your retirement age", (age or 0) + y))
    for d in facts.get("debts") or []:
        if d["balance"] > 5e6 or (d.get("rate") is not None and not 0 <= d["rate"] <= 0.6) or (d.get("monthly_payment") or 0) > 200000:
            out.append(("debts", "a debt", d["balance"]))
    for pen in facts.get("pensions") or []:
        if pen["per_year"] > 1e6 or ("start_age" in pen and not 40 <= pen["start_age"] <= 90):
            out.append(("pensions", "a pension", pen["per_year"]))
    for b in facts.get("goals.big_costs") or []:
        if b["amount"] > 1e7 or not 2026 <= b["year"] <= 2100:
            out.append(("goals.big_costs", "a big cost", b["amount"]))
    for k in ("part_time", "inheritance"):
        x = facts.get(k)
        if x and (x.get("per_year", x.get("amount", 0)) > 1e8 or (x.get("until_age") and not 40 <= x["until_age"] <= 90)):
            out.append((k, "that amount", x.get("per_year", x.get("amount"))))
    for k, v in facts.items():
        if k.startswith("budget.") and isinstance(v, (int, float)) and v > 100000:
            out.append((k, "that budget line", v))
    return out


def drop_keys(facts: dict[str, Any], bad: list[tuple[str, str, Any]]) -> None:
    for k, _, _ in bad:
        facts.pop(k, None)
        if k == "children.count":
            facts.pop("children.ages", None)
    if any(k == "age" for k, _, _ in bad):
        facts.pop("retire_in_years", None)


def implausible_reply(bad: list[tuple[str, str, Any]]) -> str:
    k, label, v = bad[0]
    if isinstance(v, (int, float)) and v >= 1000:
        shown = f"${v:,.0f}"
    elif isinstance(v, float) and 0 < v < 1.0 and "share" not in label:
        shown = f"{v:g}"
    else:
        shown = f"{v:g}" if isinstance(v, (int, float)) else str(v)
    return f"I read {label} as {shown}, which looks off. I have not stored it. What did you mean?"


# ------------------------------------------------------------------ edit intents
EDIT_VERB = re.compile(r"\b(?:adjust|change|update|fix|wrong|incorrect|correct|edit|redo|revise|modify|mistake|typo|not right|isn'?t right|"
                       r"off|not accurate|inaccurate|replace|amend|switch|different|actually)\b|need to (?:adjust|change|update|fix)", re.I)
EDIT_FIELDS: list[tuple[str, str]] = [
    (r"\b(?:partner|wife|husband|spouse)(?:'s)?\b[^.]{0,20}\b(?:pay|salary|income|earn\w*)\b", "partner_pay_per_year"),
    (r"\b(?:partner|wife|husband|spouse)(?:'s)?\b[^.]{0,20}\bretire\w*", "partner_retire_age"),
    (r"\bretire\w*\b[^.]{0,20}\b(?:spend\w*|budget|costs?)\b|\b(?:spend\w*|budget)\b[^.]{0,20}\bretire\w*", "spending_per_year"),
    (r"\bretire\w*\b|\bstop working\b", "retire_age"),
    (r"\bsplit\b|\bbreakdown\b|\ballocation\b|\bmix of (?:my )?accounts\b|\baccount types?\b", "savings_split"),
    (r"\bsocial security\b", "social_security_per_year"),
    (r"\b(?:pay|salary|income|earn\w*|wage|paycheck)\b", "pay_per_year"),
    (r"\b(?:yearly|annual|monthly)\s+sav\w+|\bsav(?:ing|e)\s+(?:a|per|each|every)\s+(?:year|month)|\bsav(?:e|ing) rate\b|\bhow much (?:i|we) (?:save|put)\b", "saving"),
    (r"\bsav\w+\b|\b401\s?\(?k\)?|\bira\b|\broth\b|nest egg|\bbalance\b", "savings"),
    (r"\bspend\w*\b|\bexpenses?\b|\bbudget\b|\bcosts?\b", "spending_now_per_year"),
    (r"\bkids?\b|\bchild\w*\b|\bsons?\b|\bdaughters?\b", "children_count"),
    (r"\bmortgage\b|\bhome\b|\bhouse\b|\brent\b|\bhousing\b", "home"),
    (r"\bdebts?\b|\bloans?\b|\bowe\b|credit card", "debts"),
    (r"\bpension\b", "pension"),
    (r"\binsurance\b|\bcover\b|\bdisability\b", "insurance"),
    (r"\bgoals?\b|\blegacy\b|\bcollege\b|\binherit\w*", "goals"),
    (r"\bhealth\b", "health"),
    (r"\bage\b|\bhow old\b|\bbirthday\b", "age"),
    (r"\bstate\b|\bwhere (?:i|we) live\b", "state"),
    (r"\brisk\b|\bstocks?\b|\binvest\w* style\b|\bcareful\b|\bgrowth\b", "risk"),
]
GENERIC_EDIT = ("pay", "salary", "income", "savings", "retire age", "retirement age", "kids", "children", "mortgage", "state", "age")


def detect_edit(text: str) -> str | None:
    """The key of the field the person wants to change, or 'which' when they want a change but name nothing."""
    low = (text or "").lower()
    if not low.strip():
        return None
    verb = bool(EDIT_VERB.search(low))
    for pat, key in EDIT_FIELDS:
        if re.search(pat, low):
            short = len(low.split()) <= 4
            if verb or short:
                return key
    return "which" if verb else None


def money_chip(v: float | None, per: str = "a year") -> str | None:
    return None if not v else f"${v:,.0f} {per}"


def edit_question(key: str, p: Profile) -> Question:
    """A targeted question for one field, with the current value as the first quick answer."""
    if key == "pay_per_year":
        cur = money_chip(p.pay_per_year)
        return Question(text="What is your pay now, before tax?", quick_answers=[x for x in [cur and f"Keep {cur}", "Use typical for my job", "Type an amount"] if x])
    if key == "partner_pay_per_year":
        cur = money_chip(p.partner_pay_per_year)
        return Question(text="What is your partner's pay now, before tax?", quick_answers=[x for x in [cur and f"Keep {cur}", "Use typical for their job", "Type an amount"] if x])
    if key == "spending_now_per_year":
        cur = money_chip(p.spending_now_per_year)
        return Question(text="About how much does your household spend now, a month or a year?",
                        quick_answers=[x for x in [cur and f"Keep {cur}", "$4,000 a month", "$7,000 a month", "Estimate it for me"] if x])
    if key == "spending_per_year":
        cur = money_chip(p.spending_per_year)
        return Question(text="In retirement, will you spend the same as now, less, or a set figure?",
                        quick_answers=[x for x in [cur and f"Keep {cur}", "Same as now", "Less, about 60%", "A set figure"] if x])
    if key == "social_security_per_year":
        cur = money_chip(p.social_security_per_year)
        return Question(text="What does your Social Security statement say you will get, for the household?",
                        quick_answers=[x for x in [cur and f"Keep {cur}", "Use the estimate", "Type an amount"] if x])
    if key == "savings_split":
        return Question(text="Give the four amounts in one message. For example: pre-tax 400k, Roth 100k, taxable 200k, cash 50k.",
                        quick_answers=["Mostly in a 401(k)", "Mostly in a bank account", "Half and half"])
    if key == "savings":
        return Question(text="About how much have you saved in all, counting 401(k)s, IRAs, other investments and cash?",
                        quick_answers=["About $50k", "About $250k", "About $750k", "About $2 million"])
    if key == "retire_age":
        cur = p.retire_age
        return Question(text="At what age do you want to stop working?", quick_answers=[x for x in [cur and f"Keep {cur}", "60", "62", "65", "67", "70"] if x])
    if key == "partner_retire_age":
        return Question(text="At what age does your partner want to stop working?", quick_answers=["60", "62", "65", "67", "Same time as me"])
    if key == "children_count":
        return Question(text="How many children do you have?", quick_answers=["None", "1", "2", "3"])
    if key == "children":
        return Question(text="How old are your children?", quick_answers=["Under 5", "5 to 12", "Teenagers", "Grown up"])
    if key == "home":
        return Question(text="Do you own your home or rent?", quick_answers=["I own it outright", "I own it with a mortgage", "I rent"])
    if key == "age":
        return Question(text="How old are you?", quick_answers=["35", "45", "55", "65"])
    if key == "state":
        return Question(text="Which state do you live in?", quick_answers=["Connecticut", "New York", "California", "Texas", "Florida"])
    if key == "risk":
        return Question(text="How do you feel about market ups and downs?", quick_answers=["Careful", "Balanced", "Growth"])
    if key in GROUP_QUESTIONS:
        return group_question(key, p)
    return which_question()


def which_question() -> Question:
    return Question(text="Which one would you like to change?",
                    quick_answers=["My pay", "My savings", "My retirement age", "My spending", "My children", "My home"])


# ------------------------------------------------------------------ optional groups
GROUP_QUESTIONS = {
    "debts": ("Do you owe anything besides a mortgage? Give the kind, the balance and the rate, for example: 30k on student loans at 6%.",
              ["No other debts", "Student loans", "Car loan", "Credit card"]),
    "debts_detail": ("How much is left, and at what rate?", ["$10k at 5%", "$30k at 6%", "$60k at 7%"]),
    "pension": ("Does anyone have a pension? Say how much a year or a month and from what age, for example: $2,000 a month at 65.",
                ["No pension", "$1,000 a month at 65", "$2,000 a month at 65", "$30,000 a year at 62"]),
    "saving": ("How much do you save each year in all? Give the 401(k) or IRA part, what your employer matches, and any other saving. For example: $12,000 a year, company matches 50% up to 6%.",
               ["10% of pay", "$10,000 a year", "Company matches 50% up to 6%", "Nothing yet"]),
    "insurance": ("What cover do you have? Term or whole life (with the amount), disability, long-term care.",
                  ["Term life, $500k", "Whole life, $250k", "Disability only", "None of these"]),
    "goals": ("Any goals: money to leave, college for the children, a big cost with a year, or help for your parents?",
              ["Leave $250k", "Private college", "Help my parents $12k a year for 10 years", "No special goals"]),
    "health": ("How is your health: excellent, good, fair or poor?", ["Excellent", "Good", "Fair", "Poor"]),
    "sex": ("Are you male or female? This only picks the right life table.", ["Male", "Female", "Skip"]),
    "costs": ("What does your household spend now? A year or a month, or a split: housing 2500, food 900, transport 600, health 400, other 1000 a month.",
              ["$4,000 a month", "$6,000 a month", "$9,000 a month", "Estimate it for me"]),
    "spending_later": ("In retirement, will you spend the same as now, less, or a set figure?", ["Same as now", "Less, about 80%", "A set figure"]),
}
GROUP_ORDER = ["debts", "pension", "saving", "insurance", "goals", "health", "costs"]
GROUP_DATA = {"debts": "debts", "pension": "pensions", "saving": "saving", "insurance": "insurance", "goals": "goals", "health": "health",
              "costs": "budget"}


def group_question(key: str, p: Profile) -> Question:
    text, chips = GROUP_QUESTIONS[key]
    if key == "health" and p.has_partner:
        text = "How is your health, and your partner's: excellent, good, fair or poor? For example: me good, partner fair."
    return Question(text=text, quick_answers=list(chips))


def more_question(done: list[str]) -> Question:
    left = [g for g in GROUP_ORDER if g not in done]
    chips = [parser_extra.GROUPS[g][0] for g in left] + ["Skip, use typical"]
    return Question(text="That is enough for a first plan. Want to add detail? Each group is one or two quick questions.", quick_answers=chips)


# ------------------------------------------------------------------ assumptions the chat states, and quick answers to adjust them
CONFIRM_BASE = {"confirm_split": "savings_split", "confirm_pay": "pay_per_year", "confirm_spending_later": "spending_later",
                "confirm_ss": "social_security_per_year", "confirm_risk": "risk"}
CONFIRM_SOURCES = {"confirm_split": ["savings"], "confirm_pay": ["pay_per_year", "partner_pay_per_year"],
                   "confirm_spending_later": ["spending_per_year"], "confirm_ss": ["social_security_per_year"], "confirm_risk": ["risk"]}
YES = re.compile(r"^\s*(?:that'?s about right|about right|that'?s right|looks right|yes|yep|yeah|ok|okay|fine|correct|good|keep(?: it)?|"
                 r"balanced is fine|use the estimate|that is about right|sounds right)\b[^a-z]*$", re.I)
MIX = {"mostly in a 401(k)": (0.8, 0.1, 0.05, 0.05), "mostly in a 401k": (0.8, 0.1, 0.05, 0.05),
       "mostly in a bank account": (0.1, 0.0, 0.2, 0.7), "half and half": (0.4, 0.1, 0.1, 0.4)}


def confirm_facts(text: str, key: str) -> dict[str, Any]:
    t = (text or "").strip()
    low = t.lower().strip(" .!")
    if YES.match(t):
        return {"confirm": key}
    if key == "confirm_split":
        if low in MIX:
            return {"savings.mix": MIX[low]}
        if low in ("change the split", "change split"):
            return {"open_edit": "savings_split"}
    if low in ("type my real pay", "type an amount", "use a different amount"):
        return {"open_edit": CONFIRM_BASE[key]}
    if low == "a set figure":
        return {"open_edit": "spending_per_year"}
    return {}


def confirm_question(key: str, p: Profile) -> Question | None:
    if key == "confirm_split":
        s = p.savings
        t = s.total
        if not t:
            return None
        sh = [round(100 * x / t) for x in (s.pretax, s.roth, s.taxable, s.cash)]
        return Question(text=f"I split your ${t:,.0f} as {sh[0]}% in pre-tax accounts like a 401(k), {sh[1]}% Roth, {sh[2]}% taxable and {sh[3]}% cash. Is that about right?",
                        quick_answers=["That's about right", "Mostly in a 401(k)", "Mostly in a bank account", "Change the split"])
    if key == "confirm_pay":
        return Question(text=f"I estimated your pay at ${p.pay_per_year:,.0f} a year from typical pay for your job and state. Is that about right?",
                        quick_answers=["That's about right", "Type my real pay"])
    if key == "confirm_spending_later":
        ratio = (p.spending_per_year or 0) / p.spending_now_per_year if p.spending_now_per_year else None
        from ..tools import costs as _costs
        no_mort = _costs.mortgage_separate(p)     # the goal leaves the mortgage out (household.complete); say so, not an odd share
        if no_mort and ratio:
            ratio = p.retire_spend_ratio if p.retire_spend_ratio is not None else 0.8
        how = (f"I assumed you will spend about {round(ratio * 100)}% of today's ${p.spending_now_per_year:,.0f}"
               + (", not counting the mortgage," if no_mort else "") + f" in retirement, "
               f"${p.spending_per_year:,.0f} a year." if ratio and p.sources.get("spending_per_year") == "assumed"
               else f"I estimated your spending in retirement at ${p.spending_per_year:,.0f} a year from your take-home pay.")
        return Question(text=how + " Is that about right?", quick_answers=["That's about right", "Same as now", "Less, about 60%", "A set figure"])
    if key == "confirm_ss":
        return Question(text=f"I estimated Social Security at ${p.social_security_per_year:,.0f} a year for the household, from pay and your claiming age. "
                             "Your real figure is at ssa.gov/myaccount. Is that about right?",
                        quick_answers=["That's about right", "Type an amount"])
    if key == "confirm_risk":
        return Question(text="I assumed a balanced mix: stocks at 110 minus your age, at most 75%. Is that about right?",
                        quick_answers=["Balanced is fine", "Careful", "Growth"])
    return None


def pending_confirms(p: Profile, immediate_only: bool = False) -> list[str]:
    """Assumptions still unconfirmed and not yet asked about, in the order to ask."""
    done = set(p.offered)
    out = []
    if p.sources.get("savings") == "assumed" and p.notes.get("savings") and "confirm_split" not in done:
        out.append("confirm_split")
    if immediate_only:
        return out
    if p.sources.get("pay_per_year") == "estimate" and p.job and "confirm_pay" not in done:
        out.append("confirm_pay")
    if p.sources.get("spending_per_year") in ("assumed", "estimate") and "confirm_spending_later" not in done:
        out.append("confirm_spending_later")
    if p.sources.get("social_security_per_year") == "estimate" and "confirm_ss" not in done:
        out.append("confirm_ss")
    if p.sources.get("risk") == "assumed" and "confirm_risk" not in done:
        out.append("confirm_risk")
    return out


# ------------------------------------------------------------------ does the message answer the pending question?
MARKERS = ("open_group", "skip_all", "keep", "type_prompt", "confirm", "open_edit", "debt_kind_only", "use_typical")
_PAY_OWN = ("pay_per_year", "household_pay", "job", "retired", "partner_pay_per_year", "partner_job", "has_partner", "partner_sex")
OWN: dict[str, tuple[str, ...] | None] = {
    "age": ("age", "partner_age", "has_partner", "partner_sex"), "partner_age": ("partner_age", "age"), "state": ("state",),
    "pay_per_year": _PAY_OWN, "partner_pay_per_year": _PAY_OWN, "savings": ("savings.",), "savings_split": ("savings.",),
    "children": ("children.",), "children_count": ("children.",), "home": ("home.",), "mortgage": ("home.",),
    "retire_age": ("retire_age", "retire_in_years", "partner_retire_age"), "partner_retire_age": ("partner_retire_age", "retire_age"),
    "spending_now_per_year": ("spending_now_per_year", "spending_per_year", "budget.", "retire_spend_ratio"),
    "spending_per_year": ("spending_per_year", "retire_spend_ratio", "spending_now_per_year"),
    "spending_later": ("retire_spend_ratio", "spending_per_year"), "social_security_per_year": ("social_security_per_year",),
    "risk": ("risk",), "debts": ("debts",), "debts_detail": ("debts",), "pension": ("pensions",), "saving": ("saving.", "save_rate"),
    "insurance": ("insurance.",), "goals": ("goals.", "children.college"), "health": ("health", "partner_health", "sex", "partner_sex"),
    "sex": ("sex", "partner_sex"),
    "costs": ("spending_now_per_year", "budget.", "part_time", "inheritance", "emergency_months", "retire_spend_ratio", "spending_per_year"),
    "more": None,        # an open question: any fact will do
}


def own_keys(asking: str | None, then: str | None = None) -> tuple[str, ...] | None:
    """The fact keys that answer the pending question (None: any). A confirmation also takes its follow-on question's keys."""
    if asking in CONFIRM_BASE:
        base = OWN.get(CONFIRM_BASE[asking]) or ()
        extra = OWN.get(then or "") or ()
        return tuple(base) + tuple(extra)
    return OWN.get(asking or "", ())


def _owns(key: str, own: tuple[str, ...]) -> bool:
    return any(key == o or (o.endswith(".") and key.startswith(o)) for o in own)


def answers(facts: dict[str, Any], asking: str | None, then: str | None = None) -> bool:
    """True when the facts hold a figure of the pending question's own kind that fits its range."""
    if not asking:
        return False
    own = own_keys(asking, then)
    if own is None:
        return bool(facts)
    if any(k in facts for k in MARKERS):
        return True
    return any(_owns(k, own) and _bad(k, v) is None for k, v in facts.items())


_CHIPS: set[str] | None = None


def all_chips() -> set[str]:
    """Every quick-answer chip the app offers, lower case. A chip typed at a different question is a stray."""
    global _CHIPS
    if _CHIPS is None:
        from ..schemas import Child, Savings
        from . import intake
        p = Profile(age=45, has_partner=True, partner_age=43, state="CT", pay_per_year=80000.0, partner_pay_per_year=0.0, retire_age=65,
                    spending_now_per_year=60000.0, spending_per_year=48000.0, social_security_per_year=30000.0, children=[Child(age=5)],
                    savings=Savings(pretax=60000.0, roth=10000.0, taxable=20000.0, cash=10000.0), savings_known=True, job="teacher")
        qs = [intake.question_for(k, p) for k in ("age", "partner_age", "state", "pay_per_year", "partner_pay_per_year", "savings", "children", "retire_age",
                                                    "spending_now_per_year", "home")]
        qs += [confirm_question(k, p) for k in CONFIRM_BASE]
        qs += [group_question(k, p) for k in GROUP_QUESTIONS]
        qs += [edit_question(k, p) for k in ("pay_per_year", "partner_pay_per_year", "spending_now_per_year", "spending_per_year", "social_security_per_year",
                                             "savings_split", "savings", "retire_age", "partner_retire_age", "children_count", "children", "home",
                                             "age", "state", "risk")]
        qs += [which_question(), more_question([])]
        _CHIPS = {c.lower() for q in qs if q for c in q.quick_answers if not c.lower().startswith("keep ")}
    return _CHIPS


def is_stray_chip(text: str, current: list[str]) -> bool:
    low = (text or "").strip().lower().strip(" .!")
    return bool(low) and low in all_chips() and low not in {c.lower() for c in current}


def reset_labels(names: list[str]) -> list[str]:
    """Plain names of the sections a reset cleared, or ['everything']."""
    if any(n.lower() == "all" for n in names):
        return ["everything"]
    out = []
    for name in names:
        norm = name.lower().replace("_", " ").replace(" & ", " ").replace("&", " ")
        sec = next((s for s in SECTION_NAMES if s.lower().replace(" & ", " ") == norm), None)
        if sec and sec.lower() not in out:
            out.append(sec.lower())
    return out


SECTION_NAMES = ["Household", "Work & pay", "Saving", "Home & debts", "Pensions & income", "Insurance", "Goals", "Health", "Costs"]


def cleared_message(names: list[str]) -> str:
    lab = reset_labels(names)
    if not lab:
        return ""
    if lab == ["everything"]:
        return "Cleared all your answers."
    return "Cleared your " + (", ".join(lab[:-1]) + " and " + lab[-1] if len(lab) > 1 else lab[0]) + "."


IS_QUESTION = re.compile(r"\?\s*$|^\s*(?:why|what|how|when|where|who|which)\b", re.I)


VALUE_EDITS = ("saving", "pay_per_year", "partner_pay_per_year", "spending_now_per_year", "spending_per_year", "social_security_per_year", "savings",
               "retire_age", "age", "partner_age")


def edit_value_facts(text: str, key: str | None, has_partner: bool = False, n_children: int = 0) -> dict[str, Any]:
    """An edit intent with its value in the same message ('my pay is wrong, it is $150,000') -> the fact to apply, else {}."""
    if key not in VALUE_EDITS:
        return {}
    facts = parser.parse(text, asking=key, has_partner=has_partner, n_children=n_children)
    facts = {k: v for k, v in facts.items() if isinstance(v, (int, float)) and not isinstance(v, bool) and _owns(k, own_keys(key) or ()) and _bad(k, v) is None}
    if not facts and key in ("retire_age", "age", "partner_age"):
        nums = [int(x) for x in re.findall(r"(?<![\d$,.])\b(\d{2})\b(?![,.]\d|%|\s*(?:k\b|years? (?:ago|from)))", text or "")]
        if len(nums) == 1 and RANGES[key][0] <= nums[0] <= RANGES[key][1]:
            facts = {key: nums[0]}
    return facts


DROP_CLAUSE = re.compile(HIDE_WHAT + "|" + HIDE_CONTEXT + r"|\b(?:hide|hiding|conceal\w*|shelter\w*|transfer\w*)\b", re.I)


def strip_concealment(text: str) -> tuple[str, bool]:
    """Take out the clauses that ask to hide money; keep every other clause (the true facts). Returns (kept text, found)."""
    from .. import safety     # late: safety has no import of this module
    kept: list[str] = []
    found = False
    for sentence in re.split(r"(?<=[.;!?])\s+|\n", text or ""):
        if not sentence.strip():
            continue
        if not (is_hiding(sentence) or safety.is_medicaid_hiding(sentence)):
            kept.append(sentence.strip())
            continue
        found = True
        clauses = re.split(r",\s+|\s+(?:and|but)\s+", sentence)
        kept += [c.strip(" .,") for c in clauses if c.strip(" .,") and not DROP_CLAUSE.search(c)]
    return ". ".join(kept), found
