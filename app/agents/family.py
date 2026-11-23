"""Family agent: children, college and pets by year, and the household's typical basics once retired."""
from __future__ import annotations

from .. import household, safety
from ..tools import costs, family_costs
from .base import RunCtx, Specialist, money


class Family(Specialist):
    name = "family"
    label = "Family costs"
    tool_name = "family_costs"
    tool_doc = "Work out yearly costs for children, college and pets, and the typical needs of this household once retired."
    instructions = ("You are the family specialist in a retirement-planning team. The family_costs tool has run. Say what the "
                    "family costs are, when they end, and what the needs will cost once retired.")

    def compute(self, ctx: RunCtx) -> dict:
        p = ctx.profile
        path = family_costs.family_path(p.age or 45, household.child_list(p), [x.model_dump() for x in p.pets],
                                        p.partner_age if p.has_partner else None)
        path["basics"] = household.basics(p)
        path["basics_per_month"] = round(path["basics"]["basics_per_year"] / 12)
        path["family_years_left"] = (path["ends_at_age"] - (p.age or 45)) if path.get("ends_at_age") else None
        c = costs.family_side(p, path)
        path["costs"] = c
        path["moments"] = path["moments"] + _cost_moments(p, c)
        return path

    def summary(self, r: dict) -> str:
        return f"Family costs {money(r['this_year'])} this year; basics once retired {money(r['basics']['basics_per_year'])} a year."

    def numbers(self, r: dict) -> dict:
        c = r["costs"]
        mort, debts, ltc = c["mortgage"], c["debts"], c["ltc"]
        tl = c["timeline"]
        out = {"spending_now_per_year": tl["total"][0], "spending_now_per_month": round(tl["total"][0] / 12),
               "health_premium_before_medicare": costs.PRE_MEDICARE_PREMIUM, "medicare_age": costs.MEDICARE_AGE,
               "ltc_nursing_home_per_year": ltc["nursing_home_per_year"], "ltc_typical_years": ltc["typical_years"],
               "college_family_share_total": sum(c["college"]), "big_costs_total": sum(c["big"]),
               "parents_help_total": sum(c["parents"])}
        if mort:
            out.update({"mortgage_ends_year": mort["end_year"], "mortgage_years_left": mort["years_left"],
                        "costs_fall_when_mortgage_ends": mort["drop_per_year"]})
        if debts["total_balance"]:
            out.update({"debt_total_balance": debts["total_balance"], "debt_payment_per_year": debts["payment_per_year"],
                        "debt_interest_per_year": debts["interest_per_year"]})
        return {**out, **self._numbers(r)}

    def _numbers(self, r: dict) -> dict:
        return {"family_this_year": r["this_year"], "family_total": r["total"], "college_total": r["college_total"],
                "family_costs_end_at_age": r["ends_at_age"], "basics_per_year": r["basics"]["basics_per_year"],
                "basics_per_month": r["basics_per_month"], "family_years_left": r["family_years_left"],
                "college_cost_per_year": r["college_cost_per_year"],
                **{f"college_child{b['child']}_per_year": b["per_year"] for b in r.get("college_by_child", [])},
                "basics_housing": r["basics"]["housing"], "basics_food": r["basics"]["food"],
                "basics_transport": r["basics"]["transport"], "basics_health": r["basics"]["health"],
                "moment_figures": [v for m in r["moments"] for v, _, _ in safety.numbers_in(m)]}

    def template(self, r: dict) -> tuple[str, list[str]]:
        b = r["basics"]
        c = r["costs"]
        if r["total"] > 0:
            head = f"Family costs come to about {money(r['this_year'])} this year and end around age {r['ends_at_age']}."
        else:
            head = "You have no child or pet costs to plan for."
        details = [f"Once retired, your basics cost about {money(b['basics_per_year'])} a year. That covers housing, food, travel and health."]
        if r["college_total"]:
            details.append(f"College adds about {money(r['college_total'])} in all, at your share.")
        if c["mortgage"]:
            m = c["mortgage"]
            details.append(f"Your costs drop about {money(m['drop_per_year'])} a year when the mortgage ends in {m['end_year']}.")
        details.append(f"Before Medicare at 65, health cover costs about {money(costs.PRE_MEDICARE_PREMIUM)} a year. This is a guess.")
        return head, details[:4]


def _cost_moments(p, c: dict) -> list[str]:
    out = []
    m = c["mortgage"]
    if m:
        out.append(f"Your costs fall by about ${m['drop_per_year']:,.0f} a year when the mortgage ends in {m['end_year']}.")
    # debts are not family moments: they show in the costs timeline ("Debts paid off ...") and the actions
    for e in c["timeline"]["events"]:
        if e.get("one_off"):
            out.append(f"{e['label']}: about ${e['change_per_year']:,.0f} once.")
    pa = p.goals.parents_per_year
    if pa and p.goals.parents_years:
        out.append(f"Helping your parents costs ${pa:,.0f} a year for {p.goals.parents_years} years.")
    return out
