from pathlib import Path
f = Path(__file__).resolve().parents[3] / "app/agents/adviser.py"
s = f.read_text(encoding="utf-8")
NEW_FUNCS = '''def horizon_text(p, lon: dict) -> str:
    """How long the money must last, in words that make sense for a big age gap: by the younger partner's age when
    your own age then would pass 100."""
    h = lon["horizon_age"]
    pa = lon.get("partner_age_at_horizon")
    if p.has_partner and p.partner_age and pa is not None and p.partner_age < (p.age or 0) and h > 100:
        return f"until your partner is {pa}"
    return f"to age {h}"


def saving_used(ctx: RunCtx) -> dict:
    """The yearly saving the plan uses until retirement, in its parts (stated, so it can be corrected)."""
    ms = ctx.results.get("money") or {}
    c = ms.get("contributions") or {}
    match = (ms.get("match") or {}).get("match") or 0
    working = (ctx.profile.retire_age or 65) > (ctx.profile.age or 45)
    return {"per_year": ms.get("save_now", 0) if working else 0,
            "accounts_per_year": round((c.get("you") or 0) + (c.get("partner") or 0)) if working else 0,
            "other_per_year": round(c.get("other") or 0) if working else 0, "match_per_year": round(match) if working else 0,
            "unspent_pay_per_year": round(ms.get("unspent_pay_per_year") or 0) if working else 0, "field": "Yearly saving"}


def assumptions(ctx: RunCtx) -> list[str]:
    """The plan's assumptions in plain sentences, with the numbers the code used."""
    from ..tools import estimates, simulate as sim
    p, m = ctx.profile, ctx.results["markets"]
    lon = ctx.results["longevity"]
    age, ra = p.age or 45, p.retire_age or 65
    out = ["All figures are in today's dollars: what money buys now, not the larger sums prices will reach."]
    out.append(f"Savings earn on average {sim.STOCK_MU * 100:.1f}% a year above inflation in stocks and {sim.BOND_MU * 100:.1f}% in bonds, "
               f"with ups and downs drawn at random in {sim.PATHS:,} scenarios. These are planning figures, not a forecast.")
    out.append(f"Inflation of {sim.INFLATION * 100:.1f}% a year is used only for pensions and annuities without a cost-of-living rise, "
               "which lose that much value each year.")
    if ra > age:
        sv = saving_used(ctx)
        parts = []
        if sv["accounts_per_year"]:
            parts.append(f"{money(sv['accounts_per_year'])} into a 401(k) or IRA")
        if sv["match_per_year"]:
            parts.append(f"{money(sv['match_per_year'])} from your employer's match")
        if sv["other_per_year"]:
            parts.append(f"{money(sv['other_per_year'])} of other saving")
        if sv["unspent_pay_per_year"] > 0:
            parts.append(f"{money(sv['unspent_pay_per_year'])} of take-home pay left after your spending, which we assume you save")
        if parts:
            out.append(f"Until you retire you save about {money(sv['per_year'])} a year: " + ", ".join(parts) +
                       ". If that is wrong, change 'Yearly saving' in your answers.")
        out.append("Pay stays at today's level until you retire; no raises are assumed.")
    aside = p.notes.get("spending_now_per_year_set_aside") or p.notes.get("spending_per_year_set_aside")
    if aside:
        out.append(aside)
    if ra <= age and p.retire_spend_ratio is None:
        out.append("You are retired, so the plan uses what you spend now as your spending.")
    claim, pclaim, already = plan_claims(p, m)
    if p.sources.get("social_security_per_year") == "estimate":
        out.append("Social Security is a rough estimate from today's pay, for work from about 22 to your retirement age "
                   f"(with fewer than {estimates.FULL_CAREER_YEARS} years, the missing years count as zeros). "
                   "Your own figure is at ssa.gov/myaccount.")
    elif p.social_security_per_year:
        out.append("Social Security uses the figure you gave" + ("." if (p.claim_age is not None or already) else
                                                                 ", read as the benefit at 67; a later start earns more."))
    if claim is not None:
        if already:
            out.append(f"You already claim Social Security (from {claim}).")
        elif pclaim is not None:
            out.append(f"Social Security starts at {claim} for you and at {pclaim} for your partner, each at their own age. "
                       "A partner with little pay of their own gets half of the other's benefit at full age, less if started earlier.")
        else:
            out.append(f"Social Security starts at {claim}.")
    if m.get("social_security_survivor_per_year") and p.has_partner:
        out.append(f"After the first death, expected at the shorter life expectancy, Social Security falls to the larger of your two "
                   f"benefits, about {money(m['social_security_survivor_per_year'])} a year. Spending stays the same.")
    state_ss = "" if tax_mod.state_exempts_ss(p.state) else " Your state taxes part of it too."
    out.append("Tax uses the 2027 federal brackets with the standard deduction (no itemizing) and your state's rates; while you work, "
               "401(k) saving comes off taxable pay and the child tax credit applies. In retirement 85% of Social Security counts as "
               "taxable income, the most the law allows, so this errs on the high side." + state_ss)
    if age < costs.MEDICARE_AGE:
        out.append(f"Health cover before Medicare at 65 costs about {money(costs.PRE_MEDICARE_PREMIUM)} a person a year if you retire "
                   "earlier (an assumption); out-of-pocket costs follow CMS figures by age.")
    out.append(f"The plan runs {horizon_text(p, lon)}, the age by which there is about a 1 in 4 chance that "
               + ("one of you" if p.has_partner else "you") + " will still be alive (US population life table, SOA 2024, with "
               "future improvement). It is not adjusted for income, and people with more money tend to live longer.")
    return out


def assemble(ctx: RunCtx, out: AdviserOut, source: str) -> dict:'''

rep = [
("""             + (" You said you have cover." if p.insurance.ltc else ""),
             f"Before Medicare at 65 a retired person pays about ${costs.PRE_MEDICARE_PREMIUM:,.0f} a year for health cover (an assumption)."]
    return {"ages": tl["ages"], "total": tl["total"], "basics": tl["basics"], "events": tl["events"],
            "now_per_year": tl["total"][0],""",
"""             + (" You said you have cover." if p.insurance.ltc else "")]
    if (p.age or 0) < costs.MEDICARE_AGE:
        notes.append(f"Before Medicare at 65 a retired person pays about ${costs.PRE_MEDICARE_PREMIUM:,.0f} a year for health cover (an assumption).")
    # "costs now" is the spending-now figure the answers panel shows, so the two always agree
    now = round(p.spending_now_per_year) if p.spending_now_per_year else tl["total"][0]
    return {"ages": tl["ages"], "total": tl["total"], "basics": tl["basics"], "events": tl["events"],
            "now_per_year": now,"""),
("""    claim, partner_claim = claim_ages(p, m.get("claim_age"))
    ranked = ranked_levers(p, m)
    safe = m["safe_spending_per_year"]
    return {
        "verdict": verdict(m),
        "retire_age": p.retire_age,
        "claim_age": claim,
        "partner_claim_age": partner_claim,
        "already_claiming": claim is not None and (p.age or 0) >= claim,
        "spending_goal": m["spending_goal_per_year"],
        "horizon_age": ctx.results["longevity"]["horizon_age"],""",
"""    claim, partner_claim, already = plan_claims(p, m)
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
        "assumptions": assumptions(ctx),"""),
("""def assemble(ctx: RunCtx, out: AdviserOut, source: str) -> dict:""", NEW_FUNCS),
("""from ..tools import costs
""", """from ..tools import costs
from ..tools import tax as tax_mod
"""),
]
for a, b in rep:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
f.write_text(s, encoding="utf-8")
print("ok")
