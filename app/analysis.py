"""The analysis: four short checks on the kept plan, all worked out in code on the plan's own scenarios (same strategy,
same 2,000 market paths, same seed), in today's dollars. No model call and no figure from a model.

1. How sure is it: the most you could spend a year and have it last in 50, 75, 90 and 95 of 100 scenarios, and the
   share of scenarios that last at each level of spending (each scenario's own limit, found in one search).
2. What could go wrong: the plan rerun under one stress at a time (a poor first decade, higher inflation for 10 years,
   living to 100, for a couple the first death 10 years early), against the plan.
3. What each choice is worth: the plan rerun with and without one change at a time (retire a year later, claim at 70,
   save $100 a month more, spend $1,000 a year less now, pay off high-rate debt, take the full match). The kept
   strategy (stock mix by age, claiming ages, any annuity) stays as it is, so the difference is the change alone.
4. Where the money comes from: each year's spending, split into pay, Social Security for each person, pensions, an
   annuity, savings, and any part the middle path cannot cover.
"""
from __future__ import annotations

import math
import time

import numpy as np

from .agents.base import RunCtx
from .tools import costs, neighbors, simulate, socialsec

LEVELS = (50, 75, 90, 95)
CURVE_POINTS = 41
STRESS_INFLATION = 0.015          # prices rise 1.5 points a year faster than assumed ...
STRESS_YEARS = simulate.SHOCK_YEARS   # ... for 10 years
EARLY_DEATH_YEARS = 10
LONG_LIFE_AGE = 100
SAVE_MORE_MONTH = 100
SPEND_LESS_YEAR = 1000
SIM_SS_KEYS = ("ss_per_year", "ss_age", "ss_by_year", "ss_people", "ss_first_death_t", "ss_work_by_year")


def _money(x: float) -> str:
    return f"${x:,.0f}"


# ------------------------------------------------------------------ one run of the kept strategy
def run_kept(sim: dict, strat: dict, people: list[dict], detail: bool = False, fixed_real: list[float] | None = None,
             trace_at: float | None = None) -> dict:
    """neighbors.score with the plan's strategy, on simulation inputs that may be changed (a stress or a lever)."""
    n = max(1, int(sim["horizon_age"]) - int(sim["age"]))
    ss = socialsec.schedule(people, n, strat["claim_age"], sim.get("ss_first_death_t"))
    args = {k: v for k, v in sim.items() if k not in SIM_SS_KEYS}
    you = ss["claims"].get("you", int(sim.get("ss_age") or 67))
    r = simulate.simulate(**args, ss_per_year=ss["total_per_year"], ss_age=you, ss_by_year=ss["by_year"],
                          ss_work_by_year=ss.get("working_by_year"), stock_path=strat["stock_path"], annuities=strat["annuities"],
                          chart=False, detail=detail, fixed_real_by_year=fixed_real, trace_at=trace_at)
    r["ss"] = ss
    return r


# ------------------------------------------------------------------ 1. how sure is it
def how_sure(sim: dict, strat: dict, people: list[dict], m: dict) -> tuple[dict, dict]:
    r = run_kept(sim, strat, people, detail=True)
    s = np.sort(r["_detail"]["max_spend"])[::-1]
    n = len(s)
    count_on = float(m.get("safe_spending_per_year") or 0)
    levels = []
    for q in LEVELS:
        v = max(0.0, float(s[max(0, math.ceil(q / 100 * n) - 1)]))
        v = count_on if q == 90 else round(v, -2)        # the 90 point is the plan's own figure (the same search)
        levels.append({"of_100": q, "per_year": v})
    for i in range(1, len(levels)):                      # never more for a surer level
        levels[i]["per_year"] = min(levels[i]["per_year"], levels[i - 1]["per_year"])
    goal = float(m.get("spending_goal_per_year") or 0)
    top = max(goal, count_on, levels[0]["per_year"], 1000.0) * 1.25
    step = max(100.0, round(top / (CURVE_POINTS - 1), -2))
    xs = [round(i * step) for i in range(CURVE_POINTS)]
    ys = [int(round(float((s >= x).mean()) * 100)) for x in xs]
    basics = float((m.get("inputs") or {}).get("basics_per_year") or sim.get("basics_per_year") or 0)
    out = {"levels": levels, "curve_spend": xs, "curve_lasts_of_100": ys, "goal_per_year": goal,
           "goal_lasts_of_100": int(m.get("goal_lasts_of_100") or 0), "count_on_per_year": count_on,
           "basics_per_year": basics, "basics_paid_of_100": int(m.get("basics_paid_of_100") or 0)}
    l50, l95 = levels[0]["per_year"], levels[-1]["per_year"]
    if l50 <= 0:
        out["line"] = ("On these numbers no level of spending lasts in half of the scenarios. Even with no spending of your own, "
                       f"the costs that come on top of it, such as health cover before Medicare, use up your savings in {100 - ys[0]} of 100.")
    else:
        out["line"] = (f"In half of the scenarios you could spend {_money(l50)} a year. To be sure in 90 of 100 it is "
                       f"{_money(count_on)}, and in 95 of 100, {_money(l95)}.")
    return out, r


# ------------------------------------------------------------------ 2. what could go wrong
def _row(key: str, title: str, what: str, r: dict, m: dict) -> dict:
    base_c, base_b = float(m.get("safe_spending_per_year") or 0), int(m.get("basics_paid_of_100") or 0)
    c, b = float(r["safe_spending_per_year"]), int(r["basics_paid_of_100"] or 0)
    return {"key": key, "title": title, "what": what, "count_on_per_year": c, "basics_paid_of_100": b,
            "count_on_change": round(c - base_c, -2), "basics_change": b - base_b}


def _first(trace: dict, i: int, sim: dict) -> dict:
    """One scenario's own story at the plan's count-on spending: the age its savings run out (None if they last), the
    years after that, the yearly gap (what it would still need from savings) and the income it has without savings."""
    n = trace["need"].shape[0]
    ft = int(trace["fail_t"][i])
    if ft < 0:
        return {"runs_out_age": None, "years_short": 0, "gap_per_year": 0.0, "income_per_year": 0.0}
    ts = range(ft, n)
    gap = float(np.mean([max(0.0, trace["need"][t, i]) for t in ts]))
    inc = float(np.mean([trace["inc"][t, i] + trace["ss"][t, i] + trace["ann"][t, i] for t in ts]))
    return {"runs_out_age": int(sim["age"]) + ft, "years_short": int(sim["horizon_age"]) - (int(sim["age"]) + ft),
            "gap_per_year": round(gap, -2), "income_per_year": round(inc, -2)}


def consequence(r: dict, sim: dict, ctx: RunCtx, P: float, c: float, b: int) -> dict:
    """How a stress plays out at the plan's own count-on spending P, in today's dollars: the worst 1 in 10 scenarios
    and the middle one (scenarios ordered by the year their savings run out; never running out counts last)."""
    tr = r.get("_trace")
    out = {"plan_spend_per_year": P, "worst_runs_out_age": None, "worst_years_short": 0, "worst_gap_per_year": 0.0,
           "typical_runs_out_age": None, "typical_years_short": 0, "typical_gap_per_year": 0.0, "typical_income_per_year": 0.0,
           "typical_income_from": "", "typical_lasts": True}
    if tr is None:
        return out
    n_p = len(tr["fail_t"])
    key = np.where(tr["fail_t"] < 0, 10 ** 6, tr["fail_t"])
    order = np.argsort(key, kind="stable")
    w = _first(tr, int(order[max(0, math.ceil(0.10 * n_p) - 1)]), sim)
    i_mid = int(order[max(0, math.ceil(0.50 * n_p) - 1)])
    t = _first(tr, i_mid, sim)
    out.update({"worst_runs_out_age": w["runs_out_age"], "worst_years_short": w["years_short"], "worst_gap_per_year": w["gap_per_year"],
                "typical_runs_out_age": t["runs_out_age"], "typical_years_short": t["years_short"],
                "typical_gap_per_year": t["gap_per_year"], "typical_income_per_year": t["income_per_year"],
                "typical_lasts": t["runs_out_age"] is None})
    if t["runs_out_age"] is not None:
        ft = int(tr["fail_t"][i_mid])
        ts = range(ft, tr["need"].shape[0])
        ss = float(np.mean([tr["ss"][k, i_mid] for k in ts]))
        inc = float(np.mean([tr["inc"][k, i_mid] for k in ts]))
        ann = float(np.mean([tr["ann"][k, i_mid] for k in ts]))
        pen = (ctx.results.get("money") or {}).get("flows", {}).get("pension_by_year") or []
        pension = float(np.mean([min(pen[k], sim["income_by_year"][k]) if k < len(pen) and k < len(sim["income_by_year"]) else 0.0 for k in ts]))
        parts = []
        if ss > 0:
            parts.append("Social Security")
        if pension > 0:
            parts.append("your pension")
        if ann > 0:
            parts.append("your annuity")
        if inc - pension > 1:
            parts.append("your pay")
        out["typical_income_from"] = " and ".join([", ".join(parts[:-1]), parts[-1]] if len(parts) > 2 else parts)
    return out


def _k(x: float) -> str:
    """A figure in whole thousands of dollars."""
    return f"${int(round(x / 1000.0)) * 1000:,}"


def _years(n: int) -> str:
    return "1 year" if n == 1 else f"{n} years"


def kind_of(x: dict) -> str:
    """Which story a stress tells: basics (at risk), fails (a typical path runs out), holds (only the worst 1 in 10 does), small."""
    if x["basics_at_risk"]:
        return "basics"
    if x["typical_runs_out_age"] is not None:
        return "fails"
    return "holds" if x["worst_runs_out_age"] is not None else "small"


def short_line(x: dict, couple: bool) -> str:
    """For risks that share one verdict (all "holds"): only what is particular to this risk, after the shared lead."""
    b = x["basics_paid_of_100"]
    age = f"when you are {x['worst_runs_out_age']}" if couple else f"at {x['worst_runs_out_age']}"
    return (f"savings run out {age}; you would cut about {_k(x['worst_gap_per_year'])} a year for {_years(x['worst_years_short'])}."
            + ("" if b >= 100 else f" Basics stay paid in {b} of 100 paths."))


def group_lead(rows: list[dict]) -> str:
    """The shared lead line when every shown risk has the same verdict, "holds"; else empty (full sentences instead)."""
    if len(rows) < 2 or any(kind_of(x) != "holds" for x in rows):
        return ""
    P = rows[0]["plan_spend_per_year"]
    if any(_k(x["plan_spend_per_year"]) != _k(P) for x in rows):
        return ""
    return f"Your {_k(P)} a year holds up in most market paths under each of these. In the worst 1 in 10:"


def sentence(x: dict, couple: bool) -> str:
    """One risk in plain words, built only from the row's own figures (no model). Figures are in whole thousands."""
    P, c, b = x["plan_spend_per_year"], x["count_on_per_year"], x["basics_paid_of_100"]

    def at(a: int) -> str:
        return f"when you are {a}" if couple else f"at {a}"
    if x["basics_at_risk"]:
        s = f"Your basics would go unpaid in {100 - b} of 100 market paths."
        if x["typical_runs_out_age"] is not None:
            s += f" In a typical path your savings run out {at(x['typical_runs_out_age'])}."
        if c <= 0:
            s += " No level of spending of your own would last."
        elif c < P and _k(c) != _k(P):
            s += f" You could count on about {_k(c)} a year, down from {_k(P)}."
        else:
            s += f" You could count on about {_k(c)} a year."
    elif x["typical_runs_out_age"] is not None:
        src = x["typical_income_from"]
        s = (f"Your {_k(P)} a year would run out {at(x['typical_runs_out_age'])} in a typical path. "
             + (f"You would have {_years(x['typical_years_short'])} with only {src}, about {_k(x['typical_income_per_year'])} a year."
                if src else f"You would have {_years(x['typical_years_short'])} with no income outside savings.")
             + (f" Spending {_k(c)} instead would last." if c > 0 else " No level of spending of your own would last."))
    elif x["worst_runs_out_age"] is not None:
        s = (f"Your {_k(P)} a year still lasts in most paths. In the worst 1 in 10, savings run out "
             f"{at(x['worst_runs_out_age'])}, and you would cut about {_k(x['worst_gap_per_year'])} a year for "
             f"{_years(x['worst_years_short'])}." + ("" if b >= 100 else f" Basics stay paid in {b} of 100 paths."))
    elif _k(c) != _k(P) and c < P:
        s = f"The plan still works: you could spend about {_k(c)} a year instead of {_k(P)}."
    else:
        s = f"The plan still works: you could still spend about {_k(P)} a year."
    if x["key"] == "early_death" and x.get("survivor_spend_pct"):
        s += f" Spending drops to {x['survivor_spend_pct']}% for the one left."
    return s


LABELS = {"bad_decade": "Stocks do badly for {y} years", "inflation": "Prices rise faster for {y} years",
          "long_you": "You live to {a}", "long_partner": "Your partner lives to {a}",
          "early_death": "The first death comes {y} years early", "late_death": "You both live {y} years longer together"}
BASICS_AT_RISK_BELOW = 90      # of 100: below this, the plan's basics are at risk under the stress


def _srow(key: str, title: str, what: str, r: dict, m: dict, sim: dict, ctx: RunCtx, couple: bool, **extra) -> dict:
    row = _row(key, title, what, r, m)
    P = float(m.get("safe_spending_per_year") or 0)
    row.update(extra)
    row["label"] = LABELS.get(key, title).format(y=row.get("stress_years"), a=row.get("to_age"))
    row["count_on_drop"] = max(0.0, -row["count_on_change"])
    row["basics_at_risk"] = row["basics_paid_of_100"] < BASICS_AT_RISK_BELOW
    row.update(consequence(r, sim, ctx, P, row["count_on_per_year"], row["basics_paid_of_100"]))
    row["sentence"] = sentence(row, couple) if P > 0 else ""
    row["kind"] = kind_of(row) if P > 0 else ""
    row["short"] = short_line(row, couple) if row["kind"] == "holds" else ""
    return row


def top_stresses(rows: list[dict], most: int = 3) -> list[str]:
    """The keys of the risks that hurt most: only those that cut what you can count on (or the basics), worst first."""
    hurt = [x for x in rows if x["count_on_change"] < 0 or x["basics_change"] < 0]
    hurt.sort(key=lambda x: (x["count_on_change"], x["basics_change"]))
    return [x["key"] for x in hurt[:most]]


def stresses(ctx: RunCtx, sim: dict, strat: dict, people: list[dict], m: dict) -> list[dict]:
    p = ctx.profile
    age, ra = int(sim["age"]), int(sim["retire_age"])
    out = []
    retired = ra <= age
    P = float(m.get("safe_spending_per_year") or 0)
    couple = bool(p.has_partner and p.partner_age)

    def go(s: dict, **kw) -> dict:
        return run_kept(s, strat, people, trace_at=P if P > 0 else None, **kw)

    def put(key, title, what, s, r, **extra):
        out.append(_srow(key, title, what, r, m, s, ctx, couple, **extra))
    # a poor first decade: the What If's "bad decade" (stocks earn 5 points a year less for 10 years)
    s1 = {**sim, "shock": {"kind": "bad_decade"}}
    put("bad_decade", "A poor first decade",
        f"Stocks earn {round(simulate.BAD_DECADE_CUT * 100)} points a year less than usual for the first 10 years "
        + ("from now." if retired else "of your retirement."), s1, go(s1), stress_years=STRESS_YEARS)
    # higher inflation: savings earn 1.5 points less after prices for 10 years; fixed pensions and annuities buy less
    n_all = len(sim["income_by_year"])
    fr = [(1 - STRESS_INFLATION) ** min(t, STRESS_YEARS) for t in range(n_all)]
    fixed = (ctx.results.get("money") or {}).get("flows", {}).get("pension_fixed_by_year") or [0.0] * n_all
    start = next((t for t, v in enumerate(fixed) if v > 0), 0)
    inc = [max(0.0, x - fixed[t] * (1 - fr[t] / fr[start])) if t >= start and t < len(fixed) else x
           for t, x in enumerate(sim["income_by_year"])]
    s2 = {**sim, "shock": {"kind": "inflation", "size": STRESS_INFLATION}, "income_by_year": inc}
    has_fixed = any(fixed) or bool(strat["annuities"])
    put("inflation", "Higher inflation",
        f"Prices rise {STRESS_INFLATION * 100:.1f} points a year faster than we assume for 10 years, so savings earn that much less"
        + (", and pensions and annuities with no cost-of-living rise buy less." if has_fixed else "."),
        s2, go(s2, fixed_real=fr), stress_years=STRESS_YEARS)
    # living to 100: the money must last longer (each person in a couple)
    h = int(sim["horizon_age"])
    tries = [("long_you", "You live to 100" if couple else "Living to 100", age + (LONG_LIFE_AGE - age))]
    if couple:
        tries.append(("long_partner", "Your partner lives to 100", age + (LONG_LIFE_AGE - int(p.partner_age))))
    for key, title, h2 in tries:
        if h2 <= h or h2 - age > costs.N_YEARS:
            continue
        who = "you are" if key != "long_partner" else "your partner is"
        s3 = {**sim, "horizon_age": h2}
        put(key, title, f"The money must last until {who} 100, {h2 - h} years longer than the plan.", s3, go(s3), to_age=LONG_LIFE_AGE)
    # the first death 10 years early (couples), never before you have both stopped work
    t0 = sim.get("ss_first_death_t")
    lon = ctx.results.get("longevity") or {}
    le_y, le_p = lon.get("life_expectancy_you"), lon.get("life_expectancy_partner")
    if couple and t0 is not None and le_y is not None and le_p is not None:
        both_retired = max(0, ra - age, costs.partner_retire_age(p) - int(p.partner_age))
        t1 = max(both_retired, int(t0) - EARLY_DEATH_YEARS)
        if t1 < t0:
            cut = t0 - t1
            ly, lp = (le_y - cut, le_p) if le_y <= le_p else (le_y, le_p - cut)
            tx = ctx.results["tax"]
            ms = costs.money_side(p, tx.get("other_income_tax_rate", 0.0), tx.get("partner_net_pay", 0), ly, lp,
                                  ctx.results["family"]["costs"])
            s4 = {**sim, "ss_first_death_t": t1, "spend_drop_t": t1, "income_by_year": ms["income_by_year"]}
            put("early_death", "The first death comes 10 years early" if cut >= EARLY_DEATH_YEARS else
                f"The first death comes {cut} years early",
                f"The first of you to die does so {cut} years sooner than expected: one Social Security check "
                f"and any pension survivor share from then, and spending falls to "
                f"{round(simulate.SURVIVOR_SPEND_SHARE * 100)}%.", s4, go(s4), stress_years=int(cut),
                survivor_spend_pct=round(simulate.SURVIVOR_SPEND_SHARE * 100))
            if out[-1]["count_on_change"] > 0:
                out[-1]["note"] = "Spending falls as well, so the money goes a little further. The one who is left has less income."
        # the other way round (audit 3A P2-6): both live longer together, so the couple's spending runs longer
        h_t = int(sim["horizon_age"]) - age
        t2 = min(h_t - 1, int(t0) + EARLY_DEATH_YEARS)
        if t2 > t0:
            add = t2 - t0
            ly, lp = (le_y + add, le_p) if le_y <= le_p else (le_y, le_p + add)
            tx = ctx.results["tax"]
            ms = costs.money_side(p, tx.get("other_income_tax_rate", 0.0), tx.get("partner_net_pay", 0), ly, lp,
                                  ctx.results["family"]["costs"])
            s5 = {**sim, "ss_first_death_t": t2, "spend_drop_t": t2, "income_by_year": ms["income_by_year"]}
            put("late_death", f"You both live {add} years longer together",
                 f"The first death comes {add} years later than expected, so the two of you spend at the couple's "
                 "level for longer before it falls.", s5, go(s5), stress_years=int(add))
            if out[-1]["count_on_change"] > 0:
                out[-1]["note"] = "Two Social Security checks also last longer, and they more than pay for it."
    return out


# ------------------------------------------------------------------ 3. what each choice is worth
def lever_tries(p, m: dict) -> list[dict]:
    """One change at a time, only those that fit the person: never their age, never retiring past 70 or once retired."""
    from . import pipeline
    from .agents import adviser
    age, ra = p.age or 45, p.retire_age or 65
    working = ra > age and p.household_pay() > 0
    out = []
    if working and ra + 1 <= adviser.RETIRE_MAX:
        out.append({"key": "retire", "title": f"Retire 1 year later, at {ra + 1}", "ch": {"retire_age": ra + 1}, "ask": f"What if I retire at {ra + 1}"})
    claim, _, already = adviser.plan_claims(p, m)
    if not already and claim is not None and claim < 70:
        out.append({"key": "claim", "title": "Claim Social Security at 70", "ch": {"claim_age": 70}, "claim": 70, "ask": "What if I claim Social Security at 70"})
    if working:
        txt = f"Save ${SAVE_MORE_MONTH} a month more"
        ch = pipeline.parse_whatif(txt, p)
        if ch and all(k in pipeline.AFFECTS or k.startswith("_") for k in ch):
            out.append({"key": "save", "title": txt, "ch": ch, "ask": f"What if I save ${SAVE_MORE_MONTH} a month more"})
        if (p.spending_now_per_year or 0) > SPEND_LESS_YEAR:
            txt = f"Spend ${SPEND_LESS_YEAR:,} a year less now"
            ch = pipeline.parse_whatif(txt, p)
            ask = f"What if I spend ${SPEND_LESS_YEAR:,} a year less now"
            out.append({"key": "spend_now", "title": txt, "ch": ch, "ask": ask} if ch.get("_spend_now") else
                       {"key": "spend_now", "title": txt, "spend_now_less": SPEND_LESS_YEAR, "ask": ask})
    for lv in m.get("levers") or []:
        if lv.get("key") in ("debt", "match") and lv.get("whatif_text"):
            if lv["key"] == "match" and not working:
                continue
            ch = pipeline.parse_whatif(lv["whatif_text"], p)
            if ch and "shock" not in ch:
                out.append({"key": lv["key"], "title": lv["title"], "ch": ch, "ask": lv["whatif_text"]})
    return [t for t in out if adviser.lever_ok(p, t["title"])]


def rerun_with(ctx: RunCtx, t: dict) -> dict | None:
    """The plan's tools on the changed profile, scored with the kept strategy. None when the change cannot run."""
    from .agents import adviser
    from .agents.family import Family
    from .agents.longevity import Longevity
    from .agents.markets import sim_inputs
    from .agents.tax import Tax
    newp = adviser._apply_try(ctx.profile, t)
    if newp is None:
        return None
    c2 = RunCtx(profile=newp, use_ai=False, options=False, session=ctx.session)
    for sp in (Longevity(), Family(), Tax()):
        c2.results[sp.name] = sp.compute(c2)
    sim2 = sim_inputs(c2)
    # the same rule as the What If for the same change (neighbors.one_change, pipeline.kept_for)
    from .agents.adviser import verdict
    person = newp.model_dump()
    strat, _ = neighbors.one_change(person, sim2, ctx.kept["strategy"], verdict(ctx.results["markets"]) == "falls_short")
    if t.get("claim"):
        strat = {**strat, "claim_age": t["claim"]}
    return neighbors.score(person, sim2, strat)


def levers(ctx: RunCtx, m: dict) -> list[dict]:
    rows = []
    for t in lever_tries(ctx.profile, m):
        try:
            r = rerun_with(ctx, t)
        except Exception:      # one change that cannot run never stops the analysis
            r = None
        if r is None:
            continue
        row = _row(t["key"], t["title"], "", r, m)
        row["ask"] = t.get("ask") or t["title"]
        if t["key"] == "retire" and row["count_on_change"] <= 0 and (ctx.results.get("money") or {}).get("save_now", 0) < 0:
            from .pipeline import DEFICIT_LATER
            row["note"] = DEFICIT_LATER.split(". ")[0] + "."
        if t["key"] == "save" and row["count_on_change"] == 0 and (ctx.results.get("money") or {}).get("unspent_pay_per_year", 0) > 0:
            row["note"] = "Your plan already counts the pay you do not spend as saved, so this adds nothing new."
        rows.append(row)
    rows.sort(key=lambda x: (-x["count_on_change"], -x["basics_change"], x["title"]))
    for x in rows:
        x.pop("what", None)
    return rows


# ------------------------------------------------------------------ 4. where the money comes from
def sources(ctx: RunCtx, sim: dict, strat: dict, base: dict, m: dict) -> dict:
    """Each year's spending at your goal, and what pays for it. Social Security and pensions are after tax, and so is
    what comes out of savings. Savings, and an annuity bought with them, follow the middle path of the savings chart."""
    p = ctx.profile
    age, ra = int(sim["age"]), int(sim["retire_age"])
    n = max(1, int(sim["horizon_age"]) - age)
    ss = base["ss"]
    med = base["_detail"]["median_by_year"]
    ss_tax = float(sim.get("ss_tax_rate") or 0)
    spend = float(sim["spend_per_year"] or 0)
    drop_t = sim.get("spend_drop_t")
    extra, inc, save = sim["extra_by_year"], sim["income_by_year"], sim["save_by_year"]
    tax_by = sim.get("tax_rate_by_year") or []
    flows = (ctx.results.get("money") or {}).get("flows", {})
    pen = flows.get("pension_by_year") or [0.0] * n
    pay_left = flows.get("pay_left_by_year") or []
    tl =ctx.results["family"]["costs"]["timeline"]["total"]
    each = ss.get("each_by_year") or {}
    who = list(each)
    couple = len(who) == 2
    ann_rows = strat["annuities"]
    t_buy = max(0, min(n, max(ra, age) - age))
    rows = {k: [0] * n for k in ("pay", "ss_you", "ss_partner", "pension", "annuity", "savings", "short")}
    spending, surplus = [0] * n, [0] * n
    for t in range(n):
        a = age + t
        retired = a >= ra
        # Social Security after its tax, split by person; after the first death the survivor keeps the larger check
        total_ss = ss["by_year"][t] if retired else ss["working_by_year"][t]
        if couple:
            y, q = each[who[0]][t], each[who[1]][t]
            if ss.get("first_death_t") is not None and t >= ss["first_death_t"]:
                y, q = (max(y, q), 0) if y >= q else (0, max(y, q))
            tot = (y + q) or 1
            ss_y, ss_q = total_ss * y / tot, total_ss * q / tot
        else:
            ss_y, ss_q = total_ss, 0.0
        ss_y, ss_q = round(ss_y * (1 - ss_tax)), round(ss_q * (1 - ss_tax))
        if retired:
            sp = spend * (simulate.SURVIVOR_SPEND_SHARE if (drop_t is not None and t >= drop_t) else 1.0)
            need_total = round(sp + extra[t])
            pension = round(min(pen[t], inc[t])) if t < len(pen) else 0
            pay = round(inc[t]) - pension
            ann = 0
            if ann_rows and t >= t_buy:
                w_buy = float(med[t_buy])
                for an in ann_rows:
                    if a >= an["start_age"]:
                        ann += w_buy * an["share"] * an["payout_rate"] * (1 - simulate.INFLATION) ** max(0, a - an["buy_age"])
                ann = round(ann)
            need = need_total - pay - pension - ss_y - ss_q - ann
            draw = max(0, need)
            gu = 1.0 - (tax_by[t] if t < len(tax_by) else float(sim["tax_rate"]))
            can = max(0.0, float(med[t])) * max(0.05, gu)     # what the middle path still holds, after tax
            covered = draw if can >= draw else round(can)
            vals = {"pay": pay, "ss_you": ss_y, "ss_partner": ss_q, "pension": pension, "annuity": ann,
                    "savings": covered, "short": draw - covered}
            spending[t] = need_total
            surplus[t] = max(0, -need)
        else:
            # while at work: the costs chart's total, paid from pay and any benefit already paid. Take-home pay left after
            # spending now (the part of the yearly saving that is not a 401(k), IRA or match) pays the costs on top
            # (college, big costs, health cover) first; only what it cannot cover comes from savings, and what is left
            # over is saved. The simulation nets the same flows (saving in, costs out), so the totals agree (audit R12:
            # a $310,000 earner saving $182,071 a year showed "pay $25,461, from savings $99,640").
            need_total = int(tl[t]) if t < len(tl) else 0
            left = float(pay_left[t]) if t < len(pay_left) else min(0.0, float(save[t]))
            from_sav = round(max(0.0, max(0.0, extra[t]) - left))
            kept = max(0, round(left - max(0.0, extra[t])))        # take-home pay left over after all of it: saved
            pay = need_total - from_sav - ss_y - ss_q
            vals = {"pay": max(0, pay) + kept, "ss_you": ss_y, "ss_partner": ss_q, "pension": 0, "annuity": 0,
                    "savings": from_sav, "short": 0}
            spending[t] = need_total
            surplus[t] = kept + max(0, -pay)
        for k, v in vals.items():
            rows[k][t] = int(v)
    labels = {"pay": "Pay", "ss_you": "Social Security, you" if couple else "Social Security",
              "ss_partner": "Social Security, your partner", "pension": "Pensions", "annuity": "Annuity",
              "savings": "From savings", "short": "Not covered: savings run out"}
    series = [{"key": k, "label": labels[k], "values": rows[k]} for k in labels if any(rows[k])]
    short_at = next((age + t for t in range(n) if rows["short"][t] > 0), None)
    if short_at is not None:
        line = f"In the middle path your savings run out at {short_at}; from then part of your spending is not covered."
    elif ra > age:
        line = "Pay covers your spending until you retire; after that Social Security, any pension and your savings do."
    else:
        line = "Social Security, any pension and your savings pay for each year's spending."
    return {"ages": [age + t for t in range(n)], "spending": spending, "series": series, "surplus": surplus,
            "line": line, "goal_per_year": spend}


# ------------------------------------------------------------------ all four
def build(ctx: RunCtx) -> dict | None:
    """The analysis for the kept plan, or None when the plan has no kept strategy (a market What If)."""
    if not ctx.kept or not ctx.kept.get("strategy"):
        return None
    t0 = time.time()
    m = ctx.results["markets"]
    sim, strat = ctx.kept["sim"], ctx.kept["strategy"]
    people = neighbors._people(ctx.kept["person"], sim)
    sure, base = how_sure(sim, strat, people, m)
    st = stresses(ctx, sim, strat, people, m)
    lv = levers(ctx, m)
    src = sources(ctx, sim, strat, base, m)
    worst = min(st, key=lambda x: (x["basics_change"], x["count_on_change"]), default=None)
    if worst and worst["count_on_change"] >= 0 and worst["basics_change"] >= 0:
        worst = None
    st_line = (f"Of these, {worst['title'].lower()} hurts most: you could count on {_money(worst['count_on_per_year'])} a year, "
               f"and your basics are paid in {worst['basics_paid_of_100']} of 100 scenarios." if worst else
               "Your plan already falls short, so these tests cannot lower it further." if not m.get("safe_spending_per_year") and not m.get("basics_paid_of_100")
               else "None of these tests lowers what you can count on.")
    if lv and lv[0]["count_on_change"] > 0:
        lv_line = f"{lv[0]['title']} adds the most: {_money(lv[0]['count_on_change'])} a year to count on."
    elif lv:
        lv_line = "None of these changes adds to what you can count on by itself." + (
            " The starting points above show bigger changes." if m.get("starting_points") else "")
    else:
        lv_line = "There is no change of this kind left to test on your numbers."
    return {
        "paths": int(m.get("paths") or simulate.PATHS), "seed": int(m.get("seed") or simulate.SEED),
        "plan_count_on_per_year": float(m.get("safe_spending_per_year") or 0),
        "plan_basics_paid_of_100": int(m.get("basics_paid_of_100") or 0),
        "how_sure": sure,
        "stresses": {"rows": st, "line": st_line, "top": top_stresses(st), "lead": group_lead([x for k in top_stresses(st) for x in st if x["key"] == k])},
        "levers": {"rows": lv, "line": lv_line},
        "sources": src,
        "seconds": round(time.time() - t0, 2),
    }
