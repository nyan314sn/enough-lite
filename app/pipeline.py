"""Runs the team: the specialists (concurrently where independent), then the adviser. Also What If and questions."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from . import ask_intent, ask_plan, ask_self, household, llm, safety, whatif_ai, whatif_read
from .agents import adviser
from .agents import college as college_each
from .agents.base import Emit, RunCtx, _no_emit, profile_facts, run_model
from .agents.family import Family
from .agents.longevity import Longevity
from .agents.markets import Markets
from .agents.parser import STATE_NAME, find_state
from .agents.research import NO_SOURCE, ask_prompt, build_ask_agent
from .agents.research import Research
from .agents.tax import Tax
from .schemas import Child, PartTime, Pet, Profile
from .tools import costs, family_costs, sources
from .tools import simulate as simulate_mod

LONGEVITY, FAMILY, TAX, RESEARCH, MARKETS = Longevity(), Family(), Tax(), Research(), Markets()
PHASE1 = (LONGEVITY, FAMILY, TAX, RESEARCH)
ALL = ("longevity", "family", "tax", "research", "markets", "adviser")


class PlanError(Exception):
    pass


BAD_PROFILE = "Some of your answers look wrong. Please check them."
STATE_CODES = frozenset(STATE_NAME) | {"DC"}
MONEY_MAX = 1e10     # no household figure is larger than this; anything above is a typing error or an attack


def _money_ok(x, path: str = "") -> bool:
    """Every number is finite, not negative and not absurd."""
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return True
    if isinstance(x, (int, float)):
        return x == x and 0 <= x <= MONEY_MAX
    if isinstance(x, dict):
        return all(_money_ok(v, str(k)) for k, v in x.items())
    if isinstance(x, (list, tuple)):
        return len(x) <= 50 and all(_money_ok(v, path) for v in x)
    return True


def validate_profile(p: Profile) -> None:
    """Range checks on top of the schema. Raises PlanError(BAD_PROFILE)."""
    # a partner may stop work at any adult age ("what if my partner stops working" sets it to their age now)
    ages = {"age": (18, 100), "partner_age": (18, 110), "retire_age": (30, 100), "partner_retire_age": (18, 100)}
    for k, (lo, hi) in ages.items():
        v = getattr(p, k)
        if v is not None and not (lo <= v <= hi):
            raise PlanError(BAD_PROFILE)
    if len(p.children) > 20 or len(p.pets) > 20 or len(p.debts) > 20 or len(p.pensions) > 20:
        raise PlanError(BAD_PROFILE)
    if any(c.age is not None and not (0 <= c.age <= 60) for c in p.children):
        raise PlanError(BAD_PROFILE)
    if any(not (0 <= x.count <= 50) for x in p.pets):
        raise PlanError(BAD_PROFILE)
    if not _money_ok(p.model_dump(exclude={"sources", "notes"})):
        raise PlanError(BAD_PROFILE)


def prepare(profile: dict | Profile) -> Profile:
    p = profile if isinstance(profile, Profile) else Profile.model_validate(profile)
    if p.age is None:
        raise PlanError("Please give your age before making a plan.")
    if not (18 <= p.age <= 100):
        raise PlanError("Please give an age between 18 and 100.")
    validate_profile(p)
    return household.complete(_clean_profile_text(p))


def _with_cost(ctx: RunCtx, emit: Emit) -> Emit:
    async def wrapped(event: dict) -> None:
        await emit(event)
        if event.get("type") == "agent_done":
            await emit(cost_event(ctx))
    return wrapped


def handoff(frm: str, to: str, message: str) -> dict:
    return {"type": "handoff", "from": frm, "to": to, "message": message}


def _who(p: Profile) -> str:
    if p.has_partner and p.partner_age:
        return f"a couple aged {p.age} and {p.partner_age}"
    return f"a person aged {p.age}"


def assignments(p: Profile) -> list[tuple[str, str]]:
    """What the lead asks each specialist. Built from the profile only."""
    out = [("longevity", f"How long must the money last for {_who(p)}?")]
    fam = []
    if p.children:
        fam.append(f"{len(p.children)} child" + ("ren" if len(p.children) != 1 else ""))
    for x in p.pets:
        fam.append(f"{x.count} {x.kind}{'s' if x.count > 1 else ''}")
    out.append(("family", (f"What will {' and '.join(fam)} cost, and what" if fam else "What") +
                f" will your needs cost once you retire in {p.state or 'the US'}?"))
    pay = p.household_pay()
    out.append(("tax", (f"How much tax on pay of ${pay:,.0f} a year now, and on withdrawals later?" if pay
                        else "How much tax on withdrawals in retirement?")))
    out.append(("research", f"Which official rules matter most at age {p.age}?"))
    return out


def feeds_to_markets(ctx: RunCtx) -> list[tuple[str, str]]:
    lon, fam, tx = ctx.results["longevity"], ctx.results["family"], ctx.results["tax"]
    out = [("longevity", f"Plan {lon.get('horizon_text') or 'to age ' + str(lon['horizon_age'])}.")]
    path = fam["per_year"]
    if path:
        msg = f"Yearly family costs, ${fam['this_year']:,.0f} this year"
        drops = [(path[t - 1] - path[t], t) for t in range(1, len(path))]
        big, t = max(drops, default=(0, 0))
        if big >= 5000:
            msg += f", with a drop of ${big:,.0f} at age {ctx.profile.age + t}"
        msg += f"; they end around age {fam['ends_at_age']}." if fam["ends_at_age"] else "."
        out.append(("family", msg))
    out.append(("family", f"Basics once retired: ${fam['basics']['basics_per_year']:,.0f} a year."))
    out.append(("tax", f"Tax takes about {round(tx['effective_rate_on_withdrawals'] * 100)}% of withdrawals."))
    return out


def markets_question(ctx: RunCtx) -> str:
    p = ctx.profile
    return (f"Will spending of ${p.spending_per_year:,.0f} a year last to age {ctx.results['longevity']['horizon_age']}? "
            "Test the strategies of similar households too.")


def feeds_to_adviser(ctx: RunCtx) -> list[tuple[str, str]]:
    m = ctx.results["markets"]
    out = [("markets", f"The goal lasts in {m['goal_lasts_of_100']} of 100 market tests; basics in {m.get('basics_paid_of_100')} of 100; "
                       f"safe spending ${m['safe_spending_per_year']:,.0f} a year, using the {m.get('strategy', 'simple plan').lower()}.")]
    moments = ctx.results["family"]["moments"]
    if moments:
        out.append(("family", f"{len(moments)} family moment{'s' if len(moments) != 1 else ''} to show, such as: {moments[0]}"))
    n = len((ctx.results.get("research") or {}).get("passages", []))
    out.append(("research", f"{n} official passage{'s' if n != 1 else ''} to cite." if n else "No passage found to cite."))
    return out


def cost_event(ctx: RunCtx) -> dict:
    return {"type": "cost", "total_tokens": sum(ctx.tokens.values()), "total_usd": round(ctx.cost_usd, 6),
            "budget_usd": llm.config.get_settings().run_budget_usd, "tokens": dict(ctx.tokens)}


async def run_plan(ctx: RunCtx, ai_agents: set[str] | None = None) -> dict:
    """The whole team. ai_agents limits which agents call the model (the rest use tools and templates)."""
    emit = ctx.emit
    ctx.emit = _with_cost(ctx, emit)
    if ctx.deadline is None:
        # model calls stop at a fixed time so a slow provider never holds the plan up; templates fill the rest
        ctx.deadline = time.monotonic() + llm.PLAN_AI_SECONDS
    await emit(cost_event(ctx))
    if ai_agents is not None:
        ctx.ai_agents = set(ai_agents)
    for to, msg in assignments(ctx.profile):
        await emit(handoff("adviser", to, msg))
    # specialists that do not depend on each other run together; their AI calls overlap
    await asyncio.gather(*(s.run(ctx) for s in PHASE1))
    for frm, msg in feeds_to_markets(ctx):
        await emit(handoff(frm, "markets", msg))
    await emit(handoff("adviser", "markets", markets_question(ctx)))
    await MARKETS.run(ctx)
    for frm, msg in feeds_to_adviser(ctx):
        await emit(handoff(frm, "adviser", msg))
    plan = await adviser.run(ctx)
    if ctx.ai_down and ctx.ai_down != "no_key" and ctx.use_ai:
        await emit({"type": "error", "message": plan["note"]})
    await emit(cost_event(ctx))
    return plan


async def tools_only_plan(profile: Profile) -> tuple[dict, RunCtx]:
    ctx = RunCtx(profile=profile, use_ai=False)
    plan = await run_plan(ctx)
    return plan, ctx


# ------------------------------------------------------------------ What If
AMT = r"\$?\s?(\d[\d,]*(?:\.\d+)?)\s?(k|thousand|m|million)?"
# assumptions of the What Ifs (round figures, named here, said aloud in the answer)
DOWNSIZE_SHARE = 0.6        # the new home costs this share of the old one
SELLING_COST = 0.06         # agent and closing costs, a share of the sale price
SAVE_ORDER = ("cash", "taxable", "roth", "pretax")    # where money comes from first
MOVE_ORDER = ("taxable", "roth", "pretax")            # what moves into cash for an emergency fund
NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12}
HYPO = re.compile(r"\bwhat if\b|\bsuppose\b|\bif (?:i|we|my|our)\b|\bwhat about\b|\bhow about\b|\binstead\b|\bwhat happens (?:if|when)\b|"
                  r"\bwhat would happen\b")
STARTS = re.compile(r"^\s*(?:another|get|adopt|have|retire|spend|save|move|pay off|build|raise|increase|downsize|claim|buy|sell|contribute|emergency fund|"
                    r"stop|quit|work|put|cut|reduce|delay|wait|earn|lower|trim)\b")
SAVE_RE = re.compile(r"\b(?:sav(?:e|es|ed|ing)|savings (?:rate|by|to)|contribut\w*|put(?:ting)?\s+(?:away|aside)|set(?:ting)?\s+aside|sock(?:ing|ed)?\s+away|"
                     r"stash\w*(?:\s+away)?|invest\w*)\b[^0-9$%]{0,30}?(\$)?\s?(\d[\d,]*(?:\.\d+)?)\s?(k\b|thousand\b|million\b|m\b)?\s?(%|percent\b|per cent\b)?", re.I)
SAVE_LESS = re.compile(r"\b(?:less|fewer|lower|cut\w*|reduc\w*|lower\w*|drop\w*)\b")
SAVE_UP_BY = re.compile(r"\b(?:bump|rais|increas|boost|up|lift)\w*\b[^.?!]{0,40}\bby\s+\$?\d")
STOP_SAVING = re.compile(r"\b(?:stop|stopped|quit|pause\w*)\s+(?:saving|contributing|putting money away)\b|\bsave nothing\b|\bno (?:more )?saving\b")


def _amount(m: re.Match) -> float:
    v = float(m.group(1).replace(",", ""))
    mult = (m.group(2) or "").lower()
    return v * {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6}.get(mult, 1)


def _is_product_number(text: str, m: re.Match, group: int) -> bool:
    """401(k), 403(b), 457(b) and 529 name products. They are never amounts."""
    return bool(re.match(r"(?:401|403|457|529)\s?(?:\(?[kb]\)?)?(?![\d,])", text[m.start(group):m.start(group) + 8], re.I)) \
        and m.group(group) in ("401", "403", "457", "529")


def _saving_change(low: str, p: Profile) -> dict[str, Any]:
    """Dollars (a year, a month or a week) are extra saving, or less with 'less'. A percent is a share of pay; 'by 3%' after
    'bump' or 'raise' is that much more. 'Stop saving' is none."""
    if STOP_SAVING.search(low):
        if p.saving.contrib_you is not None:
            return {"saving_contrib_you": 0.0, **({"saving_other_per_month": 0.0} if p.saving.other_per_month else {})}
        return {"save_rate": 0.0}
    for m in SAVE_RE.finditer(low):
        if _is_product_number(low, m, 2):
            continue
        v = float(m.group(2).replace(",", ""))
        suffix = (m.group(3) or "").lower()
        v *= {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6}.get(suffix, 1)
        tail = low[m.end():m.end() + 30]
        monthly = bool(re.match(r"[^.?!]{0,14}?(?:\b(?:a|per|each|every)\s*(?:month|mo)\b|/\s*(?:month|mo)\b|\bmonthly\b)", tail)) \
            or bool(re.search(r"\bmonthly\b", low[max(0, m.start() - 12):m.start()]))
        yearly = bool(re.match(r"[^.?!]{0,14}?(?:\b(?:a|per|each|every)\s*(?:year|yr)\b|\byearly\b|\bannually\b)", tail))
        weekly = bool(re.match(r"[^.?!]{0,14}?(?:\b(?:a|per|each|every)\s*(?:week|wk)\b|\bweekly\b)", tail))
        near = low[max(0, m.start() - 30):m.end() + 30]
        less = bool(SAVE_LESS.search(near)) and not re.search(r"\bspend\w*\b[^.?!]{0,12}\bless\b", low)
        more = bool(re.search(r"\bmore\b|\bextra\b|\banother\b|\badditional\b|\bon top\b", low)) or bool(SAVE_UP_BY.search(low)) \
            or bool(re.search(r"\bspend\w*\s+less\b[^.?!]{0,20}\bsav", low))       # "spend less now and save $250 a month": that much more
        if re.search(r"\bto\s+\$?\s?$", low[:m.start(2)]):
            less = more = False                     # "raise my savings rate to 20%", "lower it to $300 a month": the new total
        pay = max(1.0, p.household_pay())
        pct = bool(m.group(4)) or (not m.group(1) and not suffix and not monthly and not yearly and not weekly and v <= 60)
        if pct:
            rate = (p.save_rate or 0) + (-v if less else v) / 100 if (more or less) else v / 100
            rate = max(0.0, min(0.6, rate))
            if p.saving.contrib_you is not None:
                return {"saving_contrib_you": round(rate * (p.pay_per_year or pay), -1)}
            return {"save_rate": round(rate, 4)}
        per_year = v * 12 if monthly else v * 52 if weekly else v
        if less:
            # saving less: the yearly saving falls by that sum (never below none)
            if p.saving.contrib_you is not None:
                other = (p.saving.other_per_month or 0) * 12
                from_other = min(other, per_year)
                out = {"saving_contrib_you": round(max(0.0, p.saving.contrib_you - (per_year - from_other)), 2), "_extra_per_year": -per_year}
                if from_other:
                    out["saving_other_per_month"] = round((other - from_other) / 12, 2)
                return out
            return {"save_rate": round(max(0.0, (p.save_rate or 0) - per_year / pay), 4), "_extra_per_year": -per_year}
        if more:
            if p.saving.given() or pay <= 1.0:
                return {"saving_other_per_month": round((p.saving.other_per_month or 0) + per_year / 12, 2), "_extra_per_year": per_year}
            return {"save_rate": round(min(0.6, (p.save_rate or 0) + per_year / pay), 4), "_extra_per_year": per_year}
        if p.saving.contrib_you is not None:
            return {"saving_contrib_you": per_year}
        return {"save_rate": round(min(0.6, per_year / pay), 4), "_total_per_year": per_year}
    return {}


def _debt_tokens(tail: str) -> list[str]:
    out = []
    for tok, pat in (("credit_card", r"credit[- ]?cards?|\bcards?\b"), ("student", r"student|school loan"), ("car", r"\bcar\b|\bauto\b|vehicle|\btruck\b"),
                     ("mortgage", r"mortgage|\bhouse\b|\bhome\b"), ("high", r"high[- ]?(?:rate|interest)|expensive"), ("other", r"\bother\b|personal loan|medical")):
        if re.search(pat, tail):
            out.append(tok)
    if not out and re.search(r"\bdebts?\b|\bloans?\b|\ball of it\b|\beverything\b|\bwhat (?:i|we) owe\b", tail):
        out.append("all")
    return out


FALL_VERBS = r"fall|falls|fell|drop|drops|dropped|crash\w*|lose|loses|lost|down|plunge\w*|tank\w*|collaps\w*|tumbl\w*|halve\w*|sink\w*|sank|nosedive\w*|slump\w*"
FALL_RE = re.compile(r"\b(?:markets?|stocks?|shares?|the market|stock market)\b[^.?!]{0,30}?\b(?:" + FALL_VERBS + r")\b"
                     r"|\b(?:crash|fall|drop)\b[^.?!]{0,20}\b(?:markets?|stocks?)\b|\bbear market\b|\bmarket crash\b"
                     r"|\b(?:a|another|the next|there'?s a|there is a)\s+(?:big\s+|major\s+|huge\s+|bad\s+)?(?:crash|downturn|market drop)\b")
INFL_RE = re.compile(r"\b(?:high|higher|rising|runaway|bad|hot|sticky)\s+inflation\b|\binflation\s+(?:rises|stays high|spikes|of \d|is \d|runs|goes|hits|jumps|"
                     r"stays (?:at|above|over|around) \d|at \d|keeps)\b|\bprices\s+(?:keep\s+)?(?:going up|rising|rise|soar\w*|climb\w*|jump\w*)\b|\bstagflation\b")
DECADE_RE = re.compile(r"\bbad (?:first )?decade\b|\b(?:poor|bad|weak|low) returns?\b|\blost decade\b|\bbad start\b|\bbad first (?:ten|10) years\b|"
                       r"\breturns? (?:are|is|were|stay|turn out)\s+(?:bad|poor|weak|low)\b|\bbad sequence\b|\bsequence(?:-of-| of )returns?\b")


def parse_shock(low: str) -> dict | None:
    """A market What If: a fall now or at retirement ("markets fall 30%", "a crash when I retire"), high inflation for
    a decade, or a bad first decade of retirement."""
    if FALL_RE.search(low):
        m = re.search(r"(\d{1,2})\s?(?:%|percent)", low)
        size = int(m.group(1)) / 100 if m and 5 <= int(m.group(1)) <= 80 else 0.50 if re.search(r"\b(?:by half|in half|halve\w*|half (?:its|their) value)\b", low) else 0.30
        when = "retirement" if re.search(r"\b(?:when|as|once|after|the year|right after)\b[^.?!]{0,15}\bretir\w*|\bat retirement\b", low) else "now"
        return {"kind": "fall", "size": size, "when": when}
    if INFL_RE.search(low):
        return {"kind": "inflation"}
    if DECADE_RE.search(low):
        return {"kind": "bad_decade"}
    return None


def shock_words(s: dict) -> str:
    if s["kind"] == "fall":
        return (f"stocks fall {round(s['size'] * 100)}% " + ("in the year you retire" if s["when"] == "retirement" else "this year"))
    if s["kind"] == "inflation":
        return (f"inflation runs {round(simulate_mod.INFLATION_EXTRA * 100)} points above normal for the next {simulate_mod.SHOCK_YEARS} years")
    return (f"stocks earn {round(simulate_mod.BAD_DECADE_CUT * 100)} points a year less than usual in your first "
            f"{simulate_mod.SHOCK_YEARS} years of retirement")


PARTNER_STOPS = re.compile(r"\b(?:my|our)\s+(wife|husband|spouse|partner|boyfriend|girlfriend|fianc[eé]e?)\b[^.?!\d]{0,20}?\b(?:stops?|stopped|quits?|leaves?|gives? up|"
                           r"no longer|doesn'?t|does not|can'?t|cannot)\b[^.?!\d]{0,15}\b(?:work\w*|job|earning)\b"
                           r"|\b(?:my|our)\s+(?:wife|husband|spouse|partner)\b[^.?!\d]{0,10}\b(?:retires?|loses? (?:her|his|their) job)\b(?![^.?!]{0,12}\d)")


def parse_whatif(q: str, p: Profile) -> dict[str, Any]:
    low = whatif_read.normalize(q.lower())
    alloc = whatif_read.ALLOC.search(low)        # "80% in stocks" is a mix of investments, never the size of a market fall
    shock = parse_shock(whatif_read.ALLOC.sub(" ", low) if alloc else low)
    if shock:
        return {"shock": shock}
    if alloc:
        return {"_say": "I can't set an exact share in stocks. The plan has three styles: careful, balanced or growth. "
                        "Try one, or test a market fall.",
                "_chips": ["What if I choose a careful mix", "What if I choose a growth mix", "What if markets fall 30%"]}
    low = whatif_read.PCT_MORE.sub(lambda m: f"save {m.group(1)}% more", low)
    hypo = bool(HYPO.search(low))
    asked = bool(re.match(r"^\s*(?:can|could|may|when|how|at what age|is|are|does|do)\b", low)) and not re.search(r"\bwhat if\b", low)
    if not (hypo or re.search(r"\bcould (?:i|we)\b|\bcan (?:i|we)\b", low) or STARTS.match(low)):
        return {}
    firm = (hypo or bool(STARTS.match(low))) and not asked      # a plain hypothetical, not a rule question
    ch: dict[str, Any] = {}
    ra = whatif_read.retire_age(low, p.age, p.retire_age)
    if ra is None:
        ra = whatif_read.try_age(low)
    pm = PARTNER_STOPS.search(low) if ra is None else None
    if pm:
        # "what if my wife stops working": her pay stops now (no age to ask for)
        who = "your " + pm.group(1) if pm.group(1) in ("wife", "husband", "spouse", "partner") else "your partner"
        if not (p.has_partner and p.partner_age):
            return {"_say": "I plan for you on your own, so I do not model a partner's work.", "_chips": ask_plan.useful_whatifs(p)}
        if (p.partner_pay_per_year or 0) <= 0:
            she, her = {"wife": ("she stops", "her"), "husband": ("he stops", "his")}.get(pm.group(1) or "", ("they stop", "their"))
            return {"_say": f"Your answers show no pay for {who}, so nothing would change if {she} working. "
                            f"If that is wrong, add {her} pay in your answers first.", "_chips": ask_plan.useful_whatifs(p)}
        return {"partner_retire_age": int(p.partner_age), "_partner_name": who, "_partner_now": True}
    if ra is not None:
        if 40 <= ra <= 80:
            who = whatif_read.other_person(q)
            other = who or (re.search(r"\b(?:wife|husband|spouse|partner|she|he)\b[^.?!]{0,15}\b(?:retire|stop|quit|work|leave)", low)
                            and not re.search(r"\bboth\b|\bwe\b|\bi (?:retire|stop|quit|work)", low))
            if other:       # someone else's retirement never changes the person's own age
                name = who or "your partner"
                if p.has_partner and p.partner_retire_age is not None:
                    ch["partner_retire_age"] = ra
                    if who:
                        ch["_partner_name"] = who
                else:
                    ch["_say"] = (f"I do not have a retirement age for {name}, so I can't model it. Add it in your answers first."
                                  if p.has_partner else f"I plan for you on your own, so I do not model {name}'s retirement.")
                    ch["_chips"] = ask_plan.useful_whatifs(p)
                    return ch
            else:
                ch["retire_age"] = ra
            if p.has_partner and re.search(r"\bboth\b|\bwe\b|\bour\b|\bus\b|\bwe're\b", low):
                ch["_both"] = True
        else:
            ch["_say"] = "Pick a retirement age from 40 to 80."
    ch.update(whatif_read.spending_less(low))
    if ("_spend_less" in ch or "_spend_less_pct" in ch) and not ch.get("_spend_now") and p.spending_per_year:
        cut = ch.get("_spend_less") or p.spending_per_year * ch["_spend_less_pct"]
        if p.spending_per_year - cut >= 1000:
            ch["spending_per_year"], ch["_less_by"] = round(p.spending_per_year - cut), round(cut)
    if whatif_read.SPEND_LESS_BARE.search(low) and not any(k in ch for k in ("_spend_less", "_spend_less_pct")) and not re.search(r"\d", low):
        ch["_say"] = "How much less? Tell me an amount, for example: spend $500 less a month."
        ch["_chips"] = ["What if I spend $500 less a month", "What if I spend 10% less", "What if I retire at 65"]
    more = whatif_read.spending_more(low) if not any(k in ch for k in ("_spend_less", "_spend_less_pct")) else None
    if more is None and not any(k in ch for k in ("_spend_less", "_spend_less_pct")) and p.spending_per_year:
        pct = whatif_read.spending_more_pct(low)          # "spend 10% more"
        if pct is not None and 0 < pct <= 1:
            more = round(p.spending_per_year * pct, 2)
    if more and p.spending_per_year:
        ch["spending_per_year"], ch["_more_by"] = round(p.spending_per_year + more), round(more)
    m = None if more or any(k in ch for k in ("_spend_less", "_spend_less_pct")) else \
        re.search(r"\b(?:spend|spending|spent|live on|lived on|get by on|budget of)\b(?![^0-9$.?!]{0,20}\b(?:less|more|extra|fewer)\b)[^0-9$]{0,20}" + AMT, low) or \
        re.search(r"\bneed(?:ed|s)?\s+(?:only\s+|just\s+)?" + AMT + r"(?=\s*(?:a|per|each)\s+(?:year|month)|\s*(?:yearly|monthly))", low)
    if m and not _is_product_number(low, m, 1) and not re.match(r"\s?(?:%|percent)", low[m.end():]):
        v = _amount(m)
        if re.search(r"(?:a|per|each)\s+month|monthly", low[m.end():m.end() + 20]):
            v *= 12
        if 1000 <= v <= 2e6:
            ch["spending_per_year"] = v
    if firm:
        # the levers the plan names: debts, the match, an emergency fund, cover, the home, Social Security
        pm = re.search(r"\b(?:pay(?:s|ing)?\s+off|paid\s+off|clear(?:s|ed|ing)?|repa(?:y|ys|id|ying)|get\s+rid\s+of|got\s+rid\s+of|eliminat\w+|wip(?:e|ed|ing)\s+out)\b", low)
        po = re.search(r"\b(?:pay|paid|paying)\s+((?:the|my|our)\s+[a-z ]{2,25}?)\s+off\b", low)    # "paid the house off"
        if pm:
            toks = _debt_tokens(low[pm.end():pm.end() + 70])
            if toks:
                ch["pay_off"] = toks
        if "pay_off" not in ch and po:
            toks = _debt_tokens(po.group(1))
            if toks:
                ch["pay_off"] = toks
        if "pay_off" not in ch and re.search(r"\bdebt[- ]free\b|\b(?:had|have|with|owe)\s+no\s+(?:more\s+)?debts?\b|\bno (?:more )?debts?\b", low):
            ch["pay_off"] = ["all"]
        if re.search(r"\bemergency\s+(?:fund|savings|cash)\b|\brainy[- ]day\b", low):
            n = re.search(r"(\d+(?:\.\d+)?|" + "|".join(NUM_WORDS) + r")[- ]months?\b", low)
            ch["emergency_months"] = float(n.group(1)) if n and n.group(1)[0].isdigit() else (NUM_WORDS.get(n.group(1)) if n else 3)
        if re.search(r"\bdisability\b", low) and re.search(r"\b(?:get|buy|take out|add|have|purchase|carry|insurance|cover)\b", low):
            ch["insurance"] = "disability"
        elif re.search(r"\blong[- ]term care\b|\bltc\b", low) and re.search(r"\b(?:get|buy|take out|add|have|purchase|carry|insurance|cover)\b", low):
            ch["insurance"] = "ltc"
        elif re.search(r"\blife (?:insurance|cover|policy)\b|\bterm life\b|\bterm policy\b", low) and re.search(r"\b(?:get|buy|take out|add|have|purchase|carry|more|close)\b", low):
            ch["insurance"] = "life"
        if re.search(r"\bfull\s+(?:employer\s+|company\s+)?match\b|\b(?:get|capture|claim|earn)\b[^.]{0,20}\bmatch\b|\bto the match\b", low):
            ch["match_full"] = True
        if re.search(r"\bdownsiz\w+|\bsmaller (?:home|house|place)\b|\bsell (?:my|our|the) (?:home|house)\b", low):
            nv = re.search(r"\b(?:to|buy|for)\s+an?\s+" + AMT + r"\s+(?:home|house|place)\b", low)
            ch["downsize"] = _amount(nv) if nv else None
        if re.search(r"\bclaim\w*\b[^.]{0,40}\bsocial security\b|\bsocial security\b[^.]{0,40}\b(?:at|starting|from|age)\s+\d{2}\b", low):
            a = re.search(r"\b(?:at|age|by|starting|from)\s+(?:age\s+)?(\d{2})\b", low[low.find("social security"):] if "social security" in low else low) \
                or re.search(r"\b(\d{2})\b", low)
            if a:
                age = int(a.group(1))
                if 62 <= age <= 70:
                    ch["claim_age"] = age
                else:
                    ch["_say"] = "Social Security can start from 62, and the benefit stops rising at 70. Pick an age from 62 to 70."
        if "claim_age" not in ch and "_say" not in ch:
            ca = whatif_read.claim_age(low, p.age)
            if ca is not None:
                if 62 <= ca <= 70:
                    ch["claim_age"] = ca
                else:
                    ch["_say"] = "Social Security can start from 62, and the benefit stops rising at 70. Pick an age from 62 to 70."
    if not ch.get("match_full"):
        ch.update(_saving_change(low, p))
    m = re.search(r"\b(?:move\w*|relocat\w*|retir\w*\s+to|lived?\s+in|living\s+in|settl\w*\s+(?:in|down in)|go(?:ne)?\s+to\s+live\s+in)\b"
                  r"((?:\s+(?:down|up|out|over|back|away|in with [a-z ]{1,25}?))?(?:\s+(?:to|in))?\s+[a-z .']{2,40})", low)
    if m:
        place = re.split(r"\s+(?:and|but|then|so|because|if|when|to (?:be|live near|save|retire))\b|[,.?!;]", m.group(1))[0]
        s = find_state(place, asking_state=True)
        if s:
            ch["state"] = s
    qc = re.sub(r"\bneither (?:kid|child|one|of (?:them|our kids|the kids|the children))\b(?:\s+(?:goes|go|went|going))?\s+to\s+(college|university|school)",
                r"both kids skip \1", q, flags=re.I)        # "neither kid goes to college": both skip it
    if (cw := college_each.whatif_change(p, qc)) is not None and "children" not in ch:      # college, child by child
        ch.update({k: v for k, v in cw.items() if v is not None})
    elif (kd := whatif_read.kids(low)) is not None:
        how, n = kd
        add = n if how == "more" else (n - len(p.children)) if how == "all" and n is not None else None
        if how == "fewer" or (add is not None and add < 0):
            ch["_say"] = ("A What If can add a child but not take one away. To change the children in your plan, change your answers."
                          if p.children else "Your answers show no children, so there is none to take away.")
            ch["_chips"] = ["What if we have another baby", "Change an answer", "Try a What If"] if p.children else ["What if we have a baby", "Try a What If"]
        elif add == 0:
            ch["_say"] = f"Your plan already has {len(p.children)} {'child' if len(p.children) == 1 else 'children'}, so nothing would change."
            ch["_chips"] = ["What if we have another baby", "Try a What If"]
        elif add is not None and add > 4:
            ch["_say"] = "A What If can add up to 4 children at a time. Try a smaller number."
        elif add:
            ch["children"] = [c.model_dump() for c in p.children] + [{"age": 0, "college": True} for _ in range(add)]
            ch["_kids_added"] = add
    pc = whatif_read.pet_counts(low, [x.model_dump() for x in p.pets])
    if isinstance(pc, str):
        if pc == "same":
            if "_say" not in ch and not any(not k.startswith("_") for k in ch):
                ch["_say"] = "Your plan already has those pets, so nothing would change."
                ch["_chips"] = ["What if we get another dog", "Try a What If"]
        elif "_say" not in ch:
            ch["_say"], ch["_chips"] = pc, ["What if we get a dog", "What if we get a cat", "Try a What If"]
    elif pc:
        ch["pets"], changed = pc
        kind, before, after = changed[0]
        ch["_pet"] = (kind, after - before)
        ch["_pets_changed"] = changed
    if "saving_other_per_month" in ch or "save_rate" in ch or "saving_contrib_you" in ch:
        if whatif_read.PUT_IN.search(q.lower()) and whatif_read.COLLEGE.search(q.lower()):
            ch["_college"] = True
    ch.update(whatif_read.part_time(low, p.part_time.per_year if p.part_time else None, p.retire_age))
    if "_part_time_no_amount" in ch and "_say" not in ch:
        until = ch.pop("_part_time_no_amount")
        if "retire_age" in ch:
            ch["_note"] = ("I left out the part-time work because you gave no amount. Add one to include it, for example: "
                           "what if I earn $20,000 a year part time until 70.")
        else:
            near = until if isinstance(until, int) and until > (p.age or 0) else min(70, max((p.retire_age or 65) + 2, (p.age or 45) + 1))
            ch["_say"] = (f"Part-time work needs a yearly amount, so I can't run it; the closest What If is retiring at {near}.")
            ch["_chips"] = [f"What if I retire at {near}", f"What if I earn $20,000 a year part time until {near}"]
    ch.pop("_part_time_no_amount", None)
    if re.search(r"\b(?:more careful|more cautious|less risk|safer|careful|cautious\w*|conservativ\w*|play(?:ed|ing)? it safe|less risky|lower risk)\b", low):
        ch["risk"] = "careful"
    elif re.search(r"\b(?:more risk|more aggressive|aggressive\w*|riskier|growth|more in stocks|higher risk)\b", low):
        ch["risk"] = "growth"
    elif re.search(r"\bbalanced\b", low):
        ch["risk"] = "balanced"
    return ch


AFFECTS = {"retire_age": {"tax", "markets"}, "partner_retire_age": {"tax", "markets"}, "part_time": {"tax", "markets"}, "spending_per_year": {"tax", "markets"}, "save_rate": {"markets"},
           "saving_contrib_you": {"tax", "markets"}, "saving_other_per_month": {"tax", "markets"}, "match_full": {"tax", "markets"},
           "state": {"family", "tax", "markets"}, "risk": {"markets"}, "children": {"family", "markets"}, "pets": {"family", "markets"},
           "pay_off": {"family", "tax", "markets"}, "emergency_months": {"markets"}, "insurance": set(),
           "downsize": {"family", "tax", "markets"}, "claim_age": {"markets"}, "shock": {"markets"}}


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _take(p: Profile, amount: float, order=SAVE_ORDER) -> float:
    """Take money out of the savings, in this order. Returns what was taken (may be less than asked)."""
    left = amount
    for k in order:
        have = getattr(p.savings, k)
        t = min(have, left)
        setattr(p.savings, k, have - t)
        left -= t
    return amount - left


def _savings_changed(p: Profile) -> None:
    p.sources["savings"] = "you said"
    if p.sources.get("emergency_months") == "estimate":
        p.emergency_months = None          # worked out again from the new cash


SAVED_WHILE_WORKING = "While you work, the plan saves the payments that stop."


def _mortgage_out_of_basics(p: Profile) -> bool:
    """The basics already leave this mortgage out (household.basics): it ends before retiring, or, for someone at work,
    it is a cost of its own. Then they use the typical owner costs of a home without a mortgage, not the budget's housing."""
    mort = costs.mortgage_end(p)
    return bool(mort and mort["years_left"] <= max(0, (p.retire_age or 65) - (p.age or 45))) or costs.mortgage_separate(p)


def _housing_without_mortgage(p: Profile, drop_per_year: float, out_of_basics: bool) -> None:
    """The budget's housing held the mortgage payment. Once the mortgage is gone (paid off, or the home sold), housing
    in the basics must not take it back in. Before, the basics then took the whole budget housing, mortgage and all, as
    a retirement cost, so paying off the mortgage made the basics much less safe (reasonableness audit: paid in 100 of
    100 before, 0 after). Where the basics left the mortgage out, housing stays the typical owner costs they used;
    otherwise it falls by the payment, to no less than those costs."""
    if not p.budget.housing or (drop_per_year <= 0 and not out_of_basics):
        return
    row = family_costs._load("basics.json")["states"].get((p.state or "").upper(), family_costs._load("basics.json")["us"])
    floor = float(row["smoc_free"])
    p.budget.housing = floor if out_of_basics else max(floor, p.budget.housing - drop_per_year / 12)


def _freed_while_working(p: Profile, paid_by_year: list[float]) -> float:
    """Payments that stop while you still work (a debt or mortgage paid off from savings). They were part of spending
    now, so spending now falls and the plan saves them: spread evenly over the working years, so the saving adds up to
    the payments that would still have been made before retiring (after that the plan spends them, as it does when a
    debt ends on its own). Before this, paying off a debt or the mortgage cut savings and saved nothing, so what you can
    count on fell (reasonableness audit). Returns the yearly cut to spending now (0 when retired)."""
    ytr = (p.retire_age or 65) - (p.age or 45)
    now = p.spending_now_per_year or 0.0
    if ytr <= 0 or now <= 0 or p.household_pay() <= 0:
        return 0.0
    cut = min(sum(paid_by_year[:ytr]) / ytr, 0.5 * now)
    if cut < 1:
        return 0.0
    p.spending_now_per_year = round(now - cut)
    p.sources["spending_now_per_year"] = "you said"
    return cut


DEFICIT_LATER = ("You spend more than your take-home pay, so each extra year at work still draws on savings. "
                 "That is why retiring later helps little.")


def apply_whatif(base: Profile, ch: dict[str, Any]) -> tuple[Profile, dict[str, Any]]:
    """The What If's profile, and notes for the answer: what (fragments for 'If ...'), after (a closing sentence),
    only_note (the plan's figures do not move, so say why instead of comparing), _say (it cannot be run)."""
    newp = base.model_copy(deep=True)
    notes: dict[str, Any] = {"what": [], "after": "", "only_note": False}

    def said(*keys):
        for k in keys:
            newp.sources[k] = "you said"

    if ("_spend_less" in ch or "_spend_less_pct" in ch) and "_less_by" not in ch:      # "spend $500 less a month": the goal minus that amount
        goal = newp.spending_per_year or 0.0
        cut = float(ch.get("_spend_less") or goal * ch.get("_spend_less_pct", 0))
        if ch.get("_spend_now"):
            now = newp.spending_now_per_year or 0.0
            if cut <= 0 or now - cut < 0:
                notes["_say"] = f"You spend about {_money(now)} a year now, so I cannot cut {_money(cut)} from it."
                return newp, notes
            from .agents import adviser     # the same change the starting points test
            newp = adviser._spend_less(newp, cut)
            notes["what"].append(f"you spend {_money(cut)} a year less now and save it")
        elif goal <= 0 or goal - cut < 1000:
            notes["_say"] = (f"Your spending goal is {_money(goal)} a year, so {_money(cut)} less leaves too little to plan on. Try a smaller cut."
                             if goal else "I do not have your spending yet. Tell me what you spend, then try again.")
            return newp, notes
        else:
            ch["spending_per_year"] = round(goal - cut)
            ch["_less_by"] = round(cut)
    saving_keys = [k for k in ("save_rate", "saving_contrib_you", "saving_other_per_month") if k in ch]
    if saving_keys and not ask_plan.can_save(base):
        # a retiree or someone with no pay has nothing to save from: say so plainly instead of running a change that does nothing
        retired = (base.retire_age or 65) <= (base.age or 45)
        notes["_say"] = ask_plan.NO_SAVE_RETIRED if retired else ask_plan.NO_SAVE_NO_PAY
        notes["_chips"] = ask_plan.useful_whatifs(base)
        return newp, notes
    if "retire_age" in ch and (newp.retire_age or 65) <= (newp.age or 45):
        notes["_say"] = f"You are already {base.age} and retired, so there is no retirement age to test. These What Ifs can change your plan:"
        notes["_chips"] = ask_plan.useful_whatifs(base)
        return newp, notes
    if "retire_age" in ch and ch["retire_age"] < (newp.age or 0):
        notes["_say"] = (f"You are already {newp.age}, so retiring at {ch['retire_age']} is behind you. "
                         f"Pick an age from {newp.age} to 80, or change your retirement age in your answers.")
        return newp, notes
    for k in ("retire_age", "partner_retire_age", "spending_per_year", "save_rate", "state", "risk"):
        if k in ch:
            setattr(newp, k, ch[k])
            said(k)
    if "retire_age" in ch and newp.has_partner:
        if ch.get("_both") and newp.sources.get("partner_retire_age") != "assumed" and newp.partner_retire_age is not None:
            newp.partner_retire_age = ch["retire_age"]
        elif newp.sources.get("partner_retire_age") == "assumed" or newp.partner_retire_age is None:
            newp.partner_retire_age = None          # stop together: worked out again from the new age
    if "part_time" in ch:
        newp.part_time = PartTime(**ch["part_time"])
        said("part_time")
        pt = newp.part_time
        notes["what"].append(f"you earn {_money(pt.per_year)} a year part time" + (f" until {pt.until_age}" if pt.until_age else " until 70"))
    if "children" in ch:
        if (newp.age or 0) > 50 and (newp.retire_age or 0) <= (newp.age or 0) and not ch.get("_college_each"):
            notes["_say"] = "You are retired, so the plan does not add a child. If a grandchild or another child will cost you money, add it as a big cost in your answers."
            return newp, notes
        added = len(ch["children"]) - len(base.children)
        newp.children = [Child(**c) for c in ch["children"]]
        said("children")
        if ch.get("_college_each"):
            notes["what"] += ch["_college_each"]
            said("college")
        if added > 0 and newp.spending_now_per_year and (newp.retire_age or 65) > (newp.age or 45):
            # a new child costs money now too: spending now rises by a typical first-year cost (USDA), so the tax credit
            # that comes with the child never makes the plan look better on its own (audit 2A)
            def at_home(kids):
                return family_costs.family_path(newp.age or 45, [c.model_dump() for c in kids], [])["children_at_home_per_year"][:1] or [0]
            extra = max(0.0, round(at_home(newp.children)[0] - at_home(base.children)[0], -2))
            newp.spending_now_per_year += extra
            notes["after"] = (notes.get("after") or "") + f"I added about {_money(extra)} a year to your spending now for the baby."
    if "pets" in ch:
        newp.pets = [Pet(**x) for x in ch["pets"]]
        said("pets")
        if ch.get("_pet"):
            kind, n = ch["_pet"]
            cost, left = family_costs.pet_cost(kind)
            notes["after"] = f"A {'pet' if kind == 'other' else kind} costs about {_money(cost)} a year for about {int(left)} years in your plan."
    if "saving_contrib_you" in ch:
        newp.saving.contrib_you = ch["saving_contrib_you"]
        said("saving")
    if "saving_other_per_month" in ch:
        newp.saving.other_per_month = ch["saving_other_per_month"]
        said("saving")
    save_delta = 0.0
    if saving_keys:
        # the plan already saves all the take-home pay left after spending, so saving more is spending less now: the
        # contributions rise and spending now falls by the same sum (else the change only moves money between accounts
        # and what you can count on does not move, audit R12)
        c0, c1 = costs.contributions(base), costs.contributions(newp)
        save_delta = (c1["you"] + c1["partner"] + c1["other"]) - (c0["you"] + c0["partner"] + c0["other"])
        if ch.get("_extra_per_year") and save_delta > 0:
            save_delta = float(ch["_extra_per_year"])       # the sum asked for ($6,000), not the rounded share of pay
        now = newp.spending_now_per_year or 0.0
        if save_delta > 0 and now - save_delta < 0.5 * now:
            notes["_say"] = (f"Saving {_money(save_delta)} more a year means spending that much less now. "
                             f"That would cut your {_money(now)} a year by over half. Try a smaller amount.")
            notes["_chips"] = ["What if I save $200 more a month", "What if I spend $500 less a month"]
            return newp, notes
        if abs(save_delta) >= 1 and now:
            newp.spending_now_per_year = round(now - save_delta)
            said("spending_now_per_year")
    if "retire_age" in ch or "spending_per_year" in ch or "partner_retire_age" in ch:
        # Social Security and spending estimates follow the new choices unless the person gave them
        if newp.sources.get("social_security_per_year") == "estimate":
            newp.social_security_per_year = None

    if "pay_off" in ch:
        toks = ch["pay_off"]
        if "mortgage" in toks:
            bal = newp.home.mortgage_balance
            if not (newp.home.owns and bal > 0):
                notes["_say"] = "You have no mortgage balance in your answers, so there is nothing to pay off."
                return newp, notes
            got = _take(newp, bal)
            if got < bal - 1:
                notes["_say"] = f"Your savings of {_money(got)} do not cover the mortgage of {_money(bal)}, so I cannot pay it off from savings."
                return newp, notes
            mort = costs.mortgage_end(newp)
            out_of_basics = _mortgage_out_of_basics(newp)
            stops =_freed_while_working(newp, [mort["drop_per_year"] if mort and t < mort["years_left"] else 0.0
                                                for t in range(max(0, (newp.retire_age or 65) - (newp.age or 45)))])
            newp.home.mortgage_balance = newp.home.mortgage_payment = 0.0
            newp.home.mortgage_rate = None
            _housing_without_mortgage(newp, mort["drop_per_year"] if mort else 0.0, out_of_basics)
            _savings_changed(newp)
            said("home")
            notes["what"].append(f"you pay off the {_money(bal)} mortgage from your savings")
            if stops:
                notes["after"] = SAVED_WHILE_WORKING
        want = [t for t in toks if t != "mortgage"]
        if want:
            hit = [d for d in newp.debts if d.balance > 0 and ("all" in want or d.kind in want or ("high" in want and (d.rate or 0) >= costs.HIGH_RATE))]
            if not hit:
                names = " or ".join(costs.DEBT_NAME.get(t, "debt") if t not in ("all", "high") else "high-rate debt" if t == "high" else "debt" for t in want)
                notes["_say"] = f"You have no {names} in your answers, so there is nothing to pay off. Add it first, for example: we owe 10k on a credit card at 22%."
                return newp, notes
            total = sum(d.balance for d in hit)
            avail = newp.savings.total
            if total > avail + 1:
                notes["_say"] = f"Your savings of {_money(avail)} do not cover {_money(total)} of debt, so I cannot pay it off from savings."
                return newp, notes
            _take(newp, total)
            freed = sum((d.monthly_payment or 0) * 12 for d in hit)
            ytr = max(0, (newp.retire_age or 65) - (newp.age or 45))
            stops = _freed_while_working(newp, costs.debt_schedule(newp.model_copy(update={"debts": hit}), max(1, ytr))["per_year"][:ytr])
            newp.debts = [d for d in newp.debts if d not in hit]
            _savings_changed(newp)
            said("debts")
            label = ", ".join(sorted({costs.DEBT_NAME.get(d.kind, "debt") for d in hit}))
            notes["what"].append(f"you pay off {_money(total)} of {label} from your savings")
            notes["after"] = (f"Your debt payments of about {_money(freed)} a year stop. Your savings fall by {_money(total)}, cash first."
                              + (" " + SAVED_WHILE_WORKING if stops else ""))

    if "emergency_months" in ch:
        n = float(ch["emergency_months"])
        monthly = (newp.spending_now_per_year or newp.spending_per_year or 0) / 12
        if not (0 < n <= 24):
            notes["_say"] = "Pick an emergency fund between 1 and 24 months of spending."
            return newp, notes
        target, have = n * monthly, newp.savings.cash
        if monthly <= 0 or target <= have + 1:
            notes["_say"] = f"You already hold about {_money(have)} in cash, which is {(have / monthly) if monthly else 0:.1f} months of spending."
            return newp, notes
        moved = _take(newp, target - have, MOVE_ORDER)
        newp.savings.cash += moved
        newp.emergency_months = round(newp.savings.cash / monthly, 1)
        said("emergency_months")
        newp.sources["savings"] = "you said"
        notes["what"].append(f"you keep {n:g} months of spending, {_money(target)}, in cash")
        notes["after"] = (f"I moved {_money(moved)} from your other savings into cash. Your total savings stay the same, "
                          "so the figures barely move. Cash helps when pay stops or a big bill comes.")

    if "insurance" in ch:
        kind = ch["insurance"]
        ins = newp.insurance
        if kind == "disability":
            ins.disability, what = True, "you get disability cover"
        elif kind == "ltc":
            ins.ltc, what = True, "you get long-term care cover"
        else:
            earner = max(newp.pay_per_year or 0, newp.partner_pay_per_year or 0)
            have = (ins.life_face or 0) if ins.life_kind in ("term", "whole") else 0
            need = max(have, costs.LIFE_COVER_YEARS * earner)
            ins.life_kind = ins.life_kind if ins.life_kind in ("term", "whole") else "term"
            ins.life_face = need or None
            what = f"you hold life cover of {_money(need)}" if need else "you get life cover"
        said("insurance")
        notes["what"].append(what)
        notes["only_note"] = True
        notes["after"] = ("the plan's figures do not change. The plan does not model illness, early death or the cost of care. "
                          "Cover protects your household from them. I have not priced it.")

    if "match_full" in ch:
        mi = costs.match_info(newp)
        if mi.get("rate") is None:
            notes["_say"] = "I do not know your employer match yet. Tell me, for example: my company matches 50% up to 6%."
            return newp, notes
        if mi["missed"] <= 0:
            notes["_say"] = f"You already save enough, about {_money(mi['contribution'])} a year, to get the full match."
            return newp, notes
        if (newp.pay_per_year or 0) > 0:
            newp.saving.contrib_you = float(mi["full_contribution"])
        else:
            newp.saving.contrib_partner = float(mi["full_contribution"])
        said("saving")
        notes["what"].append(f"you save {_money(mi['full_contribution'])} a year in your 401(k), enough for the full match")
        notes["after"] = f"That earns about {_money(mi['missed'])} a year more from your employer."

    if "downsize" in ch:
        h = newp.home
        if not h.owns:
            notes["_say"] = "You rent, so there is no home to downsize."
            return newp, notes
        new_value = ch["downsize"] if ch["downsize"] else DOWNSIZE_SHARE * h.value
        if h.value <= 0:
            notes["_say"] = "I need your home's value to work that out. Tell me, for example: my home is worth $600,000."
            return newp, notes
        proceeds = h.value * (1 - SELLING_COST) - h.mortgage_balance - new_value
        if proceeds < 0:
            notes["_say"] = "Selling would not cover the mortgage and the new home, so there is nothing left over. Try a cheaper home."
            return newp, notes
        drop = 0.0
        if h.mortgage_payment > 0:
            row = family_costs._load("basics.json")["states"].get((newp.state or "").upper(), family_costs._load("basics.json")["us"])
            drop = max(0.0, h.mortgage_payment * 12 - row["smoc_free"] * 12)
        _housing_without_mortgage(newp, drop, _mortgage_out_of_basics(newp))
        newp.savings.taxable += proceeds
        h.value, h.mortgage_balance, h.mortgage_payment, h.mortgage_rate = new_value, 0.0, 0.0, None
        for k in ("spending_now_per_year", "spending_per_year"):
            v = getattr(newp, k)
            if v and drop:
                setattr(newp, k, max(0.0, v - drop))
        newp.sources["savings"] = "you said"
        if newp.sources.get("emergency_months") == "estimate":
            newp.emergency_months = None
        said("home")
        notes["what"].append(f"you sell your home and buy one worth {_money(new_value)} outright")
        notes["after"] = (f"I assumed selling costs of {round(SELLING_COST * 100)}%. Unless you named a price, the new home costs {round(DOWNSIZE_SHARE * 100)}% of the old "
                          f"one. About {_money(proceeds)} goes into your savings."
                          + (f" Your yearly spending drops about {_money(drop)} with the mortgage payment gone." if drop else ""))

    if "shock" in ch:
        notes["what"].append(shock_words(ch["shock"]))
        notes["after"] = ("Your answers do not change. This tests how the plan holds up. "
                          "The other market tests still vary as before.")

    if "claim_age" in ch:
        a = int(ch["claim_age"])
        if newp.age is not None and newp.age > a:
            notes["_say"] = f"You are already past {a}. Pick a claiming age from your age to 70."
            return newp, notes
        household.set_claim(newp, base, a)
        said("claim_age")
        notes["what"].append(f"you claim Social Security at {a}")
        notes["after"] = "A later start pays more each year. A sooner start pays less."

    newp = household.complete(newp)
    if "retire_age" in ch and ch["retire_age"] > (base.retire_age or 65) and costs.saving_now(newp)["per_year"] < 0:
        notes["after"] = ((notes.get("after") or "") + " " + DEFICIT_LATER).strip()
    if saving_keys and abs(save_delta) >= 1:
        # the same yearly saving the plan and the Assumptions show (costs.saving_now), said as a share "of pay"
        total = costs.saving_now(newp)["per_year"]
        pay = max(1.0, newp.household_pay())
        more = "more" if save_delta > 0 else "less"
        notes["_save_line"] = f"you save {_money(abs(save_delta))} {more} a year and spend that much {'less' if save_delta > 0 else 'more'} now"
        notes["after"] = ((notes.get("after") or "") + f" That makes about {_money(total)} a year saved in all, {round(100 * total / pay)}% of pay.").strip()
    return newp, notes


def whatif_text(ch: dict, old: dict, new: dict, notes: dict | None = None) -> str:
    notes = notes or {"what": [], "after": "", "only_note": False}
    what = []
    if "retire_age" in ch:
        what.append(f"you retire at {ch['retire_age']}")
    if "partner_retire_age" in ch:
        what.append(f"{ch.get('_partner_name') or 'your partner'} stops working now" if ch.get("_partner_now") else
                    f"{ch.get('_partner_name') or 'your partner'} retires at {ch['partner_retire_age']}")
    if ch.get("_less_by"):
        what.append(f"you spend ${ch['_less_by']:,.0f} a year less, at ${ch['spending_per_year']:,.0f}")
    elif ch.get("_more_by"):
        what.append(f"you spend ${ch['_more_by']:,.0f} a year more, at ${ch['spending_per_year']:,.0f}")
    elif "spending_per_year" in ch:
        what.append(f"you spend ${ch['spending_per_year']:,.0f} a year")
    if notes.get("_save_line"):
        what.append(notes["_save_line"])
    elif "save_rate" in ch:
        if ch.get("_extra_per_year"):
            what.append(f"you save ${ch['_extra_per_year']:,.0f} more a year, about {round(ch['save_rate'] * 100)}% of pay in all")
        else:
            what.append(f"you save {round(ch['save_rate'] * 100)}% of pay")
    if "saving_contrib_you" in ch and not notes.get("_save_line"):
        what.append(f"you put ${ch['saving_contrib_you']:,.0f} a year into your 401(k) or IRA")
    if "saving_other_per_month" in ch and not notes.get("_save_line"):
        what.append(f"you save ${ch['saving_other_per_month']:,.0f} a month outside your 401(k) or IRA"
                    if not ch.get("_extra_per_year") else f"you save ${ch['_extra_per_year']:,.0f} more a year")
    if "state" in ch:
        what.append(f"you move to {ch['state']}")
    if "risk" in ch:
        what.append(f"you choose a {ch['risk']} mix")
    if "children" in ch and not ch.get("_college_each"):
        k = ch.get("_kids_added") or 1
        what.append("you have another child" if k == 1 else f"you have {k} more children")
    if "pets" in ch:
        for kind, before, after in ch.get("_pets_changed") or [(*(ch.get("_pet") or ("other", 1)), None)]:
            word = "pet" if kind == "other" else kind
            if after is None:           # an older change dict: (kind, how many more)
                n = before
                what.append("you get another " + word if n == 1 else f"you get {n} more {word}s")
            elif after > before:
                n = after - before
                what.append(("you get another " + word if n == 1 else f"you get {n} more {word}s") + (f", {after} in all" if before else ""))
            else:
                what.append(f"you have no {word}s" if after == 0 else f"you have {after} {word}{'s' if after != 1 else ''} instead of {before}")
    what += notes.get("what", [])
    head = "If " + " and ".join(what) + ", "
    tail = (" " + ch["_note"]) if ch.get("_note") else ""
    if isinstance(ch.get("retire_age"), (int, float)) and ch["retire_age"] > 70:
        tail += " That is past 70. Social Security stops growing at 70."
    if ch.get("_college"):
        tail += " I counted the college money as extra saving. The plan has no separate college fund."
    if notes.get("only_note"):
        return head + notes["after"] + tail
    om, nm = old["markets"], new["markets"]
    new_safe, old_safe = nm["safe_spending_per_year"], om["safe_spending_per_year"]
    new_paid, old_paid = nm.get("basics_paid_of_100"), om.get("basics_paid_of_100")
    new_goal, old_goal = nm["goal_lasts_of_100"], om["goal_lasts_of_100"]
    body = head + f"you can count on ${new_safe:,.0f} a year, {_vs(new_safe, old_safe, '$')}."
    if new_paid != old_paid:
        body += f" Your needs are paid in {new_paid} of 100 market tests, {_vs(new_paid, old_paid)}."
    elif (new_paid or 0) < 90:
        body += f" Your needs are still paid in only {new_paid} of 100 market tests."
    if new_goal != old_goal:
        body += f" Your goal lasts in {new_goal} of 100 market tests, {_vs(new_goal, old_goal)}."
    return body + (" " + notes["after"] if notes.get("after") else "") + tail


def _vs(new, old, unit: str = "") -> str:
    """'up from $53,400', 'down from 95' or 'as before': the What If figure against the plan's, in plain words."""
    if new is None or old is None:
        return "as before"
    fmt = (lambda x: f"${x:,.0f}") if unit == "$" else (lambda x: f"{x}")
    if round(new) == round(old):
        return "as before"
    return f"{'up' if new > old else 'down'} from {fmt(old)}"


def _clean_profile_text(p: Profile) -> Profile:
    """Profile strings come from the browser and the whole profile goes into the specialists' prompts (as wrapped
    data): clean them first. Cut before the guard so a long string costs nothing; an unknown state is dropped."""
    for k in ("job", "partner_job"):
        v = getattr(p, k)
        if v:
            setattr(p, k, safety.guard(v[:200]).clean[:60])
    if p.state is not None and p.state.upper() not in STATE_CODES:
        p.state = None
    elif p.state:
        p.state = p.state.upper()
    for b in p.goals.big_costs:
        b.label = safety.guard((b.label or "")[:200]).clean[:40] or "Big cost"
    p.offered = [x for x in p.offered if isinstance(x, str) and len(x) <= 40][:50]
    p.asking = p.asking if p.asking and len(p.asking) <= 40 else None
    p.history = []          # the intake chat memory is not a planning input and never goes into the specialists' prompts
    return p


SAME_KEYS = {"retire_age": "you retire at {}", "partner_retire_age": "your partner retires at {}", "claim_age": "you claim Social Security at {}",
             "risk": "you invest with a {} mix", "state": "you live in {}", "spending_per_year": "you spend ${:,.0f} a year"}


def _same_as_plan(ch: dict, base: Profile) -> dict | None:
    """A What If that names what the plan already says is not run: say so, and offer something that differs."""
    shown = {k: v for k, v in ch.items() if not k.startswith("_")}
    if not shown or any(k not in SAME_KEYS or getattr(base, k, None) != v for k, v in shown.items()):
        return None
    what = " and ".join(SAME_KEYS[k].format(v) for k, v in shown.items())
    near = ask_plan.retire_examples(base)
    return ask_intent._clarify(f"That is your plan now: {what}. Try a different one, for example: what if I retire at {near[0]}.",
                               [f"What if I retire at {near[0]}", ask_plan.save_chip(base), "What if markets fall 30%"])


def kept_for(ch: dict, old_ctx: RunCtx) -> dict | None:
    """The base plan's strategy for a What If, so one change is scored the way the analysis's table scores it. A new
    investing mix needs a fresh pick, so it gets none."""
    if "risk" in ch or not old_ctx.kept or not old_ctx.kept.get("strategy"):
        return None
    return {"strategy": old_ctx.kept["strategy"], "neighbors": old_ctx.results.get("neighbors"),
            "repick": adviser.verdict(old_ctx.results["markets"]) == "falls_short"}


# How long a What If takes, for the "about N to M seconds" the team panel says while it runs. Until this server has timed a
# few, the eval's figure is used (eval/model_compare/REPORT.md: about 12 s on Haiku); then the range of the recent runs.
WHATIF_SECONDS_DEFAULT = (10, 20)
_whatif_times: list[float] = []


def whatif_estimate() -> str:
    """'about 10 to 20 seconds': the range of the last few What Ifs on this server, to the nearest 5 seconds."""
    recent = _whatif_times[-5:]
    if len(recent) < 3:
        lo, hi = WHATIF_SECONDS_DEFAULT
    else:
        lo = max(5, int(min(recent) // 5) * 5)
        hi = max(lo + 5, int(-(-max(recent) // 5)) * 5)
    return f"about {lo} to {hi} seconds"


def _timed_whatif(seconds: float) -> None:
    _whatif_times.append(seconds)
    del _whatif_times[:-20]


async def ask(question: str, profile: dict, session: str, use_ai: bool = True, pending: dict | None = None, plan_so_far: dict | None = None,
              emit: Emit | None = None) -> dict:
    """emit: when given (the streamed What If), a What If's run sends the same events as the plan, after a whatif_start
    event. Nothing else is sent: every other answer is made without an event, so the caller can return it as plain JSON."""
    tokens = {"input": 0, "cached": 0, "output": 0}
    g = safety.guard(question)
    if safety.is_medicaid_hiding(question):
        return {"kind": "refused", "text": safety.MEDICAID_REPLY, "citations": [], "tokens": tokens, "cost_usd": 0.0}
    if safety.is_refusable(question):
        return {"kind": "refused", "text": ask_plan.pick_refusal(question) or safety.REFUSE_REPLY, "citations": [], "tokens": tokens, "cost_usd": 0.0}
    if g.flagged:
        return {"kind": "refused", "text": "I can't act on instructions inside a question. Please ask about your plan or a retirement rule.",
                "citations": [], "tokens": tokens, "cost_usd": 0.0, "reasons": g.reasons}
    base = _clean_profile_text(prepare(profile))
    if pending:
        stray = ask_plan.pending_bare(g.clean, pending)
        if stray is not None:
            return stray
        step = await ask_intent.pending_step(g.clean, profile, pending, base, session, use_ai, run_plan)
        if step is not None:
            return step
        wf = ask_intent.pending_whatif_step(g.clean, pending)     # a What If the model read, offered for a yes (R7)
        if isinstance(wf, dict):
            return wf
        if isinstance(wf, str):         # yes: the plain sentence built in code, read again by the rules like any message
            return await ask(wf, profile, session, use_ai=use_ai, plan_so_far=plan_so_far, emit=emit)
    cc = ask_intent.claim_change(g.clean, base)       # "Change my Social Security start age": a change with a confirm (R6)
    if cc is not None:
        return cc
    ch = parse_whatif(g.clean, base)
    if ch.get("_say"):
        return ask_intent._clarify(ch["_say"], ch.get("_chips") or ["Try a What If", "Change an answer", "Explain my plan"])
    if not ch:
        quick = await ask_plan.answer(g.clean, base, plan_so_far, lambda: tools_only_plan(base))
        if quick is not None and quick != ask_plan.unread_whatif(g.clean, base):
            return quick
        if not safety.is_single_investment(g.clean.lower()):     # a stock pick said as a What If gets the stock reply below (R14)
            read = await whatif_ai.fallback(g.clean, base, ch, session, use_ai)    # "I can't test that", or the model's reading for a yes
            if read is not None:
                return read
            if quick is not None:
                return quick
        routed = await ask_intent.route(g.clean, base, plan_so_far, session, use_ai)
        if routed is not None:
            return routed
    elif whatif_ai.missed_topics(g.clean, ch):          # the rules read only part ("retire at 62 and get 5 dgos")
        read = await whatif_ai.fallback(g.clean, base, ch, session, use_ai)
        if read is not None:
            return read
        ch["_note"] = ((ch.get("_note") or "") + " " + whatif_ai.partial_note(whatif_ai.missed_topics(g.clean, ch))).strip()
    same = _same_as_plan(ch, base)
    if same:
        return same
    if ch:
        old_plan, old_ctx = await tools_only_plan(base)
        newp, notes = apply_whatif(base, ch)
        if notes.get("_say"):
            return ask_intent._clarify(notes["_say"], notes.get("_chips") or ["Try a What If", "Change an answer", "Explain my plan"])
        affected = set().union(*(AFFECTS.get(k, set()) for k in ch if not k.startswith("_"))) | {"adviser"}
        if emit is not None:
            await emit({"type": "whatif_start", "question": g.clean, "agents": sorted(affected), "estimate": whatif_estimate()})
        ctx = RunCtx(profile=newp, session=session, use_ai=use_ai, shock=ch.get("shock"), fixed=kept_for(ch, old_ctx), emit=emit or _no_emit)
        t0 = time.monotonic()
        plan = await run_plan(ctx, ai_agents=affected)
        if use_ai and ctx.use_ai and not ctx.ai_down:
            _timed_whatif(time.monotonic() - t0)       # only runs that used the model: template-only runs are near instant
        shown = {k: v for k, v in ch.items() if not k.startswith("_")}
        return {"kind": "whatif", "text": whatif_text(ch, old_ctx.results, ctx.results, notes), "citations": plan.get("citations", []),
                "plan": plan, "profile": newp.model_dump(), "changes": shown, "tokens": ctx.tokens, "cost_usd": round(ctx.cost_usd, 6)}

    # an answer: from cited passages (rules) or the plan's own figures
    plan, pctx = await tools_only_plan(base)
    figures = {name: f["numbers"] for name, f in pctx.findings.items()}
    figures["plan"] = {k: plan[k] for k in ("verdict", "retire_age", "claim_age", "spending_goal", "horizon_age")}
    ctx = RunCtx(profile=base, session=session, use_ai=use_ai)
    out, tk, cost = await run_model(ctx, "ask", build_ask_agent, ask_prompt(g.clean, figures), llm.SIMPLE, "low")
    allowed = safety.allowed_numbers(figures, ctx.extra_facts, base.model_dump(exclude={"sources", "notes"}), profile_facts(base))
    if out is not None:
        text = out.text
        check = safety.number_check(text, allowed)
        if not check.ok:
            prompt = ask_prompt(g.clean, figures) + "\nYour last answer was rejected. " + safety.retry_note(check.bad) + " Answer again."
            out2, tk2, cost2 = await run_model(ctx, "ask", build_ask_agent, prompt, llm.SIMPLE, "low")
            tk = {k: tk[k] + tk2[k] for k in tk}
            cost += cost2
            out = out2 if out2 is not None and safety.number_check(out2.text, safety.allowed_numbers(figures, ctx.extra_facts, base.model_dump(exclude={"sources", "notes"}), profile_facts(base))).ok else None
    found = (ctx.results.get("research") or {}).get("passages", [])
    if out is not None:
        if out.kind == "no_source":
            fallback = ask_intent.explain(g.clean, plan)
            if not fallback and ask_self.about_plan(g.clean):
                return ask_self.headline_answer(plan, base)
            if fallback:
                return {"kind": "answer", "intent": "question_plan", "text": fallback, "citations": [], "tokens": tk, "cost_usd": round(cost, 6)}
            return ask_intent.offer(NO_SOURCE, tk, round(cost, 6))
        ids = set(out.source_ids)
        cites = list({x["url"]: {"title": x["title"], "url": x["url"]} for x in found if x["id"] in ids}.values())
        return {"kind": "answer", "text": ask_intent.money_signs(out.text), "citations": cites, "tokens": tk, "cost_usd": round(cost, 6)}
    # no AI, or the answer failed the number check twice: quote the best official passage, word for word
    if ask_self.about_plan(g.clean):        # a question about the plan's own figures is never answered by a quote
        return ask_self.headline_answer(plan, base)
    hits = found or sources.search(g.clean, k=1)
    if hits:
        h = hits[0]
        return {"kind": "answer", "text": f"From the source: \"{h['text']}\"", "citations": [{"title": h["title"], "url": h["url"]}],
                "tokens": tk, "cost_usd": round(cost, 6)}
    return ask_intent.offer(NO_SOURCE, tk, round(cost, 6))
