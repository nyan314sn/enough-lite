"""Reads sloppy What If wording for the plan chat ("wat if retir 62", "if I stop at 62", "put 300 a month into college
savings", "spend $500 less a month", "work part time until 68", "get a second dog").

normalize() fixes typos and number words. extra() returns the parts of a What If that pipeline.parse_whatif's older rules
do not read: a retirement age said another way, spending cut by an amount, part-time work, a pet, a claiming age. Nothing
here runs a plan; the result is a dict of changes (keys starting with "_" are notes) or {}.
"""
from __future__ import annotations

import re
from typing import Any

ONES = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
TEENS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
         "eighteen": 18, "nineteen": 19}
TYPOS = [
    (r"\b(?:wat|wut|wht|whatt|waht|whaat)\b(?=\s+(?:if|happens|about))", "what"),
    (r"\bret(?:ir|re|yre|iere|ire)\b", "retire"), (r"\bretirre\b", "retire"), (r"\bretiring?\b(?=\s+\d)", "retire"),
    (r"\bsav\b", "save"), (r"\bsvae\b", "save"), (r"\b(?:mnth|mth|monh|mnthly)\b", "month"), (r"\bmnths\b", "months"),
    (r"\b(?:spendin|spnding|spendng|spnd)\b", "spending"), (r"\berly\b", "early"), (r"\bwrk\b", "work"), (r"\byrs\b", "years"),
    (r"\byr\b", "year"), (r"\bpt\b(?=\s+(?:job|work))", "part time"), (r"\bpart[- ]?time\b", "part time"), (r"\bhalf[- ]?time\b", "part time"),
    # 2026-11-22: more slips seen in typed What Ifs
    (r"\b(?:reitre|retrie|retier|rtire|retiree?)\b(?=\s+(?:at|in|by|now|early|earlier|later|\d))", "retire"),
    (r"\b(?:dgos|dosg|dgo|dogz)\b", "dogs"), (r"\bcatz\b", "cats"), (r"\b(?:mvoe|moev|mov)\b", "move"), (r"\b(?:spned|sepnd|spedn)\b", "spend"),
    (r"\b(?:calim|cliam|claime)\b", "claim"), (r"\b(?:markt|makret|market's)\b", "market"), (r"\b(?:hvae|ahve|hav)\b", "have"),
    (r"\b(?:socail|socal|social)\s+(?:secuirty|securty|secrity|security)\b", "social security"), (r"\bpay of\b", "pay off"),
    (r"\b(?:kdis|kidz)\b", "kids"), (r"\bsaev\b", "save"), (r"\bmoeny\b", "money"), (r"\binflaiton\b", "inflation"),
]
PUT_IN = re.compile(r"\b(?:put|putting|add|adding|throw|stash|invest|move|send|contribute)\b\s+(?:an?\s+extra\s+|another\s+|an?\s+additional\s+)?(\$?[\d,.]+\s?k?)\s*((?:a|per|each|every)\s+(?:month|year)|/\s?(?:month|year)|monthly|yearly)?"
                    r"\s*(?:more\s+)?(?:into|in|to|toward|towards|for|on)\s+(?:a\s+|the\s+|my\s+|our\s+|their\s+|the kids'?\s+)?"
                    r"(?:college|529|education|tuition|school|kids?|children|savings?|retirement|401\s?\(?k\)?|ira|roth|investments?|fund)\b")
COLLEGE = re.compile(r"\bcollege\b|\b529\b|\beducation\b|\btuition\b")
COUNTED = (r"dogs?|pupp(?:y|ies)|cats?|kittens?|pets?|rabbits?|bunn(?:y|ies)|birds?|horses?|hamsters?|fish|turtles?|kids?|child(?:ren)?|"
           r"bab(?:y|ies)|years?|months?|weeks?|hundred|thousand|grand")


def _words_to_digits(low: str) -> str:
    def tens(m: re.Match) -> str:
        return str(TENS[m.group(1)] + (ONES[m.group(2)] if m.group(2) else 0))

    low = re.sub(r"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[- ]+(one|two|three|four|five|six|seven|eight|nine)\b)?", tens, low)
    low = re.sub(r"\b(ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)\b(?!\s+(?:months?|percent|%))",
                  lambda m: str(TEENS[m.group(1)]), low)
    # "two more kids", "five dogs", "three years later", "five hundred": a count, said in words, before what it counts
    low = re.sub(r"\b(one|two|three|four|five|six|seven|eight|nine)\b(?=\s+(?:(?:more|fewer|less|extra|additional|new|little|small|big|young|"
                 r"older|of (?:the|our|my|them))\s+)?(?:(?:" + COUNTED + r")\b|percent\b|%))", lambda m: str(ONES[m.group(1)]), low)
    low = re.sub(r"\b(?:a|one)\s+(hundred|thousand)\b", lambda m: "100" if m.group(1) == "hundred" else "1000", low)
    low = re.sub(r"\b(\d{1,2})\s+hundred\b", lambda m: str(int(m.group(1)) * 100), low)
    low = re.sub(r"\b(\d{1,3})\s+(?:thousand|grand)\b", lambda m: str(int(m.group(1)) * 1000), low)
    low = re.sub(r"\ba couple(?: of)?\b(?=\s+(?:more\s+|extra\s+)?(?:" + COUNTED + r")\b)", "2", low)
    return re.sub(r"\b(\d+)\s+bucks\b", r"$\1", low)


def normalize(low: str) -> str:
    """Lower-case text with the common typos fixed, number words as digits, and 'put N a month into X' as 'save N a month more'."""
    low = re.sub(r"\s+", " ", low or "").strip().replace("’", "'")
    for pat, rep in TYPOS:
        low = re.sub(pat, rep, low)
    low = _words_to_digits(low)
    m = PUT_IN.search(low)
    if m:
        per = (m.group(2) or "").replace("/", "a ").strip()
        low = low[:m.start()] + f"save {m.group(1).strip()} {per} more".replace("  ", " ") + low[m.end():]
    return low


MONEY = r"\$?\s?(?P<n>\d[\d,]*(?:\.\d+)?)\s?(?P<s>k\b|thousand\b|m\b|million\b)?"
SUFFIX = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6}


def _val(m: re.Match) -> float:
    return float(m.group("n").replace(",", "")) * SUFFIX.get((m.group("s") or "").lower(), 1)


def _period(*parts: str) -> str | None:
    """'month', 'year', 'week' or None from the words around an amount."""
    for part in parts:
        if re.search(r"\bmonth|\bmo\b|monthly|/\s?mo", part or ""):
            return "month"
        if re.search(r"\byear|\byr\b|yearly|annual|/\s?yr", part or ""):
            return "year"
        if re.search(r"\bweek|weekly|/\s?wk", part or ""):
            return "week"
    return None


def per_year(v: float, per: str | None, month_below: float = 3000) -> float:
    """Dollars a year from an amount and its period; with no period, small sums are a month and large ones a year."""
    if per is None:
        per = "month" if v <= month_below else "year"
    return round(v * {"month": 12, "week": 52}.get(per, 1), 2)


NOT_PCT = r"(?![\d,.]|\s?(?:%|percent|per cent))"
SPEND = r"\b(?:spend|spending|spends|spent|live on|lived on|get by on|need|needed)\b"
LESS_AFTER = re.compile(SPEND + r"[^.?!$\d]{0,25}?" + MONEY + NOT_PCT + r"(?P<mid>[^.?!%]{0,25}?)\b(?:less|lower|fewer)\b(?P<post>[^.?!]{0,25})")
CUT_WHAT = (r"(?:(?:cut|reduce|lower|trim|decrease|shave|drop|slash)\w*\s+(?:my\s+|our\s+|the\s+)?(?:spending|expenses|costs|budget|spend)\b|"
            r"\bcut\w*\s+back(?:\s+on\s+(?:my\s+|our\s+)?(?:spending|expenses|costs))?|\btighten\w*\s+(?:my\s+|our\s+|the\s+)?belts?)")
CUT_BY = re.compile(r"\b" + CUT_WHAT + r"[^.?!$\d%]{0,12}?\b(?:by|with)\s+" + MONEY + NOT_PCT + r"(?P<post>[^.?!%]{0,20})")
CUT_FROM = re.compile(r"\b(?:cut|take|trim|shave|save)\w*\s+" + MONEY + NOT_PCT + r"(?P<post>[^.?!%]{0,16}?)\b(?:from|off|out of)\s+(?:my\s+|our\s+|the\s+)?"
                      r"(?:spending|expenses|budget|groceries|eating out|restaurants|dining|travel|vacations?|shopping|clothes|entertainment|subscriptions)\b")
LESS_PCT = re.compile(r"\b(?:spend|spending|spent)\b[^.?!$\d]{0,15}?(?P<p>\d{1,2}(?:\.\d+)?)\s?(?:%|percent)\s*(?:less|lower)\b|"
                      r"\b" + CUT_WHAT + r"\s*by\s+(?P<q>\d{1,2}(?:\.\d+)?)\s?(?:%|percent)")
FRACTION = {"half": 0.5, "a half": 0.5, "a third": 1 / 3, "a quarter": 0.25, "a fourth": 0.25, "a fifth": 0.2, "a tenth": 0.1}
LESS_FRAC = re.compile(r"\b(?:spend|spending|spent)\b[^.?!$\d]{0,10}?\b(half|a half|a third|a quarter|a fourth|a fifth|a tenth)\s+less\b|"
                       r"\b(?:spend|spending|spent)\s+(?:only\s+)?(half) (?:as much|of what (?:we|i) (?:do|spend|planned))\b|"
                       r"\b(?:cut|reduce|trim|slash)\w*\s+(?:my\s+|our\s+)?(?:spending|expenses|budget)\s+(?:by\s+|in\s+)?(half|a half|a third|a quarter|a fourth|a fifth|a tenth)\b")
SPEND_LESS_BARE = re.compile(r"\b(?:spend|spending)\s+(?:a (?:bit|little)\s+)?less\b|\b(?:cut|reduce|trim)\w*\s+(?:my\s+|our\s+)?(?:spending|expenses)\b")


def spending_less(low: str) -> dict[str, Any]:
    """{"_spend_less": dollars a year} or {"_spend_less_pct": share}, plus "_spend_now" for 'less now and save it'."""
    out: dict[str, Any] = {}
    m = LESS_AFTER.search(low)
    per = None
    if m:
        v, per = _val(m), _period(m.group("mid"), m.group("post"))
    else:
        m = CUT_BY.search(low) or CUT_FROM.search(low)
        if m:
            v, per = _val(m), _period(m.group("post"))
    if m:
        out["_spend_less"] = per_year(v, per)
    else:
        p = LESS_PCT.search(low)
        f = LESS_FRAC.search(low)
        if p:
            out["_spend_less_pct"] = float(p.group("p") or p.group("q")) / 100
        elif f:
            out["_spend_less_pct"] = round(FRACTION[f.group(1) or f.group(2) or f.group(3)], 4)
    if out and re.search(r"\bless (?:now|today)\b|\band save it\b|\bsave (?:it|the difference)\b", low):
        out["_spend_now"] = True
    return out


PT_WORDS = re.compile(r"\bpart time\b|\bconsult\w*|\bside (?:gig|job|work|hustle)\b|\bsemi[- ]?retire\w*|\bfreelanc\w*|\bwork (?:a little|a bit)\b")
RETIRE_PATTERNS = [
    r"\bretir\w*(?:\s+early|\s+earlier|\s+later)?\s+(?:at|by|around|about|when (?:i|we)(?:'m| am|'re| are)?|age)\s*(?:age\s+)?(\d{2})\b",
    r"\bretir\w*\s+(?:at\s+)?(\d{2})\b",
    r"\b(?:stop|stopped|stopping|quit|quitting|leave|leaving|finish|finishing|cease)\w*\s+(?:working|work|my job|the job|our jobs|my career)?\s*"
    r"(?:at|by|around|about|when (?:i|we)(?:'m| am|'re| are)?|age)\s*(?:age\s+)?(\d{2})\b",
    r"\b(?:work|worked|works|working|stay|stayed|staying|keep working|kept working|continue working|carry on|go on working|hang on|hung on|hold on|"
    r"stick it out|keep going|kept going|soldier on)(?:\s+on)?\s+(?:until|till|til|to|through|up to)\s+(?:age\s+)?(\d{2})\b",
    r"\b(?:until|till|til)\s+(?:age\s+)?(\d{2})\s+(?:instead|rather)\b",
]
CLAIM_PATTERNS = [
    r"\b(?:wait|waiting|waited|delay|delaying|delayed|hold off|held off|put off)\w*\s+(?:until|till|til|to)\s+(?:age\s+)?(\d{2})\b[^.?!]{0,25}\b(?:claim\w*|social security|benefits?|ss)\b",
    r"\b(?:wait|waiting|waited|delay|delaying|delayed|hold(?:ing)? off|held off|put(?:ting)? off)\w*\s+(?:on\s+|claiming\s+)?(?:my\s+|our\s+|the\s+)?(?:social security|benefits?|ss)\b"
    r"[^.?!\d]{0,12}?\b(?:until|till|til|to|at)\s+(?:age\s+)?(\d{2})\b",
    r"\b(?:claim\w*|take|taking|took|takes|start|starting|started|collect\w*|begin\w*|began|draw\w*|get|getting)\s+(?:my\s+|our\s+|the\s+)?(?:social security|benefits?|ss)\b"
    r"[^.?!]{0,25}?\b(?:at|age|until|till|til|by)\s+(?:age\s+)?(\d{2})\b",
    r"\b(?:claim\w*)\b[^.?!]{0,12}?\b(?:at|age|until|till|til)\s+(?:age\s+)?(\d{2})\b",
]
SS_WORD = re.compile(r"\bsocial security\b|\bbenefits?\b|\bss\b|\bclaim\w*")


def _first(patterns: list[str], low: str) -> int | None:
    for pat in patterns:
        m = re.search(pat, low)
        if m:
            return int(m.group(1))
    return None


YEARS = r"(\d{1,2}|a|an|one)\s+(?:more\s+|extra\s+)?years?"
NOW = re.compile(r"\b(?:retir\w*|stop\w* working|quit\w*(?: my job| work(?:ing)?| the job)?|leave (?:my|the) job|call it quits)\s+"
                 r"(?:right\s+)?(?:now|today|immediately|this year|straight away|at once)\b|"
                 r"\b(?:quit\w*|leave|left)\s+(?:my|the|our)\s+jobs?\s+(?:right\s+)?(?:now|today)\b[^.?!]{0,15}\bretir\w*")


def _n(word: str) -> int:
    return 1 if word in ("a", "an", "one") else int(word)


def retire_relative(low: str, age: int | None, current: int | None) -> int | None:
    """'retire now', 'retire next year', 'two years later', 'push retirement back by 2 years', 'keep going another 4 years'."""
    if age is not None and NOW.search(low):
        return age
    if age is not None and re.search(r"\bretir\w*\s+next year\b", low):
        return age + 1
    if current is None:
        return None
    m = re.search(r"\b(?:retir\w*|stop\w* working|quit\w*)\s+" + YEARS + r"\s+(earlier|sooner|early|before|later|late|after)\b", low)
    if m:
        return current + (_n(m.group(1)) if m.group(2) in ("later", "late", "after") else -_n(m.group(1)))
    m = re.search(r"\b(?:push\w*|delay\w*|postpon\w*|put\w* off|mov\w*)\s+(?:my\s+|our\s+|the\s+)?retirement\s+(?:back\s+|out\s+|later\s+)?(?:by\s+)?" + YEARS + r"(?:\s+(?:back|later))?\b", low)
    if m:
        return current + _n(m.group(1))
    m = re.search(r"\b(?:bring\w*|brought|mov\w*)\s+(?:my\s+|our\s+|the\s+)?retirement\s+(?:forward|up|earlier)\s+(?:by\s+)?" + YEARS, low)
    if m:
        return current - _n(m.group(1))
    m = re.search(r"\b(?:work\w*|stay\w*|keep (?:going|working|at it)|kept (?:going|working|at it)|carry on|hang on|stick it out)\s+(?:for\s+)?"
                  r"(?P<pre>another\s+|an extra\s+|an additional\s+)?(?P<n>\d{1,2}|a|an|one)\s+(?P<more>more\s+|extra\s+|additional\s+)?years?(?P<post>\s+longer)?\b", low)
    if m and (m.group("pre") or m.group("more") or m.group("post")):
        return current + _n(m.group("n"))
    return None


def retire_age(low: str, age: int | None, current: int | None) -> int | None:
    """The retirement age a What If names: 'stop at 62', 'work until 66', 'retire in 5 years', 'work 3 more years'."""
    if re.search(r"\bsocial security\b|\bmedicare\b|\bclaim\w*\b", low) and not re.search(r"\bretir\w*\s+(?:at\s+)?\d{2}\b|\b(?:stop|work)\w*\b[^.?!]{0,12}\b\d{2}\b|"
                                                                                       r"\bretir\w*\s+(?:right\s+)?(?:now|next year)\b|\bretir\w*\s+\d{1,2}\s+years?\b", low):
        return None
    pt = PT_WORDS.search(low) is not None
    cut = re.sub(r"\bpart time\b[^.?!]{0,40}?(?:until|till|til|to|through)\s+(?:age\s+)?\d{2}\b", " ", low) if pt else low
    cut = re.sub(r"\b(?:claim\w*|social security|benefits|ss)\b[^.?!]{0,30}?\b(?:until|till|til|to|at)\s+(?:age\s+)?\d{2}\b", " ", cut)
    a = _first(RETIRE_PATTERNS, cut)
    if a is not None:
        return a
    m = re.search(r"\bretir\w*\s+in\s+(\d{1,2})\s+years?\b", low)
    if m and age is not None:
        return age + int(m.group(1))
    return retire_relative(cut, age, current)


def claim_age(low: str, age: int | None = None) -> int | None:
    """A Social Security claiming age: 'claim at 70', 'take ss at 62', 'as early as possible', 'at full retirement age'."""
    a = _first(CLAIM_PATTERNS, low)
    if a is not None:
        return a
    if not SS_WORD.search(low):
        return None
    if re.search(r"\b(?:as (?:early|soon) as (?:possible|i can|we can)|right away|at the earliest|earliest (?:possible|age))\b", low):
        return max(62, age or 62)
    if re.search(r"\b(?:as late as (?:possible|i can|we can)|until the max\w*|at the latest|latest (?:possible|age))\b", low):
        return 70
    if re.search(r"\bfull retirement age\b|\bfra\b", low) and (age or 0) <= 66:
        return 67
    return None


# ---------------------------------------------------------------- pets: "a second dog", "5 dogs" (in all), "get 5 dogs" (more), "one fewer cat"
PET_KIND = (r"dogs?|pupp(?:y|ies)|pups?|cats?|kittens?|kitties|pets?|rabbits?|bunn(?:y|ies)|birds?|parrots?|horses?|ponies|pony|hamsters?|"
            r"guinea pigs?|fish|turtles?|lizards?|chickens?|goats?")
COUNT = r"(?:(?P<n>\d{1,3})|(?P<one>another|a new|a second|a third|a fourth|a fifth|an|a|one))"
ORDINAL = {"a second": 2, "a third": 3, "a fourth": 4, "a fifth": 5}
ITEM = re.compile(r"(?:" + COUNT + r"\s+)?(?:(?P<mod>more|extra|additional|fewer|less)\s+)?(?:new\s+|little\s+|small\s+|big\s+|second\s+|third\s+|rescue\s+|"
                  r"family\s+)?(?P<kind>" + PET_KIND + r")\b(?P<all>\s+(?:in all|in total|total|altogether|all told))?")
MORE_VERBS = (r"get|gets|got|getting|adopt|adopts|adopted|adopting|buy|bought|buying|add|added|adding|take in|took in|taking in|rescue|rescued|"
              r"rescuing|bring home|brought home|foster|fostered|fostering|welcome|welcomed|take on|took on")
ALL_VERBS = r"have|has|had|having|own|owns|owned|keep|kept|end up with|ended up with|wind up with|look after|care for|live with"
PET_VERB = re.compile(r"\b(?P<verb>" + MORE_VERBS + "|" + ALL_VERBS + r")\s+(?:the kids\s+|the children\s+|us\s+|me\s+|ourselves\s+|myself\s+|"
                      r"(?:a total of|in all|in total)\s+)?(?=(?:\d|a\b|an\b|one\b|another\b|more\b|extra\b|new\b|little\b|small\b|big\b|second\b|third\b|"
                      r"rescue\b|family\b|" + PET_KIND + r"))")
NO_PET = re.compile(r"\b(?:no|without|didn'?t have|did not have|don'?t have|do not have|got rid of|get rid of|give away|gave away|rehome\w*|"
                    r"give up|gave up|lose|lost)\s+(?:the\s+|our\s+|my\s+|any\s+|a\s+|both\s+|all (?:the |our |my )?|any more\s+)?"
                    r"(?:" + COUNT.replace("?P<n>", "?P<nn>").replace("?P<one>", "?P<oneone>") + r"\s+)?(?P<kind>" + PET_KIND + r")\b")


def _kind(word: str) -> str:
    w = word.lower()
    return "dog" if w.startswith(("dog", "pup")) else "cat" if w.startswith(("cat", "kitt")) else "other"


def pets(low: str) -> list[tuple[str, str, int]]:
    """Each pet change named: (kind, "more" | "all" | "fewer" | "none", count). 'get 5 dogs' is 5 more; 'have 5 dogs' and
    '5 dogs in all' are 5 in all; 'one fewer cat' is 1 fewer; 'no dogs' or 'get rid of the dog' is none of that kind."""
    out: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    for m in NO_PET.finditer(low):
        word = m.group("kind")
        k = _kind(word)
        if m.group(0).split()[0] in ("lose", "lost") and not re.search(r"s$", word) and not m.group("nn"):
            out.append((k, "fewer", 1))           # "lose a dog": one fewer
        elif m.group("nn") and int(m.group("nn")) > 0 and m.group(0).split()[0] in ("lose", "lost", "give", "gave", "rehome", "rehomed", "rehoming"):
            out.append((k, "fewer", int(m.group("nn"))))
        else:
            out.append((k, "none", 0))
        seen.add(k)
    for v in PET_VERB.finditer(low):
        verb = v.group("verb")
        mode0 = "more" if re.fullmatch(MORE_VERBS, verb) else "all"
        pos = v.end()
        while True:                                  # "a dog and a cat", "two dogs, a cat and a rabbit"
            m = ITEM.match(low, pos)
            if not m:
                break
            k = _kind(m.group("kind"))
            mod, one = m.group("mod"), (m.group("one") or "")
            n = int(m.group("n")) if m.group("n") else 1
            if mod in ("fewer", "less"):
                mode = "fewer"
            elif one in ORDINAL:
                mode, n = "ordinal", ORDINAL[one]      # "a third dog": the third in all, or one more if there are already that many
            elif mod or one in ("another", "a new"):
                mode = "more"
            elif m.group("all"):
                mode = "all"
            else:
                mode = mode0
            if one == "" and not m.group("n") and mode == "all" and m.group("kind").endswith("s") and m.group("kind") not in ("fish",):
                break                                # "if we had dogs": no count, nothing to model
            if k not in seen:
                out.append((k, mode, n))
                seen.add(k)
            nxt = re.match(r"\s*(?:,\s*|\s+and\s+|\s+plus\s+|,\s*and\s+)", low[m.end():])
            if not nxt:
                break
            pos = m.end() + nxt.end()
    for m in re.finditer(r"\b(?:(\d{1,3})\s+(fewer|less|more|extra)|(another|a second|a third|one more|1 more))\s+(?P<kind>" + PET_KIND + r")\b", low):
        k = _kind(m.group("kind"))
        if k in seen:
            continue
        if m.group(3):
            out.append((k, "ordinal", ORDINAL[m.group(3)]) if m.group(3) in ORDINAL else (k, "more", 1))
        else:
            out.append((k, "fewer" if m.group(2) in ("fewer", "less") else "more", int(m.group(1))))
        seen.add(k)
    for m in re.finditer(r"\b(\d{1,3})\s+(?P<kind>" + PET_KIND + r")\s+(?:in all|in total|total|altogether)\b", low):
        k = _kind(m.group("kind"))
        if k not in seen:
            out.append((k, "all", int(m.group(1))))
            seen.add(k)
    return out


def pet(low: str) -> tuple[str, int] | None:
    """('dog'|'cat'|'other', how many more) for 'get a second dog', 'adopt two cats', 'another pet' (the first 'more' change)."""
    for kind, mode, n in pets(low):
        if mode == "more":
            return kind, n
    return None


def pet_counts(low: str, current: list[dict]) -> tuple[list[dict], list[tuple[str, int, int]]] | str | None:
    """The pets after the What If and [(kind, before, after)] for each kind that changes, a reason it cannot run, or None."""
    said = pets(low)
    if not said:
        return None
    now = [dict(x) for x in current]
    have = {x["kind"]: x["count"] for x in now}
    changed = []
    for kind, mode, n in said:
        before = have.get(kind, 0)
        after = before + n if mode == "more" else n if mode == "all" else max(n, before + 1) if mode == "ordinal" else max(0, before - n) if mode == "fewer" else 0
        if mode in ("fewer", "none") and before == 0:
            word = "pet" if kind == "other" else kind
            return f"Your answers show no {word}s, so there is none to take away."
        if after > PET_MAX or n > PET_MAX:
            return f"I can plan for up to {PET_MAX} of one kind of pet. Try a smaller number."
        if after != before:
            changed.append((kind, before, after))
            have[kind] = after
    if not changed:
        return "same"
    out = [{"kind": k, "count": c} for k, c in have.items() if c > 0]
    return out, changed


PET_MAX = 10


# ---------------------------------------------------------------- children: "have a baby", "2 more kids", "twins", "3 kids" (in all)
KID = r"(?:kids?|child(?:ren)?|bab(?:y|ies)|little ones?|sons?|daughters?)"


def kids(low: str) -> tuple[str, int | None] | None:
    """("more", n), ("all", n) or ("fewer", n or None) for a What If about children; None when it names none."""
    if re.search(r"\bfewer\s+(?:\d+\s+)?" + KID + r"|\b(?:no|less)\s+kids\b|\bone less (?:kid|child)\b|\bwithout (?:the |our |any )?" + KID, low):
        return "fewer", None
    m = re.search(r"\b(twins|triplets)\b", low)
    if m and re.search(r"\b(?:have|had|having|get|got|adopt\w*|expect\w*)\b", low):
        return "more", 2 if m.group(1) == "twins" else 3
    m = re.search(r"\b(\d)\s+(?:more|extra|additional)\s+" + KID + r"\b", low)
    if m:
        return "more", int(m.group(1))
    if re.search(r"\b(?:another|one more|1 more|a new|a second|a third|a fourth|a fifth|a sixth)\s+(?:little\s+)?(?:baby|kid|child|son|daughter)\b", low):
        return "more", 1
    if re.search(r"\b(?:have|has|had|having|get|got|adopt\w*|expect\w*|welcome\w*)\s+(?:a|an?\s+other)\s+(?:little\s+)?(?:baby|child|kid|son|daughter)\b"
                 r"(?!\s+(?:support|care|benefit|credit|tax))", low) or re.search(r"\b(?:have|had|having|expect\w*)\s+(?:a\s+)?baby\b", low):
        return "more", 1
    m = re.search(r"\b(?:have|has|had|having|raise|raising|end up with)\s+(\d)\s+(?:kids|children|kid|child)\b", low)
    if m:
        return "all", int(m.group(1))
    return None


def part_time(low: str, current_per_year: float | None, retire_at: int | None = None) -> dict[str, Any]:
    """Part-time work: {"part_time": {per_year, until_age}} with an amount (or the one already given), else notes.
    'for 5 years after I retire' ends it 5 years after the retirement age."""
    if not PT_WORDS.search(low):
        return {}
    until = re.search(r"(?:until|till|til|to|through|age)\s+(?:age\s+)?(\d{2})\b", low)
    until_age = int(until.group(1)) if until and 50 <= int(until.group(1)) <= 90 else None
    span = re.search(r"\bfor\s+(\d{1,2}|a|an|one)\s+(?:more\s+)?years?\b(?:\s+(?:after|once)\s+(?:i|we)\s+retire\w*)?", low)
    if until_age is None and span and retire_at:
        until_age = retire_at + _n(span.group(1))
    amt = None
    for m in re.finditer(MONEY + r"(?P<post>[^.?!]{0,16})", low):
        v, raw = _val(m), m.group(0)
        if until and m.start("n") == until.start(1):
            continue
        if span and m.start("n") == span.start(1):
            continue
        per = _period(m.group("post"))
        if "$" not in raw and not m.group("s") and v < 1000 and per is None:
            continue
        amt = per_year(v, per, month_below=8000)
        break
    if amt is None and current_per_year:
        amt = current_per_year
    if amt is None:
        return {"_part_time_no_amount": until_age or True}
    return {"part_time": {"per_year": amt, "until_age": until_age}}


# ------------------------------------------------------------------ natural forms (round 3)
TRY_AGE = re.compile(r"^\W*(?:(?:what if|what about|how about|and what about|ok(?:ay)?,?|so)\s+)?(?:(?:i|we)\s+)?(?:try|trying|make it|go with|go for|say|test|use)\s+(?:age\s+)?(\d{2})\b\W*$|"
                     r"^\W*(?:what about|how about|what if)\s+(?:age\s+)?(\d{2})\W*$")


def try_age(low: str) -> int | None:
    """'what if i try 58', 'how about 62': a retirement age said in the shortest way."""
    m = TRY_AGE.match(low or "")
    return int(m.group(1) or m.group(2)) if m else None


SPEND_MORE = re.compile(r"\b(?:spend|spending|spends|spent)\b[^.?!$\d]{0,25}?" + MONEY + NOT_PCT + r"(?P<mid>[^.?!%]{0,25}?)\b(?:more|extra|higher)\b(?P<post>[^.?!]{0,25})|"
                        r"\b(?:spend|spending|spent)\s+(?:an?\s+)?(?:extra|additional|another)\s+" + MONEY.replace("(?P<n>", "(?P<n2>").replace("(?P<s>", "(?P<s2>") + r"(?P<post2>[^.?!]{0,25})")
MORE_PCT = re.compile(r"\b(?:spend|spending|spent)\b[^.?!$\d]{0,15}?(\d{1,3}(?:\.\d+)?)\s?(?:%|percent)\s*(?:more|higher)\b|"
                      r"\b(?:raise|increase|lift|bump)\w*\s+(?:my\s+|our\s+)?(?:spending|budget)\s+by\s+(\d{1,3}(?:\.\d+)?)\s?(?:%|percent)")


def spending_more(low: str) -> float | None:
    """Dollars a year more spent: 'spend 6,000 a year more', 'spend an extra $500 a month'."""
    m = SPEND_MORE.search(low or "")
    if not m:
        return None
    if m.group("n"):
        v, per = float(m.group("n").replace(",", "")) * SUFFIX.get((m.group("s") or "").lower(), 1), _period(m.group("mid"), m.group("post"))
    else:
        v, per = float(m.group("n2").replace(",", "")) * SUFFIX.get((m.group("s2") or "").lower(), 1), _period(m.group("post2"))
    return per_year(v, per)


def spending_more_pct(low: str) -> float | None:
    """'spend 10% more': the share more (0.10)."""
    m = MORE_PCT.search(low or "")
    return float(m.group(1) or m.group(2)) / 100 if m else None


PCT_MORE = re.compile(r"(?<!spend )(?<!spending )\b(\d{1,2}(?:\.\d+)?)\s?(?:%|percent)\s+more\s+(?:in\s+|into\s+|to\s+|of\s+)?(?:my\s+|the\s+|our\s+)?(?:401\s?\(?k\)?|ira|retirement|savings?)\b")
ALLOC = re.compile(r"\b\d{1,3}\s?(?:%|percent)\s*(?:of (?:it |my \w+ )?)?(?:in |into |to )?(?:stocks?|equit\w+|bonds?)\b|"
                   r"\b(?:in|into)\s+(?:stocks?|equit\w+|bonds?)\b[^.?!]{0,10}\d{1,3}\s?(?:%|percent)|\b(?:stocks?|bonds?|equity)\s+(?:allocation|share|mix|split)\b|"
                   r"\b(?:stocks?|bonds?)\s*/\s*(?:stocks?|bonds?)\b|\b\d{1,2}\s?/\s?\d{1,2}\s+(?:stocks?|portfolio|split)\b|"
                   r"\ball[- ]in on (?:the )?(?:stocks?|equities|the (?:stock )?market)\b|\b(?:all|only|just) (?:in )?(?:stocks|bonds|equities)\b|\beverything (?:in|into) (?:stocks|bonds)\b")


NOT_NAMES = {"I", "We", "My", "He", "She", "They", "You", "It", "Both", "Then", "The", "If", "What", "So", "And", "Or"}
OTHER_RETIRES = re.compile(r"(?i:\b(?:what if|if|and|suppose|what about|how about|then|but)\s+)([A-Z][a-z]{1,14})(?:'s)?\s+(?:(?i:retire\w*|stop\w*|quit\w*|work\w*|leav\w*|finish\w*))")
PARTNER_WORD = re.compile(r"\b(?:wife|husband|spouse|partner|girlfriend|boyfriend|fianc\w+)\b")


def other_person(q: str) -> str | None:
    """A named person other than the one asking ('what if Dave retires at 62'): the name, else None."""
    m = OTHER_RETIRES.search(q or "")
    return m.group(1) if m and m.group(1) not in NOT_NAMES else None
