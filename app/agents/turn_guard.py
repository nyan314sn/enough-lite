"""The guard: checks in code on what the model read from a message. No model calls here.

- Every figure must be backed by its evidence_quote, and the quote must be in the message. A figure may also be a sum of
  quoted figures (four accounts and their total) or a month-to-year conversion.
- Digits inside 401(k), 403(b), 457(b) and 529 are never amounts.
- "Retire at 65" is the retirement age, never the person's age.
- Types and ranges are checked; a figure that looks off is not stored and the person is asked what they meant.
- The rule parser's facts are a cross-check: where both agree, the fact is applied; where they disagree, the reading whose
  evidence fits the field wins, or one short confirm question is asked.
"""
from __future__ import annotations

import itertools
from datetime import date
import re
from dataclasses import dataclass, field
from typing import Any

from ..schemas import Profile
from . import intake_support as sup
from . import parser, parser_extra

# ------------------------------------------------------------------ figures in a quote
SMALL = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
                                     "sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
DIGITS = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k\b|grand\b|thousand\b|mm\b|m\b|mil\b|million\b)?", re.I)
DMULT = {"k": 1e3, "grand": 1e3, "thousand": 1e3, "m": 1e6, "mm": 1e6, "mil": 1e6, "million": 1e6}


def _word_numbers(text: str) -> list[float]:
    """'sixty five thousand' -> 65000, 'fourteen thousand' -> 14000, 'two' -> 2, 'a hundred and twenty thousand' -> 120000."""
    toks = re.findall(r"[a-z]+", text.lower().replace("-", " "))
    out: list[float] = []
    total, cur, live = 0.0, 0.0, False
    for i, t in enumerate(toks + ["."]):
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        if t in SMALL:
            cur += SMALL[t]
            live = True
        elif t in TENS:
            cur += TENS[t]
            live = True
        elif t in ("a", "one") and nxt in ("hundred", "thousand", "million") and not live:
            cur, live = 1.0, True
        elif t == "hundred" and live:
            cur = (cur or 1) * 100
        elif t in ("thousand", "grand") and live:
            total += (cur or 1) * 1000
            cur = 0.0
        elif t == "million" and live:
            total += (cur or 1) * 1e6
            cur = 0.0
        elif t == "and" and live and nxt in SMALL | TENS:
            continue
        else:
            if live:
                out.append(total + cur)
            total, cur, live = 0.0, 0.0, False
    return out


def quote_numbers(quote: str) -> list[float]:
    """Every figure in a quote, digits or words. 401(k), 403(b), 457(b) and 529 are names, not figures."""
    q = parser_extra.PRODUCT_NUM.sub(" ", quote or "")
    q = re.sub(r"\b(?:401|403|457)\s*\(?\s*[kb]\s*\)?", " ", q, flags=re.I)
    out: list[float] = []
    for m in DIGITS.finditer(q):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if m.group(2):
            v *= DMULT[m.group(2).lower()]
        out.append(v)
    out += _word_numbers(q)
    for pat, v in FRACTION_WORDS:
        if pat.search(q):
            out.append(v)
    return out


FRACTION_WORDS = [(re.compile(r"\bhalf (?:a |of a )?mil(?:lion)?\b", re.I), 500000.0),
                  (re.compile(r"\bthree quarters? (?:of )?(?:a )?mil(?:lion)?\b", re.I), 750000.0),
                  (re.compile(r"(?<!three )\b(?:a )?quarter (?:of )?(?:a )?mil(?:lion)?\b", re.I), 250000.0),
                  (re.compile(r"\b(?:a|one) mil(?:lion)?\b", re.I), 1000000.0)]


ASKING_SENTENCE = re.compile(r"^\s*(?:and\s+|but\s+|so\s+|also\s+|wait,?\s+)?(?:why|where|what|how|who|when|is|are|do|does|did|can|could|should|would|will)\b"
                             r"|\bwhy\b|\bwhere did\b|\bwhere does\b|\bwhere do\b", re.I)


def question_sentences(message: str) -> list[str]:
    """Sentences that ask something ("Why are you using $108,000?"): figures in them are quoted back, not stated."""
    return [s for s in re.split(r"(?<=[.?!])\s+", message or "")[:400] if s.strip().endswith("?") and ASKING_SENTENCE.search(s)
            and not re.search(r"\b(?:change|fix|update|set|correct|use|make it|put|switch)\b", s, re.I)]


def statements(message: str) -> str:
    """The message without its question sentences, for the rule parser."""
    qs = set(question_sentences(message))
    kept = [s for s in re.split(r"(?<=[.?!])\s+", message or "") if s not in qs]
    return " ".join(kept) if kept else ""


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9$.%]+", " ", (s or "").lower()).strip(" .")


def in_message(quote: str, message: str) -> bool:
    q = _norm(quote)
    return bool(q) and q in _norm(message)


# ------------------------------------------------------------------ fields
PER_YEAR = {"pay_per_year", "partner_pay_per_year", "household_pay", "spending_now_per_year", "spending_per_year", "social_security_per_year",
            "pension.you", "pension.partner"}
PER_MONTH = {"home.mortgage_payment", "home.rent"}
BALANCES = {"savings.total", "savings.pretax", "savings.roth", "savings.taxable", "savings.cash", "home.value", "home.mortgage_balance",
            "debts.student", "debts.car", "debts.credit_card", "debts.other"}
MONEY = PER_YEAR | PER_MONTH | BALANCES
AGES = {"age", "partner_age", "retire_age", "partner_retire_age"}
LATER_WORDS = re.compile(r"retir|later|after (?:we|i) stop|once (?:we|i)|when (?:we|i) stop|old age|golden years|down the road", re.I)
BORN_YEAR = re.compile(r"\bborn\b[^.;]{0,20}?\b(19[2-9]\d|200\d)\b|\b(?:birth ?year|year of birth)\b[^.;]{0,10}?\b(19[2-9]\d|200\d)\b", re.I)
BOOLS = {"has_partner", "retired", "home.owns", "home.has_mortgage", "debts.none", "pension.none"}
CHOICE_WORDS = {
    "risk": {"low": "careful", "conservative": "careful", "cautious": "careful", "safe": "careful", "low risk": "careful",
             "risk averse": "careful", "risk-averse": "careful", "moderate": "balanced", "medium": "balanced", "middle": "balanced", "middle of the road": "balanced", "some risk": "balanced",
             "average": "balanced", "mid": "balanced", "high": "growth", "aggressive": "growth", "high risk": "growth", "bold": "growth", "comfortable with ups and downs": "growth", "high tolerance": "growth",
             "risk tolerant": "growth", "risk-tolerant": "growth", "very conservative": "careful", "low tolerance": "careful"},
    "health": {"great": "excellent", "very good": "excellent", "fine": "good", "decent": "good", "ok": "fair", "okay": "fair",
               "so-so": "fair", "so so": "fair", "average": "fair", "not great": "fair", "bad": "poor", "not good": "poor", "terrible": "poor", "healthy": "good", "some health issues": "fair",
               "health issues": "fair", "chronic condition": "fair", "serious illness": "poor"},
}
CHOICE_WORDS["partner_health"] = CHOICE_WORDS["health"]
CHOICES = {"risk": ("careful", "balanced", "growth"), "sex": ("male", "female"), "partner_sex": ("male", "female"), "health": ("excellent", "good", "fair", "poor"),
           "partner_health": ("excellent", "good", "fair", "poor")}
RANGE = re.compile(r"(?:\bbetween\s+\$?(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|grand)?\s*(?:and|to|-|–)|\$?(?<![\d,.])(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|grand)?\s*(?:to|-|–))"
                   r"\s*\$?(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|grand)?", re.I)
NO_MONEY = re.compile(r"\b(?:no|none|nothing|zero|nada|paid off|don'?t have|do not have|haven'?t)\b|\$0\b", re.I)
NO_WORK = re.compile(r"stays? (?:at )?home|stay[- ]at[- ]home|at home|homemaker|housewife|house husband|not working|doesn'?t work|does not work|"
                     r"isn'?t working|unemployed|retired|between jobs|full[- ]time (?:mom|dad|parent)", re.I)
RETIRE_WORDS = re.compile(r"retir|stop(?:ping)? work|leave work|quit|stop at|done working|work until|out at|hang it up|call it quits|be done|"
                          r"wrap (?:it )?up|leave the workforce|clock out|out of work|out by|work till|work til\b|hang up|hang it up|"
                          r"pack it in|step away|step down|leave my job|stop my job|last day|finish work|done by", re.I)
# words that show a quote is about a field (used when two readings disagree)
FITS = {
    "pay_per_year": r"pay|salary|make|earn|income|paid|wage|\bgross\b",
    "partner_pay_per_year": r"pay|salary|make|earn|income|paid|wage",
    "household_pay": r"together|combined|household|between us|we make|we earn",
    "savings": r"sav|401|403|457|ira|roth|brokerage|cash|check|bank|invest|stock|pre-?tax|total|account|tsp|nest egg|put away|retirement",
    "home.mortgage_balance": r"mortgage|owe|left|balance|loan",
    "home.mortgage_payment": r"payment|month|mortgage|/mo",
    "home.rent": r"rent|lease",
    "home.value": r"worth|value|valued|house|home",
    "spending_now_per_year": r"spend|budget|live on|expenses|costs|bills|go through",
    "spending_per_year": r"spend|budget|live on|expenses|costs|retire",
    "retire_age": r"retir|stop|leave|quit|work",
    "age": r"\bi'?m\b|\bam\b|\bage\b|\bold\b|\bturn",
    "social_security_per_year": r"social security|\bss\b|benefit",
}


@dataclass
class GuardResult:
    facts: dict[str, Any] = field(default_factory=dict)        # in the rule parser's key format, ready for intake.apply
    evidence: dict[str, str] = field(default_factory=dict)     # fact key -> quote
    rejected: list[tuple[str, Any, str]] = field(default_factory=list)   # (field_path, value, why)
    looks_off: list[tuple[str, str, Any, Any]] = field(default_factory=list)   # (key, label, value, suggestion)
    corrections: set[str] = field(default_factory=set)         # fact keys the person marked as corrections
    breakdown_note: str = ""                                   # "your four accounts add to $267,000"
    conflict: tuple[str, Any, Any] | None = None               # (key, model value, rule value): ask which


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(1.0, 0.005 * abs(b))


def money_supported(value: float, quote: str, allow_sum: bool = True) -> bool:
    nums = quote_numbers(quote)
    base = list(dict.fromkeys(nums + [n * 1000 for n in nums if 0 < n < 5000]))
    cands = set()
    for n in base:
        cands |= {n, n * 12, n / 12}
    if any(_close(value, c) for c in cands):
        return True
    if allow_sum and 2 <= len(nums) <= 10:
        pool = [n for n in base if n >= 100][:10]
        for r in range(2, min(len(pool), 6) + 1):
            for combo in itertools.combinations(pool, r):
                s = sum(combo)
                if _close(value, s) or _close(value, s * 12):
                    return True
    return False


def count_supported(value: int, quote: str) -> bool:
    q = re.sub(r"\b(?:was|as|like|were)\s+an?\s+(?:kid|child|boy|girl)\b", " ", quote.lower())     # "since I was a kid"
    nums = quote_numbers(q)
    if any(_close(value, n) for n in nums):
        return True
    if value == 0 and re.search(r"\bno\b|\bnone\b|\bzero\b|don'?t have|childless|without", q):
        return True
    if value == 1 and re.search(r"\b(?:a|an|my|our|one|only)\s+(?:\w+\s+)?(?:son|daughter|kid|child|boy|girl|dog|cat|puppy)\b", q):
        return True
    if value == 2 and re.search(r"\btwins\b|\bboth\b|\bcouple of\b", q):
        return True
    ages = [n for n in nums if n < 60]
    return len(ages) == value and value > 0


def _state_code(v: Any) -> str | None:
    if not isinstance(v, str):
        return None
    s = v.strip()
    if s.upper() in parser.CODES:
        return s.upper()
    return parser.STATES.get(s.lower()) or parser.CITIES.get(s.lower())


def fits(key: str, quote: str) -> bool:
    k = "savings" if key.startswith("savings.") else key
    pat = FITS.get(k)
    return bool(pat and re.search(pat, quote or "", re.I))


def check_updates(updates: list, message: str, p: Profile, asking: str | None = None) -> GuardResult:
    """Turn the model's updates into facts, keeping only what the message backs up."""
    g = GuardResult()
    vals: dict[str, Any] = {}
    quotes: dict[str, str] = {}
    corr: set[str] = set()
    bare = len(message.split()) <= 4
    asked_in = [_norm(qs) for qs in question_sentences(message)[:30]]
    nmsg = _norm(message)
    for u in updates or []:
        fp, v, unit = u.field_path, u.value, (u.unit or "text")
        quote = (u.evidence_quote or "").strip()
        if not quote and bare:
            quote = message
        nq = _norm(quote)
        if not nq or nq not in nmsg:
            g.rejected.append((fp, v, "quote not in the message"))
            continue
        if not bare and any(nq in qs for qs in asked_in):
            g.rejected.append((fp, v, "figure quoted in a question"))
            continue
        # an account label the words do not support: "an IRA" is not a Roth, and a Roth is not pre-tax
        if fp == "savings.roth" and not re.search(r"roth", quote, re.I) and re.search(r"401|403|457|\bira\b|\btsp\b|pre-?tax|traditional", quote, re.I):
            fp = "savings.pretax"
        elif fp == "savings.pretax" and re.search(r"\broth\b", quote, re.I) and not re.search(r"pre-?tax|traditional", quote, re.I):
            fp = "savings.roth"
        # retire versus age
        if fp == "age" and RETIRE_WORDS.search(quote):
            fp = "retire_age"
        if fp == "spending_per_year" and not LATER_WORDS.search(quote) \
                and asking not in ("spending_per_year", "spending_later", "confirm_spending_later"):
            fp = "spending_now_per_year"     # "we need 5 grand a month to live": spending now, unless they speak of later
        if fp == "retire_age" and not RETIRE_WORDS.search(quote) and asking not in ("retire_age", "partner_retire_age") and not bare:
            g.rejected.append((fp, v, "no retirement words in the quote"))
            continue
        if bare and asking and (fp in MONEY or fp in AGES) and asking != "more" and not fits(fp, quote) and not fits(fp, message) \
                and not sup._owns(fp, sup.own_keys(asking) or ()):
            # "no, make it 65" at the children question: a bare figure for some other field is not guessed at
            g.rejected.append((fp, v, "bare figure for a field other than the pending question"))
            continue
        if fp.startswith("debts.") and fp != "debts.none" and asking in ("mortgage", "home") \
                and not re.search(r"student|car\b|auto|card|medical|personal|other|besides|also", quote, re.I):
            fp = "home.mortgage_balance"     # "I owe about 70k" at the mortgage question is the mortgage
        if fp in MONEY:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                g.rejected.append((fp, v, "not a number"))
                continue
            v = float(v)
            if fp in ("home.rent", "home.mortgage_payment") and parser.INCLUDING.search(quote):
                g.rejected.append((fp, v, "a total that includes the rent, not the rent"))
                continue
            zero_ok = v == 0 and (NO_MONEY.search(quote) or (fp in ("pay_per_year", "partner_pay_per_year") and NO_WORK.search(quote)))
            hm = parser.HOURLY.search(quote) if fp in ("pay_per_year", "partner_pay_per_year", "household_pay") else None
            if hm:
                # "$45 an hour": a year's pay, worked out here (full time 2,080 hours, part time 1,040), whatever the model sent
                v = float((hm.group(1) or hm.group(2)).replace(",", "")) * (1040 if parser.PART_TIME.search(message) else 2080)
            elif not zero_ok and not money_supported(v, quote, allow_sum=True):
                g.rejected.append((fp, v, "figure not in the quote"))
                continue
            rng = RANGE.search(quote)
            if rng and fp in MONEY:
                a_num, a_unit = (rng.group(1), rng.group(2)) if rng.group(1) else (rng.group(3), rng.group(4))
                mult = DMULT.get((rng.group(6) or a_unit or "").lower(), 1)
                lo, hi = float(a_num.replace(",", "")) * mult, float(rng.group(5).replace(",", "")) * mult
                for scale in (1, 12):
                    if hi > lo > 0 and (_close(v, hi * scale) or _close(v, lo * scale)):
                        v = (lo + hi) / 2 * scale    # "between 6 and 7 thousand a month": the middle, said out loud
                        g.breakdown_note = (g.breakdown_note + " " if g.breakdown_note else "") + \
                            f"You gave a range, so I used the middle, ${v:,.0f}{' a year' if fp in PER_YEAR else ''}."
                        break
            month_words = re.search(r"month|/\s?mo\b|\bmo\b|monthly", _window(message, quote), re.I)
            if fp in PER_YEAR and (unit == "per_month" or (month_words and v < 20000)) and v < 100000:
                v *= 12
            elif fp in PER_MONTH and (unit == "per_year" or v >= 20000 and fp == "home.rent") and v >= 6000:
                v /= 12
            if fp == "home.mortgage_payment" and v >= 20000:
                v /= 12
        elif fp in AGES:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                g.rejected.append((fp, v, "not a number"))
                continue
            v = int(round(v))
            by = BORN_YEAR.search(quote) if fp in ("age", "partner_age") else None
            if by:
                v = date.today().year - int(by.group(1) or by.group(2))       # the birthday may not have come yet: within a year either way
            elif not any(_close(v, n) for n in quote_numbers(quote)):
                g.rejected.append((fp, v, "age not in the quote"))
                continue
        elif fp in ("children.count", "pets.dogs", "pets.cats"):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                g.rejected.append((fp, v, "not a number"))
                continue
            v = int(round(v))
            if not 0 <= v <= (15 if fp == "children.count" else 10):
                g.looks_off.append((fp, "the number of children" if fp == "children.count" else "the number of pets", v, None))
                continue
            if not count_supported(v, quote):
                g.rejected.append((fp, v, "count not in the quote"))
                continue
        elif fp == "children.ages":
            if not isinstance(v, list) or not all(isinstance(a, (int, float)) and not isinstance(a, bool) for a in v) or not v or len(v) > 15:
                g.rejected.append((fp, v, "not a list of ages"))
                continue
            nums = quote_numbers(quote)
            v = [int(round(a)) for a in v]
            if not all(any(_close(a, n) for n in nums) for a in v):
                g.rejected.append((fp, v, "ages not in the quote"))
                continue
        elif fp == "home.mortgage_rate":
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not any(_close(float(v), n) for n in quote_numbers(quote)):
                g.rejected.append((fp, v, "rate not in the quote"))
                continue
            v = float(v) / 100 if v > 1 else float(v)
        elif fp in BOOLS:
            if not isinstance(v, bool):
                if isinstance(v, str) and v.lower() in ("true", "yes", "false", "no"):
                    v = v.lower() in ("true", "yes")
                else:
                    g.rejected.append((fp, v, "not yes or no"))
                    continue
        elif fp == "state":
            code = _state_code(v)
            if not code or (parser.find_state(quote, asking_state=True) != code and parser.STATE_NAME.get(code, "").lower() not in quote.lower()):
                g.rejected.append((fp, v, "state not in the quote"))
                continue
            v = code
        elif fp in ("job", "partner_job"):
            if not isinstance(v, str) or not v.strip() or len(v) > 40 or len(v.split()) > 3 \
                    or not all(re.escape(w[:5]) in message.lower() or w in message.lower() for w in v.strip().lower().split()) \
                    or re.search(r"javascript|script|<|>|=|https?:|\bwww\.", v, re.I):
                g.rejected.append((fp, v, "job not in the message"))
                continue
            v = re.sub(r"[^a-z \-]", "", v.strip().lower())[:40]
        elif fp in CHOICES:
            if fp == "sex" and re.search(rf"\b{parser.PARTNER}\b|\bmarried to\b", quote, re.I) and not re.search(r"\bi(?:'m| am)\b", quote, re.I):
                fp = "partner_sex"          # "my spouse is male" is about the partner, not the person
            if fp in ("sex", "partner_sex") and isinstance(v, str) and re.search(r"non-?binary|non binary", quote, re.I):
                v = "unstated"              # the average of the two life tables
            elif isinstance(v, str) and v.strip().lower() in CHOICE_WORDS.get(fp, {}):
                v = CHOICE_WORDS[fp][v.strip().lower()]
            elif not isinstance(v, str) or v.lower() not in CHOICES[fp]:
                g.rejected.append((fp, v, "not an allowed choice"))
                continue
            v = v.lower()
        else:
            g.rejected.append((fp, v, "unknown field"))
            continue
        if fp.startswith("savings.") and fp != "savings.total" and fp in vals and quotes.get(fp) != quote and isinstance(v, float):
            v += vals[fp]            # two accounts of one kind named in different words ("401(k)s ... an IRA"): they add up
        vals[fp] = v
        quotes[fp] = quote
        if u.is_correction:
            corr.add(fp)
    _to_facts(vals, quotes, corr, p, asking, g, message)
    _range_checks(g, p)
    return g


def _window(message: str, quote: str) -> str:
    """The quote and a few words after it in the message (where 'a month' usually sits)."""
    m, q = message.lower(), quote.lower()
    i = m.find(q[:20]) if q else -1
    return message[i:i + len(q) + 30] if i >= 0 else quote


def _to_facts(vals: dict, quotes: dict, corr: set, p: Profile, asking: str | None, g: GuardResult, message: str = "") -> None:
    f = g.facts

    def put(key, v, src):
        f[key] = v
        g.evidence[key] = quotes.get(src, "")
        if src in corr:
            g.corrections.add(key)
    for k in ("age", "partner_age", "state", "job", "partner_job", "pay_per_year", "partner_pay_per_year", "household_pay", "retire_age",
              "partner_retire_age", "spending_now_per_year", "spending_per_year", "social_security_per_year", "risk", "sex", "partner_sex",
              "health", "partner_health", "has_partner"):
        if k in vals:
            put(k, vals[k], k)
    if vals.get("retired"):
        put("retired", True, "retired")
    if ("partner_pay_per_year" in vals or "partner_age" in vals) and not p.has_partner:
        f.setdefault("has_partner", True)
    # savings: the accounts win over a stated total; a total alone gets the usual assumed split
    parts = {k: vals[f"savings.{k}"] for k in ("pretax", "roth", "taxable", "cash") if f"savings.{k}" in vals}
    total = vals.get("savings.total")
    if total and parts and not sum(parts.values()):
        parts = {}                  # "zero Roth" with a stated total: the total is the figure
    if parts:
        s = sum(parts.values())
        if total is not None and not _close(total, s) and abs(total - s) > 0.02 * max(total, s):
            # the accounts as the words pair them ("$330,000 in 401(k)s ... $20,000 in an IRA"): when they add to the total, they are the
            # accounts, and no figure is left over to guess a home for
            for src in (" ".join(dict.fromkeys(v for k, v in quotes.items() if k.startswith("savings."))), message):
                pair = parser.parse_split(src) if src else {}
                if pair and _close(sum(pair.values()), total):
                    for k in ("pretax", "roth", "taxable", "cash"):
                        vals.pop(f"savings.{k}", None)
                    parts = {k.split(".", 1)[1]: v for k, v in pair.items()}
                    for k, v in parts.items():
                        vals[f"savings.{k}"] = v
                        quotes[f"savings.{k}"] = quotes.get("savings.total", "") or src
                    s = sum(parts.values())
                    break
        if total is not None and not _close(total, s) and abs(total - s) > 0.02 * max(total, s):
            free = [k for k in ("taxable", "cash", "roth", "pretax") if k not in parts]
            if "pretax" in free and re.search(r"401|403|457|\bira\b|pre-?tax|tsp", " ".join(quotes.values()), re.I):
                free = ["pretax"] + [k for k in free if k != "pretax"]
            if total > s > 0 and free:
                # "about $363k in all" but the accounts named add to $320k: keep their total, the rest in an account not named
                parts[free[0]] = total - s
                vals[f"savings.{free[0]}"] = total - s
                quotes[f"savings.{free[0]}"] = quotes.get("savings.total", "")
                name = {"taxable": "taxable investments", "cash": "cash", "roth": "Roth", "pretax": "pre-tax accounts"}[free[0]]
                g.breakdown_note = (f"The accounts you named add to ${s:,.0f}. You said ${total:,.0f} in all, so I put the other "
                                    f"${total - s:,.0f} in {name}. Tell me if it belongs elsewhere.")
            else:
                g.breakdown_note = f"Your accounts add to ${s:,.0f}, so I used that, not ${total:,.0f}."
        cur = p.savings
        s = sum(parts.values())
        corrected = any(f"savings.{k}" in corr for k in parts) or "savings.total" in corr
        partial = (len(parts) == 1 or (s < 0.9 * cur.total and not corrected and asking not in ("savings", "savings_split", "confirm_split")))
        if partial and total is None and p.savings_known and p.sources.get("savings") == "assumed" and cur.total > s:
            # some accounts against a stated total with an assumed split: keep the total, spread the rest over the other accounts
            k1 = next(iter(parts))
            rest = cur.total - s
            others = {k: getattr(cur, k) for k in ("pretax", "roth", "taxable", "cash") if k not in parts}
            osum = sum(others.values())
            if rest > 0 and others:
                for k, v in others.items():
                    share = (v / osum) if osum > 0 else (1.0 if k == next(iter(others)) else 0.0)
                    put(f"savings.{k}", round(rest * share, -2), f"savings.{k1}")
            for k, v in parts.items():
                put(f"savings.{k}", v, f"savings.{k}")
            f["savings.replace"] = True
        else:
            for k, v in parts.items():
                put(f"savings.{k}", v, f"savings.{k}")
            if len(parts) >= 2 or asking in ("savings", "savings_split") or not p.savings_known or p.sources.get("savings") == "assumed":
                f["savings.replace"] = True
    elif total is not None:
        put("savings.total", total, "savings.total")
    # home
    if "home.owns" in vals:
        put("home.owns", vals["home.owns"], "home.owns")
    renter = vals.get("home.owns") is False or "home.rent" in vals or bool(re.search(r"\brent(?:s|ing|ers?)?\b", quotes.get("home.has_mortgage", ""), re.I))
    if "home.has_mortgage" in vals and renter:
        f["home.owns"] = False              # "no mortgage, we rent": a renter, not an owner with no mortgage
    elif "home.has_mortgage" in vals:
        if vals["home.has_mortgage"]:
            put("home.has_mortgage", True, "home.has_mortgage")
            f["home.owns"] = True
        elif not vals.get("home.mortgage_balance"):
            put("home.mortgage_balance", 0.0, "home.has_mortgage")
            f["home.mortgage_payment"] = 0.0
            f["home.owns"] = True
    for k in ("home.value", "home.mortgage_balance", "home.mortgage_payment", "home.mortgage_rate"):
        if k in vals:
            put(k, vals[k], k)
            f.setdefault("home.owns", True)
    if "home.rent" in vals:
        put("home.rent", vals["home.rent"], "home.rent")
        f["home.owns"] = False
    # children
    if "children.ages" in vals:
        put("children.ages", vals["children.ages"], "children.ages")
    elif "children.count" in vals:
        put("children.count", vals["children.count"], "children.count")
    # pets
    if "pets.dogs" in vals or "pets.cats" in vals:
        pets = [x.model_dump() for x in p.pets if x.kind not in (("dog",) if "pets.dogs" in vals else ()) + (("cat",) if "pets.cats" in vals else ())]
        for kind in ("dog", "cat"):
            n = vals.get(f"pets.{kind}s")
            if n:
                pets.append({"kind": kind, "count": n})
        put("pets", pets, "pets.dogs" if "pets.dogs" in vals else "pets.cats")
    # debts
    debts = [{"kind": k, "balance": vals[f"debts.{k}"]} for k in ("student", "car", "credit_card", "other") if f"debts.{k}" in vals]
    if debts:
        put("debts", debts, next(f"debts.{d['kind']}" for d in debts))
    elif vals.get("debts.none"):
        put("debts", [], "debts.none")
    # pensions
    pens = [{"who": w, "per_year": vals[f"pension.{w}"]} for w in ("you", "partner") if f"pension.{w}" in vals]
    if pens:
        put("pensions", pens, next(f"pension.{x['who']}" for x in pens))
    elif vals.get("pension.none"):
        put("pensions", [], "pension.none")


LOOKS_OFF_LOW = {"pay_per_year": "your pay", "partner_pay_per_year": "your partner's pay", "household_pay": "your pay",
                 "spending_now_per_year": "your spending now", "spending_per_year": "your spending in retirement", "savings.total": "your savings"}


def _range_checks(g: GuardResult, p: Profile) -> None:
    f = g.facts
    for k, label in LOOKS_OFF_LOW.items():
        v = f.get(k)
        if isinstance(v, (int, float)) and k.startswith("spending") and v == 0:
            g.looks_off.append((k, label, v, None))       # nobody spends nothing: ask
            f.pop(k, None)
        elif isinstance(v, (int, float)) and 0 < v < 1000:
            g.looks_off.append((k, label, v, v * 1000))
            f.pop(k, None)
    bad = sup.implausible(f, p)
    for k, label, v in bad:
        g.looks_off.append((k, label, v, None))
    sup.drop_keys(f, bad)


def looks_off_reply(items: list[tuple[str, str, Any, Any]]) -> str:
    k, label, v, sugg = items[0]
    if k in ("children.count", "pets.dogs", "pets.cats"):
        return f"I read {label} as {v}, which looks off, so I have not stored it. How many is it?"
    shown =f"${v:,.0f}" if isinstance(v, (int, float)) and (v >= 1000 or k in LOOKS_OFF_LOW) else (f"{v:g}" if isinstance(v, (int, float)) else str(v))
    if sugg is not None:
        return f"I read {label} as {shown}, which looks off, so I have not stored it. Did you mean ${sugg:,.0f}?"
    return f"I read {label} as {shown}, which looks off, so I have not stored it. What did you mean?"


# ------------------------------------------------------------------ the rule parser as a cross-check
MARKERS = set(sup.MARKERS) | {"savings.replace", "savings.mix", "children.college", "children.college_type", "children.college_share", "children.college_each", "partner_sex"}
GROUPS = {"savings": ("savings.",), "children": ("children.count", "children.ages"), "pay": ("pay_per_year", "partner_pay_per_year", "household_pay")}


def _numeric_values(facts: dict) -> dict[str, float]:
    out = {}
    for k, v in facts.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = float(v)
    return out


def merge(rule: dict[str, Any], g: GuardResult, message: str = "") -> dict[str, Any]:
    """The model's checked facts, cross-checked against the rule parser's.

    Agree: apply. Only one reader: apply, unless the rule parser's figure is one the model put in another field (the model's
    evidence fits its field). Disagree on a figure: the reading whose evidence fits the field wins; when neither does, store
    neither and ask (g.conflict)."""
    ai = g.facts
    out: dict[str, Any] = {k: v for k, v in rule.items() if k in MARKERS}
    out.update(ai)
    # words that say it outright beat the model: "my spouse is a woman", "my partner passed away"
    if "partner_sex" in rule:
        out["partner_sex"] = rule["partner_sex"]
    if rule.get("has_partner") is False:
        out["has_partner"] = False
    ai_nums = _numeric_values(ai)
    ai_has_savings = any(k.startswith("savings.") for k in ai)
    off = {x[0] for x in g.looks_off} | {"pets" for x in g.looks_off if x[0].startswith("pets.")} \
        | {"children.count", "children.ages"} & {x[0] for x in g.looks_off}
    for k, v in rule.items():
        if k in off:
            continue                                  # a figure the checks found off is not let in by the other reader
        if k in MARKERS or k in ai:
            if k in ai and k not in MARKERS:
                rv, av = rule[k], ai[k]
                if isinstance(rv, (int, float)) and isinstance(av, (int, float)) and not isinstance(rv, bool) and not _close(float(av), float(rv)):
                    if k == "social_security_per_year" and rv > av and "social_security_parts" in rule:
                        out[k] = rv          # both partners' benefits, added: the household figure
                        continue
                    if not fits(k, g.evidence.get(k, "")) and k not in ("age", "partner_age", "retire_age") and g.conflict is None \
                            and not k.startswith("savings."):
                        g.conflict = (k, av, rv)
                        out.pop(k, None)
                elif k in ("debts", "pensions") and isinstance(rv, list) and isinstance(av, list):
                    out[k] = _merge_items(av, rv, "kind" if k == "debts" else "who")
            continue
        if k.startswith("savings.") and ai_has_savings:
            continue                                  # one reader for the accounts, so nothing is counted twice
        if k in GROUPS["children"] and any(x in ai for x in GROUPS["children"]):
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool) and k not in ("saving.match_rate", "saving.match_cap"):
            taken = [ak for ak, av in ai_nums.items() if ak != k and _close(av, float(v))]
            if taken:
                continue                              # the model put this figure in another field, with evidence
            if k == "age" and RETIRE_WORDS.search(message) and "retire_age" in ai and _close(float(ai["retire_age"]), float(v)):
                continue
        out[k] = v
    if "savings.replace" in out and not any(k.startswith("savings.") and k not in ("savings.replace", "savings.mix") for k in out):
        out.pop("savings.replace")
    return out


def _merge_items(ai: list[dict], rule: list[dict], key: str) -> list[dict]:
    """Model items, with the details only the rule parser read (rate, payment, start age) carried over."""
    by = {r.get(key): r for r in rule}
    out = []
    for a in ai:
        r = by.get(a.get(key), {})
        out.append({**{k: v for k, v in r.items() if v is not None}, **{k: v for k, v in a.items() if v is not None}})
    seen = {a.get(key) for a in ai}
    amounts = [a.get("balance", a.get("per_year")) for a in ai]
    for r in rule:
        amt = r.get("balance", r.get("per_year"))
        if r.get(key) not in seen and not any(isinstance(x, (int, float)) and isinstance(amt, (int, float)) and _close(x, amt) for x in amounts):
            out.append(r)
    return out
