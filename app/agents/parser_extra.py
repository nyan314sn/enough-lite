"""Rule parser for the optional detail: debts, pensions, saving, insurance, goals, health, costs.

Called by parser.parse(). Works clause by clause. Returns (facts, consumed): the facts, and the clauses it used, so the
savings parser does not read "$30k on student loans" or "$12,000 a year into my 401(k)" as a savings balance.
Percentages become fractions (6% -> 0.06). Money is a yearly figure unless the key says month.
"""
from __future__ import annotations

import re
from typing import Any

AMT = re.compile(r"(\$)?\s?(?<![\d,])(?<!\d\.)(\d[\d,]*(?:\.\d+)?)\s?(k|thousand|mm|m|million)?(?![\w%])", re.I)
MULT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mm": 1e6, "million": 1e6}
# 401(k), 403(b), 457(b) and 529 plans are product names: the number in them is never an amount
PRODUCT_NUM = re.compile(r"(?:401|403|457|529)\s?(?:\(\s?[kb]\s?\)|[kb]\b)|529\s+(?:plan|account)s?\b|457\s+plan\b", re.I)


def is_product(text: str, start: int) -> bool:
    """True when the number starting at `start` is part of a product name such as 401(k)."""
    return bool(PRODUCT_NUM.match(text, start))


PCT = re.compile(r"(?<![\d,])(?<!\d\.)(\d+(?:\.\d+)?)\s?(?:%|percent|per cent)", re.I)
PARTNER = r"(?:wife|husband|partner|spouse)"
YEAR = re.compile(r"\b(20[2-9]\d)\b")


def money_in(s: str, floor: float = 0) -> list[tuple[float, int, int]]:
    """(value, start, end) for each amount. A bare number counts only when it is at least `floor` or has $/k."""
    out = []
    for m in AMT.finditer(s):
        if is_product(s, m.start(2)):
            continue
        try:
            v = float(m.group(2).replace(",", ""))
        except ValueError:
            continue
        if m.group(3):
            v *= MULT[m.group(3).lower()]
        if (m.group(1) or m.group(3) or v >= max(floor, 100)) and not YEAR.fullmatch(m.group(2)) or (m.group(1) and not YEAR.fullmatch(m.group(2))):
            out.append((v, m.start(), m.end()))
    return out


def _per_month(s: str, end: int) -> bool:
    return bool(re.match(r"\s*(?:a|per|each|every|/)\s*(?:month|mo)\b|\s*monthly", s[end:end + 20], re.I))


def _per_year(s: str, end: int) -> bool:
    return bool(re.match(r"\s*(?:a|per|each|every|/)\s*(?:year|yr)\b|\s*(?:yearly|annually)", s[end:end + 20], re.I))


def yearly(s: str, v: float, end: int) -> float:
    return v * 12 if _per_month(s, end) else v


def clauses(text: str) -> list[str]:
    parts = re.split(r"\.(?!\d)|[;!?\n]|,\s+(?=[a-zA-Z])|\s+and\s+(?=(?:we|i|my|our|she|he)\s+(?:owe|get|have|also|want|plan|pay|put|contribute|are|will|expect|need))", text)
    return [c for c in (x.strip() for x in parts if x) if c]


DEBT_KIND = [("student", r"student (?:loans?|debt)|school loans?"), ("car", r"(?:car|auto|vehicle|truck) (?:loans?|payments?|debt)"),
             ("credit_card", r"credit[- ]cards?|cards? debt|card balance"), ("other", r"personal loans?|medical debt|\bdebts?\b|\bloans?\b")]
NEG = r"(?:\bno\b|\bnot\b|n't|\bnone\b|\bwithout\b|\bnever\b)"


def _debt_kind(s: str) -> str | None:
    for kind, pat in DEBT_KIND:
        if re.search(pat, s, re.I):
            return kind
    return None


def parse_debts(clause: str, inherit: str | None = None) -> list[dict]:
    """'we owe 30k on student loans at 6%' -> one debt. Several amounts in a clause give several debts."""
    low = clause.lower()
    if "mortgage" in low or re.search(NEG + r"[^.]{0,20}\b(?:debt|loans?|owe)", low):
        return []
    if not (inherit or re.search(r"\b(?:owe|owing|debts?|loans?|balance|borrowed)\b", low) or _debt_kind(low)):
        return []
    out = []
    pieces = [x for x in re.split(r"\s+and\s+|,\s+|,(?!\d{3})|\s*\+\s*", clause) if x.strip()]
    pieces = pieces if len([a for a in money_in(clause) if not _per_month(clause, a[2])]) > 1 else [clause]
    if len(pieces) > 1:
        # "making 62k, 45k in student loans at 7%, 8k saved": only the pieces that name a debt hold one
        debt_word = re.compile(r"\b(?:owe|owing|debts?|loans?|balance|borrowed|car|auto|truck|credit|cards?|student|medical|personal)\b", re.I)
        named = [pc for pc in pieces if debt_word.search(pc) or _debt_kind(pc)]
        if named:
            pieces = named
    rate_all = PCT.search(clause)
    for pc in pieces:
        amts = [a for a in money_in(pc) if not _per_month(pc, a[2]) or _debt_kind(pc)]
        if not amts:
            continue
        kind = _debt_kind(pc) or _debt_kind(clause) or inherit or "other"
        bal_amt = amts[0]
        bal = bal_amt[0]
        pay = None
        m = re.search(r"(?:paying|pay|payments? of|payment is|minimum)\s+(?:about\s+)?\$?\s?(\d[\d,]*(?:\.\d+)?)\s?(k)?\s*(?:a|per|/|each)?\s*(?:month|mo)?", pc, re.I)
        pm = re.search(r"\$?\s?(\d[\d,]*(?:\.\d+)?)\s?(k)?\s*(?:a|per|each|/)\s*month", pc, re.I)
        if pm and (pm.start() != bal_amt[1] or len(amts) > 1):
            pay = float(pm.group(1).replace(",", "")) * (1000 if pm.group(2) else 1)
        elif m and m.group(1) and float(m.group(1).replace(",", "")) != bal:
            pay = float(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1)
        if pay is not None and pay == bal:
            pay = None
        r = PCT.search(pc) or rate_all
        out.append({"kind": kind, "balance": bal, "rate": (float(r.group(1)) / 100) if r else None, "monthly_payment": pay})
    return out


NOT_NAMES = {"i", "we", "my", "our", "the", "she", "he", "they", "it", "a", "an", "this", "that", "and", "also", "but", "so", "his", "her", "their",
             "both", "each", "one", "once", "when", "if", "then", "now", "yes", "no", "hi", "hello", "thanks"}


def names_in(text: str) -> tuple[set[str], set[str]]:
    """(the partner's first names, the writer's own first names) read from the whole message: 'married to David', 'I'm Maria'."""
    partner = {m.group(1) for m in re.finditer(
        rf"(?:married to|marry|engaged to|with|and|my {PARTNER}|our {PARTNER}|{PARTNER}(?: is| named| called)?)[, ]+(?:named |called )?([A-Z][a-z]{{2,}})\b", text or "")
        if m.group(1).lower() not in NOT_NAMES}
    own = {m.group(1) for m in re.finditer(r"\b(?:I'?m|I am|my name is|this is|it'?s|name'?s)\s+([A-Z][a-z]{2,})\b", text or "")}
    return partner - own, own


def pension_owner(clause: str, has_partner: bool, partner_names: set[str], own_names: set[str]) -> str | None:
    """'partner' when a first name starts the clause and it is the partner's (named in the message, or any name but the writer's when
    the household has a partner); 'you' when it is the writer's own name."""
    m = re.match(r"\s*(?:and\s+|also\s+|but\s+)?([A-Z][a-z]{2,})\b(?=[^.]{0,30}\b(?:will|would|gets?|has|receives?|is (?:going|due|getting)|expects?)\b)", clause)
    if not m or m.group(1).lower() in NOT_NAMES:
        return None
    n = m.group(1)
    if n in partner_names:
        return "partner"
    if n in own_names:
        return "you"
    return "partner" if has_partner else None


def parse_pension(clause: str, has_partner: bool = False, partner_names: set[str] | None = None, own_names: set[str] | None = None) -> dict | None:
    low = clause.lower()
    if not re.search(r"\bpension\b|\bdefined benefit\b|\bannuity\b", low) or re.search(NEG + r"[^.]{0,15}\bpension", low):
        return None
    # "300k saved" next to a pension is the savings, not the pension
    amts = [a for a in money_in(clause) if not re.match(r"\s*(?:saved|in (?:savings|the bank|a 401|my 401|total|all)|total|put away)", clause[a[2]:a[2] + 20], re.I)]
    if not amts:
        return None
    v, s0, e0 = amts[0]
    per_year = yearly(clause, v, e0)
    out: dict[str, Any] = {"per_year": per_year, "who": "you"}
    if re.search(rf"\b(?:{PARTNER}|she|her)\b[^.]{{0,25}}\bpension|\b{PARTNER}'?s? pension", low):
        out["who"] = "partner"
    elif (who := pension_owner(clause, has_partner, partner_names or set(), own_names or set())):
        out["who"] = who
    m = re.search(r"(?:at|from|starting(?: at)?|beginning(?: at)?|when (?:i|she|he)(?:'m| am| is| turns?)?|age)\s+(?:age\s+)?(\d{2})\b(?!\s*%)", low)
    if m and 40 <= int(m.group(1)) <= 90:
        out["start_age"] = int(m.group(1))
    if re.search(r"cost[- ]of[- ]living|\bcola\b|inflation[- ]?(?:adjusted|protected|indexed)|indexed to inflation|keeps up with inflation", low):
        out["inflation_adjusted"] = True
    elif re.search(r"\bfixed\b|not (?:adjusted|indexed)|no (?:cola|cost[- ]of[- ]living|inflation)", low):
        out["inflation_adjusted"] = False
    m = re.search(r"(\d{2,3})\s?%\s+(?:to|for|goes to|continues to|paid to)\s+(?:a |the |my )?(?:survivor|surviving|spouse|wife|husband|partner)", low)
    if m:
        out["survivor_share"] = float(m.group(1)) / 100
    elif re.search(r"\b(?:full|100%) survivor\b|joint and (?:100%|full)|survivor gets (?:all|it all)", low):
        out["survivor_share"] = 1.0
    elif re.search(r"\bno survivor\b|ends when i die|stops when i die", low):
        out["survivor_share"] = 0.0
    return out


def parse_saving(clause: str, has_partner: bool) -> dict[str, Any]:
    low = clause.lower()
    out: dict[str, Any] = {}
    if re.search(r"\byou(?:'ve| have)? (?:put|placed|assumed|guessed|used|wrote|made it|entered)\b", low):
        return out          # "the $4,000 you put in Roth is wrong": the app's figure, not the person's saving
    mm = re.search(r"\bmatch(?:es|ing|ed)?\b", low)
    if mm:
        lead = re.search(r"(\d+(?:\.\d+)?)\s?%\s+(?:(?:employer|company|401\(?k\)?|retirement|plan)\s+)?match", low)     # "a 4% match"
        clause = clause[mm.start():]
        low = clause.lower()
        pcts = [float(x) / 100 for x in PCT.findall(clause)]
        if not pcts and lead:
            pcts = [float(lead.group(1)) / 100]
        if "dollar for dollar" in low or "dollar-for-dollar" in low or "100% match" in low:
            out["saving.match_rate"] = 1.0
            if pcts:
                out["saving.match_cap"] = [x for x in pcts if x != 1.0][0] if [x for x in pcts if x != 1.0] else DEFAULT_CAP
        elif len(pcts) >= 2:
            out["saving.match_rate"], out["saving.match_cap"] = pcts[0], pcts[1]
        elif len(pcts) == 1:
            out["saving.match_rate"], out["saving.match_cap"] = 1.0, pcts[0]
        elif re.search(r"\bno match|doesn'?t match|does not match|no employer match", low):
            out["saving.match_rate"], out["saving.match_cap"] = 0.0, 0.0
        if re.search(r"\bno match|doesn'?t match|does not match|no employer match", low):
            out["saving.match_rate"], out["saving.match_cap"] = 0.0, 0.0
        if out:
            return out
    acct = re.search(r"401\s?\(?k\)?|403\s?\(?b\)?|\b457\b|\btsp\b|\bira\b|\broth\b|retirement (?:account|plan)|\bplan\b", low)
    verb = re.search(r"\b(?:contribut\w*|put(?:ting)?|defer\w*|save|saving|invest\w*|max(?:ing)? out|deposit\w*)\b", low)
    if acct and verb and not re.search(r"\b(?:have|has|got|balance|worth|in my|saved up|total)\b[^.]{0,12}(?:\$|\d)", low) or (acct and verb and re.search(r"\b(?:a|per|each) (?:year|month)\b|% of", low)):
        who = "partner" if re.search(rf"\b(?:{PARTNER}|she|her)\b", low) and not re.search(r"\b(?:i|we|my)\s+(?:put|contribute|save|invest)", low) else "you"
        amts = money_in(clause)
        if amts:
            v, _, e0 = amts[0]
            out["saving.contrib_" + who] = yearly(clause, v, e0)
        else:
            m = PCT.search(clause)
            if m and who == "you":
                out["save_rate"] = float(m.group(1)) / 100
        return out
    if verb and re.search(r"\b(?:save|saving|invest|set aside|put away|put aside)\b", low) and re.search(r"(?:a|per|each|/)\s*month|monthly", low) \
            and not acct:
        amts = money_in(clause)
        if amts:
            v, _, e0 = amts[0]
            out["saving.other_per_month"] = v if _per_month(clause, e0) else v / 12
    return out


DEFAULT_CAP = 0.06
RETRACT_DEBTS = re.compile(r"\bno (?:other )?debts?(?: at all)?\b|\b(?:don'?t|do not) owe (?:anything|a thing|any)\b|\bowe nothing\b|\bnothing (?:owed|left to pay)\b|\bdebt[- ]free\b"
                           r"|\bno (?:car|truck|student|credit[- ]card) (?:loans?|debts?)\b", re.I)


def parse_saving_answer(text: str, has_partner: bool = False) -> dict[str, Any]:
    """A plain answer to the saving question: '$10,000 a year', '12000', '$500 a month', '10% of pay', 'nothing yet'.
    A share of pay is a saving rate, not a change of pay. A bare or yearly figure is the 401(k) or IRA saving a year."""
    t = (text or "").strip()
    low = t.lower().strip(" .!")
    if re.match(r"^(?:nothing|none|zero|0|nothing yet|not yet)\b", low) and not re.search(r"\d{2,}", low):
        return {"saving.contrib_you": 0.0}
    m = PCT.search(t)
    if m and not re.search(r"\bmatch", low):
        return {"save_rate": float(m.group(1)) / 100}
    if re.search(r"\bmatch", low):
        return {}
    amts = money_in(t, floor=100)
    if not amts:
        return {}
    v, _, e0 = amts[0]
    return {"saving.contrib_you": yearly(t, v, e0)}


def parse_insurance(clause: str) -> dict[str, Any]:
    low = clause.lower()
    out: dict[str, Any] = {}
    def neg_at(m) -> bool:
        return bool(re.search(NEG, low[max(0, m.start() - 22):m.start()]))

    m = re.search(r"\blong[- ]term care\b|\bltc\b", low)
    if m:
        out["insurance.ltc"] = not neg_at(m)
    m = re.search(r"\bdisability\b", low)
    if m:
        out["insurance.disability"] = not neg_at(m)
    m = re.search(r"\b(?:term|whole|universal|permanent)\b[^.]{0,12}\blife\b|\blife insurance\b|\blife cover\b|\bterm policy\b", low)
    if m:
        if neg_at(m) and not re.search(r"\b(?:term|whole)\b", low):
            out["insurance.life_kind"] = "none"
        else:
            out["insurance.life_kind"] = "whole" if re.search(r"\bwhole\b|\buniversal\b|\bpermanent\b", low) else "term"
            amts = money_in(clause)
            face = prem = None
            for v, s0, e0 in amts:
                near = low[max(0, s0 - 14):s0]
                if re.search(r"premium|paying|pay\b|costs?\b", near) or _per_month(clause, e0) or _per_year(clause, e0):
                    prem = yearly(clause, v, e0)
                else:
                    face = face or v
            if face is None and amts and prem is None:
                face = amts[0][0]
            if face is not None:
                out["insurance.life_face"] = face
            if prem is not None:
                out["insurance.life_premium"] = prem
    return out


BIG_WORDS = r"(?:wedding|boat|renovat\w*|remodel\w*|new car|car|roof|trip|cruise|vacation|down payment|second home|cabin|pool|surgery|tuition|kitchen|addition|rv)"


# money coming TO the person is a possible inheritance or gift, information only: "my aunt may leave me a house worth 200k", "I expect a $50,000 gift"
INHERIT_CUE = re.compile(r"\binherit\w*|\b(?:leave|leaves|leaving|left|will|may|might|gonna|going to)\s+(?:it\s+)?(?:to\s+)?(?:me|us)\b|\b(?:leave|leaves|leaving)\s+(?:me|us)\b", re.I)
GIFT_CUE = re.compile(r"\b(?:expect\w*|may|might|could|will|going to|promised|plans? to|getting|get|receiv\w+|given|giving (?:me|us))\b[^.]{0,50}\bgift\b|\bgift (?:from|of)\b[^.]{0,40}\b(?:next|in \d|when)|^\s*(?:an?\s+)?(?:\$\s?)?\d[\d,.]*\s*[km]?\s+gift\b|^\s*(?:an?\s+)?gift of \$?\d", re.I)


def parse_goals(clause: str) -> dict[str, Any]:
    low = clause.lower()
    out: dict[str, Any] = {}
    if re.search(r"\b(?:leave|leaving|pass on|bequeath|legacy|estate of)\b", low) and not re.search(r"\bleave (?:my|the) job\b|\bleave work\b", low) \
            and not INHERIT_CUE.search(low):
        amts = money_in(clause)
        if amts:
            out["goals.legacy"] = amts[0][0]
        elif re.search(r"\b(?:nothing|zero|spend it all|no legacy)\b", low):
            out["goals.legacy"] = 0.0
        elif re.search(r"\b(?:something|some|a little|a bit|money|anything|a legacy|an inheritance)\b", low):
            out["goals.legacy_wish"] = True        # "leave something to our daughter": a wish with no amount
    if re.search(r"\bcollege\b|\bschool\b|\buniversity\b|\btuition\b", low):
        if re.search(r"\bprivate\b", low):
            out["children.college_type"] = "private"
        elif re.search(r"\bpublic\b|state school|in[- ]state|community college", low):
            out["children.college_type"] = "public"
        elif re.search(r"\bno college\b|\bnot going to college\b|\bwon'?t go to college\b", low):
            out["children.college_type"] = "none"
        m = re.search(r"(?:pay|cover|fund)\w*\s+(?:for\s+)?(\d{1,3})\s?%", low)
        if m:
            out["children.college_share"] = min(1.0, float(m.group(1)) / 100)
        elif re.search(r"\b(?:pay|cover|fund)\w*\s+(?:for\s+)?half\b|\bhalf of (?:the )?college|\bhalf the cost", low):
            out["children.college_share"] = 0.5
        elif re.search(r"\b(?:pay|cover|fund)\w*\s+(?:for\s+)?(?:all|everything|in full|it all)\b|\bin full\b", low):
            out["children.college_share"] = 1.0
    ym = YEAR.search(clause)
    if ym and re.search(r"\b(?:plan|planning|buy|buying|build|need|will|going to|want to|expect|save for)\b|" + BIG_WORDS, low) \
            and not re.search(r"\bretire|\binherit|\bpension|\bsocial security|college", low):
        amts = [a for a in money_in(clause) if a[0] >= 500 and clause[a[1]:a[2]].strip() != ym.group(1)]
        if amts:
            lm = re.search(BIG_WORDS, low)
            label = {"car": "New car", "new car": "New car"}.get(lm.group(0), lm.group(0).capitalize()) if lm else "Big cost"
            out["goals.big_cost"] = {"label": label, "amount": amts[0][0], "year": int(ym.group(1))}
    pm = re.search(r"\b(?:my |our |his |her )?(?:parents?|mother|mom|father|dad|in-laws?)\b", low)
    if pm and re.search(r"\b(?:help|support|care for|pay for|send|give)\w*\b", low):
        amts = money_in(clause)
        if amts:
            v, _, e0 = amts[0]
            out["goals.parents_per_year"] = yearly(clause, v, e0)
            y = re.search(r"for\s+(?:about\s+)?(\d{1,2})\s+years?", low)
            out["goals.parents_years"] = int(y.group(1)) if y else 10
    return out


def parse_other(clause: str, asking: str | None) -> dict[str, Any]:
    low = clause.lower()
    out: dict[str, Any] = {}
    if re.search(r"part[- ]time|consult\w*|side (?:gig|job|work)|freelanc\w*", low) and re.search(r"retire|until|till|after|\bage\b|\bto\b", low) or asking == "part_time":
        amts = money_in(clause)
        if amts and re.search(r"part[- ]time|consult\w*|side|freelanc\w*|work", low):
            v, _, e0 = amts[0]
            until = re.search(r"(?:until|till|to|through|age)\s+(?:age\s+)?(\d{2})\b", low)
            out["part_time"] = {"per_year": yearly(clause, v, e0), "until_age": int(until.group(1)) if until else None}
    gift = bool(GIFT_CUE.search(low)) and not INHERIT_CUE.search(low)
    if INHERIT_CUE.search(low) or gift:
        amts = [a for a in money_in(clause) if clause[a[1]:a[2]].strip() not in ()]
        amts = [a for a in amts if not YEAR.fullmatch(clause[a[1]:a[2]].strip().lstrip("$"))]
        if amts:
            ym = YEAR.search(clause)
            count = bool(re.search(r"\bcount (?:it|on it)|include it|counting on|plan on (?:it|getting)|we can count|please count", low)) \
                and not re.search(r"\b(?:don'?t|do not|not|never)\b[^.]{0,10}\b(?:count|include)", low)
            out["inheritance"] = {"amount": amts[0][0], "year": int(ym.group(1)) if ym else None, "count": count, **({"gift": True} if gift else {})}
    m = re.search(r"(?<![\d,])(?<!\d\.)(\d+(?:\.\d+)?)\s+months?\b[^.]{0,30}(?:expenses|spending|cash|emergency|saved)|emergency fund[^.]{0,20}?(?<![\d,])(?<!\d\.)(\d+(?:\.\d+)?)\s+months?", low)
    if m:
        out["emergency_months"] = float(m.group(1) or m.group(2))
    return out


BUDGET_WORDS = {"housing": r"(?:rent|mortgage|housing|home)", "food": r"(?:food|groceries|grocery|dining)", "transport": r"(?:transport\w*|car|gas|commut\w*)",
                "health": r"(?:health\w*|medical|insurance)", "childcare": r"(?:child ?care|daycare|day care|nanny|tuition)",
                "debt": r"(?:debt|loan|credit card)s?(?: payments?)?", "other": r"(?:other|everything else|misc\w*|fun|entertainment)"}


def parse_budget(text: str, asking: str | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    hits = {}
    for k, pat in BUDGET_WORDS.items():
        m = re.search(rf"\b{pat}\b([^\d$.;!?]{{0,14}})(\$?\s?\d[\d,]*(?:\.\d+)?\s?k?)(?!\s*%|\s*percent)", text, re.I)
        if m and re.search(r"\b(?:make|makes|earn|earns|at|owe|saved|save|match\w*)\b", m.group(1), re.I):
            m = None            # "I rent. I make $95,000", "loans at 6.5%": not a budget line
        if m and (re.search(r"\b(?:loans?|debts?|balance|owe|owed|left|worth|value)\b", m.group(1), re.I) or m.group(1).strip().lower() == "of"
                  or re.match(r"\s*(?:at|@)\s*\d", text[m.end():], re.I)):
            m = None            # "a car loan of $14,000 at 5%" is a balance owed, never a monthly cost
        if m:
            mm = AMT.search(m.group(2))
            if mm:
                v = float(mm.group(2).replace(",", ""))
                if mm.group(3):
                    v *= MULT[mm.group(3).lower()]
                hits[k] = v
    if len(hits) >= 2 or (asking == "budget" and hits):
        for k, v in hits.items():
            out["budget." + k] = v
    return out


NOW = r"\b(?:now|currently|right now|today|at the moment|these days|so far|presently)\b"


def parse_costs(clause: str, asking: str | None) -> dict[str, Any]:
    low = clause.lower()
    out: dict[str, Any] = {}
    if asking == "spending_later" or re.search(r"\bin retirement\b|\bwhen (?:i|we) retire|\bonce retired\b|\bafter (?:i|we) retire", low):
        if re.search(r"\b(?:same|as much|no change|about equal)\b", low) and not money_in(clause):
            out["retire_spend_ratio"] = 1.0
        elif re.search(r"\bless\b|\blower\b|\bcheaper\b", low) and not money_in(clause) and not PCT.search(clause):
            out["retire_spend_ratio"] = 0.8
        elif re.search(r"\bmore\b|\bhigher\b", low) and not money_in(clause):
            out["retire_spend_ratio"] = 1.2
        else:
            m = PCT.search(clause)
            if m and asking == "spending_later" and re.search(r"\b(?:owe|owing|loans?|debts?|rate|interest|match\w*|mortgage|return)\b", low) \
                    and not re.search(r"\bretire|\b(?:of|as much as)\b[^.]{0,12}\b(?:now|today|current)", low):
                m = None
            if m and asking == "spending_later" or (m and re.search(r"\b(?:of|as much as)\b[^.]{0,12}\b(?:now|today|current)", low)):
                out["retire_spend_ratio"] = float(m.group(1)) / 100
    return out


# ------------------------------------------------------------------ the group questions: chips and plain answers
GROUPS = {"debts": ("Add debts", ("debts",)), "pension": ("Add a pension", ("pensions",)),
          "saving": ("Add saving", ("saving.contrib_you", "saving.contrib_partner", "saving.match_rate", "saving.other_per_month", "save_rate")),
          "insurance": ("Add insurance", ("insurance.life_kind", "insurance.disability", "insurance.ltc")),
          "goals": ("Add goals", ("goals.legacy", "goals.big_cost", "goals.parents_per_year", "children.college_type", "children.college_share")),
          "health": ("Add health", ("health", "partner_health", "sex", "partner_sex")),
          "costs": ("Add costs", ("spending_now_per_year", "budget.housing", "retire_spend_ratio", "spending_spec", "emergency_months", "part_time", "inheritance"))}
CHIP_TO_GROUP = {v[0].lower(): k for k, v in GROUPS.items()}
SKIP_ALL = ("skip, use typical", "skip and use typical", "use typical", "skip all")
NO_ANSWER = re.compile(r"^\s*(?:no|none|nope|nothing|n/a|no\b.*(?:debts?|pension|insurance|goals?|cover)|none of these|not any|no special goals|no other debts)\s*[.!]?\s*$", re.I)
HEALTH_WORDS = {"excellent": "excellent", "great": "excellent", "very good": "excellent", "good": "good", "fine": "good", "okay": "good", "ok": "good",
                "average": "good", "fair": "fair", "so-so": "fair", "poor": "poor", "bad": "poor", "not good": "poor", "sick": "poor", "ill": "poor"}


def parse_health(t: str, asking: str | None, has_partner: bool) -> dict[str, Any]:
    low = t.lower().strip(" .!")
    out: dict[str, Any] = {}
    if asking == "health":
        for w in sorted(HEALTH_WORDS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(w)}\b", low):
                out["health"] = HEALTH_WORDS[w]
                break
    m = re.search(r"\b(?:my )?health(?: is| has been|'s)?\s+(excellent|great|very good|good|fair|poor|bad)", low) or \
        re.search(r"\bi(?:'m| am)\s+in\s+(excellent|great|very good|good|fair|poor|bad)\s+health", low) or \
        re.search(r"\bin\s+(excellent|great|very good|good|fair|poor|bad)\s+health\b", low)
    if m and not re.search(rf"\b{PARTNER}\b", low[:m.start()][-30:]):
        out["health"] = HEALTH_WORDS[m.group(1)]
    m = re.search(rf"\b{PARTNER}(?:'s)?\s+(?:health\s+)?(?:is|has|in)?\s*(?:in\s+)?(excellent|great|very good|good|fair|poor|bad)(?:\s+health)?", low)
    if m and re.search(r"health", low):
        out["partner_health"] = HEALTH_WORDS[m.group(1)]
    if asking == "sex":
        if re.search(r"\b(?:female|woman|women|girl|she|her)\b", low):
            out["sex"] = "female"
        elif re.search(r"\b(?:male|man|men|guy|he|him)\b", low):
            out["sex"] = "male"
    else:
        m = re.search(r"\bi(?:'m| am)\s+an?\s+(?:\d+[- ]year[- ]old\s+)?(male|female|man|woman)\b", low)
        if m:
            out["sex"] = "female" if m.group(1) in ("female", "woman") else "male"
    return out


def parse_retire_partner(t: str) -> dict[str, Any]:
    m = re.search(rf"\b(?:{PARTNER}|she|he)\b[^.;]{{0,30}}\bretire\w*\s+(?:at|by|around|when .{{0,10}} is)\s+(?:age\s+)?(\d{{2}})\b", t, re.I)
    return {"partner_retire_age": int(m.group(1))} if m else {}


def parse(text: str, asking: str | None = None, has_partner: bool = False, pending_kind: str | None = None) -> tuple[dict[str, Any], set[str]]:
    out: dict[str, Any] = {}
    consumed: set[str] = set()
    t = text.strip()
    low = t.lower().strip(" .!")
    if low in SKIP_ALL:
        out["skip_all"] = True
        return out, consumed
    if asking == "more":
        for chip, g in CHIP_TO_GROUP.items():
            if low == chip:
                out["open_group"] = g
                return out, consumed
    out.update(parse_health(t, asking, has_partner))
    out.update(parse_retire_partner(t))
    debts: list[dict] = []
    ins_all = parse_insurance(t)
    out.update(ins_all)
    segs = re.split(r"\.(?!\d)|[;!?\n]|\s+and\s+(?=(?:a |an |\$?\d)[^,]*?\b(?:loans?|cards?|debts?|owe)\b)", t)
    mortgage_ctx = asking in ("mortgage", "home") or bool(re.search(r"\bmortgage\b|\bown (?:it|the house|our home|my home)\b", t, re.I))
    for seg in segs:
        if not seg or not seg.strip():
            continue
        if mortgage_ctx \
                and not _debt_kind(seg.replace("debt", "")) and not re.search(r"\bother\b|\bbesides\b|\balso\b", seg, re.I):
            continue        # "I owe about 70k" at the mortgage question is the mortgage, not another debt
        d = parse_debts(seg.strip(), pending_kind if asking == "debts_detail" else None)
        debts += d
    pnames, onames = names_in(t)
    for c in clauses(t):
        used = bool(debts) and bool(re.search(r"\b(?:owe|owing|debts?|loans?|balance|borrowed|credit[- ]cards?)\b", c, re.I)) \
            and "mortgage" not in c.lower()
        pen = parse_pension(c, has_partner, pnames, onames)
        if pen:
            out.setdefault("pensions", []).append(pen)
            used = True
        sv = parse_saving(c, has_partner)
        if sv:
            out.update(sv)
            used = True
        if ins_all and re.search(r"insurance|\blife\b|disability|\bltc\b|long[- ]term care|premium|policy", c, re.I):
            used = True
        g = parse_goals(c)
        if g:
            if "goals.big_cost" in g:
                out.setdefault("goals.big_costs", []).append(g.pop("goals.big_cost"))
            out.update(g)
            used = True
        o = parse_other(c, asking if asking == "part_time" else None)
        if o:
            out.update(o)
            used = True
        co = parse_costs(c, asking)
        if co:
            out.update(co)
            used = True
        if used:
            consumed.add(c)
    from . import college as _college
    each = _college.parse(t)       # college child by child; a message that names no child keeps the flat reading
    if each and (any(not i["who"].get("all") for i in each) or any(i["ambiguous"] for i in each)
                 or not ({"children.college_type", "children.college_share"} & set(out))):
        out["children.college_each"] = each
        out.pop("children.college_type", None)
        out.pop("children.college_share", None)
    if "pensions" not in out:
        # "a pension from the county hospital, about $1,500 a month at 62": the figure sits in a later clause of the sentence
        for sentence in re.split(r"\.(?!\d)|[;!?\n]", t):
            pen = parse_pension(sentence, has_partner, pnames, onames)
            if pen:
                out.setdefault("pensions", []).append(pen)
                consumed.add(sentence.strip())
    if debts:
        out["debts"] = debts
    b = parse_budget(t, asking)
    if b:
        out.update(b)
        consumed.add(t)
    # a bare kind with no amount: "student loans" -> ask for the amount next
    if asking == "debts" and not debts and _debt_kind(low) and not NO_ANSWER.match(low):
        out["debt_kind_only"] = _debt_kind(low)
    if NO_ANSWER.match(t) or re.match(r"^\s*(?:no|none)\b", low):
        if asking == "debts":
            out["debts"] = []
        elif asking == "pension":
            out["pensions"] = []
        elif asking == "insurance":
            out["insurance.life_kind"] = "none"
            out["insurance.disability"] = False
            out["insurance.ltc"] = False
        elif asking == "goals":
            out["goals.none"] = True
        elif asking == "saving":
            out["saving.none"] = True
    if asking in ("saving", "save_rate") and not any(k.startswith("saving.") or k == "save_rate" for k in out):
        out.update(parse_saving_answer(t, has_partner))
    if "debts" not in out and RETRACT_DEBTS.search(t) and not re.search(NEG + r"[^.]{0,12}\bmortgage", low) and not re.search(r"\b(?:except|besides|other than|but)\b[^.]*\d", low):
        out["debts"] = []       # "the truck is paid off, so I have no debts at all": a retraction removes the debt and ends the question
    if asking == "insurance" and re.search(r"\bdisability only\b", low):
        out["insurance.disability"] = True
        out["insurance.life_kind"] = "none"
    return out, consumed
