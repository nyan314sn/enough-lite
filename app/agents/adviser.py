"""Adviser (lead): reads the specialists' findings and writes the plan: needs, wants, wishes and three actions.

It never makes up numbers: every figure in its text must appear in a finding's numbers or a tool summary (the number
check). It gets one retry with the rejected figures named; then the app uses a plain template.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import time

from pydantic import BaseModel, Field

from .. import config, llm, safety
from ..tools import costs
from ..tools import tax as tax_mod
from .base import STYLE, RunCtx, figure_lines, money, profile_facts, run_model


class Action(BaseModel):
    title: str = Field(description="A short instruction, under 10 words, starting with a verb.")
    why: str = Field(description="One or two plain sentences on why, using only the allowed figures.")


class AdviserOut(BaseModel):
    needs_line: str = Field(description="One sentence: what the basics cost and how often they are paid.")
    wants_line: str = Field(description="One sentence: how much can go to wants on top of the basics.")
    wishes_line: str = Field(description="One or two sentences: the spending goal and what may be left for wishes.")
    actions: list[Action] = Field(description="Exactly three actions, most important first.", min_length=3, max_length=3)


INSTRUCTIONS = (
    "You are the lead adviser in a retirement-planning team. Specialists have worked out the facts with tools. "
    "Write the plan in the frame 'Needs safe. Wants sure. Wishes open.': needs are the basics, wants are the spending you "
    "can count on (safe in 90 of 100 scenarios, basics included: markets.safe_spending_per_year), wishes are what is left after that. "
    "markets.above_basics_per_year is how much of it is above the basics. When that is near zero, never write 'Wants are $0'; "
    "say what can be counted on a year, that it is about the basics, and that there is little room above them yet. Then give three actions. "
    "Rules: use only the figures under 'Numbers you may use', as written or rounded; do no arithmetic of your own "
    "(the gap between goal and safe spending is listed). Keep the person's own retirement age; never tell "
    "them to retire later and never suggest working past 70. Verdicts: falls_short means the basics are not safe; say once, "
    "plainly, that the plan does not work on these numbers and use the listed starting points. below_goal means the basics "
    "are safe but the goal is above what lasts; say that, and never write 'falls short' for it. close means near the goal. "
    "If the plan uses the plan of a similar household, say so plainly in one action's reason. When 'Actions the person's own inputs point to' are listed "
    "(paying off high-rate debt, the full employer match, an emergency fund, a gap in cover), use them for the actions in place of "
    "generic ones, most urgent first, with the reason's figures as listed. If the person is saving for a legacy, a pension or "
    "extra income is counted, or costs change when the mortgage ends, you may say so in the wants or wishes line, using only "
    "listed figures. A figure whose name ends in 'assumed' is an assumption: if you use it, say it is assumed. "
    "No product sales talk. " + STYLE)


BASICS_SAFE = 90       # the basics must be paid in at least this many of 100 scenarios for the goal to "work" or be "close"
SECOND_TRY_SECONDS = 6.0   # the adviser's second draft starts only with this much of the plan's time left


def verdict(m: dict) -> str:
    """works / close / below_goal / falls_short. "Falls short" has one meaning: the basics are paid in fewer than 90
    of 100 scenarios. With the basics safe, the spending goal is compared with what you can count on: works (at or
    above it), close (within 10%), below_goal (further below)."""
    goal, safe = m.get("spending_goal_per_year") or 0, m.get("safe_spending_per_year") or 0
    paid = m.get("basics_paid_of_100")
    if paid is not None and paid < BASICS_SAFE:
        return "falls_short"
    if safe >= goal:
        return "works"
    if safe >= 0.9 * goal:
        return "close"
    return "below_goal"


VERDICT_WORDS = {"works": "works", "close": "close to your goal", "below_goal": "below your goal",
                 "falls_short": "falls short: the basics are not safe"}


def needs_line(m: dict, basics: float) -> str:
    """The needs line, built in code from basics paid of 100 (never written by the model)."""
    paid = m.get("basics_paid_of_100")
    head = f"Your basics cost about {money(basics)} a year."
    if paid is None:
        return head
    if paid >= 100:
        return head + " They are paid in all 100 scenarios."
    if paid >= BASICS_SAFE:
        return head + f" They are paid in {paid} of 100 scenarios."
    if paid == 0:
        return head + " On these numbers they are not paid in any of 100 scenarios, so the plan starts there."
    return head + f" They are paid in only {paid} of 100 scenarios, so the plan starts there."


THIN_SHARE = 0.05      # room above the basics under 5% of them counts as "little room above the basics"


def above_basics(m: dict, basics: float) -> float:
    return max(0.0, round((m.get("safe_spending_per_year") or 0) - basics, -2))


def wants_thin(m: dict, basics: float) -> bool:
    return above_basics(m, basics) < THIN_SHARE * max(basics, 1)


def below_ss_note(m: dict) -> str:
    """Why what you can count on is below your Social Security, when it is: built from the plan's own inputs. Two short
    sentences (R18): the comparison, then at most two reasons in plain clauses. Spending now above take-home pay, when it
    is the cause, is named alone: it drains savings first."""
    safe, ss = m.get("safe_spending_per_year") or 0, m.get("social_security_per_year") or 0
    if not ss or safe >= ss:
        return ""
    inp = m.get("inputs") or {}
    # each reason a plain clause a reader can follow, the largest first; at most two, so the sentence stays short (R18
    # audit: "The reasons: tax on it, health costs on top and the years before it starts" could not be followed)
    why = []
    if (inp.get("save_per_year") or 0) < 0 and (inp.get("retire_age") or 0) > (inp.get("age") or 0):
        why.append("you spend more now than your take-home pay, so your savings run down before you retire")
    else:
        if m.get("ss_starts_later"):
            why.append("your savings must pay for the years before it starts")
        if m.get("health_extra_in_retirement"):
            why.append("health costs come on top of your spending")
        if m.get("social_security_survivor_per_year"):
            why.append("it falls to one check after the first death")
        if (m.get("ss_tax_rate") or 0) > 0:
            why.append("tax takes part of it")
        if not why:
            why.append("the plan keeps a margin for bad markets")
    why = why[:2]
    lst = " and ".join(why)
    # when the plan starts it at another age than your answers, say so, so the figure matches the one in your answers' basis
    return f" That is less than your Social Security of {money(ss)} a year{m.get('ss_when') or ''}. That is because {lst}."


def headline(m: dict, basics: float) -> str:
    """One plain sentence on what the person can count on (plan.wants.per_year). Built in code from the simulation."""
    safe = m.get("safe_spending_per_year") or 0
    return _headline(m, basics) + below_ss_note(m)


def _headline(m: dict, basics: float) -> str:
    safe = m.get("safe_spending_per_year") or 0
    falls_short = verdict(m) == "falls_short"
    if safe < 0.95 * basics or falls_short:
        pts = m.get("starting_points") or []
        more = (" The starting points below show what would make the basics safe." if any(x.get("makes_basics_safe") for x in pts) else
                " The starting points below each help, but none we tried makes the basics safe." if pts else "")
        paid = m.get("basics_paid_of_100")
        rel = "less than" if safe < basics else "about"
        how = f", which are paid in only {paid} of 100 scenarios" if falls_short and paid is not None and safe >= 0.95 * basics else ""
        return (f"You can count on {money(safe)} a year, {rel} your basics of {money(basics)}{how}. "
                f"On your numbers the plan does not work yet.{more}")
    if wants_thin(m, basics):
        return f"You can count on {money(safe)} a year, about your basics. There is little room above them yet."
    return f"You can count on {money(safe)} a year: {money(basics)} for basics and {money(above_basics(m, basics))} for the rest."


def plan_claims(p, m: dict) -> tuple[int | None, int | None, bool]:
    """(your claiming age, your partner's, already claiming) as the kept strategy uses them: each person's own age;
    someone already claiming keeps the age they gave."""
    claim = m.get("claim_age")
    if claim is None:
        return None, None, False
    partner = m.get("partner_claim_age") if (p.has_partner and p.partner_age) else None
    already = bool(m.get("already_claiming")) if "already_claiming" in m else (p.age or 0) >= int(claim)
    return int(claim), (int(partner) if partner is not None else None), already


def claim_ages(p, claim: int | None) -> tuple[int | None, int | None]:
    """Your claiming age and your partner's, each 62 to 70. Someone already past 70 shows 70 (the benefit stops
    rising then). The partner claims at the same age as you, or now if already past it, never past 70."""
    if claim is None:
        return None, None
    you = max(62, min(70, int(claim)))
    if not (p.has_partner and p.partner_age):
        return you, None
    partner = max(you, min(70, p.partner_age)) if p.partner_age > you else you
    return you, max(62, min(70, partner))


GOAL_KEY = "goal"
GOAL_GAP_MIN, GOAL_GAP_SHARE = 1000, 0.03     # a smaller gap to the goal is noise, not the first thing to act on
LEVER_TIER = {"goal": 0, "debt": 1, "match": 1, "emergency": 2, "life": 3, "disability": 3, "ltc": 3}


def lever_impact(x: dict) -> float:
    """Dollars a year each lever is worth: the goal gap, the debt's interest, the missed match. Others count 0."""
    n = x.get("numbers") or {}
    return float(n.get("gap_per_year") or n.get("high_rate_debt_interest_per_year") or n.get("match_missed_per_year") or 0)


def ranked_levers(p, m: dict) -> list[dict]:
    """The plan's levers by dollar impact: the gap to the goal first (when it falls short), then high-rate debt and the
    match (the larger yearly sum first), then the emergency fund, then cover. Nothing that repeats the current plan."""
    out = list(m.get("levers") or [])
    gap = max(0, round((m.get("spending_goal_per_year") or 0) - (m.get("safe_spending_per_year") or 0), -2))
    pts = m.get("starting_points") or []
    if verdict(m) == "falls_short":
        # the basics are not safe: no "spend less" (it does not make the basics safe); the starting points instead
        paid = m.get("basics_paid_of_100") or 0
        why = f"On your numbers your basics are paid in {paid} of 100 scenarios."
        if pts:
            why += " The starting points show what helps on your numbers."
        else:
            why += " Lower fixed costs, such as housing, or more income in retirement would help most."
        out.append({"key": GOAL_KEY, "title": "Make your basics safe first",
                    "whatif_text": next((x["whatif_text"] for x in pts if x["whatif_text"]), ""),
                    "numbers": {"gap_per_year": max(gap, 1)}, "why": why})
    elif verdict(m) != "works" and gap >= max(GOAL_GAP_MIN, GOAL_GAP_SHARE * (m.get("spending_goal_per_year") or 0)):
        safe = m.get("safe_spending_per_year") or 0
        out.append({"key": GOAL_KEY, "title": "Set your spending goal nearer the safe level",
                    "whatif_text": f"What if I spend ${round(safe, -3):,.0f} a year" if safe >= 1000 else "",
                    "numbers": {"gap_per_year": gap},
                    "why": f"Your goal is about {money(gap)} a year above what lasts in 90 of 100 scenarios, "
                           f"{money(safe)} a year. Start there and raise it as savings grow."})
    working = (p.retire_age or 65) > (p.age or 45)
    years_left = (p.retire_age or 65) - (p.age or 45)
    keep = []
    for x in out:
        if x["key"] in ("match", "disability") and (not working or years_left < MATCH_MIN_YEARS):
            continue
        if x["key"] == "match" and lever_impact(x) < MATCH_MIN_DOLLARS:
            continue        # a few dollars of match a year is not worth an action        # no match or disability advice once work is about to stop
        keep.append(x)
    return sorted(keep, key=lambda x: (LEVER_TIER.get(x["key"], 9), -lever_impact(x)))


MATCH_MIN_YEARS = config.MATCH_MIN_YEARS_LEFT
MATCH_MIN_DOLLARS = 100    # a missed match below this a year is not worth an action (audit 2A: a $50 match action)
CATCH_UP_SHARE = 0.8       # the catch-up action only for someone already saving near the yearly limit
RETIRE_MAX = 70            # never suggest retiring past 70
SPEND_LESS_SHARE = 0.10    # the "spend less" starting point: a tenth of spending, at least $1,000
SAVE_MORE_SHARE = 0.05     # the "save more" starting point: a twentieth of pay more a year, said as a sum a month
GOAL_CUT_SHARE = 0.85      # the "smaller goal" starting point: 85% of the goal, never below the basics
HELPS_MIN = 500            # count-on must rise by at least this (and 5%) for a change to count as a help


def _spend_less(p, x: float):
    """Spend x a year less now (a real cut). Retirement spending follows unless the person gave it."""
    from .. import household
    newp = p.model_copy(deep=True)
    newp.spending_now_per_year = max(0.0, (p.spending_now_per_year or 0) - x)
    newp.sources["spending_now_per_year"] = "you said"
    if p.sources.get("spending_per_year") != "you said" and (p.retire_age or 65) > (p.age or 45):
        newp.spending_per_year = None
        newp.sources.pop("spending_per_year", None)
    if newp.sources.get("social_security_per_year") == "estimate":
        newp.social_security_per_year = None
    return household.complete(newp)


def _tries(p, m: dict) -> list[dict]:
    """Single changes worth testing, each as a What If text and the change it makes (the What If parser reads the same
    text the same way): retire one or two years later (never past 70), spend less now, save more, claim Social
    Security at 70, a smaller goal. The person's own age is kept."""
    from .. import pipeline
    age, ra = p.age or 45, p.retire_age or 65
    working = ra > age and p.household_pay() > 0
    goal = p.spending_per_year or 0
    out = []
    if working:
        for k in (1, 2):
            if ra + k <= RETIRE_MAX:
                out.append({"key": "retire", "text": f"Retire at {ra + k}", "ch": {"retire_age": ra + k}})
        now = p.spending_now_per_year or 0
        if now > 0:
            x = min(max(1000, round(SPEND_LESS_SHARE * now, -3)), round(0.5 * now, -3))
            deficit = -float((m.get("inputs") or {}).get("save_per_year") or 0)
            if deficit > 0:
                # spending now above take-home pay drains savings: the cut that stops the drain (audit 3A P2-3)
                x = min(max(x, math.ceil(deficit / 1000) * 1000), round(0.5 * now, -3))
            txt = f"Spend ${x:,.0f} a year less now"
            ch = pipeline.parse_whatif(txt, p)
            # the What If reads it as a cut to spending now: run it the same way; else cut it here
            out.append({"key": "spend_now", "text": txt, "ch": ch} if ch.get("_spend_now") else
                       {"key": "spend_now", "text": txt, "spend_now_less": x})
        month = max(100, round(SAVE_MORE_SHARE * p.household_pay() / 12, -2))
        txt = f"Save ${month:,.0f} a month more"
        ch = pipeline.parse_whatif(txt, p)
        if ch and all(k in pipeline.AFFECTS or k.startswith("_") for k in ch):
            out.append({"key": "save", "text": txt, "ch": ch})
    claim, _, already = plan_claims(p, m)
    if not already and claim is not None and claim < 70:
        out.append({"key": "claim", "text": "Claim Social Security at 70", "ch": {"claim_age": 70}})
    basics = (m.get("inputs") or {}).get("basics_per_year") or 0
    new_goal = max(round(GOAL_CUT_SHARE * goal, -3), round(basics, -3))
    if goal and new_goal < goal - 999:
        cut = goal - new_goal
        txt = f"Spend ${cut:,.0f} a year less"
        parsed = pipeline.parse_whatif(txt, p)
        if parsed.get("spending_per_year") != new_goal or working:
            # the plain form for a goal: "Spend $X a year" (for someone working, "less" is a cut to spending now)
            txt = f"Spend ${new_goal:,.0f} a year" + (" in retirement" if working else "")
        out.append({"key": "goal", "text": txt, "ch": {"spending_per_year": new_goal}})
    return out


def _apply_try(p, t):
    """The profile after one change, or several at once (a combination). None when it cannot run."""
    from .. import pipeline
    parts = t if isinstance(t, list) else [t]
    ch: dict = {}
    for x in parts:
        ch.update(x.get("ch") or {})
    newp, notes = pipeline.apply_whatif(p, ch) if ch else (p.model_copy(deep=True), {})
    if notes.get("_say"):
        return None
    for x in parts:
        if x.get("spend_now_less"):
            newp = _spend_less(newp, x["spend_now_less"])
    return newp


def _join_texts(texts: list[str]) -> str:
    out = [texts[0]] + [t[0].lower() + t[1:] for t in texts[1:]]
    return out[0] if len(out) == 1 else ", ".join(out[:-1]) + " and " + out[-1]


async def starting_points(ctx: RunCtx) -> list[dict]:
    """When the basics are not safe: changes worked out on the person's own numbers (their age kept), kept only when
    they help (more scenarios pay the basics, or more to count on). When no single change makes the basics safe, the
    helpful ones are tried together. Each has a What If text for the same change. Those that make the basics safe
    come first."""
    from .. import pipeline
    p, m = ctx.profile, ctx.results["markets"]
    base_paid, base_safe = m.get("basics_paid_of_100") or 0, m.get("safe_spending_per_year") or 0

    async def run(t):
        try:
            newp = _apply_try(p, t)
            if newp is None:
                return None
            # scored on the plan's own strategy, as the What If for the same text is (pipeline.kept_for)
            fixed = ({"strategy": ctx.kept["strategy"], "neighbors": ctx.results.get("neighbors"), "repick": verdict(m) == "falls_short"}
                     if ctx.kept and ctx.kept.get("strategy") else None)
            c2 = RunCtx(profile=newp, use_ai=False, options=False, session=ctx.session, fixed=fixed)
            await pipeline.run_plan(c2)
            return c2.results["markets"]
        except Exception:      # a starting point is a help, never a reason for the plan to fail
            return None

    def point(t, m2):
        paid, safe = m2.get("basics_paid_of_100") or 0, m2.get("safe_spending_per_year") or 0
        helps = paid > base_paid or (safe >= 1.05 * base_safe and safe - base_safe >= HELPS_MIN)
        if not helps or (paid == 0 and safe <= 0):
            return None
        parts = t if isinstance(t, list) else [t]
        text = _join_texts([x["text"] for x in parts])
        res = f"basics paid in {paid} of 100 (now {base_paid}), and {money(safe)} a year to count on (now {money(base_safe)})"
        return {"title": text, "whatif_text": text, "paid_of_100": paid, "count_on_per_year": safe, "result": res,
                "makes_basics_safe": paid >= BASICS_SAFE, "keys": [x["key"] for x in parts]}

    tries = _tries(p, m)
    out = []
    for t in tries:
        m2 = await run(t)
        x = point(t, m2) if m2 else None
        if x:
            out.append(x)
    if out and not any(x["makes_basics_safe"] for x in out):
        # together: the latest retirement tried, with spending less now, a later claim and a smaller goal where each helped
        helped = {k for x in out for k in x["keys"]}
        best_retire = max((t for t in tries if t["key"] == "retire"), key=lambda t: t["ch"]["retire_age"], default=None)
        pool = [t for t in tries if t["key"] in helped and t["key"] in ("spend_now", "claim", "goal")]
        combo = ([best_retire] + pool) if (best_retire is not None and pool) else (pool if len(pool) >= 2 else None)
        if combo:
            m2 = await run(combo)
            x = point(combo, m2) if m2 else None
            if x:
                out.append(x)
    ra = p.retire_age or 65
    if not any(x["makes_basics_safe"] for x in out) and any(t["key"] == "retire" for t in tries):
        # a year or two is not enough: the nearest later age (never past 70) that helps, with the other helps beside it
        others = [t for t in tries if t["key"] in ("spend_now", "claim") and any(t["key"] in x["keys"] for x in out)]
        for age_try in sorted({a for a in (ra + 4, 62, 65, 67, RETIRE_MAX) if ra + 2 < a <= RETIRE_MAX}):
            t = {"key": "retire", "text": f"Retire at {age_try}", "ch": {"retire_age": age_try}}
            tries.append(t)
            got = []
            for c in ([t], [t] + others) if others else ([t],):
                m2 = await run(c)
                x = point(c, m2) if m2 else None
                if x:
                    got.append(x)
            out += got
            if any(x["makes_basics_safe"] for x in got):
                break
    out.sort(key=lambda x: (not x["makes_basics_safe"], -x["paid_of_100"], -x["count_on_per_year"]))
    # one "retire later" is enough: the nearer age when both make the basics safe, else the one that helps more
    rets = [x for x in out if x["keys"] == ["retire"]]
    safe_rets = [x for x in rets if x["makes_basics_safe"]]
    keep_ret = min(safe_rets, key=lambda x: x["title"]) if safe_rets else (rets[0] if rets else None)
    kept = [x for x in out if x["keys"] != ["retire"] or x is keep_ret]
    combos = [x for x in kept if "retire" in x["keys"] and len(x["keys"]) > 1]
    if len(combos) > 1:
        safe_c = [x for x in combos if x["makes_basics_safe"]]
        best = min(safe_c, key=lambda x: x["title"]) if safe_c else combos[0]
        kept = [x for x in kept if x not in combos or x is best]
    kept = kept[:3]
    for x in kept:
        ctx.extra_facts += [x["paid_of_100"], x["count_on_per_year"], base_paid, base_safe]
    for t in tries:
        ctx.extra_facts += [v for v in (t.get("ch") or {}).values() if isinstance(v, (int, float))] + [t.get("spend_now_less") or 0]
    return [{k: v for k, v in x.items() if k != "keys"} for x in kept]


def allowed_for_adviser(ctx: RunCtx) -> set[float]:
    findings = [{"numbers": f.get("numbers"), "text": [f.get("headline"), *f.get("details", [])]} for f in ctx.findings.values()]
    nb = ctx.results.get("neighbors") or {}
    return safety.allowed_numbers(findings, getattr(ctx, "tool_summaries", []), ctx.extra_facts, nb.get("note", ""),
                                  (ctx.results.get("family") or {}).get("moments", []),
                                  profile_facts(ctx.profile, (ctx.results.get("longevity") or {}).get("horizon_age")),
                                  ctx.profile.model_dump(exclude={"sources", "notes"}))


def figures_list(ctx: RunCtx) -> list[str]:
    """'Numbers you may use': every figure of every finding, formatted the way people read it."""
    out = []
    for name, f in ctx.findings.items():
        out += figure_lines(f.get("numbers") or {}, prefix=name + " ")
    return out


def template(ctx: RunCtx) -> AdviserOut:
    p, m, fam = ctx.profile, ctx.results["markets"], ctx.results["family"]
    tx = ctx.results.get("tax", {})
    basics = fam["basics"]["basics_per_year"]
    paid = m.get("basics_paid_of_100")
    room = above_basics(m, basics)
    goal = m["spending_goal_per_year"]
    v = verdict(m)
    needs = needs_line(m, basics)
    wants_line = (f"You can count on about {money(m['safe_spending_per_year'])} a year in 90 of 100 scenarios, "
                  f"{money(room)} more than the basics." if not wants_thin(m, basics) else headline(m, basics))
    wishes = f"Your spending goal of {money(goal)} a year lasts in {m['goal_lasts_of_100']} of 100 scenarios."
    if (m.get("extras") or {}).get("legacy_to_leave"):
        wishes += f" That keeps {money(m['extras']['legacy_to_leave'])} to leave behind."
    if v == "works" and m.get("median_at_horizon"):
        wishes += f" In a middle case, about {money(m['median_at_horizon'])} is left at the end for wishes."
    elif v == "close":
        wishes += " That is close to your goal; wishes wait until it is met."
    elif v != "works":
        wishes += " Your goal is above what lasts on these numbers, so wishes wait."
    actions = [Action(title=x["title"], why=x["why"]) for x in ranked_levers(p, m)[:2]]
    working = (p.retire_age or 65) > (p.age or 45)
    years_left = (p.retire_age or 65) - (p.age or 45)
    lim = tx.get("limits_2027") or {}
    near_limit = bool(lim) and costs.contributions(p)["you"] >= CATCH_UP_SHARE * lim["401k_limit"]
    if working and years_left >= MATCH_MIN_YEARS and (p.age or 45) >= 50 and lim and near_limit:
        actions.append(Action(title="Use the catch-up limit in your 401(k)",
                              why=f"From 50 you may add {money(lim['401k_catch_up_50_plus'])} a year on top of the {money(lim['401k_limit'])} limit."))
    elif working and years_left >= MATCH_MIN_YEARS:
        actions.append(Action(title="Save a little more each year until you retire",
                              why="Each dollar saved now has years to grow, and it lowers what you must draw later."))
    claim, _, already = plan_claims(p, m)
    if claim is not None and not already and (p.age or 0) < claim:
        actions.append(Action(title=f"Plan to claim Social Security at {claim}",
                              why=f"In this plan that pays about {money(m.get('social_security_per_year') or p.social_security_per_year)} a year for the household."))
    nb = ctx.results.get("neighbors") or {}
    why_mix = nb.get("note") or "This mix balances growth against falls in the market."
    actions.append(Action(title=f"Keep about {round(m['stock_share_now'] * 100)}% of savings in stocks now", why=why_mix))
    spares = [Action(**x) for x in SPARES]
    actions += spares[:max(0, 3 - len(actions))]
    return AdviserOut(needs_line=needs, wants_line=wants_line, wishes_line=wishes, actions=actions[:3])


LEVER_WORDS = {"goal": ("goal", "spend", "safe level"), "debt": ("debt", "loan", "card"), "match": ("match",),
               "emergency": ("emergency",), "life": ("life",), "disability": ("disability",), "ltc": ("long-term care",)}


def _same_action(a: dict, b: dict) -> bool:
    """Two actions that say the same thing: the same title (ignoring case and a trailing figure or full stop), or the
    same first four words ("Set your spending goal nearer ...")."""
    def norm(t: str) -> list[str]:
        return re.sub(r"[^a-z0-9 ]", " ", (t or "").lower()).split()
    x, y = norm(a["title"]), norm(b["title"])
    return bool(x) and bool(y) and (x == y or x[:4] == y[:4])


SPARES = [{"title": "Check your plan once a year",
           "why": "Markets, prices and your own needs change. A yearly check keeps the plan close to the facts."},
          {"title": "Draw on taxable savings first",
           "why": "Then pre-tax accounts, and Roth accounts last. That order usually keeps the tax bill lower."}]
CONCRETE = ("debt", "match")      # the actions that move money now: pay the high-rate debt, claim the match
STATUS_RE = re.compile(r"^\s*(?:keep\b(?! about \d)|continue|stay|stick|maintain|remain|plan for your money to last)\b", re.I)


def order_actions(ranked: list[dict], written: list) -> list[dict]:
    """The three actions, built in code from the tools' figures: the goal gap first when there is one, then the top
    concrete money action (high-rate debt, the employer match), then the next levers by dollar impact. The adviser's own
    actions fill what is left, and no action repeats another."""
    head = ranked[:2]
    head += [x for x in ranked[2:] if x["key"] in CONCRETE][:1]       # a third slot for a debt or match the top two skipped
    if len(head) < 3:
        head += [x for x in ranked[2:] if x not in head][:3 - len(head)]   # then the next real lever, before any filler
    out: list[dict] = []
    for x in head:
        a = {"title": x["title"], "why": x["why"]}
        if not any(_same_action(a, o) for o in out):
            out.append(a)
    used = [w for x in head for w in LEVER_WORDS.get(x["key"], ())]
    cands = [a.model_dump() for a in written]

    def repeats_lever(a: dict) -> bool:
        return any(w in (a["title"] + " " + a["why"]).lower() for w in used)

    def add(pool: list[dict]) -> None:
        for a in pool:
            if len(out) < 3 and not any(_same_action(a, o) for o in out):
                out.append(a)

    def status(a: dict) -> bool:
        # "Keep your spending goal at or below ...", "Keep saving toward 70": a state of affairs, not a thing to do
        return bool(STATUS_RE.match(a["title"] or ""))

    # the adviser's own actions that say something new, then the standing ones, and only then one that echoes a lever
    add([a for a in cands if not repeats_lever(a) and not status(a)])
    add([dict(a) for a in SPARES])
    add([a for a in cands if not status(a)])
    return out[:3]


def _repeats_plan(p, x: dict) -> bool:
    """A lever whose What If is the plan as it stands (retire at the age already planned)."""
    import re
    mm = re.search(r"retire at (\d{2})", (x.get("whatif_text") or "").lower())
    return bool(mm and int(mm.group(1)) == p.retire_age)


CHILD_MAX_AGE = 50      # no "another child" What If past this age


def lever_ok(p, text: str) -> bool:
    """A What If worth offering: no retirement age already passed, past 70, or for someone already retired; no
    "another child" past 50."""
    low = (text or "").lower()
    age = p.age or 45
    retired = (p.retire_age or 65) <= age
    mm = re.search(r"\bretire\w*\b[^.]{0,12}?\b(\d{2})\b", low)
    if mm and (retired or int(mm.group(1)) <= age or int(mm.group(1)) > RETIRE_MAX):
        return False
    if retired and re.search(r"\bretire\w*\b", low):
        return False
    if age > CHILD_MAX_AGE and re.search(r"\b(?:another|a new|one more|a)\s+(?:child|baby|kid)\b|\bhave a baby\b", low):
        return False
    return True


def costs_by_age(ctx: RunCtx) -> dict:
    """The cost timeline for the chart: ages, total and basics a year, labelled events, and notes on what is not counted."""
    c = ctx.results["family"]["costs"]
    h = ctx.results["longevity"]["horizon_age"]
    tl = costs.trim_timeline(c["timeline"], h)
    ltc = c["ltc"]
    p = ctx.profile
    notes = [f"Long-term care is not in these figures. A private nursing home room costs about ${ltc['nursing_home_per_year']:,.0f} a year, "
             f"and care lasts about {ltc['typical_years']:g} years on average."
             + (" You said you have cover." if p.insurance.ltc else "")]
    if (p.age or 0) < costs.MEDICARE_AGE:
        notes.append(f"Before Medicare at 65 a retired person pays about ${costs.PRE_MEDICARE_PREMIUM:,.0f} a year for health cover (an assumption).")
    # "costs now" is the spending-now figure the answers panel shows, so the two always agree
    now = round(p.spending_now_per_year) if p.spending_now_per_year else tl["total"][0]
    return {"ages": tl["ages"], "total": tl["total"], "basics": tl["basics"], "events": tl["events"], "parts": tl.get("parts", []),
            "now_per_year": now, "retired_per_year": p.spending_per_year, "retire_age": p.retire_age,
            "now_source": p.sources.get("spending_now_per_year", "you said"), "retired_source": p.sources.get("spending_per_year", "you said"),
            "notes": notes}


ANNUITY_MIN_SAVINGS = 200_000     # below this a single person has too little to put part of it into an income annuity
CHECK_NOTE = "This is something to look into, not a recommendation. I have not priced it."


def worth_checking(p, m: dict) -> list[dict]:
    """Products to look into when the person's own answers point to them. No prices, no advice to buy: each note says
    what the product is for and that it is a thing to check. Returns [{kind, title, why}]."""
    out: list[dict] = []
    ins = p.insurance
    working = (p.retire_age or 65) > (p.age or 45) and (p.household_pay() > 0)
    kids = any((c.age or 0) < 22 for c in p.children)
    partner_home = bool(p.has_partner and (p.partner_pay_per_year or 0) == 0 and (p.pay_per_year or 0) > 0)
    dependants = kids or partner_home
    no_life = ins.life_kind in (None, "none") or not (ins.life_face or 0)
    if dependants and working and no_life:
        out.append({"kind": "term_life", "title": "Term life insurance",
                    "why": "People depend on your pay and your answers show no life cover. Term life pays your household a sum if you die "
                           "while you still work. " + CHECK_NOTE})
    if dependants and working and ins.disability is not True and (p.pay_per_year or 0) > 0:
        out.append({"kind": "disability", "title": "Disability insurance",
                    "why": "People depend on your pay and your answers show no disability cover. It replaces part of your pay if illness "
                           "or injury stops you working. " + CHECK_NOTE})
    single = not p.has_partner
    # no field says "I worry about outliving my money", so the plan stands in: savings are large enough to matter and the
    # money runs out in the worst of the scenarios (the low case at the end is zero) or the goal does not last in all 100
    longevity = (m.get("low_at_horizon") or 0) <= 0 or (m.get("goal_lasts_of_100") or 0) < 100
    if single and p.savings.total >= ANNUITY_MIN_SAVINGS and longevity and not p.pensions and (p.age or 0) >= 50:
        out.append({"kind": "income_annuity", "title": "An income annuity",
                    "why": "You are one person with savings that may not last in a long life. An income annuity trades part of your savings "
                           "for a fixed sum each year for life. The sum loses value to inflation and the money cannot be taken back. "
                           "This is information only. " + CHECK_NOTE})
    return out


def horizon_text(p, lon: dict) -> str:
    """How long the money must last, in words that make sense for a big age gap: by the younger partner's age when
    your own age then would pass 100."""
    h = lon["horizon_age"]
    pa = lon.get("partner_age_at_horizon")
    if p.has_partner and p.partner_age and pa is not None and p.partner_age < (p.age or 0) and h > 100:
        return f"until your partner is {pa}"
    return f"to age {h}"


def saving_assumed(p) -> bool:
    """The 401(k) or IRA saving is an assumption (10% of pay), not the person's own figure."""
    return p.sources.get("save_rate") != "you said" and not p.saving.given()


def saving_used(ctx: RunCtx) -> dict:
    """The yearly saving the plan uses until retirement, in its parts (costs.saving_now, the same figure the answers
    panel shows as 'Yearly saving'). assumed: the 401(k) or IRA part is assumed, not given."""
    p = ctx.profile
    return {**costs.saving_now(p), "assumed": saving_assumed(p), "field": "Yearly saving"}


def ss_basis(p, m: dict) -> dict:
    """The Social Security figure in your answers (the panel) beside the one this plan uses. They differ when the plan
    starts it at another age than the one the answers were read at (67 unless you chose an age)."""
    claim, pclaim, already = plan_claims(p, m)
    panel = round(float(p.social_security_per_year or 0))
    plan = round(float(m.get("social_security_per_year") or 0))
    panel_age = p.claim_age if p.claim_age is not None else (household_claim(p) if p.sources.get("social_security_per_year") == "estimate" else 67)
    return {"panel_per_year": panel, "plan_per_year": plan, "panel_age": panel_age, "claim_age": claim, "partner_claim_age": pclaim,
            "already": already, "same": abs(panel - plan) < 100 or already}


def household_claim(p) -> int:
    from .. import household
    return household.claim_age(p)


def _when(claim, pclaim) -> str:
    """'at 67', 'at 63 for each of you', 'at 67 for you and 65 for your partner': each person at their own age."""
    if pclaim is not None and pclaim != claim:
        return f"at {claim} for you and {pclaim} for your partner"
    return f"at {claim}" + (" for each of you" if pclaim is not None else "")


def assumptions(ctx: RunCtx) -> list[str]:
    """The plan's assumptions in plain sentences, with the numbers the code used, most important first: today's
    dollars, returns, saving, Social Security, the survivor, health cover before Medicare, tax, the life table."""
    from ..tools import estimates, simulate as sim
    p, m = ctx.profile, ctx.results["markets"]
    lon = ctx.results["longevity"]
    age, ra = p.age or 45, p.retire_age or 65
    out = ["All figures are in today's dollars: what money buys now, not the larger sums prices will reach."]
    out.append(f"Savings grow on average {sim.STOCK_MU * 100:.1f}% a year above inflation in stocks and {sim.BOND_MU * 100:.1f}% in bonds, "
               "with good and bad years. The plan tests many possible market paths. These are planning figures, not a forecast. "
               "They are fixed, so every plan is tested on the same markets; to see a bad stretch, try a What If such as markets fall 30%.")
    if any(not x.inflation_adjusted for x in p.pensions):
        out.append(f"A pension with no yearly rise for prices loses about {sim.INFLATION * 100:.1f}% of its value each year.")
    # saving until retirement: the figure the answers show as "Yearly saving"
    if ra > age:
        sv = saving_used(ctx)
        acc = sv["accounts_per_year"]
        tag = " (assumed: 10% of pay)" if sv["assumed"] else ""
        parts = []
        if acc:
            parts.append(f"{money(acc)} into a 401(k) or IRA{tag}")
        if sv["match_per_year"]:
            parts.append(f"{money(sv['match_per_year'])} from your employer's match")
        if sv["other_per_year"]:
            parts.append(f"{money(sv['other_per_year'])} of other saving")
        if sv["unspent_pay_per_year"] > 0:
            parts.append(f"{money(sv['unspent_pay_per_year'])} of take-home pay left after your spending, which the plan assumes you save")
        if sv["per_year"] < 0:
            out.append(f"Your spending now is about {money(-sv['per_year'])} a year more than your take-home pay, so until you retire "
                       "the plan takes that from your savings each year. If that is wrong, change your spending now or your pay.")
        elif sv["unspent_pay_per_year"] < 0:
            out.append(f"Until you retire you save about {money(sv['per_year'])} a year: what your take-home pay leaves after your "
                       "spending now" + (", which is less than the 10% of pay assumed" if sv["assumed"] else ", which is less than the saving you gave")
                       + (f", plus {money(sv['match_per_year'])} from your employer's match" if sv["match_per_year"] else "")
                       + ". If that is wrong, change 'Yearly saving' or your spending now in your answers.")
        elif parts:
            out.append(f"Until you retire you save about {money(sv['per_year'])} a year: " + ", ".join(parts) +
                       ". If that is wrong, change 'Yearly saving' in your answers.")
        out.append("Pay stays at today's level until you retire, with no raises. This is fixed: raises are not certain, so the plan "
                   "does not count on them. If your pay changes, change it in your answers.")
        mort = costs.mortgage_end(p)
        if mort and costs.mortgage_separate(p) and mort["years_left"] > ra - age:
            out.append(f"Your spending in retirement leaves out the mortgage. The payments left after you retire, until {mort['end_year']}, "
                       "are counted as a cost of their own.")
    aside = p.notes.get("spending_now_per_year_set_aside") or p.notes.get("spending_per_year_set_aside")
    if aside:
        out.append(aside)
    if ra <= age and (p.notes.get("spending_per_year") or "").startswith("The same as you spend now"):
        out.append("You are retired, so the plan uses what you spend now as your spending.")
    # Social Security: the basis, then the age it starts in this plan
    b = ss_basis(p, m)
    if b["already"] and b["claim_age"] is not None:
        out.append(f"You already get Social Security (from {b['claim_age']}): the plan uses the {money(b['panel_per_year'])} a year you gave.")
    elif b["claim_age"] is not None:
        if p.sources.get("social_security_per_year") == "estimate":
            first = (f"Social Security is a rough estimate from today's pay, for work from about 22 until you retire "
                     f"(with fewer than {estimates.FULL_CAREER_YEARS} years of work, the missing years count as zero). "
                     "Your own figure is at ssa.gov/myaccount.")
        else:
            first = "Social Security uses the figure you gave" + ("." if p.claim_age is not None else ", read as the benefit at 67.")
        when = _when(b["claim_age"], b["partner_claim_age"])
        if b["same"]:
            out.append(first + f" It starts {when}: {money(b['plan_per_year'])} a year.")
        else:
            out.append(first + f" Your answers show {money(b['panel_per_year'])} a year from {b['panel_age']}. This plan starts it "
                       f"{when}, which pays about {money(b['plan_per_year'])} a year.")
        if b["partner_claim_age"] is not None:
            out.append("A partner with little pay of their own gets half of the other's benefit at 67, less if started sooner.")
    if m.get("social_security_survivor_per_year") and p.has_partner:
        out.append(f"After the first death (at the shorter life expectancy), Social Security falls to the larger of your two benefits, "
                   f"about {money(m['social_security_survivor_per_year'])} a year, and spending falls to "
                   f"{round(config.SURVIVOR_SPEND_SHARE * 100)}% of what the two of you spend.")
    if age < costs.MEDICARE_AGE:
        out.append(f"If you retire before Medicare starts at 65, health cover costs about {money(costs.PRE_MEDICARE_PREMIUM)} a person "
                   "a year until then (an assumption). Other health costs follow CMS figures by age.")
    state_ss = "" if tax_mod.state_exempts_ss(p.state, max(age, ra)) else " Your state taxes part of it too."
    work = ""
    if ra > age and p.household_pay() > 0:
        kids = any((c.age or 99) < costs.CHILD_CREDIT_AGE for c in p.children)
        work = " While you work, 401(k) saving comes off taxable pay" + (" and the child tax credit applies." if kids else ".")
    out.append("Tax uses the 2027 federal brackets, the standard deduction and your state's rates." + work +
               " In retirement the plan counts 85% of Social Security as taxable, the most the law allows, so the tax may be "
               "a little high." + state_ss)
    out.append(f"The plan runs {horizon_text(p, lon)}. There is about a 1 in 4 chance that "
               + ("one of you" if p.has_partner else "you") + " will live that long (US life table, SOA 2024). "
               "People with more money tend to live longer than that table says.")
    return out


CHANGE_RETIRE_Q = "Change my retirement age"
CHANGE_CLAIM_Q = "Change my Social Security start age"


def assumption_changes(p, m: dict) -> list[dict]:
    """Buttons under the Assumptions for the plan's own choices a person may change (R6): the retirement age, and the
    age Social Security starts. Each sends a change to the chat, which asks for the figure and confirms before it
    rebuilds the plan. Market growth and no raises stay fixed; the Assumptions say why."""
    out = []
    if (p.retire_age or 65) > (p.age or 45):
        out.append({"label": f"Change the retirement age ({p.retire_age})", "q": CHANGE_RETIRE_Q})
    claim, _, already = plan_claims(p, m)
    if claim is not None and not already and (p.age or 0) < 70:
        out.append({"label": f"Change when Social Security starts ({claim})", "q": CHANGE_CLAIM_Q})
    return out


def one_figure_check(ctx: RunCtx, plan: dict) -> list[str]:
    """One figure everywhere: the plan's saving, spending now and Social Security agree with the answers panel (the
    completed profile) and with the simulation's inputs. Returns the disagreements (empty when all agree); a
    disagreement is also logged."""
    import logging
    p, bad = ctx.profile, []
    ms = ctx.results.get("money") or {}
    sv = plan.get("saving") or {}
    if (p.retire_age or 65) > (p.age or 45) and ms and sv.get("per_year") != ms.get("save_now"):
        bad.append(f"saving: plan {sv.get('per_year')} vs simulation {ms.get('save_now')}")
    if sv.get("per_year") != costs.saving_now(p)["per_year"]:
        bad.append(f"saving: plan {sv.get('per_year')} vs answers {costs.saving_now(p)['per_year']}")
    now = (plan.get("costs_by_age") or {}).get("now_per_year")
    if p.spending_now_per_year and now != round(p.spending_now_per_year):
        bad.append(f"spending now: plan {now} vs answers {round(p.spending_now_per_year)}")
    b = ss_basis(p, ctx.results["markets"])
    text = " ".join([plan.get("headline") or ""] + list(plan.get("assumptions") or []))
    if b["claim_age"] is not None and not b["same"]:
        if money(b["panel_per_year"]) not in text or money(b["plan_per_year"]) not in text:
            bad.append(f"social security: answers {b['panel_per_year']} and plan {b['plan_per_year']} are not both named")
    elif b["claim_age"] is not None and "Social Security of" in (plan.get("headline") or "") and money(b["panel_per_year"]) not in plan["headline"]:
        bad.append(f"social security: headline does not show the answers' {b['panel_per_year']}")
    if bad:
        logging.getLogger("enough.plan").warning("one-figure check: %s", "; ".join(bad))
    return bad


def assemble(ctx: RunCtx, out: AdviserOut, source: str) -> dict:
    p, m, fam = ctx.profile, ctx.results["markets"], ctx.results["family"]
    nb = ctx.results.get("neighbors") or {}
    basics = fam["basics"]["basics_per_year"]
    chart = dict(m["chart"])
    chart["band"] = "10th to 90th percentile"
    claim, partner_claim, already = plan_claims(p, m)
    ranked = ranked_levers(p, m)
    safe = m["safe_spending_per_year"]
    lon = ctx.results["longevity"]
    return {
        "verdict": verdict(m),
        "verdict_words": VERDICT_WORDS[verdict(m)],
        "retire_age": p.retire_age,
        "already_retired": (p.retire_age or 65) <= (p.age or 45),
        "claim_age": claim,
        "partner_claim_age": partner_claim,
        "already_claiming": already,
        "partner_already_claiming": bool(m.get("partner_already_claiming")),
        "social_security_per_year": m.get("social_security_per_year"),
        "spending_goal": m["spending_goal_per_year"],
        "horizon_age": lon["horizon_age"],
        "horizon_text": horizon_text(p, lon),
        "starting_points": m.get("starting_points") or [],
        "saving": saving_used(ctx),
        "assumptions": assumptions(ctx),
        "assumption_changes": assumption_changes(p, m),
        "ss_basis": ss_basis(p, m),
        "needs": {"basics_per_year": basics, "paid_of_100": m.get("basics_paid_of_100"), "line": out.needs_line,
                  "basis": fam["basics"].get("basis", "typical")},
        "headline": headline(m, basics),
        # wants = what you can count on a year (safe in 90 of 100 scenarios), basics included; the headline's figure
        "wants": {"per_year": safe, "above_basics_per_year": above_basics(m, basics),
                  "line": headline(m, basics) if wants_thin(m, basics) else out.wants_line},
        "count_on_per_year": safe,
        "wishes": {"line": out.wishes_line},
        "actions": order_actions(ranked, out.actions),
        "worth_checking": worth_checking(p, m),
        "family_moments": fam["moments"],
        "neighbors": {"used": bool(nb.get("used")), "note": nb.get("note", ""), "candidates_tested": nb.get("candidates_tested", []),
                      "chosen": nb.get("chosen"), "low_confidence": bool(nb.get("low_confidence")),
                      "low_confidence_reasons": nb.get("low_confidence_reasons", [])},
        "chart": chart,
        "costs_by_age": costs_by_age(ctx),
        "levers": [{"key": x["key"], "title": x["title"], "why": x["why"], "whatif_text": x["whatif_text"]} for x in ranked
                   if x.get("whatif_text") and not _repeats_plan(p, x) and lever_ok(p, x["whatif_text"])],
        "citations": [{"title": c["title"], "url": c["url"]} for c in ctx.citations],
        "ai": ctx.ai_down is None and ctx.use_ai,
        "text_source": source,
        "note": "" if (ctx.ai_down is None and ctx.use_ai) else (llm.BUDGET_STOP if (ctx.ai_down or "").startswith("budget") else llm.AI_UNAVAILABLE),
    }


async def run(ctx: RunCtx) -> dict:
    """Write and assemble the plan. Emits agent_start, agent_done and the plan event."""
    await ctx.emit({"type": "agent_start", "agent": "adviser", "label": "Your plan"})
    t0 = time.time()
    m0 = ctx.results["markets"]
    if ctx.options and not ctx.shock and verdict(m0) == "falls_short" and "starting_points" not in m0:
        m0["starting_points"] = await starting_points(ctx)
    # the analysis (app/analysis.py) runs in a thread beside the model call, so it adds little time to the plan
    job = asyncio.create_task(asyncio.to_thread(plan_analysis, ctx)) if ctx.options and not ctx.shock else None
    b = ss_basis(ctx.profile, m0)
    m0["ss_when"] = "" if b["same"] or b["claim_age"] is None else " (starting " + _when(b["claim_age"], b["partner_claim_age"]) + " in this plan)"
    allowed = allowed_for_adviser(ctx)
    findings = {k: {"headline": f["headline"], "details": f["details"]} for k, f in ctx.findings.items()}
    m = ctx.results["markets"]
    nb = ctx.results.get("neighbors") or {}
    base_prompt = (
        f"Findings from the specialists (computed by tools):\n{json.dumps(findings, indent=1)}\n\n"
        "Numbers you may use (no other figures):\n" + "\n".join(figures_list(ctx)) + "\n\n"
        f"Verdict on the spending goal: {verdict(m)}.\n"
        f"Strategy test: {nb.get('note', 'not run')}\n"
        + ("Actions the person's own inputs point to, largest dollar effect first (use them first, in this order):\n"
           + "\n".join(f"- {x['title']}: {x['why']}" for x in ranked_levers(ctx.profile, m)) + "\n" if ranked_levers(ctx.profile, m) else "")
        +
        f"Family moments (already shown to the person): {json.dumps(ctx.results['family']['moments'])}\n"
        "Write the plan.")
    tokens = {"input": 0, "cached": 0, "output": 0}
    cost = 0.0
    out, source = None, "template"
    prompt = base_prompt
    for attempt in range(2):
        res, tk, c = await run_model(ctx, "adviser", lambda: _build(), prompt, llm.LEAD, "medium")
        for k in tokens:
            tokens[k] += tk[k]
        cost += c
        if res is None:
            break
        text = " ".join([res.needs_line, res.wants_line, res.wishes_line] + [a.title + " " + a.why for a in res.actions])
        check = safety.number_check(text, allowed)
        ctx.checks.append({"agent": "adviser", "attempt": attempt + 1, "ok": check.ok, "bad": check.bad, "text": text})
        if check.ok:
            out, source = res, "ai" if attempt == 0 else "ai (second try)"
            break
        source = "template (number check failed twice: " + ", ".join(check.bad[:4]) + ")"
        if ctx.deadline is not None and ctx.deadline - time.monotonic() < SECOND_TRY_SECONDS:
            source = "template (number check failed; no time for a second try: " + ", ".join(check.bad[:4]) + ")"
            break
        prompt = base_prompt + "\n\nYour last draft was rejected. " + safety.retry_note(check.bad) + " Rewrite it."
    if out is None:
        out = template(ctx)
    out = guard_lines(ctx, out)
    plan = assemble(ctx, out, source)
    plan["analysis"] = (await job) if job is not None else None
    plan["consistency"] = one_figure_check(ctx, plan)
    finding = {"headline": plan["headline"].split(". ")[0].rstrip(".") + ".", "details": short_details(plan),
               "numbers": {"basics_per_year": plan["needs"]["basics_per_year"], "paid_of_100": plan["needs"]["paid_of_100"],
                           "wants_per_year": plan["wants"]["per_year"], "spending_goal": plan["spending_goal"],
                           "retire_age": plan["retire_age"], "claim_age": plan["claim_age"]},
               "source": source}
    ctx.findings["adviser"] = finding
    await ctx.emit({"type": "agent_done", "agent": "adviser", "finding": finding, "tokens": tokens, "cost_usd": round(cost, 6),
                    "seconds": round(time.time() - t0, 2)})
    await ctx.emit({"type": "plan", "plan": plan})
    return plan


def plan_analysis(ctx: RunCtx) -> dict | None:
    """The plan's analysis section, checked against its schema. None when it cannot be worked out: the plan never
    fails because of it."""
    from .. import analysis
    from ..schemas import Analysis
    try:
        a = analysis.build(ctx)
        return Analysis.model_validate(a).model_dump() if a else None
    except Exception:
        logging.getLogger(__name__).exception("analysis failed")
        return None


LITTLE_ROOM = re.compile(r"little room|not much room|thin|tight", re.I)
FALLS_SHORT = re.compile(r"falls? short|fell short|does not work|doesn't work", re.I)
ABOUT_BASICS = re.compile(r"\babout (?:the|your) basics\b", re.I)


def _first_sentence(t: str) -> str:
    t = (t or "").strip()
    i = t.find(". ")
    return t if i < 0 else t[:i + 1]


def short_details(plan: dict) -> list[str]:
    """The adviser's finding for the team panel: two short sentences at most (the basics, then the goal)."""
    return [x for x in (_first_sentence(plan["needs"]["line"]), _first_sentence(plan["wishes"]["line"])) if x][:2]


def guard_lines(ctx: RunCtx, out: AdviserOut) -> AdviserOut:
    """Lines the code owns or checks: the needs line is built from basics paid of 100; a wants line that says there is
    little room when there is room, or a line that says "falls short" when the basics are safe, is replaced."""
    m, basics = ctx.results["markets"], ctx.results["family"]["basics"]["basics_per_year"]
    t = template(ctx)
    v = verdict(m)
    wants = out.wants_line
    if ((LITTLE_ROOM.search(wants) or ABOUT_BASICS.search(wants)) and not wants_thin(m, basics)) or             (FALLS_SHORT.search(wants) and v != "falls_short"):
        wants = t.wants_line
    wishes = out.wishes_line
    # the wishes line says what the verdict says, without contradicting itself: code-built unless the plan works and
    # the model's line names neither a shortfall nor a goal above what lasts
    if v != "works" or FALLS_SHORT.search(wishes) or re.search(r"\babove what|\bbelow what|\bnot safe|\bshort\b", wishes, re.I):
        wishes = t.wishes_line
    return AdviserOut(needs_line=needs_line(m, basics), wants_line=wants, wishes_line=wishes, actions=out.actions)


def _build():
    from pydantic_ai import Agent

    return Agent(llm.make_model(), output_type=AdviserOut, deps_type=RunCtx, instructions=INSTRUCTIONS, name="adviser")
