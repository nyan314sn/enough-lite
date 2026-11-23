"""Markets agent: the simulation tool and the similar-households tool.

1. simulate_plan: 2,000 market scenarios on the rule of thumb (stocks 110 minus age, capped by the risk choice).
2. test_similar_households: the whole strategies of the 5 most similar households in the library, and the rule of
   thumb, scored on the person's own numbers with the same scenarios; the plan keeps the one that pays the basics most
   often, then leaves the most to spend.
"""
from __future__ import annotations

import asyncio

from .. import household
from ..tools import costs, neighbors, simulate
from .base import RunCtx, Specialist, money, tool_event


def sim_inputs(ctx: RunCtx) -> dict:
    p = ctx.profile
    lon, fam, tx = ctx.results["longevity"], ctx.results["family"], ctx.results["tax"]
    age, ra = p.age or 45, p.retire_age or 65
    c = fam["costs"]
    ms = costs.money_side(p, tx.get("other_income_tax_rate", 0.0), tx.get("partner_net_pay", 0), lon.get("life_expectancy_you"),
                          lon.get("life_expectancy_partner"), c)
    ctx.results["money"] = ms
    extra = c["extra_by_year"]
    n = max(1, lon["horizon_age"] - age)
    ss = household.ss_household(p, n, lon.get("life_expectancy_you"), lon.get("life_expectancy_partner"))
    working = ra > age
    return {
        "age": age, "retire_age": ra, "horizon_age": lon["horizon_age"],
        "savings": p.savings.total, "save_per_year": ms["save_now"] if working else 0,
        "spend_per_year": p.spending_per_year or 0, "ss_per_year": ss["total_per_year"], "ss_age": ss["claims"]["you"],
        "ss_by_year": ss["by_year"], "ss_people": ss["people"], "ss_first_death_t": ss["first_death_t"],
        "ss_work_by_year": ss["working_by_year"], "spend_drop_t": ss["first_death_t"],
        "extra_by_year": extra, "tax_rate": tx["effective_rate_on_withdrawals"],
        "tax_rate_by_year": [tx["effective_rate_on_withdrawals"] if x > 0 else tx.get("rate_without_other_income", tx["effective_rate_on_withdrawals"])
                             for x in ms["income_by_year"]], "risk": p.risk or "balanced",
        "basics_per_year": fam["basics"]["basics_per_year"],
        "save_by_year": ms["save_by_year"], "income_by_year": ms["income_by_year"], "lump_by_year": ms["lump_by_year"],
        "legacy": ms["legacy"], "ss_tax_rate": tx.get("social_security_tax_rate", 0.0),
        "shock": ctx.shock,
    }


ARRAYS = ("extra_by_year", "save_by_year", "income_by_year", "lump_by_year", "ss_by_year", "ss_people", "tax_rate_by_year", "ss_work_by_year")
NOT_SIM = ("ss_people", "ss_first_death_t")     # inputs for the strategy test, not for simulate()


def sim_args(sim: dict) -> dict:
    return {k: v for k, v in sim.items() if k not in NOT_SIM}


def extras(ctx: RunCtx) -> dict:
    """Figures from the person's own inputs that the plan quotes. Worked out in code so the text may use them."""
    p = ctx.profile
    ms, c = ctx.results["money"], ctx.results["family"]["costs"]
    m = ms["match"]
    out = {"contributions_per_year": ms["contributions"]["you"] + ms["contributions"]["partner"],
           "other_saving_per_year": ms["contributions"]["other"]}
    if m.get("rate") is not None:
        out.update({"employer_match_per_year": m["match"], "match_full_contribution": m["full_contribution"],
                    "match_missed_per_year": m["missed"]})
    if ms["pension_per_year"]:
        out["pension_per_year"] = ms["pension_per_year"]
    if ms["income_at_retirement"]:
        out["other_income_after_tax_at_retirement"] = ms["income_at_retirement"]
    if ms["legacy"]:
        out["legacy_to_leave"] = ms["legacy"]
    if ms["inheritance_counted"]:
        out["inheritance_counted"] = ms["inheritance_amount"]
    mort = c["mortgage"]
    if mort:
        out["costs_fall_when_mortgage_ends"], out["mortgage_ends_year"] = mort["drop_per_year"], mort["end_year"]
    d = c["debts"]
    if d["total_balance"]:
        out.update({"debt_total_balance": d["total_balance"], "debt_payment_per_year": d["payment_per_year"]})
    out["big_costs_total"], out["parents_help_total"] = sum(c["big"]), sum(c["parents"])
    lv = costs.levers(p, d, m, p.spending_now_per_year or 0, p.savings.cash)
    for x in lv:
        out.update(x["numbers"])
    return out, lv


def derived_markets(r: dict, inp: dict) -> dict:
    """Figures worked out in code so the text may quote them: differences, monthly amounts, years until."""
    goal, safe = r.get("spending_goal_per_year") or 0, r.get("safe_spending_per_year") or 0
    out = {"goal_runs_out_of_100": 100 - r["goal_lasts_of_100"], "gap_per_year": max(0, goal - safe),
           "safe_spending_per_month": round(safe / 12), "spending_goal_per_month": round(goal / 12), "scenarios": r.get("paths", simulate.PATHS)}
    if goal:
        out["safe_share_of_goal"] = round(safe / goal, 2)
    ra, age = inp.get("retire_age"), inp.get("age")
    if ra and age and ra > age:
        out["years_to_retire"] = ra - age
    return out


class Markets(Specialist):
    name = "markets"
    label = "Markets"
    tool_name = "simulate_plan"
    tool_doc = "Run 2,000 market scenarios for this household on the rule of thumb and report how often the money lasts."
    tool2_name = "test_similar_households"
    tool2_doc = ("Test the whole strategies of the 5 most similar households in the library, and the rule of thumb, on this "
                 "household's numbers. Keeps the one that pays the needs most often, then leaves the most to spend.")
    instructions = ("You are the markets specialist in a retirement-planning team. The tools have run. Say how often the spending "
                    "goal lasts, the most the household can spend and still be safe in 90 of 100 market tests, and which plan "
                    "was kept, in plain words (a simple plan, or the plan of a similar household). Report the kept plan's figures "
                    "only. Say plainly that markets are uncertain. A figure whose name ends in 'assumed' is an assumption, "
                    "not the person's own figure: if you use it, say it is assumed.")

    def compute(self, ctx: RunCtx) -> dict:
        sim = sim_inputs(ctx)
        r = simulate.simulate(**sim_args(sim))
        r["inputs"] = {k: v for k, v in sim.items() if k not in ARRAYS}
        r["extras"], r["levers"] = extras(ctx)
        r["strategy"] = "Simple plan"
        p = ctx.profile
        r["saving_assumed"] = (p.retire_age or 65) > (p.age or 45) and p.sources.get("save_rate") != "you said" and not p.saving.given()
        return r

    def summary(self, r: dict) -> str:
        return (f"{r['paths']:,} market tests: the goal lasts in {r['goal_lasts_of_100']} of 100; "
                f"safe spending {money(r['safe_spending_per_year'])} a year.")

    async def run_neighbors(self, ctx: RunCtx) -> dict:
        if "neighbors" in ctx.results:
            return ctx.results["neighbors"]
        base = await self.run_tool(ctx)
        sim = sim_inputs(ctx)
        person = ctx.profile.model_dump()
        if ctx.fixed and ctx.fixed.get("strategy"):
            # one change to the plan: keep the plan's strategy, so only the change moves the figures (the same path as the
            # analysis's "what each choice is worth"; a fresh pick let retiring a year later give less, audit R12)
            strat0, fresh = await asyncio.to_thread(neighbors.one_change, person, sim, ctx.fixed["strategy"], bool(ctx.fixed.get("repick")))
            r0 = chosen = await asyncio.to_thread(neighbors.score, person, sim, strat0, True)
            if fresh is not None:
                res = fresh
            else:
                old = ctx.fixed.get("neighbors") or {}
                kept = {**(old.get("chosen") or {}), "name": strat0["name"], "source": strat0["source"],
                        "basics_paid_of_100": r0["basics_paid_of_100"], "safe_spending_per_year": r0["safe_spending_per_year"],
                        "wants_per_year": r0["wants_per_year"], "goal_lasts_of_100": r0["goal_lasts_of_100"], "claim_age": r0["claim_age"]}
                res = {**{k: v for k, v in old.items() if k != "kept_strategy_result"}, "chosen": kept, "chosen_strategy": strat0,
                       "candidates_tested": [kept]}
        else:
            res = await asyncio.to_thread(neighbors.test_strategies, person, sim)
            chosen = await asyncio.to_thread(neighbors.score, person, sim, res["chosen_strategy"], True)
        chosen["inputs"] = base["inputs"]
        chosen["extras"], chosen["levers"] = base["extras"], base["levers"]
        chosen["saving_assumed"] = base.get("saving_assumed", False)
        chosen["strategy"] = res["chosen"]["name"]
        chosen["rule_of_thumb"] = {k: base[k] for k in ("goal_lasts_of_100", "safe_spending_per_year", "basics_paid_of_100")}
        strat = res.pop("chosen_strategy", None)
        ctx.kept = {"strategy": strat, "sim": sim, "person": person}
        chosen.update(derived_markets(chosen, base["inputs"]))
        # why what you can count on may sit below Social Security (for the headline's note)
        age, ra = sim["age"], sim["retire_age"]
        chosen["ss_tax_rate"] = sim.get("ss_tax_rate", 0.0)
        chosen["health_extra_in_retirement"] = any(x > 0 for i, x in enumerate(sim["extra_by_year"][:max(1, sim["horizon_age"] - age)]) if age + i >= ra)
        chosen["ss_starts_later"] = (chosen.get("claim_age") or 0) > max(age, ra)
        chosen["social_security_by_year"] = neighbors.ss_for(person, sim, strat["claim_age"])["by_year"]
        res["kept_strategy_result"] = {k: chosen.get(k) for k in ("goal_lasts_of_100", "spending_goal_per_year", "safe_spending_per_year",
                                                                 "wants_per_year", "basics_paid_of_100", "claim_age", "stock_share_now")}
        ctx.results["neighbors"] = res
        ctx.results["markets"] = chosen
        c = res["chosen"]
        await tool_event(ctx, self.name, self.tool2_name,
                         f"Tested {len(res['candidates_tested'])} strategies; kept {c['name'].lower()}: needs paid in "
                         f"{c['basics_paid_of_100']} of 100, safe spending {money(c['safe_spending_per_year'])}, goal lasts in "
                         f"{c['goal_lasts_of_100']} of 100. {c['description']}.")
        return res

    def figures(self, ctx, r):
        from .base import figure_lines
        return figure_lines(self.numbers(r)) + [f"- plan kept: {r.get('strategy', 'Simple plan')} (a simple plan is stocks at 110 minus your age)"]

    def trace_events(self, mine):
        # the plan uses the kept strategy, so the finding must not quote the first (rule of thumb) run
        return [e for e in mine if e[1].startswith("Tested")]

    def tool_list(self):
        return [(self.tool_name, self.tool_doc, self.run_tool), (self.tool2_name, self.tool2_doc, self.run_neighbors)]

    async def ensure(self, ctx: RunCtx) -> dict:
        await self.run_tool(ctx)
        await self.run_neighbors(ctx)
        return ctx.results["markets"]

    def numbers(self, r: dict) -> dict:
        keep = ("goal_lasts_of_100", "spending_goal_per_year", "safe_spending_per_year", "wants_per_year", "basics_paid_of_100",
                "median_at_retirement", "median_at_horizon", "low_at_horizon", "stock_share_now", "stock_share_at_retirement",
                "claim_age", "social_security_per_year", "goal_runs_out_of_100", "gap_per_year", "safe_spending_per_month",
                "spending_goal_per_month", "safe_share_of_goal", "years_to_retire", "scenarios", "above_basics_per_year",
                "short_before_retirement_of_100", "partner_claim_age", "social_security_survivor_per_year")
        out = {k: r[k] for k in keep if k in r}
        inp = r.get("inputs") or {}
        out.update(r.get("extras") or {})
        out.update({"retire_age": inp.get("retire_age"), "savings_now": inp.get("savings"), "saving_per_year": inp.get("save_per_year"),
                    "horizon_age": inp.get("horizon_age")})
        if r.get("saving_assumed"):
            # an assumed saving is named as one, so the text says "assumed" (simulated users read it as a fact)
            for k in ("saving_per_year", "contributions_per_year"):
                if k in out:
                    out[k + "_assumed"] = out.pop(k)
        if "social_security_per_year" not in out:
            out["social_security_per_year"] = inp.get("ss_per_year")
            out["claim_age"] = inp.get("ss_age")
        return out

    def template(self, r: dict) -> tuple[str, list[str]]:
        ex = r.get("extras") or {}
        d = [f"You can spend about {money(r['safe_spending_per_year'])} a year and stay safe in 90 of 100 market tests.",
             f"The plan keeps about {round(r['stock_share_now'] * 100)}% of savings in stocks now.",
             "Markets are uncertain. These are chances, not promises."]
        if "costs_fall_when_mortgage_ends" in ex:
            d.insert(1, f"Your costs drop about {money(ex['costs_fall_when_mortgage_ends'])} a year when the mortgage ends in {ex['mortgage_ends_year']}.")
        if ex.get("pension_per_year"):
            d.insert(1, f"Your pension adds about {money(ex['pension_per_year'])} a year before tax.")
        if ex.get("legacy_to_leave"):
            d.insert(1, f"The plan keeps {money(ex['legacy_to_leave'])} to leave behind.")
        return (f"Your goal of {money(r['spending_goal_per_year'])} a year lasts in {r['goal_lasts_of_100']} of 100 market tests.", d)
