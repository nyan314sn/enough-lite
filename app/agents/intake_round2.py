"""Intake fixes from loop round 2 (simulated users C, UI audit B). Small pure helpers; intake.run calls them at a few points.

Rules behind them: never a dead end; a skipped input gets a proposed typical figure shown for approval, and an approved
figure becomes the person's own; never fill silently; plain words.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..schemas import Profile, Question
from . import intake_answers as answers

MORE = {"k": 1e3, "thousand": 1e3, "grand": 1e3, "m": 1e6, "million": 1e6}
FIG = re.compile(r"\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(k\b|grand\b|thousand\b|m\b|million\b)?", re.I)
BARE = re.compile(r"^\s*\$?\s*\d[\d,]*(?:\.\d+)?\s*(?:k|thousand|grand)?\s*(?:a|per|/)?\s*(?:month|mo|year|yr|monthly|annually)?\s*[.!]?\s*$", re.I)

FALLBACK = "I lost the thread of that, sorry. Here is the question again."

# ------------------------------------------------------------------ approving a typical figure
APPROVE = re.compile(
    r"\bwhatever(?:'s| is)? (?:normal|typical|usual|average|fine|best)\b|\buse (?:the |a |your )?(?:typical|usual|average|normal|estimate\w*)\b|"
    r"\b(?:click|take|pick|choose|go with|press)\s+(?:the\s+)?(?:estimate|typical)\w*(?:\s+one)?\b|\b(?:the\s+)?estimate(?:d)? (?:one|figure|number)\b|"
    r"\bestimate it\b|\btypical (?:figure|number|one)\b|^\s*use this\b|\byou (?:pick|choose|decide|guess)\b|\byour (?:best )?guess\b|\bup to you\b|"
    r"\bjust guess\b|\bnormal one\b", re.I)
USE_THIS = re.compile(r"^\s*use this\b", re.I)
QWORD = re.compile(r"^\s*(?:(?:hmm|well|um+|ok(?:ay)?|so)[,.]?\s*)*(?:why|what|how|who|where|when|which|is|are|do|does|did|can|could|should|would|will)\b", re.I)
NO_FIGURE = {"state": "typical US taxes and costs", "partner_age": "the same age as you", "children_count": "no children",
             "debts": "no other debts", "mortgage": "a typical payment"}
APPROVABLE = ("spending_now_per_year", "pay_per_year", "partner_pay_per_year", "retire_age", "social_security_per_year", "spending_per_year")


AFFIRM = re.compile(r"^\s*(?:yes|yeah|yep|yup|ok(?:ay)?|fine|sure|correct|right|good|about right|that'?s (?:about |all )?(?:right|fine|ok|okay|good|correct)|"
                    r"sounds (?:about )?(?:right|good|fine)|looks (?:about )?(?:right|good|fine))\b", re.I)
AFFIRM_LABEL = {"spending_now_per_year": ("your spending now", " a year"), "pay_per_year": ("your pay", " a year"),
                "partner_pay_per_year": ("your partner's pay", " a year"), "retire_age": ("your retirement age", ""),
                "social_security_per_year": ("your Social Security", " a year"), "spending_per_year": ("your spending in retirement", " a year")}


def affirms(text: str) -> bool:
    """'that's about right', 'yes', 'ok', 'fine', 'sounds right': a yes, with nothing added that could be a figure or a change."""
    t = (text or "").strip()
    return bool(AFFIRM.match(t)) and len(t.split()) <= 6 and not re.search(r"\d|\b(?:but|not|no|except|though|however|too|wrong)\b", t, re.I)


def affirm_line(asking: str, v: float, typical: bool = False) -> str:
    """'Good. I will use $166,000 a year for your spending now.' The figure is named, and from now on it is the person's own."""
    label, unit = AFFIRM_LABEL[asking]
    fig = f"age {v:g}" if asking == "retire_age" else f"${v:,.0f}{unit}"
    if typical:
        return f"Using the typical figure, {fig} for {label}. It is now yours to change."
    return f"Good. I will use {fig} for {label}."


def approves(text: str) -> bool:
    """'use typical', 'click the estimate one', 'whatever is normal', 'use this': approving the figure on offer."""
    t = text or ""
    return bool(APPROVE.search(t)) and not QWORD.match(t) and len(t.split()) <= 30


def skips(text: str, base: tuple[str, ...]) -> bool:
    low = (text or "").lower()
    hit = any((re.search(r"(?<![a-z])pass(?![a-z])", low) if s == "pass" else s in low) for s in base)      # "passed away" is not "pass"
    return hit or approves(text)


# Federal Reserve Board, Survey of Consumer Finances 2022, interactive chart table "Retirement accounts", median by age of head
# (https://www.federalreserve.gov/econres/scf/dataviz/scf/table/): median among families that hold such an account.
# The Fed table is in 2025 dollars; divided by 1.0956 (its 2025 all-family median $95,211 / the Bulletin's 2022 figure $86,900
# in "Changes in U.S. Family Finances from 2019 to 2022", 2023) to give 2022 dollars, rounded to $1,000.
# Bands map one to one: under 35, 35-44, 45-54, 55-64, 65-74, 75 or older.
_SAVINGS_BY_AGE = ((35, 19000.0), (45, 45000.0), (55, 115000.0), (65, 185000.0), (75, 200000.0), (200, 131000.0))


def typical_savings(age: int | None) -> float:
    a = age or 45
    return next(v for lim, v in _SAVINGS_BY_AGE if a < lim)


SAVINGS_NOTE = "Typical for your age (Federal Reserve survey)."


def proposal(asking: str | None, full: Profile) -> tuple[str, str] | None:
    """(the figure in words, the 'Use this' chip) for a pending question that has a typical figure."""
    if asking == "spending_now_per_year" and full.spending_now_per_year:
        f = f"${full.spending_now_per_year:,.0f} a year"
    elif asking == "pay_per_year" and full.pay_per_year:
        f = f"${full.pay_per_year:,.0f} a year"
    elif asking == "partner_pay_per_year" and full.partner_pay_per_year:
        f = f"${full.partner_pay_per_year:,.0f} a year"
    elif asking == "retire_age" and full.retire_age:
        f = f"age {full.retire_age}"
    elif asking == "social_security_per_year" and full.social_security_per_year:
        f = f"${full.social_security_per_year:,.0f} a year"
    elif asking == "savings":
        f = f"about ${typical_savings(full.age):,.0f}"
    elif asking in NO_FIGURE:
        f = NO_FIGURE[asking]
    else:
        return None
    return f, f"Use this: {f}"


def approved_facts(asking: str, now_full: Profile, text: str) -> dict[str, Any]:
    """The typical figure the person approved, as facts (so it becomes their own)."""
    if asking == "savings":
        m = re.search(r"about \$?([\d,]+)", text or "", re.I)
        return {"savings.total": float(m.group(1).replace(",", "")) if m else typical_savings(now_full.age)}
    if asking in APPROVABLE:
        v = getattr(now_full, asking, None)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v:
            return {asking: v}
    return {}


def typical_line(asking: str | None, full: Profile) -> str:
    if asking == "savings" and full.savings_known and full.sources.get("savings") == "assumed":
        return f"Fine. I will use ${full.savings.total:,.0f} for your savings, the typical figure for your age, marked so you can change it."
    pr = proposal(asking, full)
    if pr is None or asking == "savings" or asking in NO_FIGURE:
        return ""
    label = {"spending_now_per_year": "your spending", "pay_per_year": "your pay", "partner_pay_per_year": "your partner's pay",
             "retire_age": "your retirement", "social_security_per_year": "your Social Security"}[asking]
    return f"Fine. For {label} I will use {pr[0]}, a typical figure, marked in the panel so you can change it."


def stuck_offer(q: Question, asking: str | None, full: Profile) -> tuple[Question, str] | None:
    """The third time the same question comes back: put a typical figure on the table with a 'Use this' button."""
    pr = proposal(asking, full)
    if pr is None:
        return None
    chips = [pr[1], *[c for c in q.quick_answers if not c.lower().startswith("use this")][:3]]
    note = f"Here is a typical {'choice' if asking in NO_FIGURE else 'figure'}: " + pr[0] + (" (the median for your age)" if asking == "savings" else "") + ". Press Use this, or type your own."
    return Question(text=q.text, quick_answers=chips), note


# ------------------------------------------------------------------ what a message quotes, rejects or ranges over
COMPLAINT = re.compile(
    r"where did|how did you (?:get|come|work)|came from|come from|never (?:said|told|gave|stated|mentioned)|didn'?t (?:say|tell|give)|"
    r"did not (?:say|tell|give)|made[- ]up|making (?:it|them|numbers)|pulled|out of nowhere|"
    r"you(?:'re|'ve| are| have)? (?:assuming|assumed|wrote|written|recorded|put|stored|noted|using|made|said|told)|fix (?:it|that|this)|not mine", re.I)
SOURCE = {
    "social_security_per_year": "I estimated it from your pay and the age you retire, using the Social Security formula. "
                                "It is a yearly amount in today's dollars, before income tax.",
    "spending_now_per_year": "I estimated it from your pay and state, less what a household like yours typically saves.",
    "spending_per_year": "I assumed about 80% of what you spend now, a common starting point.",
    "pay_per_year": "I took the typical pay for your job and state.",
    "partner_pay_per_year": "I took the typical pay for their job and state.",
    "mortgage_payment": "It is a typical monthly payment for your state.",
}
LABEL = {"social_security_per_year": "your household Social Security", "spending_now_per_year": "your spending now",
         "spending_per_year": "your spending in retirement", "pay_per_year": "your pay", "partner_pay_per_year": "your partner's pay",
         "mortgage_payment": "your mortgage payment"}
WAY_OFF = re.compile(
    r"(\$?\s*\d[\d,]*(?:\.\d+)?\s*(?:k\b|grand\b|thousand\b|million\b|m\b)?)\s*(?:a year|a month|total|in savings|saved)?(?:\s+(?:spending|pay|income|savings|payment|number|figure|amount|estimate|guess|costs?)){0,3}(?:\s+you\s+(?:put|guessed|assumed|used|wrote)(?:\s+(?:in|for|as)\s+(?:the\s+)?[\w-]+(?:\s+[\w-]+)?)?)?\s*,?\s*"
    r"(?:is|are|was|'s)\s+(?:way|far|totally|completely|much|so|just)?\s*(?:off\b|wrong\b|incorrect\b|too (?:low|high|much|little|small|big)\b|not (?:right|correct|close)\b|way\b)", re.I)
RANGE = re.compile(r"\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(k\b|grand\b|thousand\b|m\b|million\b)?\s*(?:to|-|–|—|and)\s*\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(k\b|grand\b|thousand\b|m\b|million\b)?", re.I)
RANGE_FACT = {"pay_per_year": "pay_per_year", "partner_pay_per_year": "partner_pay_per_year", "savings": "savings.total",
              "spending_now_per_year": "spending_now_per_year", "spending_per_year": "spending_per_year"}
NOTE_KEY = {"pay_per_year": "pay_per_year", "partner_pay_per_year": "partner_pay_per_year", "savings.total": "savings",
            "spending_now_per_year": "spending_now_per_year", "spending_per_year": "spending_per_year"}
PAY_BUCKETS = {"under $50k": "$40,000", "over $200k": "$250,000"}
CHILD_CHIPS = {"under 5": 3, "5 to 12": 9, "teenagers": 15, "grown up": 24, "grown": 24}
PARTNER_AGE_Q = re.compile(r"\b(?:husband|wife|spouse|partner|boyfriend|girlfriend|fianc[eé]e?)(?:'s)?\b[^.?!]{0,40}\bage\b|\bage\b[^.?!]{0,40}\b(?:husband|wife|spouse|partner|boyfriend|girlfriend|fianc[eé]e?)\b", re.I)
GONE = re.compile(r"\b(?:passed|died|dead|late|widow\w*|gone|lost)\b", re.I)


def _val(num: str, unit: str | None) -> float:
    return float(num.replace(",", "")) * (MORE[unit.lower()] if unit else 1.0)


def figures(text: str) -> list[float]:
    out = []
    for m in FIG.finditer(text or ""):
        try:
            out.append(_val(m.group(1), m.group(2)))
        except ValueError:
            continue
    return out


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(1.0, 0.01 * abs(b))


@dataclass
class Prep:
    said: str
    quoted: list[float] = field(default_factory=list)       # figures of the app's own that a complaint points at
    explain: str = ""
    rejected: list[float] = field(default_factory=list)     # "$50k is way off"
    reject_bit: str = ""
    bare: bool = False
    partner_note: str = ""
    accept: set[str] = field(default_factory=set)           # doubtful figures the person just confirmed


ACCOUNT_WORD = re.compile(r"pre-?tax|\broth\b|taxable|\bcash\b|401|\bira\b|brokerage|in (?:the )?bank", re.I)


def _own_values(p: Profile) -> list[float]:
    out = []
    for k in ("pay_per_year", "partner_pay_per_year", "spending_now_per_year", "spending_per_year", "social_security_per_year"):
        v = getattr(p, k, None)
        if v and p.sources.get(k) == "you said":
            out.append(float(v))
    return out


def _app_candidates(full0: Profile) -> list[tuple[float, str]]:
    out = []
    for k in ("social_security_per_year", "spending_now_per_year", "spending_per_year", "pay_per_year", "partner_pay_per_year"):
        v = getattr(full0, k, None)
        if isinstance(v, (int, float)) and v and full0.sources.get(k) != "you said":
            out.append((float(v), k))
    if full0.home.mortgage_payment and full0.notes.get("mortgage_payment_said") != "yes":
        out.append((float(full0.home.mortgage_payment), "mortgage_payment"))
    return out


REST_ZERO = re.compile(r"rest (?:is |are |to )?(?:zero|0|nothing)|no roth at all|nothing else|everything else is (?:zero|0)", re.I)
NOT_FIG = re.compile(r"[,;]?\s*(?:and\s+)?not\s+(?:the\s+|a\s+|an\s+)?\$?\s*\d[\d,]*(?:\.\d+)?\s*(?:k\b|grand\b|thousand\b|m\b|million\b)?(?:\s+(?:you|that|which)\s+(?:guessed|assumed|put|used|said|wrote))?", re.I)


def prepare(clean: str, said: str, p: Profile, asking: str | None, full0: Profile, app_texts: list[str]) -> Prep:
    prep = Prep(said=NOT_FIG.sub(" ", said or ""), bare=bool(asking) and bool(BARE.match(clean or "")))
    # a figure the person points at ("where did $33,600 come from?") is the app's, not a statement of theirs
    if COMPLAINT.search(clean or ""):
        cands = _app_candidates(full0)
        shown = [v for t in app_texts for v in figures(t) if v >= 100]
        own = _own_values(p)
        for m in FIG.finditer(clean or ""):
            try:
                v = _val(m.group(1), m.group(2))
            except ValueError:
                continue
            hit = next((c for c in cands if _close(v, c[0])), None)
            near = (clean[max(0, m.start() - 20):m.start()] + " " + clean[m.end():m.end() + 25]).lower()
            states_account = bool(ACCOUNT_WORD.search(near))      # "the $150,000 is pre-tax $130k": the person's own figures
            if hit or (v >= 100 and any(_close(v, x) for x in shown) and not any(_close(v, y) for y in own) and not states_account):
                prep.quoted.append(v)
                if prep.explain:
                    continue
                if hit:
                    k = hit[1]
                    prep.explain = (f"That ${v:,.0f} is my estimate of {LABEL[k]}, not something you told me. {SOURCE[k]} "
                                    "It is marked as an estimate in the panel. Tell me the right figure and I will use it.")
                else:
                    prep.explain = (f"That ${v:,.0f} came from me, not from you: it is a typical figure, marked in the panel. "
                                    "Tell me the right figure and I will use it.")
        if prep.quoted:
            prep.said = FIG.sub(lambda m: "that figure" if any(_close(_val(m.group(1), m.group(2)), q) for q in prep.quoted) else m.group(0), prep.said)
    # "$50k is way off": a rejection of that figure, not a figure
    for m in list(WAY_OFF.finditer(prep.said)):
        fm = FIG.search(m.group(1))
        if fm:
            prep.rejected.append(_val(fm.group(1), fm.group(2)))
            prep.said = prep.said.replace(m.group(0), " that figure is off ")
    if prep.rejected:
        prep.reject_bit = f"Understood: ${prep.rejected[0]:,.0f} is not right. What should it be? You can also take a typical figure."
    if PARTNER_AGE_Q.search(clean or "") and not p.has_partner and not p.partner_age:
        word = re.search(r"\b(husband|wife|spouse|partner|boyfriend|girlfriend|fianc[eé]e?)\b", clean or "", re.I)   # their own word
        prep.partner_note = (f"I am sorry about your {word.group(1).lower() if word else 'partner'}. " if GONE.search(clean or "") else "") + \
            "I plan for you on your own, so only your age counts. If that is wrong, tell me about your partner and their age."
    return prep


def drop_quoted(facts: dict[str, Any], quoted: list[float]) -> None:
    """After a complaint or a rejection, no fact may carry the quoted figure."""
    for k, v in list(facts.items()):
        if isinstance(v, (int, float)) and not isinstance(v, bool) and any(_close(float(v), q) for q in quoted):
            facts.pop(k)
        elif k == "debts" and isinstance(v, list) and v:
            facts[k] = [d for d in v if not any(_close(float(d.get("balance") or 0), q) for q in quoted)]
            if not facts[k]:
                facts.pop(k)


def range_midpoint(clean: str, asking: str | None, facts: dict[str, Any]) -> tuple[str, float, str] | None:
    """A range typed or clicked for a money question: stored at the middle, and the reply says so."""
    low = (clean or "").lower().strip(" .!")
    key = RANGE_FACT.get(asking or "")
    if not key:
        return None
    if asking in ("pay_per_year", "partner_pay_per_year") and low in PAY_BUCKETS:
        return key, float(facts.get(asking) or 0), f"I used {PAY_BUCKETS[low]} for \"{low}\". It is a guess; give your real figure any time."
    m = RANGE.search(clean or "")
    if not m:
        return None
    a_unit, b_unit = m.group(2), m.group(4)
    a, b = float(m.group(1).replace(",", "")), float(m.group(3).replace(",", ""))
    a = a * MORE[a_unit.lower()] if a_unit else (a * MORE[b_unit.lower()] if b_unit and a < 1000 else a)
    b = b * MORE[b_unit.lower()] if b_unit else b
    if a < 1000 or b <= a or b > 2e8:
        return None
    mid = round((a + b) / 2, -2)
    if asking == "spending_now_per_year" and re.search(r"month|\bmo\b", low):
        mid *= 12
    return key, mid, f"I used the middle of that range, ${mid:,.0f}{'' if asking == 'savings' else ' a year'}. It is a guess; give your real figure any time."


def children_list(clean: str, asking: str | None) -> dict[str, Any]:
    """'11, 9, 6' (or '11 9 6 k') for the children question: every age, and that many children."""
    if asking not in ("children", "children_count"):
        return {}
    lead = re.match(r"\s*(\d{1,2})\s*(?:kids?|children)\b[,:\s]+(.*)$", clean or "", re.I)
    if lead:        # "3 children 11 9 6": the first figure is the count, the rest are the ages
        rest = re.sub(r"\b(?:k|kids?|children|years?(?: old)?|yrs?|and)\b|[,;&/]", " ", lead.group(2), flags=re.I).split()
        if rest and all(re.fullmatch(r"\d{1,2}", x) and 0 <= int(x) <= 25 for x in rest) and len(rest) == int(lead.group(1)):
            return {"children.ages": [int(x) for x in rest], "children.count": len(rest)}
    t = re.sub(r"\b(?:k|kids?|children|years?(?: old)?|yrs?)\b", " ", clean or "", flags=re.I)
    t = re.sub(r"\band\b|[,;&/]", " ", t, flags=re.I)
    toks = t.split()
    if len(toks) >= 2 and all(re.fullmatch(r"\d{1,2}", x) and 0 <= int(x) <= 25 for x in toks):
        ages = [int(x) for x in toks]
        return {"children.ages": ages, "children.count": len(ages)}
    return {}


def student_loan_guard(facts: dict[str, Any], text: str) -> None:
    """'$8,000 saved and student loans': the $8,000 is savings; the loan has no amount yet, so ask for it."""
    debts = facts.get("debts")
    if not debts or not isinstance(debts, list):
        return
    keep, kind_only = [], None
    for d in debts:
        bal = float(d.get("balance") or 0)
        ok = False
        for m in FIG.finditer(text or ""):
            try:
                v = _val(m.group(1), m.group(2))
            except ValueError:
                continue
            if not _close(v, bal):
                continue
            around = (text[max(0, m.start() - 35): m.start()] + " | " + text[m.end(): m.end() + 35]).lower()
            after = text[m.end(): m.end() + 18].lower()
            if re.search(r"\b(?:saved|savings|in the bank|in cash|put away|401|ira)\b", after):
                continue
            if re.search(r"loan|debt|owe|card|balance|borrow|left on|bills?\b|medical|hospital|financ|visa|mastercard|amex|payday|line of credit|heloc|\bnote\b|\bleft\b", around):
                ok = True
                break
        if ok:
            keep.append(d)
        elif kind_only is None:
            kind_only = d.get("kind")
    if keep:
        facts["debts"] = keep
    else:
        facts.pop("debts")
        if kind_only:
            facts["debt_kind_only"] = kind_only


def sanity(facts: dict[str, Any], hh_pay: float, accept: set[str]) -> list[tuple[str, float, str]]:
    """Figures that are possible but doubtful: (key, value, why). Ask before storing."""
    out = []
    mp = facts.get("home.mortgage_payment")
    if isinstance(mp, (int, float)) and mp and "home.mortgage_payment" not in accept:
        if mp > 10000:
            out.append(("home.mortgage_payment", float(mp), "is far more than a usual mortgage payment"))
        elif hh_pay > 0 and mp > 0.6 * hh_pay / 12:
            out.append(("home.mortgage_payment", float(mp), "is over 60% of your monthly pay"))
    return out


def too_small(facts: dict[str, Any], bare: bool) -> list[tuple[str, str, float]]:
    """(key, label, value) for a figure too small to be that kind of figure ($62 as a mortgage payment)."""
    out = []
    mp = facts.get("home.mortgage_payment")
    if isinstance(mp, (int, float)) and 0 < mp < 100:
        out.append(("home.mortgage_payment", "a mortgage payment", float(mp)))
    for k, lbl in (("pay_per_year", "a year's pay"), ("partner_pay_per_year", "your partner's yearly pay")):
        v = facts.get(k)       # "$45" as a year's pay is an hourly rate or a slip, never a salary
        if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v < 1000:
            out.append((k, lbl, float(v)))
    return out


# ------------------------------------------------------------------ answers to questions asked along the way
USE_Q = re.compile(
    r"what (?:does|do|will|would) (?:the |my |this |that )?(?:\w+ )?(?:number|figure|answer|savings|pay|info|information)\b[^.?!]*\b(?:do|mean|change|used? for)\b|"
    r"what the plan (?:does|do) with|before it'?s? (?:used|goes?|is used|gets? used|goes? in|goes? anywhere)|see (?:it|the (?:number|figure)s?|them) (?:first|before)|"
    r"do i (?:get to )?see\b|whether i (?:get to )?see|what is it used for|what'?s it for", re.I)
PRIVACY_Q = re.compile(r"who (?:sees|can see|gets|reads)|my data|privacy|private|stored?|share my|sell my|keep my", re.I)
FIND_Q = re.compile(r"where (?:do|can|would) i (?:find|look up|get|see)|how (?:do|can) i (?:find|look up|get)", re.I)
FIND_ANSWER = ("Look for your latest statement from the company that holds the account, or log in to your employer's benefits site. "
               "A rough total is enough. If you cannot find it, type skip and I will use a typical figure, marked so you can change it.")
PRIVACY_SHORT = "I covered that above. Your answers stay in this browser tab, and an AI model reads each message."
SEE_FIRST = "You see every figure in the panel, and can change it, before the plan is built."


def shape_answer(text: str, clean: str, asking: str | None, priv_seen: bool) -> str:
    """One short answer to 'what does this number do?'; the privacy paragraph at most once a session."""
    if text and USE_Q.search(clean or "") and not PRIVACY_Q.search(clean or "") and asking in answers.WHY:
        return f"{answers.WHY[asking]} {SEE_FIRST}"
    if text and FIND_Q.search(clean or "") and asking in ("savings", "savings_split"):
        return FIND_ANSWER
    if text.startswith(answers.PRIVACY[:60]) and priv_seen:
        return PRIVACY_SHORT + text[len(answers.PRIVACY):]
    return text


def used_privacy(reply: str) -> bool:
    return answers.PRIVACY[:60] in (reply or "")
