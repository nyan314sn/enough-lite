"""Longevity agent: the life table tool -> a planning horizon."""
from __future__ import annotations

from ..tools import lifetable
from .base import RunCtx, Specialist


class Longevity(Specialist):
    name = "longevity"
    label = "How long to plan for"
    tool_name = "life_table"
    tool_doc = "Look up the household's survival chances in the US life table and return a planning horizon."
    instructions = ("You are the longevity specialist in a retirement-planning team. The life_table tool has run. Say how long "
                    "the money should last and why: the planning horizon is the age at which there is only about a 1 in 4 chance "
                    "that anyone in the household is still alive. When your partner is much younger and the horizon would pass 100 for you, "
                    "say it as your partner's age (partner_age_at_horizon), never as your own age past 100. Give one horizon only, never a "
                    "second one for a partner, and never name an age past 100.")

    def compute(self, ctx: RunCtx) -> dict:
        p = ctx.profile
        m, pm = lifetable.health_mult(p.health), lifetable.health_mult(p.partner_health)
        r = lifetable.horizon(p.age or 45, p.sex, p.partner_age if p.has_partner else None, p.partner_sex, mult=m, partner_mult=pm)
        r["health_you"], r["health_partner"] = p.health or "good", p.partner_health if p.has_partner else None
        r["mortality_multiplier_you"] = m
        if p.has_partner:
            r["mortality_multiplier_partner"] = pm
        if m != 1.0 or (p.has_partner and pm != 1.0):
            avg = lifetable.horizon(p.age or 45, p.sex, p.partner_age if p.has_partner else None, p.partner_sex)
            r["horizon_age_average_health"] = avg["horizon_age"]
            r["years_shift_from_health"] = r["horizon_age"] - avg["horizon_age"]
        r["age_now"] = p.age
        r["age_mark_90"], r["age_mark_100"] = 90, 100
        r["partner_age_now"] = p.partner_age if p.has_partner else None
        age, ra = p.age or 45, p.retire_age or 65
        r["years_to_plan"] = r["horizon_age"] - age
        if ra > age:
            r["retire_age"], r["years_to_retire"] = ra, ra - age
        r["years_in_retirement"] = max(0, r["horizon_age"] - max(ra, age))
        from .adviser import horizon_text
        r["horizon_text"] = horizon_text(p, r)
        return r

    def summary(self, r: dict) -> str:
        return f"Planning horizon: {r.get('horizon_text') or 'age ' + str(r['horizon_age'])}."

    def numbers(self, r: dict) -> dict:
        keep = ("horizon_age", "chance_alive_at_horizon", "chance_someone_reaches_90", "chance_someone_reaches_100", "life_expectancy_you",
                "life_expectancy_partner", "years_to_plan", "partner_age_at_horizon", "retire_age", "years_to_retire",
                "years_in_retirement", "mortality_multiplier_you", "mortality_multiplier_partner", "horizon_age_average_health",
                "years_shift_from_health")
        out = {k: r[k] for k in keep if k in r}
        out["age_now"] = r.get("age_now")
        out["age_mark_90"], out["age_mark_100"] = 90, 100
        out["partner_age_now"] = r.get("partner_age_now")
        return {k: v for k, v in out.items() if v is not None}

    def tidy(self, r: dict, headline: str, details: list[str]) -> tuple[str, list[str]]:
        """One horizon, said once, built in code ("to age 95", or "until your partner is 94"); no sentence that names an
        age past 100 or a second horizon for a partner."""
        import re
        head = f"Plan for your money to last {r.get('horizon_text') or 'to age ' + str(r['horizon_age'])}."

        def odd(s: str) -> bool:
            return bool(re.search(r"partner'?s plan|plan for your partner|\b1\d\d\b", s)) or "1 in 4" in s
        return head, [d for d in details if not odd(d)][:3]

    def template(self, r: dict) -> tuple[str, list[str]]:
        who = "one of you" if "life_expectancy_partner" in r else "you"
        reach = "one of you reaches" if who == "one of you" else "you reach"
        return (f"Plan for your money to last {r.get('horizon_text') or 'to age ' + str(r['horizon_age'])}.",
                [f"There is about a {round(r['chance_alive_at_horizon'] * 100)}% chance that {who} will still be alive then.",
                 f"The chance that {reach} 90 is about {round(r['chance_someone_reaches_90'] * 100)}%.",
                 "Planning for a long life is safer than planning for an average one."]
                + ([f"You said your health is {r['health_you']}. That moves the age about {abs(r['years_shift_from_health'])} years "
                    f"{'earlier' if r['years_shift_from_health'] < 0 else 'later'}. It is a rough guess, not a medical forecast."]
                   if r.get("years_shift_from_health") else []))
