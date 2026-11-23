"""Plan-chat answers about the plan's own figures: what the count-on figure includes, what the plan assumes, "just tell me",
what to do first, how risky it is, and how Social Security is treated.

Each answer is built from `plan` (the plan dict) and the profile, in plain words. A question about the plan's own figures is
never answered with a quote from an official source: the sources answer rules, the plan answers itself.
"""
from __future__ import annotations

import re
from typing import Any

from .agents import intake_fields
from .schemas import Profile

CHIPS = ["Try a What If", "Explain my plan", "Change an answer"]
ZERO = {"input": 0, "cached": 0, "output": 0}

INCLUDE_Q = re.compile(r"\b(?:includ\w*|count(?:s|ed|ing)?|cover(?:s|ed)?|contain\w*|account(?:s|ed)? for|factor(?:s|ed)? in|part of|inside|"
                       r"in(?:cluding)? (?:it|there|that|this)|separate|on top of|before tax|after tax|made (?:up )?of|split)\b", re.I)
PLAN_REF = re.compile(r"\$\s?\d|\b(?:does|do|is|are)\s+(?:that|this|it)\s+(?:\w+\s+){0,2}(?:includ|count|cover|contain)\w*|\b(?:the|that|this|my|our)\s+(?:\w+\s+)?(?:figure|number|amount|total|plan|result|safe|spending|count[- ]on)\b|"
                      r"\bcount(?:ing)? on\b|\bsafe (?:amount|spending)\b|\bhow much i can spend\b|\bthe plan\b|\bmy plan\b", re.I)
TOPICS = [
    ("social", re.compile(r"\bsocial security\b|\bss\b|\bbenefits?\b", re.I)),
    ("pension", re.compile(r"\bpensions?\b", re.I)),
    ("savings", re.compile(r"\bwithdraw\w*|\bsavings?\b|\b401\s?\(?k\)?|\bira\b|\bnest egg\b|\binvestments?\b", re.I)),
    ("housing", re.compile(r"\bmortgage\b|\brent\b|\bhousing\b|\bhome\b|\bhouse\b|\bpayment\b", re.I)),
    ("tax", re.compile(r"\btax\w*\b", re.I)),
    ("health", re.compile(r"\bhealth\b|\bmedicare\b|\binsurance\b|\bmedical\b", re.I)),
    ("pay", re.compile(r"\bpay\b|\bsalary\b|\bwages?\b|\bpart[- ]time\b|\bearnings?\b", re.I)),
]
ASSUME_Q = re.compile(r"\bassum\w*\b|\bwhat (?:is|are) (?:it|the plan|you) (?:counting|using|taking)\b|\bwhat(?:'s| is) (?:it|the plan) (?:counting|using)\b|"
                      r"\bwhat (?:does|do) (?:the plan|it|you) (?:count|use|take|think)\b|\bwhat(?:'s| is) it counting\b", re.I)
JUST_TELL = re.compile(r"\bjust tell me\b|\bstraight answer\b|\bgive me (?:a|the) (?:number|answer|bottom line)\b|\bbottom line\b|"
                       r"\bwhat(?:'s| is) the (?:answer|verdict)\b|\bso (?:am i|are we) (?:ok|okay|fine)\b|\bwill (?:i|we) be (?:ok|okay|fine)\b|\bjust (?:say|answer)\b", re.I)
FIRST_Q = re.compile(r"\b(?:what|which)\b[^.?!]{0,30}\b(?:do|change|look at|fix|start|try)\b[^.?!]{0,15}\bfirst\b|\bfirst thing\b|\bwhere (?:do|should) (?:i|we) start\b|"
                     r"\bwhat would it take\b|\bwhat should (?:i|we) do\b|\bwhat do (?:i|we) do\b|\bwhat(?:'s| is) the next step\b|\bwhere do i begin\b", re.I)
RISK_Q = re.compile(r"\bhow risky\b|\btoo risky\b|\bhow (?:likely|sure|safe)\b[^.?!]{0,40}\b(?:run out|last|work)\b|\brun out of money\b|\bhow risk\w*\b", re.I)
SS_TREAT = re.compile(r"\bhow\b[^.?!]{0,40}\b(?:treat|handl|us|count|includ|work|model|fit)\w*\b[^.?!]{0,30}\bsocial security\b|"
                      r"\bsocial security\b[^.?!]{0,20}\b(?:fit|fits|in the plan|in there|in it|in this)\b", re.I)


def reply(text: str, chips: list[str] | None = None) -> dict:
    return {"kind": "answer", "intent": "question_plan", "text": text, "citations": [], "quick_answers": chips or CHIPS,
            "tokens": dict(ZERO), "cost_usd": 0.0}


def _m(x: Any) -> str:
    return f"${float(x):,.0f}"


def _has(plan: dict | None, *keys: str) -> bool:
    return isinstance(plan, dict) and all(plan.get(k) is not None for k in keys)


def _per_year(plan: dict) -> float | None:
    w = plan.get("wants") if isinstance(plan.get("wants"), dict) else {}
    v = w.get("per_year", plan.get("count_on_per_year"))
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _source_bits(base: Profile) -> dict[str, tuple[str, str]]:
    try:
        return {str(r.get("key")): (str(r.get("display")), str(r.get("source"))) for r in intake_fields.rows(base)}
    except Exception:     # noqa: BLE001  a row that cannot be built is never a reason to fail an answer
        return {}


def _ss_line(base: Profile, plan: dict) -> str:
    ss = plan.get("social_security_per_year") or base.social_security_per_year
    claim = plan.get("claim_age")
    if not ss:
        return "Social Security is counted, but I have no figure for yours yet."
    start = "and you already get it" if plan.get("already_claiming") else (f"starting at {claim}" if claim else "")
    return f"Social Security: about {_m(ss)} a year{(' ' + start) if start else ''}."


def _pension_line(base: Profile) -> str:
    if not base.pensions:
        return ""
    bits = [f"{_m(p.per_year)} a year from {p.start_age}" if p.start_age else f"{_m(p.per_year)} a year" for p in base.pensions if p.per_year]
    return ("Pensions: " + ", ".join(bits) + ".") if bits else ""


def includes(q: str, base: Profile, plan: dict) -> dict | None:
    low = q.lower()
    if not INCLUDE_Q.search(low) or not PLAN_REF.search(low):
        return None
    topics = [name for name, rx in TOPICS if rx.search(low)]
    per = _per_year(plan)
    head = (f"The {_m(per)} a year you can count on" if per else "The amount you can count on") + \
           " is what you can spend a year, from every source. Your money lasts in 90 of 100 market tests."
    sources = ["Social Security", "pensions" if base.pensions else None, "pay while you work", "withdrawals from your savings"]
    head += " It draws on " + ", ".join(s for s in sources if s).replace(", withdrawals", " and withdrawals", 1) + "."
    extra = []
    if "social" in topics:
        extra.append(_ss_line(base, plan))
    if "pension" in topics:
        extra.append(_pension_line(base) or "You gave no pension, so none is counted.")
    if "savings" in topics:
        extra.append("Your savings are spent down over the years, in the order that usually keeps tax lowest.")
    if "housing" in topics:
        b = (plan.get("needs") or {}).get("basics_per_year")
        extra.append("Housing, a mortgage payment or rent, is part of your needs" + (f" ({_m(b)} a year)" if b else "") +
                     ", so it is already inside the figure, not on top of it.")
    if "tax" in topics:
        extra.append("The plan counts income tax with the 2027 federal brackets and your state's rates.")
    if "health" in topics:
        extra.append("Health care is part of your needs, so it is inside the figure.")
    if "pay" in topics and not base.pay_per_year == 0:
        extra.append("Your pay counts until you retire.")
    if not extra:
        extra = [_ss_line(base, plan), _pension_line(base)]
    return reply(" ".join([head] + [e for e in extra if e][:3]))


def assumes(q: str, base: Profile, plan: dict) -> dict | None:
    if not ASSUME_Q.search(q.lower()) or re.search(r"\bwhat if\b", q.lower()):
        return None
    rows = _source_bits(base)
    pick = []
    for key, label in (("retire_age", "you retire at"), ("spending_per_year", "your spending goal is"), ("savings", "your savings are"),
                       ("social_security_per_year", "your Social Security is"), ("pay_per_year", "your pay is")):
        if key in rows:
            disp, src = rows[key]
            if key == "pay_per_year" and str(disp).lower().startswith("no pay"):
                pick.append(f"you have no pay ({src})")
                continue
            if key == "social_security_per_year" and plan.get("claim_age") and not plan.get("already_claiming"):
                disp += f", claimed at {plan['claim_age']}"
            pick.append(f"{label} {disp} ({src})")
    lines = [re.sub(r"\s+", " ", str(x))[:260] for x in (plan.get("assumptions") or []) if isinstance(x, str)]
    rest = [x for x in lines if re.search(r"today's dollars|Pay stays|earn on average|Inflation", x)][:2] or lines[:2]
    ht = plan.get("horizon_text")
    text = ("The plan uses what you told me: " + "; ".join(pick) + ". " if pick else "") + (f"It plans {re.sub(chr(10), ' ', ht)[:200]}. " if isinstance(ht, str) and ht else "") + " ".join(rest)
    return reply(text.strip(), ["Change an answer", "Explain my plan", "Try a What If"])


def next_step(plan: dict) -> str:
    try:
        a0 = plan["actions"][0]
        return f"First step: {str(a0['title']).rstrip('.')}. {str(a0['why']).strip()}"
    except (KeyError, IndexError, TypeError):
        return "Your plan page lists what to do first."


def risk_line(plan: dict) -> str:
    try:
        return f"{plan['needs']['line']} {plan['wishes']['line']}"
    except (KeyError, TypeError):
        return ""


def headline_answer(plan: dict, base: Profile, risk: bool = False) -> dict:
    head = plan.get("headline") if isinstance(plan.get("headline"), str) else ""
    head = head.split(". ")[0].rstrip(".") + "." if head else head      # the long second sentence is on the plan page
    if not head and _per_year(plan):
        head = f"You can count on {_m(_per_year(plan))} a year."
    parts = [head, risk_line(plan) if risk else "", next_step(plan)]
    return reply(" ".join(p for p in parts if p), ["Try a What If", "Explain my plan", "Change an answer"])


def social_security(base: Profile, plan: dict) -> dict:
    parts = [_ss_line(base, plan)]
    if plan.get("claim_age") and not plan.get("already_claiming"):
        parts.append(f"The plan claims at {plan['claim_age']}; each year of waiting, up to 70, raises the benefit.")
    if base.has_partner and plan.get("partner_claim_age"):
        parts.append(f"Your partner claims at {plan['partner_claim_age']}.")
    parts.append("It is part of the amount you can count on, with pensions and withdrawals from savings.")
    return reply(" ".join(parts), ["What if I claim Social Security at 70", "What if I claim Social Security at 67", "Explain my plan"])


def about_plan(q: str) -> bool:
    """A question that points at the plan's own figures, so a source quote cannot answer it."""
    low = q.lower()
    return bool(PLAN_REF.search(low) or JUST_TELL.search(low) or FIRST_Q.search(low) or RISK_Q.search(low) or ASSUME_Q.search(low) or SS_TREAT.search(low))


def answer(q: str, base: Profile, plan: dict) -> dict | None:
    """None means: not a question about the plan's own figures."""
    low = q.lower()
    if re.search(r"\bwhat if\b", low) and not ASSUME_Q.search(low):
        return None
    out = assumes(q, base, plan) or includes(q, base, plan)
    if out:
        return out
    if SS_TREAT.search(low) and not re.search(r"\b(?:limit|tax|taxable|wage base|earnings|medicare|spous\w*|survivor)\b", low):
        return social_security(base, plan)
    first, risk, tell = bool(FIRST_Q.search(low)), bool(RISK_Q.search(low)), bool(JUST_TELL.search(low))
    if first or risk or tell:
        return headline_answer(plan, base, risk=risk)
    return None
