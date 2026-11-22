"""Tax agent: simple federal and state rates, and the after-tax view of retirement withdrawals."""
from __future__ import annotations

from ..tools import costs, tax
from .base import RunCtx, Specialist, money


class Tax(Specialist):
    name = "tax"
    label = "Taxes"
    tool_name = "tax_estimate"
    tool_doc = "Estimate income tax now and in retirement, and the order in which to draw on accounts."
    instructions = ("You are the tax specialist in a retirement-planning team. The tax_estimate tool has run. Say what share "
                    "of income goes to tax now and in retirement, and which accounts to draw on first: taxable savings first, then "
                    "pre-tax accounts such as a 401(k), and Roth accounts last (the order the tool uses). This is a rough guide, "
                    "not tax advice.")

    def compute(self, ctx: RunCtx) -> dict:
        p = ctx.profile
        over65 = int((p.retire_age or 65) >= 65) + int(p.has_partner and (p.partner_age or 0) + ((p.retire_age or 65) - (p.age or 45)) >= 65)
        work = costs.work_tax(p)
        pension = sum(x.per_year for x in p.pensions)
        part_time = p.part_time.per_year if p.part_time else 0.0
        ret = tax.retirement_years(p.spending_per_year or 0, p.social_security_per_year or 0, p.savings.model_dump(), p.state,
                                   p.has_partner, over65, other_income=pension + part_time)
        ret["pension_per_year"], ret["part_time_per_year"] = round(pension), round(part_time)
        # the rate on withdrawals in years with no pension or part-time pay yet (they stack on top of it otherwise)
        ret["rate_without_other_income"] = (tax.retirement_years(p.spending_per_year or 0, p.social_security_per_year or 0,
                                          p.savings.model_dump(), p.state, p.has_partner, over65)["effective_rate_on_withdrawals"]
                                          if pension + part_time > 0 else ret["effective_rate_on_withdrawals"])
        if p.partner_pay_per_year:
            ret["partner_net_pay"] = round(work["after_tax_pay"] * (p.partner_pay_per_year / max(1.0, work["gross_pay"])))
        else:
            ret["partner_net_pay"] = 0
        lim = tax.limits_2027()
        lim["401k_total_50_plus"] = lim["401k_limit"] + lim["401k_catch_up_50_plus"]
        lim["401k_total_60_to_63"] = lim["401k_limit"] + lim["401k_catch_up_60_to_63"]
        lim["ira_total_50_plus"] = lim["ira_limit"] + lim["ira_catch_up_50_plus"]
        derived = {"total_tax_working": work["federal_tax"] + work["state_tax"] + work["payroll_tax"]}
        sh = ret.get("shares") or {}
        derived.update({"pretax_share_of_savings": sh.get("pretax"), "roth_share_of_savings": sh.get("roth"),
                        "taxable_and_cash_share_of_savings": sh.get("taxable_and_cash")})
        return {**work, **ret, **derived, "limits_2027": lim}

    def summary(self, r: dict) -> str:
        return f"Tax now {round(r['effective_rate_working'] * 100)}% of pay; in retirement {round(r['effective_rate_on_withdrawals'] * 100)}% of withdrawals."

    def numbers(self, r: dict) -> dict:
        return {"effective_rate_working": r["effective_rate_working"], "after_tax_pay": r["after_tax_pay"], "gross_pay": r["gross_pay"],
                "federal_tax": r["federal_tax"], "state_tax": r["state_tax"], "payroll_tax": r["payroll_tax"],
                "gross_withdrawal_per_year": r["gross_withdrawal_per_year"], "total_tax_working": r["total_tax_working"],
                "pretax_share_of_savings": r["pretax_share_of_savings"], "roth_share_of_savings": r["roth_share_of_savings"],
                "taxable_and_cash_share_of_savings": r["taxable_and_cash_share_of_savings"],
                "effective_rate_on_withdrawals": r["effective_rate_on_withdrawals"], "tax_per_year_retired": r["tax_per_year_retired"],
                "pension_per_year": r["pension_per_year"], "part_time_per_year": r["part_time_per_year"],
                "tax_on_pension_and_part_time_per_year": r["other_income_tax_per_year"],
                "tax_rate_on_pension_and_part_time": r["other_income_tax_rate"],
                **{"limit_" + k: v for k, v in r["limits_2027"].items()},
                "catch_up_age_50": 50, "super_catch_up_age_60": 60, "super_catch_up_age_63": 63, "medicare_age": 65}

    def template(self, r: dict) -> tuple[str, list[str]]:
        d = []
        if r["gross_pay"]:
            d.append(f"While you work, about {round(r['effective_rate_working'] * 100)}% of pay goes to tax, leaving {money(r['after_tax_pay'])} a year.")
        if r.get("pension_per_year") or r.get("part_time_per_year"):
            d.append(f"Your pension and part-time pay count as income. Tax on them is about {money(r['other_income_tax_per_year'])} a year.")
        d.append("Draw on taxable savings first, then pre-tax accounts, and Roth accounts last.")
        return (f"In retirement, tax takes about {round(r['effective_rate_on_withdrawals'] * 100)}% of what you withdraw.", d)
