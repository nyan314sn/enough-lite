"""Plan-chat answers that come from the plan's own fields, never from a source quote.

"where did $56,000 come from", "when does my money run out", "can I rely on this", "is my data private", bitcoin,
a bare number with no question to answer, and a What If the reader could not run. Each answer is plain words built in
code from the profile (its `sources`: you said, estimate, assumed, default) and the plan. No figure is invented.
"""
from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from . import ask_self, whatif_read
from .agents import intake_answers as answers
from .agents import intake_fields
from .agents import intake_support as sup
from .agents.parser_extra import money_in
from .schemas import Profile

ZERO = {"input": 0, "cached": 0, "output": 0}
CHIPS = ["Explain my plan", "Try a What If", "Change an answer"]
SOURCE_WORDS = {"you said": "your own answer", "estimate": "an estimate from typical figures for people like you, not something you said",
                "assumed": "an assumption: you did not say, so the plan uses a typical figure", "default": "a typical default"}


def reply(text: str, chips: list[str] | None = None, kind: str = "answer", intent: str = "question_plan") -> dict:
    out = {"kind": kind, "text": text, "citations": [], "quick_answers": chips or CHIPS, "tokens": dict(ZERO), "cost_usd": 0.0}
    if kind == "answer":
        out["intent"] = intent
    return out


def _num(x: Any) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or x != x or not 0 <= x <= 1e9:
        return None
    return float(x)


# ------------------------------------------------------------------ bitcoin and crypto
CRYPTO = re.compile(r"\b(?:bitcoin|btc|ethereum|dogecoin|doge|solana|xrp|ripple|cardano|litecoin|shiba inu|usdt|bnb|polkadot|chainlink|monero|stablecoins?|memecoins?|"
                    r"crypto\w*|altcoins?|\w+coins?)\b", re.I)
CRYPTO_LINE = ("Bitcoin and other crypto swing hard, and no one can say where they will go. So I don't pick them or tell you to buy or sell. "
               "If you hold some, include it in your savings total. To see a bad stretch, try 'markets fall 30%'.")


def pick_refusal(q: str) -> str | None:
    """Text for a refused 'which crypto / stock should I buy': one plain line, not the generic refusal."""
    return CRYPTO_LINE if CRYPTO.search(q) else None


# ------------------------------------------------------------------ bare numbers
BARE = re.compile(r"^\s*(?P<d>\$)?\s?(?P<n>\d[\d,]*(?:\.\d+)?)\s*(?P<u>k|thousand|m|million|%|percent|years?|yrs?|years old)?\s*[.!]?\s*$", re.I)
AGE_KEYS = {"age": (18, 110), "partner_age": (18, 110), "retire_age": (30, 80), "partner_retire_age": (30, 80), "children_count": (0, 15)}
MONEY_KEYS = {"pay_per_year", "partner_pay_per_year", "spending_now_per_year", "spending_per_year", "social_security_per_year", "savings", "home",
              "household_pay", "mortgage_payment", "mortgage_balance", "home_value"}
NAMES = {"age": "your age", "partner_age": "your partner's age", "retire_age": "your retirement age", "partner_retire_age": "your partner's retirement age",
         "children_count": "the number of children", "pay_per_year": "your pay", "partner_pay_per_year": "your partner's pay",
         "spending_now_per_year": "your spending", "spending_per_year": "your spending in retirement", "social_security_per_year": "your Social Security",
         "savings": "your savings", "home": "your home"}


def bare_value(q: str) -> tuple[float, str, bool] | None:
    """(number, unit, had a $ sign) when the whole message is one number, else None."""
    m = BARE.fullmatch(q.strip())
    if not m:
        return None
    v = float(m.group("n").replace(",", ""))
    unit = (m.group("u") or "").lower()
    v *= {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6}.get(unit, 1)
    return v, unit, bool(m.group("d"))


def _shown(v: float) -> str:
    return f"{v:,.0f}" if v == int(v) else f"{v:,.2f}"


def which_figure(v: float, unit: str) -> dict:
    n = _shown(v)
    chips = []
    if 30 <= v <= 80 and not unit and v == int(v):
        return reply(f"Do you mean retiring at {n}?", [f"What if I retire at {n}", f"My age is {n}" if 18 <= v <= 110 else "Change an answer", "Explain my plan"], kind="clarify")
    if 18 <= v <= 110 and not unit == "%":
        chips += [f"My age is {n}"]
    if 30 <= v <= 80 and not unit == "%":
        chips += [f"What if I retire at {n}"]
    if v >= 1000:
        chips += [f"My pay is ${n}", f"My savings are ${n}"]
    return reply(f"I am not sure what {n} is. Which figure do you mean? Say it in a sentence, for example: " +
                 ("my retirement age is 65." if v < 1000 else "my pay is $90,000 a year."), (chips + ["Change an answer", "Explain my plan"])[:4], kind="clarify")


def pending_bare(q: str, pending: dict | None) -> dict | None:
    """A bare number goes to the pending question's field only when it is plausible for it. Otherwise ask which field."""
    b = bare_value(q)
    if b is None:
        return None
    v, unit, dollar = b
    if not isinstance(pending, dict):
        return None
    key = pending.get("ask")
    if pending.get("facts"):
        if unit == "%" or v == v:
            return reply(f"I have a change waiting. Say Yes to make it or No to drop it. If {_shown(v)} is something else, say what it is, for example: my age is 65.",
                         ["Yes, rebuild", "No"], kind="clarify")
    if not isinstance(key, str):
        return None
    if key in AGE_KEYS:
        lo, hi = AGE_KEYS[key]
        if lo <= v <= hi and unit not in ("%", "k", "thousand", "m", "million") and not dollar:
            return None
    elif key in MONEY_KEYS:
        if v >= 1000 or unit in ("k", "thousand", "m", "million") or (dollar and v >= 100):
            return None
    else:
        return None
    what = NAMES.get(key, "that figure")
    out = which_figure(v, unit)
    out["text"] = f"{_shown(v)} does not look like {what}. " + out["text"]
    return out


# ------------------------------------------------------------------ "plan to age 95" and an expected inheritance
END_AGE = re.compile(r"\b(?:plan(?:ning)?|make (?:it|the money|my money|the plan) last|(?:money|savings|plan) (?:to |must |should |has to |needs to )?last|last)\s+(?:to|until|till|through|for)\s+"
                     r"(?:(?:age|i'?m|i am)\s+)?(\d{2,3})\b(?!\s*(?:k\b|%|years|yrs|months|dollars))", re.I)
INHERIT = re.compile(r"\binherit\w*|\bleave (?:me|us)\b[^.?!]{0,20}\b(?:money|\$)", re.I)
COUNT_IT = re.compile(r"\bcount (?:it|on it|that)|\binclude (?:it|that)|\bcounting on\b|\bplan on (?:it|getting)|\bplease count\b|\bwrong\b|\bfix\b|\bcorrect\b", re.I)


def plan_end_age(q: str, base: Profile, plan: dict | None) -> dict | None:
    """'plan to age 95', 'make it last to 95': the plan's end age. It comes from the life table and cannot be set, so say so.
    Never a change to the person's own age."""
    low = q.lower()
    m = END_AGE.search(low)
    if not m or re.search(r"\bretir\w*|\bwork\w*|\bsocial security\b|\bclaim\w*", low):
        return None
    n = int(m.group(1))
    if not (70 <= n <= 120) and "age" not in low:
        return None
    h = plan.get("horizon_age") if isinstance(plan, dict) and isinstance(plan.get("horizon_age"), int) else None
    mine = f" Your age stays {base.age}." if base.age else ""
    why = "Only about 1 in 4 households has anyone alive at that age, by the life table. I can't set it myself."
    if h is not None and n <= h:
        text = f"Your plan already runs to age {h}, past {n}. {why}{mine}"
    elif h is not None:
        text = f"Your plan runs to age {h}, not {n}. {why} To see a harder test, try a market fall or spending more.{mine}"
    else:
        text = f"The plan's end age comes from the life table, not from you, so I can't change it to {n}. {why}{mine}"
    return reply(text, ["What if markets fall 30%", "Explain my plan", "Change an answer"], intent="question_plan")


def inheritance_note(q: str) -> dict | None:
    """'I may inherit $300,000': information only. It is not certain, so the plan does not count it."""
    low = q.lower()
    if not INHERIT.search(low) or COUNT_IT.search(low) or not re.search(r"\b(?:i|we|my|our)\b", low):
        return None
    amts = [v for v, a, b in money_in(q, 1000) if not re.fullmatch(r"(?:19|20)\d\d", q[a:b].strip().lstrip("$"))]
    if not amts:
        return None
    return reply(f"A possible inheritance of ${amts[0]:,.0f} is noted for information. It is not counted, because it is not certain.",
                 ["Explain my plan", "Try a What If", "Change an answer"], intent="question_plan")


# ------------------------------------------------------------------ where did $X come from
PROV = re.compile(r"\bwhere\b[^.?!]{0,40}\b(?:come|came|get|got|from)\b|\bhow did you (?:get|come up|arrive|work out|figure|calculate|pick|choose|decide|know)\b|"
                  r"\bwhy did you (?:assume|use|put|pick|choose|say)\b|\bwhat(?:'s| is) (?:that|this|the \w+) based on\b|\bbased on what\b|"
                  r"\bwhere is (?:that|this|it) from\b|\bsource of (?:that|this|the)\b|\bwhat did you base\b|\bwhere do (?:these|those|the) (?:numbers|figures)", re.I)
PROV_PERSONAL = re.compile(r"\byou\b|\bthis\b|\bthat\b|\bthese\b|\bthose\b|\bassum\w*|\bnumbers?\b|\bfigures?\b|\bmy\b|\bour\b|\bplan\b", re.I)
FIG = re.compile(r"(?<![\w.])(?P<d>\$)?\s?(?P<n>\d[\d,]*(?:\.\d+)?)\s?(?P<s>k\b|thousand\b|million\b|m\b)?\s?(?P<p>%|percent\b)?", re.I)


def figures(text: str) -> list[tuple[float, bool, str]]:
    """(value, is a percent, as typed) for each figure in the text."""
    out = []
    for m in FIG.finditer(text or ""):
        raw = m.group("n").replace(",", "")
        try:
            v = float(raw)
        except ValueError:
            continue
        v *= {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6}.get((m.group("s") or "").lower(), 1)
        pct = bool(m.group("p"))
        if not pct and not m.group("d") and not m.group("s") and v < 100 and "," not in m.group("n"):
            continue            # a bare small number such as "2 kids" or "62" is not a dollar figure to trace
        out.append((v, pct, m.group(0).strip()))
    return out[:4]


def _row_numbers(row: dict, derived: bool = True) -> list[tuple[float, bool]]:
    nums: list[tuple[float, bool]] = []
    for v, pct, _ in figures(str(row.get("display") or "")):
        nums.append((v, pct))
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s?(?:%|percent)", str(row.get("display") or "")):
        nums.append((float(m.group(1)), True))
    val = row.get("value")
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        nums.append((float(val), False))
        if 0 < val < 1:
            nums.append((round(val * 100, 2), True))
    for v, pct in (list(nums) if derived else []):       # "$1,900" a month is $22,800 a year, and the other way round
        if not pct and v >= 1000:
            nums += [(round(v / 12), False), (v * 12, False)]
    return nums


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(0.5, 0.015 * abs(b)) if b >= 1000 else abs(a - b) < 0.51


def _plan_lines(plan: dict | None) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    if not isinstance(plan, dict):
        return out
    w = plan.get("wants") if isinstance(plan.get("wants"), dict) else {}
    n = plan.get("needs") if isinstance(plan.get("needs"), dict) else {}
    basis = {"typical": "typical costs for your state and household", "budget": "the budget you gave, with typical figures where you gave none"}.get(
        n.get("basis") if isinstance(n.get("basis"), str) else "", "typical costs for your state and household")
    for v, text in ((_num(w.get("per_year")), "the most you can spend a year and still have money in 90 of 100 market tests. The plan works it out from 2,000 market tests. It is not a figure you gave"),
                    (_num(w.get("above_basics_per_year")), "your wants, the part of what you can count on above your needs. The plan works it out. It is not a figure you gave"),
                    (_num(n.get("basics_per_year")), f"your needs (housing, food, transport, health care), built from {basis}"),
                    (_num(plan.get("spending_goal")), "your spending goal, the amount you want to spend a year"),
                    (_num(plan.get("social_security_per_year")), "your Social Security a year, from the figure you gave or the plan's estimate")):
        if v:
            out.append((v, text))
    return out


def _lower(label: str) -> str:
    return label[:1].lower() + label[1:] if label and not label.startswith(("Partner", "Social")) else label


TOPIC_ROWS = [(re.compile(r"\bsocial security\b"), "social_security_per_year"), (re.compile(r"\bpensions?\b"), "pensions"),
              (re.compile(r"\bsavings?\b|\bnest egg\b"), "savings"), (re.compile(r"\bmortgage\b|\brent\b|\bhome\b|\bhouse\b"), "home"),
              (re.compile(r"\bretire\w*\b"), "retire_age"), (re.compile(r"\bspending\b|\bspend\b"), "spending_per_year"), (re.compile(r"\bpay\b|\bsalary\b"), "pay_per_year")]


def provenance(q: str, base: Profile, plan: dict | None) -> dict | None:
    low = q.lower()
    figs = figures(q)
    if not PROV.search(low) or not (figs or PROV_PERSONAL.search(low)):
        return None
    try:
        rows = intake_fields.rows(base)
    except Exception:       # noqa: BLE001  a row that cannot be built is not a reason to fail the answer
        rows = []
    if base.savings_known and base.savings.total > 0:      # the savings total is not on any row
        src = next((r.get("source") for r in rows if r.get("key") == "savings"), "you said")
        rows = list(rows) + [{"label": "Savings", "display": f"${base.savings.total:,.0f} in all", "value": base.savings.total, "source": src, "key": "savings_total"}]
    lines: list[str] = []
    for v, pct, raw in figs:
        said = None
        def from_rows(derived: bool) -> str | None:
            for row in rows:
                if any(_close(v, x) and pct == is_pct for x, is_pct in _row_numbers(row, derived)):
                    src = SOURCE_WORDS.get(str(row.get("source")), str(row.get("source")))
                    return f"{raw} is {_lower(str(row['label']))}: {row['display']}. It is {src}." + (f" {row['note']}" if row.get("note") and row.get("source") != "you said" else "")
            return None

        said = from_rows(False)                  # a figure as the person gave it, then the plan's own lines, then a monthly or yearly twin
        if said is None and not pct:
            for x, text in _plan_lines(plan):
                if _close(v, x):
                    said = f"{raw} is {text}."
                    break
        if said is None:
            said = from_rows(True)
        if said is None and not pct and plan:
            for line in (plan.get("assumptions") or []):
                if isinstance(line, str) and any(_close(v, x) for x, _, _ in [(a, 0, 0) for a, _, _ in figures(line)]):
                    said = f"{raw} comes from the plan's assumptions: {re.sub(chr(10), ' ', line)[:260]}"
                    break
        lines.append(said or f"I can't trace {raw} to one of your answers or a line of the plan. Tell me where you see it on the page.")
    if not lines:
        for rx, key in TOPIC_ROWS:
            if rx.search(low):
                row = next((r for r in rows if r.get("key") == key), None)
                if row:
                    src = SOURCE_WORDS.get(str(row.get("source")), str(row.get("source")))
                    lines.append(f"{row['label']}: {row['display']}. It is {src}." + (f" {row['note']}" if row.get("note") and row.get("source") != "you said" else ""))
                    break
    if not lines:
        guessed = [r for r in rows if r.get("source") in ("estimate", "assumed", "default") and r.get("key") not in ("sex", "partner_sex")][:4]
        if guessed:
            lines.append("Anything marked \"you said\" is your own answer. The rest I filled in: " +
                         "; ".join(f"{_lower(str(r['label']))} ({r['display']}, {r['source']})" for r in guessed) +
                         ". Change any of them in your answers and the plan is rebuilt.")
        else:
            lines.append("Every figure comes from your own answers and the fixed assumptions on the plan page. "
                         "Those cover market returns, inflation and how long people live.")
    return reply(" ".join(lines[:3]), ["Change an answer", "Explain my plan", "Try a What If"])


# ------------------------------------------------------------------ when does my money run out
RUNOUT = re.compile(r"\b(?:when|what age|at what age|how long)\b[^.?!]{0,40}\b(?:run|runs|running|ran)\s+out\b|"
                    r"\b(?:when|what age|at what age)\b[^.?!]{0,30}\b(?:hit|hits|reach|reaches)\s+(?:zero|0)\b|\bhow long (?:will|does|would|can)\b[^.?!]{0,30}\b(?:last|go)\b|"
                    r"\b(?:when|what age)\b[^.?!]{0,25}\b(?:money|savings|nest egg)\b[^.?!]{0,20}\b(?:gone|depleted|used up|zero|finished|spent)\b|"
                    r"\b(?:will|would) (?:i|we) (?:run out|outlive)\b", re.I)


def _first_zero(ages: list, vals: list, start: int) -> int | None:
    for a, v in zip(ages, vals):
        if isinstance(a, (int, float)) and isinstance(v, (int, float)) and a >= start and v <= 0:
            return int(a)
    return None


def runs_out(base: Profile, plan: dict | None, results: dict | None) -> dict:
    ch = plan.get("chart") if isinstance(plan, dict) and isinstance(plan.get("chart"), dict) else {}
    ages, low, med = ch.get("ages"), ch.get("low"), ch.get("median")
    ok = all(isinstance(x, list) and x for x in (ages, low, med)) and len(ages) == len(low) == len(med)
    horizon = plan.get("horizon_age") if isinstance(plan, dict) and isinstance(plan.get("horizon_age"), int) else None
    m = (results or {}).get("markets") or {}
    n_goal = m.get("goal_lasts_of_100")
    start = base.retire_age or base.age or 0
    typical = _first_zero(ages, med, start) if ok else None
    bad = _first_zero(ages, low, start) if ok else None
    bits = []
    if ok:
        bits.append(f"In a typical run your money runs out around age {typical}." if typical else
                    f"In a typical run your money lasts through age {horizon or ages[-1]}, the last age the plan covers.")
        bits.append(f"In a bad run, one of the worst 1 in 10, it runs out around age {bad}." if bad else
                    f"Even in a bad run, one of the worst 1 in 10, it lasts through age {horizon or ages[-1]}.")
    else:
        bits.append(f"I don't have a run-out age for this plan. It is planned through age {horizon or 'your horizon'}.")
    if isinstance(n_goal, int):
        bits.append(f"At your spending goal the money lasts to the end in {n_goal} of 100 market tests.")
    return reply(" ".join(bits), ["Try a What If", "Explain my plan", "Change an answer"])


SAME_100_90 = re.compile(r"\b(?:100|hundred)\b[^.?!]{0,60}\b(?:90|ninety)\b|\b(?:90|ninety)\b[^.?!]{0,60}\b(?:100|hundred)\b", re.I)
EXPLAIN_100_90 = ("They count different things. \"Needs paid in 100 of 100\" covers only your needs: housing, food, transport and health care. "
                  "\"90 of 100\" covers the whole amount you can count on, needs and wants. "
                  "So your needs can be safe in every market test while the larger amount is safe in 90 of 100.")


# ------------------------------------------------------------------ privacy and "can I rely on this"
PRIV_STRONG = re.compile(r"\bprivacy\b|\bconfidential\w*|\bwho (?:sees|can see|gets|reads|has|stores)\b", re.I)
PRIV = re.compile(r"\b(?:private|secure|safe|stored?|saved|shared?|sold|sell|delete[ds]?|keep|kept|anonymous)\b", re.I)
DATA = re.compile(r"\b(?:data|information|info|answers|numbers|details|figures|conversation|chat|messages?|ssn|social security number)\b", re.I)
RELY = re.compile(r"\b(?:rely|trust|reliable|accurate|accuracy|guarantee\w*|how (?:good|sure|certain|accurate|reliable)|financial advice|"
                  r"is (?:this|it|that) (?:right|correct|true)|should i (?:follow|believe|trust|act on)|can i (?:depend|lean|bank) on|a real adviser)\b", re.I)
RELY_TEXT = ("Use it as a guide, not as advice. The numbers are chances from 100 paths markets might take, not promises, and they are only as good as your "
             "answers: the ones marked estimate or assumed are guesses you can correct. For a big decision, talk to a fee-only adviser who must act in your interest.")


# ------------------------------------------------------------------ a What If that could not be read
HYPO_Q = re.compile(r"\bwhat if\b|\bwhat happens (?:if|when)\b|\bwhat would happen\b|\bsuppose\b|\bif (?:i|we|my|our)\b|\bwhat about\b|\bhow about\b", re.I)
LEVER = re.compile(r"\b(?:retir\w*|stop\w*|quit\w*|work\w*|sav\w*|spend\w*|claim\w*|part time|mov\w*|pets?|dogs?|cats?|child\w*|babies|baby|kids?|"
                   r"debts?|mortgage|markets?|inflation|returns?|risk\w*|stocks?|bonds?|invest\w*|income|pay|raise|salary|pension|inherit\w*|insurance|"
                   r"home|house|downsiz\w*|college|rent|car|health|contribut\w*|put|add|cut|reduce|earn\w*|sell|buy)\b", re.I)
RULEQ = re.compile(r"\b(?:ira|401\s?\(?k\)?|roth|limit|rmd|required minimum|medicare|tax|taxes|bracket|catch[- ]up|hsa|irmaa|penalty|contribution)\b", re.I)
RETURNS = re.compile(r"\b(?:returns?|interest rates?|inflation|growth rate|stock market (?:goes|does)|recession)\b", re.I)


def can_save(base: Profile) -> bool:
    """Saving What Ifs only make sense for someone still at work with pay (audit: offered to retirees, they did nothing)."""
    return (base.retire_age or 65) > (base.age or 45) and base.household_pay() > 0


def save_chip(base: Profile) -> str:
    """The saving example chip, or for a retiree or someone with no pay a What If that can move their plan."""
    return "What if I save $500 more a month" if can_save(base) else "What if I spend $500 less a month"


def useful_whatifs(base: Profile) -> list[str]:
    """What Ifs that can change this person's plan, for a reply that has to say no to the one asked."""
    out = []
    if (base.retire_age or 65) > (base.age or 45):
        out += [f"What if I retire at {a}" for a in retire_examples(base)[:1]]
    out.append(save_chip(base))
    if base.claim_age is not None and (base.age or 0) < base.claim_age < 70 and (base.retire_age or 65) <= (base.age or 45):
        out.append("What if I claim Social Security at 70")
    out.append("What if markets fall 30%")
    return out[:3]


def retire_examples(base: Profile) -> list[int]:
    age, ra = base.age or 45, base.retire_age or 65
    out = [a for a in (ra - 3, ra + 2, ra + 5) if age <= a <= 75 and a != ra]
    return out[:2] or [min(80, max(age, ra) + 2)]


def unread_whatif(q: str, base: Profile) -> dict | None:
    """A hypothetical the reader could not run: say what can run, with buttons. Never a source quote."""
    low = q.lower()
    if not HYPO_Q.search(low) or low.strip(" .!?") == "try a what if":
        return None
    if RULEQ.search(low) and not LEVER.search(low):
        return None             # a rule question ("what if I miss Medicare enrollment"): the cited sources answer it
    a = retire_examples(base)
    if RETURNS.search(low):
        return reply("I can't set market returns or prices myself. The closest What If I can run is a market fall or a bad first decade.",
                     ["What if markets fall 30%", "What if we have a bad first decade"], kind="clarify")
    retired = (base.retire_age or 65) <= (base.age or 45)
    if re.search(r"\b(?:retir\w*|stop\w*|quit\w*)\b", low):
        if retired:
            return reply(f"You are already {base.age} and retired, so there is no retirement age to test. These What Ifs can change your plan:",
                         useful_whatifs(base), kind="clarify")
        return reply(f"At what age? Name it and I will run it, for example: what if I retire at {a[0]}.",
                     [f"What if I retire at {x}" for x in a] + [save_chip(base)], kind="clarify")
    if re.search(r"\b(?:long[- ]term care|nursing home|assisted living|care costs?)\b", low):
        why, chips = ("The plan has no separate long-term care cost to switch on, so I can't run that as a What If. "
                      "The closest are spending more for the years you picked, or a market fall."), ["What if I spend $10,000 a year more", "What if markets fall 30%"]
    elif re.search(r"\b(?:sav\w*|invest\w*|contribut\w*|401\s?\(?k\)?|ira)\b", low) and can_save(base):
        why, chips = ("I did not find an amount or a change in your message that I can model. Say how much, for example: what if I save $500 more a month."),             ["What if I save $500 more a month", f"What if I retire at {a[0]}"]
    elif re.search(r"\b(?:sav\w*|contribut\w*)\b", low):
        why, chips = (NO_SAVE_RETIRED if retired else NO_SAVE_NO_PAY), useful_whatifs(base)
    elif re.search(r"\b(?:spend\w*|cost\w*|expens\w*|budget)\b", low):
        why, chips = ("I did not find an amount in that. Say how much, for example: what if I spend $6,000 a year more."),             ["What if I spend $6,000 a year more", "What if I spend $500 less a month"]
    else:
        why, chips = ("I did not find a change I can test. I can test when you retire, spending and saving. "
                      "I can also test when Social Security starts, part-time work, a move, a child or pet, a debt, or a market fall."), useful_whatifs(base)[:2]
    return reply(why, chips, kind="clarify")


NO_SAVE_RETIRED = ("You have retired, so there is no pay to save from: the plan draws on your savings now. "
                   "Spending less does what saving more would. These What Ifs can change your plan:")
NO_SAVE_NO_PAY = ("Your answers show no pay, so there is nothing to save from. If you earn, add your pay in your answers first. "
                  "These What Ifs can change your plan:")


SPOUSE = re.compile(r"\b(?:husband|wife|spouse|partner)\b", re.I)
FORMER = re.compile(r"\b(?:passed|died|dead|late|widow\w*|gone|lost|former|ex|divorced|deceased)\b", re.I)
ASSUME = re.compile(r"\bwhat (?:does|do|is|are) (?:the plan|you|it)\b[^.?!]{0,20}\bassum\w*|\bwhat are (?:the|your) assumptions\b|\bwhat do you assume\b", re.I)


# ------------------------------------------------------------------ the entry point
async def answer(q: str, base: Profile, plan: dict | None, get_plan: Callable[[], Awaitable[tuple[dict, Any]]]) -> dict | None:
    """The plan chat's own-fields answers. None means: not one of these, go on."""
    low = q.lower().strip()
    if CRYPTO.search(low) and not re.search(r"\bwhere\b|\bhow did\b", low):
        return reply(CRYPTO_LINE, ["Try a What If", "Explain my plan", "Change an answer"], intent="question_rule")
    end = plan_end_age(q, base, plan)
    if end is not None:
        return end
    inh = inheritance_note(q)
    if inh is not None:
        return inh
    b = bare_value(whatif_read.normalize(low)) if re.fullmatch(r"[a-z\- ]{3,20}", low) else bare_value(q)
    if b is not None:
        return which_figure(b[0], b[1])
    if PRIV_STRONG.search(low) or (PRIV.search(low) and DATA.search(low)):
        return reply(answers.PRIVACY, intent="question_rule")
    if RELY.search(low) and not ask_self.ASSUME_Q.search(low):
        if re.search(r"\bfinancial advice\b|\b(?:is|are) (?:this|it|that) advice\b", low):
            return reply(answers.ADVICE + " " + RELY_TEXT.split(". ", 1)[1], intent="question_rule")
        return reply(RELY_TEXT, intent="question_rule")
    if SAME_100_90.search(low) and re.search(r"\bwhy\b|\bdifferent\b|\bdiffer\w*|\bsame\b|\bchang\w*|\bconfus\w*|\bwhat'?s the difference\b", low):
        return reply(EXPLAIN_100_90)
    if RUNOUT.search(low):
        results = None
        if not (isinstance(plan, dict) and isinstance(plan.get("chart"), dict)):
            plan, ctx = await get_plan()
            results = ctx.results
        else:
            try:
                _, ctx = await get_plan()
                results = ctx.results
            except Exception:       # noqa: BLE001  the goal count is a nicety, never a reason to fail
                results = None
        return runs_out(base, plan, results)
    sp = SPOUSE.search(low)
    if sp and not base.has_partner and not base.partner_age and (FORMER.search(low) or re.search(r"\bage\b|how old", low)):
        who = sp.group(0)
        return reply((f"I am sorry about your {who}. " if FORMER.search(low) else "") +
                     "I plan for you on your own, so only your age counts.", ["Explain my plan", "Try a What If", "Change an answer"])
    if ask_self.ASSUME_Q.search(low) or (ask_self.about_plan(q) and not PROV.search(low)):
        if not (isinstance(plan, dict) and isinstance(plan.get("assumptions"), list) and plan.get("actions")):
            plan, _ = await get_plan()
        own = ask_self.answer(q, base, plan)
        if own:
            return own
    prov = provenance(q, base, plan)
    if prov:
        return prov
    return unread_whatif(q, base)
