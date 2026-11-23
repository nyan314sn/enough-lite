"""Rule parser for the start page: plain sentences -> profile facts. No model calls.

Ideas taken from the full app's backend/agents/introduce.py (number words, states, cities, job patterns), rewritten small.
Returns {key: value} for what the person said, using profile keys (savings.pretax etc. as dotted keys).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from ..tools import estimates
from . import parser_extra

NUMW = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "a": 1, "an": 1, "a couple of": 2, "a few": 3, "no": 0, "zero": 0, "twin": 2, "twins": 2}
DOG_BREEDS = r"beagle|labrador|golden retriever|retriever|poodle|\w*doodle|bulldog|terrier|chihuahua|husky|german shepherd|dachshund|corgi|rottweiler|shih tzu|pug|collie|spaniel|mutt|pit bull"
CAT_BREEDS = r"tabby|siamese|persian|maine coon|kitty|kitten"
NUMW_RE = r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|a couple of|a few|an|a|no|zero)"
STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "district of columbia": "DC", "washington dc": "DC", "washington d.c.": "DC", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington state": "WA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
CITIES = {"nyc": "NY", "new york city": "NY", "brooklyn": "NY", "manhattan": "NY", "boston": "MA", "chicago": "IL", "seattle": "WA",
          "los angeles": "CA", "san francisco": "CA", "san diego": "CA", "austin": "TX", "houston": "TX", "dallas": "TX", "denver": "CO",
          "atlanta": "GA", "miami": "FL", "phoenix": "AZ", "philadelphia": "PA", "pittsburgh": "PA", "new haven": "CT", "hartford": "CT",
          "stamford": "CT", "detroit": "MI", "minneapolis": "MN", "nashville": "TN", "charlotte": "NC", "las vegas": "NV",
          "baltimore": "MD", "cleveland": "OH", "columbus": "OH",
          # regions and nicknames people use instead of a state
          "bay area": "CA", "silicon valley": "CA", "socal": "CA", "norcal": "CA", "sacramento": "CA", "san jose": "CA", "oakland": "CA",
          "jersey": "NJ", "philly": "PA", "dfw": "TX", "san antonio": "TX", "twin cities": "MN", "new orleans": "LA", "nola": "LA",
          "st louis": "MO", "st. louis": "MO", "kansas city": "MO", "salt lake city": "UT", "orlando": "FL", "tampa": "FL",
          "jacksonville": "FL", "raleigh": "NC", "indianapolis": "IN", "milwaukee": "WI", "honolulu": "HI", "anchorage": "AK",
          "albuquerque": "NM", "boise": "ID", "long island": "NY", "queens": "NY", "the bronx": "NY",
          "buffalo": "NY", "cincinnati": "OH", "louisville": "KY", "memphis": "TN", "oklahoma city": "OK", "omaha": "NE",
          "des moines": "IA", "providence": "RI", "tucson": "AZ", "el paso": "TX", "fort worth": "TX"}
CODES = set(STATES.values())
STATE_NAME = {v: k.title() for k, v in STATES.items() if k not in ("washington dc", "washington d.c.", "washington state")}
STATE_NAME["DC"] = "the District of Columbia"

AMOUNT_RE = re.compile(r"(\$)?\s?(?<![\d,])(?<!\d\.)(\d[\d,]*(?:\.\d+)?)\s?(k|thousand|mm|m|million)?(?![\w%])", re.I)
MULT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mm": 1e6, "million": 1e6}
PARTNER = r"(?:wife|husband|partner|spouse|boyfriend|girlfriend|fianc[eé]e?)"
# the partner's sex, only for the life table; never guessed from the person's own sex or from the word "partner"
_SEX_OF = {"man": "male", "male": "male", "guy": "male", "woman": "female", "female": "female", "lady": "female",
           "nonbinary": "unstated", "non-binary": "unstated", "non binary": "unstated"}
_PARTNER_IS = re.compile(rf"\b{PARTNER}(?:\s+is|'s)\s+(?:actually\s+|really\s+|also\s+|in fact\s+)?(?:an?\s+)?"
                         r"(man|male|guy|woman|female|lady|non-?binary|non binary)\b"
                         r"|\bmarried to\s+(?:an?\s+)?(man|guy|woman|lady)\b", re.I)
_SEX_WORD = re.compile(r"\b(wife|husband|girlfriend|boyfriend)\b")
_WORD_SEX = {"wife": "female", "girlfriend": "female", "husband": "male", "boyfriend": "male"}


def partner_sex_said(low: str) -> str | None:
    """'my partner is actually a man' -> male; 'my husband, not wife' -> male; 'my partner is nonbinary' -> 'unstated' (the
    average of the two tables). None when the words say nothing about it."""
    m = _PARTNER_IS.search(low)
    if m:
        return _SEX_OF[(m.group(1) or m.group(2)).lower()]
    words = [w.group(1) for w in _SEX_WORD.finditer(low) if not re.search(r"\bnot\s+(?:an?\s+|my\s+)?$", low[:w.start()])]
    return _WORD_SEX[words[-1]] if words else None


def fix_typos(text: str) -> str:
    """Letter o typed for a zero: '4o yrs' -> '40 yrs', '6o' -> '60', '1oo k' -> '100 k'."""
    t = re.sub(r"\b(\d)([oO0]+)(?=\b|k\b|K\b)", lambda m: m.group(1) + "0" * len(m.group(2)), text or "")
    return fix_words(t)


_RETIRE_TYPO = re.compile(r"\b(?:retier|retiere|retrie|retirre|retie|reitre|retire?r?d?e?)\b", re.I)
_RETIREMENT_TYPO = re.compile(r"\b(?:retirment|retiement|retirmnet|retirement|retierment|retirmen|retiremnet)\b", re.I)


def fix_words(text: str) -> str:
    """Common slips for the one word the plan hangs on: 'retier' and 'retrie' are 'retire'; 'retirment' is 'retirement'."""
    def retire(m: "re.Match[str]") -> str:
        w = m.group(0)
        return w if w.lower() in ("retire", "retired", "retiree") else ("Retire" if w[:1].isupper() else "retire")
    t = _RETIRE_TYPO.sub(retire, text or "")
    return _RETIREMENT_TYPO.sub(lambda m: m.group(0) if m.group(0).lower() == "retirement" else "retirement", t)


CORRECTION = re.compile(r"\b(?:actually|i mean|make it|correction|sorry|scratch that|not \d+\s*,?\s*but)\s*,?\s*(?:it'?s\s+|its\s+|i'?m\s+|we'?re\s+)?"
                        r"(\$?\d[\d,]*(?:\.\d+)?\s*(?:k|thousand|m|million)?)\b", re.I)


def late_correction(text: str, out: dict[str, Any]) -> None:
    """'I'm 40... actually 45': the figure after 'actually' (or 'make it', 'I mean') replaces the one it corrects."""
    m = None
    for m in CORRECTION.finditer(text):
        pass
    if not m:
        return
    raw = m.group(1).lower().replace("$", "").replace(",", "").strip()
    mult = 1e6 if raw.endswith(("m", "million")) else 1e3 if raw.endswith(("k", "thousand")) else 1
    try:
        v = float(re.sub(r"[a-z ]+$", "", raw)) * mult
    except ValueError:
        return
    small = v < 120
    keys = [k for k, x in out.items() if isinstance(x, (int, float)) and not isinstance(x, bool) and k not in ("children.count",)
            and ((x < 120) == small) and x != v]
    if small:
        keys = [k for k in keys if k in ("age", "partner_age", "retire_age", "partner_retire_age")]
    if len(keys) == 1:
        out[keys[0]] = int(v) if small else v


def num(word: str) -> int | None:
    w = word.lower().strip()
    return int(w) if w.isdigit() else NUMW.get(w)


MAX_AMOUNTS = 60    # figures read from one message; more would only slow the parser (each is matched against its clause)


def amounts(text: str, floor: float = 1000.0) -> list[tuple[float, int, int]]:
    out = []
    for m in AMOUNT_RE.finditer(text):
        if len(out) >= MAX_AMOUNTS:
            break
        if parser_extra.is_product(text, m.start(2)):      # 401(k), 403(b): a product name, not an amount
            continue
        try:
            v = float(m.group(2).replace(",", ""))
        except ValueError:
            continue
        if m.group(3):
            v *= MULT[m.group(3).lower()]
        if m.group(1) or m.group(3) or v >= floor:
            tail = text[m.end(): m.end() + 25].lower()
            if re.match(r"\s*(?:a|per|each|/|every)\s*(?:month|mo)\b", tail) or re.match(r"\s*monthly", tail):
                v *= 12
            out.append((v, m.start(), m.end()))
    return out


# two-letter codes that are also ordinary words: only ever read in capitals
AMBIGUOUS_CODES = frozenset({"al", "co", "de", "hi", "id", "in", "la", "ma", "me", "mo", "ms", "ne", "oh", "ok", "or", "pa"})
BARE_WORD_CODES = frozenset({"OK", "HI", "ME", "IN", "OR", "OH", "AL", "DE", "ID", "MA", "LA", "PA", "CO", "NE", "MO", "MS"})
LOCATED_CODE = re.compile(r"(?:\b(?:in|from|to)|,)\s+([A-Za-z]{2})\b(?![-'\w])")


def find_state(text: str, asking_state: bool = False) -> str | None:
    """A state from its name, a city, or a code. A code counts only in capitals, or in a place context ('in HI', 'from ny',
    'move to tx'), or as the answer to the state question. Greetings and the words hi, ok, me, in and or never count."""
    low = text.lower()
    for name in sorted(CITIES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", low):
            return CITIES[name]
    for name in sorted(STATES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", low):
            if name == "washington" and re.search(r"\bwashington\s+(?:dc|d\.c\.)", low):
                return "DC"
            return STATES[name]
    for m in LOCATED_CODE.finditer(text):
        w = m.group(1)
        if w.upper() in CODES and (w.isupper() or w.lower() not in AMBIGUOUS_CODES):
            return w.upper()
    bare = text.strip().strip(".!")
    if bare.upper() in CODES:
        if bare.isupper() and (asking_state or bare not in BARE_WORD_CODES):
            return bare
        if asking_state and bare.lower() not in AMBIGUOUS_CODES:
            return bare.upper()
    return None


JOB_PATTERNS = [
    re.compile(r"\bi\s+work\s+as\s+(?:an?\s+)?([a-z][a-z \-]{1,40}?)(?=\s+(?:in|at|for|from|with|and|who|living|making|earning)\b|[,.;!]|$)", re.I),
    re.compile(r"\b(?:i'?m|i\s+am|im)\s+(?:a|an)\s+(retired\s+)?([a-z][a-z \-]{1,40}?)(?=\s+(?:in|at|for|from|with|and|who|living|making|earning|of)\b|[,.;!]|$)", re.I),
    re.compile(r"^\s*(retired\s+)?([a-z][a-z \-]{1,40}?)\s+(?:in|from)\s+[A-Z]", re.I),
    re.compile(r"(?:^|,|\band\b)\s*(?:a\s+)?(retired\s+)([a-z][a-z \-]{1,30}?)(?=\s+(?:in|at|from|for)\b|[,.;!]|$)", re.I),
    re.compile(r"\b(?:make|earn|work)\w*\b[^,.;]*?\bas\s+(?:an?\s+)?()([a-z][a-z \-]{1,30}?)(?=\s+(?:in|at|for|and)\b|[,.;!]|$)", re.I),
    re.compile(r"(?:^|,)\s*(?:i'?m\s+|i\s+am\s+)?(?:an?\s+)?(retired\s+)?([a-z][a-z \-]{1,30}?)\s+(?:making|earning|who makes|who earns)\b", re.I),
    re.compile(r"(?:^|,)\s*an?\s+(retired\s+)?([a-z][a-z \-]{1,30}?)(?=\s+(?:in|at|from|for|with|and|who)\b|[,.;!]|$)", re.I),
]
MARITAL = re.compile(r"^(?:widowed|divorced|single|married)\s+", re.I)


def parse_job(text: str) -> tuple[str | None, bool]:
    for i, pat in enumerate(JOB_PATTERNS):
        m = pat.search(text)
        if not m:
            continue
        retired, job = (False, m.group(1)) if i == 0 else (bool(m.group(1)), m.group(2))
        job = re.sub(r"^(?:self[- ]employed|full[- ]time|part[- ]time)\s+", "", MARITAL.sub("", job.strip()), flags=re.I)
        if estimates.match_job(job):
            return job.lower(), retired or bool(re.search(r"\bretired\b", text, re.I))
    return None, bool(re.search(r"\b(?:i'?m|i am|im|we'?re|we are)\s+(?:both\s+|already\s+)?retired\b|(?:^|,)\s*(?:and\s+|already\s+)?retired\s*(?:,|\.|$)",
                                text, re.I))


def _savings_kind(clause: str) -> str | None:
    c = clause.lower()
    if re.search(r"\broth\b", c):
        return "roth"
    if re.search(r"401\s?\(?k\)?|403\s?\(?b\)?|\b457\b|\btsp\b|\bira\b|pre-?tax|traditional|pension pot|retirement account", c):
        return "pretax"
    if re.search(r"brokerage|taxable|stocks|index funds?|investments?|mutual funds?", c):
        return "taxable"
    if re.search(r"\bcash\b|in the bank|checking|savings account|emergency fund|\bcds?\b|money market", c):
        return "cash"
    if re.search(r"\bsaved\b|\bsavings\b|nest egg|put away|retirement|\bin total\b|net worth", c):
        return "total"
    return None


ACCOUNT_RE = re.compile(
    r"\broth(?:\s+(?:ira|401\s?\(?k\)?|403\s?\(?b\)?))?|\btraditional(?:\s+(?:ira|401\s?\(?k\)?))?|\bpre-?tax\b|\b401\s?\(?k\)?|"
    r"\b403\s?\(?b\)?|\b457\b|\btsp\b|\bira\b|\btaxable\b|\bbrokerage\b|\binvestments?\b|\bstocks\b|\bcash\b|\bbank\b|"
    r"\bsavings account\b|\bchecking\b", re.I)
GAP_BAD = re.compile(r"[,;.\n\d]|\b(?:and|but|plus|then|also)\b|^\s*(?:a|per|each|every)\s+(?:year|month)\b", re.I)      # "$23,000 a year into my 401(k)" is a saving a year, not a balance
GAP_MAX = 30
_OTHER_MONEY = (r"\bsav(?:ed|ings?)\b|\b401\s?\(?k|\b403\s?\(?b|\bira\b|\broth\b|brokerage|nest egg|put away|in the bank|\bowe\b|\bloans?\b|"
                r"\bdebts?\b|\bmortgage\b|\brent\b|\bpension\b|social security")
_PAY_WORDS = r"\b(?:make|makes|making|earn|earns|earning|salary|income|(?:my|his|her|our)\s+(?:pay|wages?))\b"
# a figure labelled as something else is not the answer to the pending money question ("300k saved" while asking pay)
OTHER_LABEL = {
    "pay_per_year": re.compile(_OTHER_MONEY + r"|\bspend|\bbudget\b", re.I),
    "partner_pay_per_year": re.compile(_OTHER_MONEY + r"|\bspend|\bbudget\b", re.I),
    "spending_now_per_year": re.compile(_OTHER_MONEY + "|" + _PAY_WORDS, re.I),
    "spending_per_year": re.compile(_OTHER_MONEY + "|" + _PAY_WORDS, re.I),
    "social_security_per_year": re.compile(r"\bsav(?:ed|ings?)\b|\b401\s?\(?k|\bowe\b|\bmortgage\b|\brent\b|\bspend|" + _PAY_WORDS, re.I),
}
INCLUDING = re.compile(r"\b(?:including|includes|include|incl\.?|counting|with|plus)\s+(?:the\s+|our\s+|my\s+)?(?:rent|mortgage|housing|car|loans?|debts?)\b", re.I)
PAY_CHIPS = {"under $50k": 40000, "$50k to $100k": 75000, "$100k to $200k": 150000, "over $200k": 250000}


def account_kind(word: str) -> str:
    """'401(k)', 'IRA', 'traditional', 'pre-tax' -> pretax; 'Roth ...' -> roth; brokerage, taxable -> taxable; cash, bank ... -> cash."""
    w = word.lower()
    if w.startswith("roth"):
        return "roth"
    if re.match(r"taxable|brokerage|investment|stocks", w):
        return "taxable"
    if re.match(r"cash|bank|savings account|checking", w):
        return "cash"
    return "pretax"


def parse_split(t: str) -> dict[str, float]:
    """'300k pre-tax, 50k roth' or 'pre-tax 300k, roth 50k' -> {savings.pretax: 300000, savings.roth: 50000}.

    Every amount is paired with its nearest account word, on either side. Only neighbours pair: no other amount or
    account word between them, and no comma, 'and' or other break in the gap. The digits of '401(k)' are never an amount."""
    events: list[tuple[int, int, str, Any]] = [(s0, e0, "A", v) for v, s0, e0 in amounts(t, floor=0)]
    for i, m in enumerate(ACCOUNT_RE.finditer(t)):
        if i >= MAX_AMOUNTS:
            break
        events.append((m.start(), m.end(), "L", account_kind(m.group(0))))
    events.sort(key=lambda e: (e[0], e[1]))
    cands = []
    for i in range(len(events) - 1):
        x, y = events[i], events[i + 1]
        if x[2] == y[2] or y[0] < x[1]:
            continue
        gap = t[x[1]:y[0]]
        if len(gap) <= GAP_MAX and not GAP_BAD.search(gap):
            cands.append((len(gap), i))
    used: set[int] = set()
    out: dict[str, float] = {}
    for _, i in sorted(cands):
        if i in used or i + 1 in used:
            continue
        used.update((i, i + 1))
        amt, lab = (events[i], events[i + 1]) if events[i][2] == "A" else (events[i + 1], events[i])
        key = "savings." + lab[3]
        out[key] = out.get(key, 0) + amt[3]
    return out


RETIRE_AGE_WORDS = re.compile(r"\b(?:(?:set|change|make|update|put)\s+)?(?:my|our)\s+((?:partner'?s?|wife'?s?|husband'?s?|spouse'?s?)\s+)?"
                              r"retirement\s+age\s+(?:to\s+|as\s+|is\s+|at\s+|of\s+|should be\s+|=\s*)?(?:actually\s+)?(\d{2})\b", re.I)


HOURLY = re.compile(r"\$?\s?(\d{1,3}(?:\.\d{1,2})?)\s*(?:dollars?\s*)?(?:an|per|/|a)\s*(?:hour|hr)\b|\$?\s?(?<![\d,])(\d{1,3}(?:\.\d{1,2})?)\s*hourly\b", re.I)
PART_TIME = re.compile(r"part[- ]?time", re.I)
# "my partner passed away", "we split up", "my ex": planned for alone (a partner's parent or friend dying is not this)
NO_PARTNER_NOW = re.compile(rf"\bmy\s+{PARTNER}\s+(?:passed(?: away)?|died|is gone|left me)\b|\blost my\s+{PARTNER}\b|"
                            r"\bwe(?:'ve| have)?\s+(?:split up|separated|broke up|divorced)\b|\bmy ex\b|\bit'?s just me( now)?\b|\bon my own now\b", re.I)
BORN = re.compile(rf"\b(?:(my|our)\s+{PARTNER}\s+(?:was\s+)?)?born\s+(?:in\s+)?(?:[a-z]+\s+)?(19[2-9]\d|200\d)\b", re.I)


def parse(text: str, asking: str | None = None, has_partner: bool = False, n_children: int = 0, pending_kind: str | None = None) -> dict[str, Any]:
    """Facts the person stated, as {key: value}."""
    out: dict[str, Any] = {}
    t = fix_typos(text.strip())
    # "make my retirement age 67", "my retirement age is 62": a retirement age, never the person's age or a child's
    t = RETIRE_AGE_WORDS.sub(lambda m: f"{m.group(1) or ''}retire at {m.group(2)}", t)
    # "$45 an hour": a year's pay, full time (2,080 hours) or part time (1,040)
    t = HOURLY.sub(lambda m: f"${float((m.group(1) or m.group(2)).replace(',', '')) * (1040 if PART_TIME.search(t) else 2080):,.0f} a year", t)
    low = t.lower()
    if not t:
        return out
    if asking and low.startswith("keep") and len(low.split()) <= 4:
        return {"keep": True}
    if asking == "partner_retire_age" and low in ("same time as me", "same time"):
        return {"use_typical": ["partner_retire_age"]}

    # --- the extra groups first: debts, pensions, saving, insurance, goals, health, costs
    extra, consumed = parser_extra.parse(t, asking, has_partner, pending_kind)
    out.update(extra)
    om = re.search(r"\bowe\s+(\$[\d,.]+\s?[km]?)\s+on\s+(?:our|my|the|a)\s+(\$[\d,.]+\s?[km]?)\s+(?:home|house|condo|place)\b", t, re.I)
    if om and (bal := amounts(om.group(1), floor=1)) and (val := amounts(om.group(2), floor=1)):      # "owe $420,000 on our $850,000 home"
        rest = [d for d in out.get("debts", []) if d.get("balance") != bal[0][0]]
        if rest:
            out["debts"] = rest
        else:
            out.pop("debts", None)
        out["home.owns"], out["home.mortgage_balance"], out["home.value"] = True, bal[0][0], val[0][0]
    wm = re.search(r"\b(?:house|home|condo|place)\b[^.;]{0,25}?\b(?:worth|valued at|value of)\s+(\$[\d,.]+\s?[km]?)[^.;]{0,40}?\b(?:owe|owing|mortgage of|left on)\s+(\$[\d,.]+\s?[km]?)", t, re.I)
    if wm and not om and (val := amounts(wm.group(1), floor=1)) and (bal := amounts(wm.group(2), floor=1)):
        # "our house is worth $620,000 and we owe $310,000 at 3.1% with payments of $2,150 a month": the mortgage, not another debt
        out["home.owns"], out["home.mortgage_balance"], out["home.value"] = True, bal[0][0], val[0][0]
        for d in out.get("debts", []):
            if d.get("balance") == bal[0][0]:
                if d.get("rate") is not None:
                    out["home.mortgage_rate"] = d["rate"]
                if d.get("monthly_payment"):
                    out["home.mortgage_payment"] = d["monthly_payment"]
        rest = [d for d in out.get("debts", []) if d.get("balance") != bal[0][0]]
        if rest:
            out["debts"] = rest
        else:
            out.pop("debts", None)
    if "open_group" in out or "skip_all" in out:
        return out
    # --- answers to the edit questions
    if asking in ("pay_per_year", "partner_pay_per_year") and low in PAY_CHIPS:
        out[asking] = PAY_CHIPS[low]
    elif asking in ("pay_per_year", "partner_pay_per_year", "spending_now_per_year", "spending_per_year", "social_security_per_year"):
        a = amounts(t, floor=100)
        bare_low = INCLUDING.sub(" ", low)
        if a and "%" not in t and not OTHER_LABEL[asking].search(bare_low):
            v = a[0][0]
            if asking == "spending_now_per_year" and v < 20000 and not re.search(r"year|annual", low):
                v *= 12
            out[asking] = v
        elif asking in ("pay_per_year", "partner_pay_per_year"):
            jb = low.strip(" .!").removeprefix("i'm a ").removeprefix("i am a ").removeprefix("a ")
            not_a_job = re.search(r"not sure|don.?t know|no idea|leave it out|estimate|typical|skip|rather not|prefer not|\bidk\b|dunno", jb)
            if len(jb.split()) <= 6 and not any(c.isdigit() for c in jb) and not not_a_job and estimates.match_job(jb):
                out["partner_job" if asking == "partner_pay_per_year" else "job"] = jb
    if asking == "children_count":
        n = re.match(r"^\s*(\d{1,2}|none|no|zero|one|two|three|four|five)\s*(?:kids?|children)?\s*$", low)
        if n:
            out["children.count"] = 0 if n.group(1) in ("none", "no", "zero") else num(n.group(1))
    if asking == "partner_retire_age" and re.match(r"^\s*(\d{2})\s*$", t):
        out["partner_retire_age"] = int(t)
    sp = parse_split(t)
    if len(sp) >= 2 or (asking == "savings_split" and sp):
        out.update(sp)
        consumed.add(t)

    # --- answers to the last question, in short form
    if asking == "age":
        m = re.match(r"^\s*(?:i'?m\s+|we'?re\s+)?(\d{2})\s*(?:and|&|,|/)\s*(?:she'?s\s+|he'?s\s+)?(\d{2})\b", t, re.I)
        if m:
            out["age"], out["partner_age"] = int(m.group(1)), int(m.group(2))
        elif re.match(r"^\s*(\d{2})\s*$", t):
            out["age"] = int(t)
    if asking == "partner_age" and re.match(r"^\s*(?:she'?s\s+|he'?s\s+)?(\d{2})\s*(?:years? old)?\s*$", t, re.I):
        out["partner_age"] = int(re.sub(r"\D", "", t))
    if asking == "retire_age" and re.match(r"^\s*(?:at\s+)?(\d{2})\s*$", t):
        out["retire_age"] = int(re.sub(r"\D", "", t))
    if asking == "children":
        quick = {"under 5": 3, "5 to 12": 9, "teenagers": 15, "grown up": 24, "grown": 24}
        if low in quick:
            out["children.ages"] = [quick[low]] * max(1, n_children)
        else:
            ages = [int(x) for x in re.findall(r"\b(\d{1,2})\b", t)]
            if ages and (n_children == 0 or len(ages) == n_children or not re.search(r"[a-z]{4,}", low)):
                out["children.ages"] = ages
    if asking == "home":
        if re.search(r"own(?:\s+it)?\s+outright|paid\s+off|no mortgage", low):
            out["home.owns"], out["home.mortgage_balance"] = True, 0
        elif re.search(r"mortgage", low):
            out["home.owns"] = True
            out["home.has_mortgage"] = True
        elif re.search(r"\brent", low):
            out["home.owns"] = False
    if asking == "savings":
        a = amounts(t, floor=100)
        if a and not _savings_kind(t):
            out["savings.total"] = a[0][0]
    if asking == "state":
        s = find_state(t, asking_state=True)
        if s:
            out["state"] = s

    # --- age
    m = re.search(r"\b(?:i'?m|i am|im|age|aged)\s+(\d{2,3})\b(?!\s*(?:k|%|kids|children|years? (?:in|at|of)))", t, re.I) or \
        re.search(r"\b(\d{2})[- ](?:years?[- ]old|yo|y/o)\b(?!\s+(?:son|daughter|kid|child|boy|girl|dog|cat))", t, re.I)
    if m and int(m.group(1)) >= 18:
        out.setdefault("age", int(m.group(1)))
    for bm in BORN.finditer(t):          # "I was born in 1968", "my wife was born in March 1970": this year minus the year
        out["partner_age" if bm.group(1) else "age"] = date.today().year - int(bm.group(2))
    if "age" not in out and asking in (None, "age", "more"):
        # a bare age as its own clause: "I'm a doctor, 44, married", "28, I rent", "40 yrs, married"
        for m in re.finditer(r"(?:^|,)\s*(\d{2})\s*(?:yrs?|years?(?:\s+old)?|yo)?\s*(?=,|;|$|\.\s)", t, re.I):
            head = t[:m.start()][-30:]
            if 18 <= int(m.group(1)) <= 99 and not re.search(r"\b(?:aged?|ages|kids?|children|sons?|daughters?|retire\w*|at)\b[^,]*$|\d\s*$", head, re.I):
                out["age"] = int(m.group(1))
                break
    m = re.search(r"\bwe(?:'?re| are)\s+(\d{2})\s*(?:and|&)\s*(\d{2})\b", t, re.I)
    if m:
        out.setdefault("age", int(m.group(1)))
        out.setdefault("partner_age", int(m.group(2)))
    m = re.search(rf"\b{PARTNER}(?:\s+is|,)?\s+(\d{{2}})\b", t, re.I) or re.search(rf"\b(\d{{2}})[- ]year[- ]old\s+{PARTNER}", t, re.I)
    if m and 18 <= int(m.group(1)) <= 100:
        out.setdefault("partner_age", int(m.group(1)))

    # --- partner
    alone = re.search(r"\b(?:divorced|widowed|widow|widower|single|separated)\b", low) or NO_PARTNER_NOW.search(low)
    if re.search(rf"\b{PARTNER}\b|\bmarried\b|\bmy (?:fiance|fiancee)\b", low) and not alone:
        out["has_partner"] = True
        has_partner = True
        sex = partner_sex_said(low)
        if sex is not None:
            out["partner_sex"] = sex
    if alone:
        out["has_partner"] = False
    if has_partner and re.search(rf"(?:stay[- ]at[- ]home|homemaker|housewife|house husband|full[- ]time (?:mom|dad|parent))\s*{PARTNER}?|{PARTNER}\s+(?:stays (?:at )?home|is (?:at|a stay[- ]at) home|doesn'?t work|does not work|is not working|isn'?t working|is retired|is a homemaker)", low):
        out["partner_pay_per_year"] = 0
        out["partner_job"] = "at home"
    m = re.search(rf"\b{PARTNER}\s+(?:is|works as)\s+(?:a|an)\s+([a-z][a-z \-]{{1,30}}?)(?=\s+(?:in|at|for|and|who|making|earning)\b|[,.;!]|$)", t, re.I)
    if m and estimates.match_job(m.group(1)):
        out["partner_job"] = m.group(1).lower()

    # --- children
    if re.search(r"\b(?:no|zero) (?:kids|children)\b|\bchildless\b|\bdon'?t have (?:any )?(?:kids|children)\b", low):
        out["children.count"] = 0
    else:
        m = re.search(NUMW_RE + r"\s+(?:young\s+|little\s+|grown\s+|teenage\s+)?(kids?|children|child|sons?|daughters?|boys?|girls?)\b", low)
        if m and m.group(1) in ("a", "an") and re.search(r"\b(?:was|as|like|be|being|were)\s+$", low[:m.start()]):
            m = None            # "since I was a kid" is not a child
        if m and num(m.group(1)) is not None:
            out["children.count"] = num(m.group(1))
            # "two kids, 12 and 9": the ages right after the count
            after = re.findall(r"(?<![\d$,.])\b(\d{1,2})\b(?![,.]?\d|\s*(?:k\b|%|years? (?:ago|from)|dogs?|cats?))", low[m.end():m.end() + 30])
            if out["children.count"] and len(after) == out["children.count"] and not re.search(r"\b(?:aged?|ages)\b", low):
                out["children.ages"] = [int(x) for x in after]
        ages = re.search(r"\b(?:kids|children|sons|daughters)?\s*(?:aged?|ages)\s+((?:\d{1,2}(?:\s*(?:,|and|&)\s*)?)+)", low)
        if ages:
            out["children.ages"] = [int(x) for x in re.findall(r"\d{1,2}", ages.group(1))]
        else:
            yo = re.findall(r"\b(\d{1,2})[- ]year[- ]old\s+(?:son|daughter|kid|child|boy|girl)", low)
            if yo:
                out["children.ages"] = [int(x) for x in yo]
        if re.search(r"\bno college\b|\bnot going to college\b", low):
            out["children.college"] = False

    # --- pets
    pets = []
    for m in re.finditer(NUMW_RE + r"\s+(dogs?|cats?|puppies|puppy|kittens?)\b", low):
        n = num(m.group(1))
        if n and n <= 10:
            pets.append({"kind": "dog" if m.group(2).startswith(("dog", "pup")) else "cat", "count": n})
    if not pets:
        if re.search(r"\b(?:a|our|my) dog\b", low):
            pets.append({"kind": "dog", "count": 1})
        if re.search(r"\b(?:a|our|my) cat\b", low):
            pets.append({"kind": "cat", "count": 1})
    if not pets:        # a breed is a pet: "I have a beagle", "we have two labs"
        for m in re.finditer(r"\b(\d{1,2}|one|two|three|four|five|six|a|an|our|my)\s+(?:[a-z]+\s+)?(" + DOG_BREEDS + r"|" + CAT_BREEDS + r")s?\b", low):
            n = num(m.group(1)) if m.group(1) not in ("a", "an", "our", "my") else 1
            kind = "cat" if re.match(CAT_BREEDS, m.group(2)) else "dog"
            if n and n <= 10:
                pets.append({"kind": kind, "count": n})
    if pets:
        out["pets"] = pets
    elif re.search(r"\bno pets\b", low):
        out["pets"] = []

    # --- state
    s = find_state(t, asking_state=asking == "state")
    if s:
        out["state"] = s

    # --- job
    job, retired = parse_job(t)
    if job:
        out["job"] = job
    if retired and asking == "partner_pay_per_year" and not re.search(r"\b(?:i'?m|i am|im|we'?re|we are|both|me)\b", low):
        out["partner_pay_per_year"] = 0         # the "Retired" chip at the partner's pay question is about the partner, not about me
        retired = False
    if retired:
        out["retired"] = True
    if re.search(r"\b(?:i'?m|i am|im)\s+(?:a\s+)?(?:stay[- ]at[- ]home|homemaker|unemployed|not working|between jobs)\b", low):
        out["pay_per_year"] = 0

    # --- Social Security for a couple: "$2,900 a month, and she gets $1,100" is the household's $48,000 a year
    for sent in re.split(r"\.(?!\d)|[;!?\n]", t):
        sm = re.search(r"social security", sent, re.I)
        if not sm:
            continue
        mine = partner = 0.0
        monthly = False
        seg = sent[sm.start():]
        for v, s0, e0 in amounts(seg, floor=100):
            tail = seg[e0:e0 + 25].lower()
            if re.match(r"\s*(?:a|per|each|/|every)\s*(?:month|mo)\b|\s*monthly", tail):
                monthly = True          # amounts() already made this yearly
            elif monthly and v < 10000:
                v *= 12                 # "and she gets $1,100": the same unit as the figure before it
            elif v < 6000 and not re.search(r"\b(?:year|annual)", tail):
                v *= 12
            head = seg[max(0, s0 - 30):s0].lower()
            if re.search(r"\b(?:she|he|wife|husband|partner|spouse|her|his)\b", head):
                partner += v
            else:
                mine += v
        if mine or partner:
            out["social_security_per_year"] = mine + partner
            if mine and partner:
                out["social_security_parts"] = [mine, partner]
            consumed.add(sent.strip())
        break

    # --- money: each amount is read with the words around it (up to the amounts on either side)
    for clause in re.split(r"\.(?!\d)|[;!?\n]|,\s+(?=[a-zA-Z$\d])|\s+and\s+(?=(?:we|i|my|our|she|he)\s+(?:owe|get|have|also|want|plan|pay|put|contribute))", t):
        if not clause or not clause.strip():
            continue
        used = clause.strip() in consumed or t in consumed or any(clause.strip() and clause.strip() in c for c in consumed)
        found = amounts(clause)
        for i, (v, s0, e0) in enumerate(found):
            if used and not (re.search(r"\b(?:make|makes|making|earn|earns|earning|salary)\b[^\d$]{0,12}$", clause[:s0], re.I)
                             or re.match(r"\s*(?:saved|in savings|in the bank|put away)\b", clause[e0:e0 + 20], re.I)):
                continue        # the extra-group reader already used this clause; only a pay or savings figure is read again
            if re.match(r"\s*(?:a|per|each|every)\s*(?:year|month)\b", clause[e0:e0 + 14], re.I) \
                    and re.search(r"\b(?:put|putting|contribute|contributing|defer|deferring)\b[^$\d]{0,15}$", clause[:s0], re.I):
                continue        # "I put $23,000 a year into my 401(k)": a yearly saving, read by the saving reader, not a balance
            left = found[i - 1][2] if i > 0 else 0
            right = found[i + 1][1] if i + 1 < len(found) else len(clause)
            _money(clause[left:right], clause, v, out, after=clause[e0:right], before=clause[left:s0])
    m = re.search(r"\b(?:retire\w*|hang it up|call it quits|stop(?:ping)? working|quit working|be done|done working|leave work|work until|"
                  r"wrap (?:it )?up)\s+(?:at|by|around|until|when i'?m)\s+(?:age\s+)?(\d{2})\b(?!\s*(?:k\b|%))", low)
    if m and not (out.get("age") == int(m.group(1)) and not re.search(r"\bretire", low)):
        out["retire_age"] = int(m.group(1))
    m = re.search(r"\bretire\w*\s+in\s+(\d{1,2})\s+years\b", low)
    if m:
        out["retire_in_years"] = int(m.group(1))
    if re.search(r"\bown (?:my|our|a|the) (?:home|house|condo|place)\b|\bhomeowners?\b", low):
        out.setdefault("home.owns", True)
    if re.search(r"\b(?:we|i) rent\b(?!\s+out)|\brenting\b|\brenters?\b", low):
        out.setdefault("home.owns", False)
    paid_home = re.search(r"\bno mortgage\b|\b(?:house|home|mortgage|condo|place)\b[^.;]{0,25}\bpaid off\b|\bpaid off (?:the |our |my )?(?:house|home|mortgage)\b|"
                          r"\bown (?:it|the house|the home|our home|my home) (?:outright|free and clear)\b", low) \
        or (asking in ("home", "mortgage") and re.search(r"\bpaid off\b", low))
    if paid_home and out.get("home.owns") is not False:
        out["home.owns"], out["home.mortgage_balance"], out["home.mortgage_payment"] = True, 0, 0
    if re.search(r"\b(?:careful|cautious|conservative|safe|low risk|nervous about (?:the )?market)\b", low):
        out["risk"] = "careful"
    elif re.search(r"\b(?:aggressive|growth|high risk|lots of risk)\b", low):
        out["risk"] = "growth"
    elif re.search(r"\b(?:balanced|moderate|middle)\b", low):
        out["risk"] = "balanced"
    late_correction(t, out)
    return out


def _money(piece: str, clause: str, v: float, out: dict[str, Any], after: str = "", before: str = "") -> None:
    c = piece.lower()
    whole = clause.lower()
    if re.search(r"\b(?:make|makes|making|earn|earns|earning|salary|income|paid|pay is|bring in|brings in)\b", c):
        if re.search(rf"\b{PARTNER}\b|\bshe\b|\bhe\b", c):
            out["partner_pay_per_year"] = v
        elif re.search(r"\bwe\b|\btogether\b|\bhousehold\b|\bcombined\b", c):
            out["household_pay"] = v
        else:
            out["pay_per_year"] = v
        return
    if re.search(r"\bsocial security\b", c):
        out["social_security_per_year"] = v
        return
    spend_re = r"\b(?:spend|spending|live on|need about|budget)\b"
    if re.search(spend_re, before.lower()[-40:]) or re.search(spend_re, after.lower()[:18]) \
            or (re.search(spend_re, c) and not re.search(r"\brent\b|\bmortgage\b", c)):
        now_words = re.search(r"\b(?:now|currently|right now|today|at the moment|these days|presently)\b", whole) or \
            re.search(r"\b(?:i|we)\s+(?:spend|go through|live on)\b|\bour (?:spending|budget) is\b", whole)
        if now_words and not re.search(r"\bretire", whole):
            out["spending_now_per_year"] = v
        else:
            out["spending_per_year"] = v
        return
    if re.search(r"\brent\b", c) and not re.search(r"\bown\b", c) and not INCLUDING.search(c):
        out["home.owns"], out["home.rent"] = False, v / 12 if v >= 6000 else v
        return
    if re.search(r"\bmortgage\b", c) and not (re.search(r"\b(?:saved|savings)\b", before.lower()[-25:]) and "mortgage" not in before.lower()):
        out["home.owns"] = True
        if re.search(r"\bpayment\b|\bmonth\b|\bmonthly\b", c) or v < 60000:
            out["home.mortgage_payment"] = v / 12 if v >= 6000 else v
        else:
            out["home.mortgage_balance"] = v
        return
    if re.search(r"\b(?:house|home|condo|place)\b[^.]{0,30}\b(?:worth|valued|value)\b|\b(?:worth|valued)\b[^.]{0,20}\b(?:house|home)\b", c):
        out["home.owns"], out["home.value"] = True, v
        return
    kind = _savings_kind(after) or _savings_kind(before)
    if kind is None and not re.search(r"\b(?:pay|make|earn|rent|mortgage|spend)", whole):
        kind = _savings_kind(whole)
    if kind:
        key = "savings." + kind
        out[key] = out.get(key, 0) + v
