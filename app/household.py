"""Fill the gaps in a profile with plain estimates and assumptions, and mark each one so the person can check it."""
from __future__ import annotations

from .schemas import Child, Profile
from .tools import costs, estimates, family_costs, socialsec, tax

ASSUMED_KID_AGES = [6, 9, 12, 4, 15, 2]
DEFAULT_SAVE_RATE = 0.10
FRA = 67


def claim_age(p: Profile) -> int:
    if p.claim_age is not None:
        return max(62, min(70, p.claim_age))
    r = p.retire_age or 65
    return FRA if r < FRA else min(70, r)


def partner_claim_age(p: Profile) -> int | None:
    """Your partner's claiming age, of their own age: their own choice, else yours if you chose one, else the same
    rule as yours on their own retirement age."""
    if not (p.has_partner and p.partner_age):
        return None
    if p.partner_claim_age is not None:
        return max(62, min(70, p.partner_claim_age))
    if p.claim_age is not None:
        return max(62, min(70, p.claim_age))
    r = costs.partner_retire_age(p)
    return FRA if r < FRA else min(70, r)


TYPICAL_PAY = 50980.0     # BLS median pay of all US workers; stands in for a career when no pay is given


def ss_people(p: Profile) -> list[dict]:
    """Each person's Social Security for socialsec.schedule: own full-age benefit, the spousal top-up, claiming age,
    and whether they already claim.

    Estimated (no figure given): from each person's pay, years of work from about 22 to their retirement age (fewer
    than 35 years are averaged over 35); a partner with no pay gets the spousal benefit (half of yours at full age).
    Given: the household figure is split in the shares the estimates give. Someone already claiming gets their share as
    stated; for someone not yet claiming it is read at the claiming age they named, else at 67."""
    age = p.age or 45
    couple = bool(p.has_partner and p.partner_age)
    pay_you = p.pay_per_year if p.pay_per_year else (0.0 if couple and (p.partner_pay_per_year or 0) > 0 else TYPICAL_PAY)
    pia_you = estimates.pia_per_year(pay_you, estimates.career_years(p.retire_age or 65)) if pay_you else 0.0
    claim_you = claim_age(p)
    people = [{"who": "you", "age": age, "pia": pia_you, "spousal_pia": 0.0, "claim": claim_you,
               "chosen": p.claim_age is not None, "fixed": age >= claim_you,
               "pay": float(p.pay_per_year or 0), "work_until": p.retire_age or 65}]
    if couple:
        pp = p.partner_pay_per_year or 0.0
        pia_p = estimates.pia_per_year(pp, estimates.career_years(costs.partner_retire_age(p))) if pp else 0.0
        share = estimates.spouse_share()
        people[0]["spousal_pia"] = share * pia_p
        cp = partner_claim_age(p)
        people.append({"who": "partner", "age": p.partner_age, "pia": pia_p, "spousal_pia": share * pia_you, "claim": cp,
                       "chosen": p.partner_claim_age is not None or p.claim_age is not None, "fixed": p.partner_age >= cp,
                       "pay": float(pp), "work_until": costs.partner_retire_age(p)})
    stated = float(p.social_security_per_year or 0)
    if stated > 0 and p.sources.get("social_security_per_year") != "estimate":
        full = [max(x["pia"], x["spousal_pia"]) for x in people]
        tot = sum(full)
        shares = [f / tot for f in full] if tot > 0 else [1.0 / len(people)] * len(people)
        # someone already claiming gets their share as stated; someone not yet claiming has it read at the claiming age
        # they named, else at 67 (so a later start earns the delayed credits and working longer never lowers it)
        for x, s in zip(people, shares):
            part = stated * s
            x["spousal_pia"] = 0.0
            if x["fixed"]:
                x["amount"], x["pia"] = part, part / estimates.claim_factor(x["claim"])
            else:
                x["pia"] = part / estimates.claim_factor(x["claim"]) if p.claim_age is not None else part
    else:
        for x in people:
            if x["fixed"]:
                own, top = socialsec.amount({**x, "fixed": False}, x["claim"])
                x["amount"] = own + top
    return people


def ss_household(p: Profile, n: int, le_you: float | None = None, le_partner: float | None = None,
                 claim: int | None = None) -> dict:
    """The household's Social Security by year (socialsec.schedule), with the survivor step-down after the first
    expected death (the one with the shorter life expectancy, in remaining years)."""
    people = ss_people(p)
    death = first_death_t(p, le_you, le_partner)
    out = socialsec.schedule(people, n, claim, death)
    out["people"], out["first_death_t"] = people, death
    return out


def first_death_t(p: Profile, le_you: float | None, le_partner: float | None) -> int | None:
    if not (p.has_partner and p.partner_age) or le_you is None or le_partner is None:
        return None
    return int(round(min(le_you, le_partner)))


def stated_ss_at_claim(p: Profile, ss_age: int) -> float:
    """The household's Social Security a year if it starts at ss_age. A figure the person gave is read as the benefit at
    full retirement age (SSA's own statement leads with it), so a start after 67 earns the delayed credits and working
    longer never lowers it. Estimates are already worked out at the claim age. Someone who named a claiming age, or who
    is already claiming, keeps their figure as given."""
    ss = float(p.social_security_per_year or 0)
    if ss <= 0 or p.sources.get("social_security_per_year") == "estimate" or p.claim_age is not None:
        return ss
    if (p.age or 0) >= ss_age or ss_age <= FRA:
        return ss
    return round(ss / estimates.claim_factor(FRA) * estimates.claim_factor(ss_age), -2)


def _mark(p: Profile, key: str, source: str, note: str = "") -> None:
    if p.sources.get(key) != "you said":
        p.sources[key] = source  # type: ignore[assignment]
        if note:
            p.notes[key] = note


SPEND_FLOOR_SHARE = 0.25   # spending under a quarter of the typical basics here is read as a slip, not a figure


def basics(p: Profile, cap: bool = True) -> dict:
    """The basics once retired: housing, food, transport and health care, a year.

    Typical figures (family_costs.basics_per_year), replaced by the person's own where they gave them: the budget's
    housing (unless a mortgage in it ends before retirement) and health (at least the Medicare premiums); food and
    transport up to the typical figure (spending above a typical basic level is a want, not a need). Basics never exceed the person's spending goal: a goal is what they plan
    to spend in all, so it holds the basics. A mortgage that ends before retirement is not a retirement cost: housing
    then is the owner costs of a home without a mortgage. (One that ends later is counted, and the costs timeline takes
    its end off.)"""
    home = p.home.model_dump()
    mort = costs.mortgage_end(p)
    ends_before = bool(mort and mort["years_left"] <= max(0, (p.retire_age or 65) - (p.age or 45))) or costs.mortgage_separate(p)   # or counted on its own (costs.family_side)
    if ends_before:
        home["mortgage_balance"], home["mortgage_payment"] = 0.0, 0.0
    b = family_costs.basics_per_year(p.state, p.adults(), max(p.retire_age or 65, 65), home)
    bud = p.budget
    own = []
    if bud.housing and not ends_before:
        b["housing"], b["housing_basis"] = round(bud.housing * 12), "your budget"
        own.append("housing")
    if bud.food:
        b["food"] = round(min(bud.food * 12, b["food"]))
        own.append("food")
    if bud.transport:
        b["transport"] = round(min(bud.transport * 12, b["transport"]))
        own.append("transport")
    if bud.health:
        b["health"] = round(max(bud.health * 12, family_costs.medicare_premiums_per_year() * p.adults()))
        own.append("health")
    total = round(b["housing"] + b["food"] + b["transport"] + b["health"], -2)
    b["basis"] = "your budget" if len(own) == 4 else ("your budget where given, else typical" if own else "typical")
    goal = (p.spending_per_year or 0) if cap else 0
    if goal and total > goal:
        total, b["basis"] = float(int(goal // 100) * 100), "your spending goal (typical basics are higher)"
    b["basics_per_year"] = total
    return b


def set_claim(newp: Profile, base: Profile, a: int) -> None:
    """Start Social Security at age a (a What If or a change in the chat). An estimate is worked out again for the new
    age; a figure the person gave is moved from the age it was read at to the new one (SSA's reduction and credits)."""
    old_age = claim_age(base)
    if base.claim_age is None:
        old_age = min(old_age, FRA)       # a figure the person gave is read at 67 (stated_ss_at_claim)
    newp.claim_age = int(a)
    if newp.sources.get("social_security_per_year") == "estimate":
        newp.social_security_per_year = None
    elif newp.social_security_per_year:
        newp.social_security_per_year = round(newp.social_security_per_year / estimates.claim_factor(old_age) * estimates.claim_factor(int(a)), -2)
    newp.sources["claim_age"] = "you said"


def complete(p: Profile) -> Profile:
    """Return a copy with every planning input filled. Never overwrites what the person said."""
    p = p.model_copy(deep=True)
    age = p.age or 45
    if p.partner_age and not p.has_partner:
        p.has_partner = True
    if p.has_partner and p.partner_age is None:
        p.partner_age = age
        _mark(p, "partner_age", "assumed", "Assumed the same age as you.")
    if p.retire_age is None:
        retired = p.notes.get("retired") == "yes"
        p.retire_age = age if (retired or age >= 67) else max(65, age + 1)
        _mark(p, "retire_age", "assumed", "A common goal. Change it to test another age.")
    if p.risk is None:
        p.risk = "balanced"
        _mark(p, "risk", "assumed", "Stocks at 110 minus your age, at most 75%.")
    working = p.retire_age > age
    if p.pay_per_year is None:
        est = estimates.pay_estimate(p.job, p.state) if p.job else None
        if not working:
            p.pay_per_year = 0
            _mark(p, "pay_per_year", "assumed", "You are retired, so no pay.")
        elif est:
            p.pay_per_year = est["pay_per_year"]
            _mark(p, "pay_per_year", "estimate", est["note"])
        else:
            p.pay_per_year = 50980.0
            _mark(p, "pay_per_year", "assumed", "The typical pay of all US workers (BLS). Please give yours.")
    if p.has_partner and p.partner_pay_per_year is None:
        est = estimates.pay_estimate(p.partner_job, p.state) if p.partner_job else None
        if est and working:
            p.partner_pay_per_year = est["pay_per_year"]
            _mark(p, "partner_pay_per_year", "estimate", est["note"])
        elif working and p.notes.get("skipped_partner_pay_per_year") == "yes":
            p.partner_pay_per_year = 50980.0       # asked for a typical figure: the typical pay of all US workers, shown for approval
            _mark(p, "partner_pay_per_year", "estimate", "The typical pay of all US workers (BLS). Please give your partner's.")
        else:
            p.partner_pay_per_year = 0
            _mark(p, "partner_pay_per_year", "assumed", "Assumed your partner has no pay. Change it if they work.")
    for i, c in enumerate(p.children):
        if c.age is None:
            c.age = ASSUMED_KID_AGES[i % len(ASSUMED_KID_AGES)]
            _mark(p, "children", "assumed", "Children's ages were assumed. Please give them.")
    if p.save_rate is None:
        p.save_rate = DEFAULT_SAVE_RATE if working else 0.0
        _mark(p, "save_rate", "assumed", "Assumed you save 10% of pay until you retire." if working else "")
    if p.social_security_per_year is None:
        people = ss_people(p)
        total = sum(sum(socialsec.amount(x, x["claim"])) for x in people)
        p.social_security_per_year = round(total, -2)
        when = (f"you claiming at {people[0]['claim']} and your partner at {people[1]['claim']}, each at their own age"
                if len(people) == 2 else f"claiming at {people[0]['claim']}")
        _mark(p, "social_security_per_year", "estimate",
              f"Rough estimate from pay, {when}. Get your real figure at ssa.gov/myaccount.")
    # optional detail: typical defaults, each marked
    if p.health is None:
        p.health = "good"
        _mark(p, "health", "assumed", "Assumed good health, which leaves the life table as it is.")
    if p.has_partner and p.partner_health is None:
        p.partner_health = "good"
        _mark(p, "partner_health", "assumed", "Assumed good health.")
    if p.has_partner and p.partner_retire_age is None:
        p.partner_retire_age = costs.partner_retire_age(p)
        _mark(p, "partner_retire_age", "assumed", "Assumed 65, or about when you stop if you are close in age. Say their age.")
    for d in p.debts:
        costs.fill_debt(d)
    if p.debts:
        _mark(p, "debts", "you said" if p.sources.get("debts") == "you said" else "assumed")
        if any(d.assumed for d in p.debts):
            p.notes["debts"] = "A rate or payment you did not give is assumed: " + ", ".join(
                f"{d.kind.replace('_', ' ')} {' and '.join(x.replace('monthly_payment', 'payment') for x in d.assumed)}" for d in p.debts if d.assumed) + "."
    for pen in p.pensions:
        if pen.start_age is None:
            pen.start_age = 65
            pen.assumed.append("start_age")
        if pen.inflation_adjusted is None:
            pen.inflation_adjusted = False
            pen.assumed.append("inflation_adjusted")
        if pen.survivor_share is None:
            pen.survivor_share = 0.5
            pen.assumed.append("survivor_share")
    if p.pensions and any(x.assumed for x in p.pensions):
        said_it = {a for x in p.pensions for a in x.assumed}
        bits = [t for k, t in (("start_age", "start at 65"), ("inflation_adjusted", "no inflation adjustment"),
                               ("survivor_share", "half to a surviving partner")) if k in said_it]
        p.notes["pensions"] = "Assumed where not given: " + ", ".join(bits) + "."
    if p.home.owns and p.home.mortgage_balance > 0 and p.home.mortgage_rate is None:
        p.home.mortgage_rate = costs.DEFAULT_MORTGAGE_RATE
        _mark(p, "mortgage_rate", "assumed", "Assumed a 5% mortgage rate.")
    if p.part_time and p.part_time.until_age is None:
        p.part_time.until_age = 70
        p.notes["part_time"] = "Assumed you work part-time until 70."
    # college is set per child: the person's own choice, or the typical one (public in-state, family pays all) marked as an estimate
    for c in p.children:
        if c.college_type is None:
            c.college_type = "public" if c.college else "none"
            c.college_source = c.college_source or "estimate"
        elif c.college_source is None:
            c.college_source = "estimate" if p.sources.get("college") == "assumed" else "you said"
        c.college = c.college_type != "none"
    if p.children:
        p.notes.pop("college", None)        # the row's note is worked out per child; an old whole-family note would be stale
        p.sources["college"] = "you said" if any(c.college_source == "you said" for c in p.children) else "estimate"
    if p.has_partner and (p.partner_pay_per_year or 0) > 0 and (p.pay_per_year or 0) >= 0:
        pass
    # spending now and in retirement. A figure far below what the basics cost here is a slip ($100 a year), not a plan:
    # it is set aside and estimated again, and the note says so.
    floor = SPEND_FLOOR_SHARE * basics(p, cap=False)["basics_per_year"]
    for k in ("spending_now_per_year", "spending_per_year"):
        v = getattr(p, k)
        if v is not None and v < floor:
            setattr(p, k, None)
            p.sources.pop(k, None)
            p.notes[k + "_set_aside"] = (f"You gave ${v:,.0f} a year, far below what the basics cost where you live, so the plan "
                                         "uses an estimate. Please check this figure.")
    retired_now = (p.retire_age or 65) <= age
    after = None
    if p.household_pay() > 0:
        after = costs.work_tax(p)["after_tax_pay"]
    if p.spending_now_per_year is None:
        if p.budget.given() and p.budget.total_month() * 12 >= floor:
            p.spending_now_per_year = round(p.budget.total_month() * 12, -2)
            _mark(p, "spending_now_per_year", "estimate", "Added up from the budget you gave.")
        else:
            b = basics(p)["basics_per_year"]
            if after:
                c = costs.contributions(p)
                saved = c["you"] + c["partner"] + c["other"]
                est = round(after - saved, -3)
                cap = estimates.high_earner_spend_cap(p.household_pay())
                if cap is not None and est > cap:
                    p.spending_now_per_year = max(round(b, -3), cap)
                    _mark(p, "spending_now_per_year", "estimate",
                          "Estimated from what US households with pay like yours spend (BLS Consumer Expenditure Survey 2024): "
                          "high earners save more than a tenth of pay. Please check it.")
                else:
                    p.spending_now_per_year = max(round(b, -3), est)
                    _mark(p, "spending_now_per_year", "estimate", "Estimated as your take-home pay less what you save, and no less than typical basics.")
            else:
                p.spending_now_per_year = round(b * 1.25, -3)
                _mark(p, "spending_now_per_year", "estimate", "Estimated as typical basics plus a quarter for wants.")
    if p.spending_per_year is None:
        said_now = p.sources.get("spending_now_per_year") == "you said" or p.budget.given() or p.retire_spend_ratio is not None
        if said_now:
            # already retired: what you spend now is what you spend in retirement
            ratio = p.retire_spend_ratio if p.retire_spend_ratio is not None else (1.0 if retired_now else 0.8)
            base = p.spending_now_per_year
            mort = costs.mortgage_end(p)
            if not retired_now and mort:
                # still at work: the goal leaves the mortgage out, whenever it ends; payments left after retiring are a cost of
                # their own (costs.mortgage_separate). Spending never falls below the basics or half of what is spent now:
                # a payment that is more than the stated spending cannot all be inside it
                base = max(base - mort["drop_per_year"], floor, 0.5 * base)
            p.spending_per_year = round(ratio * base, -2)
            same_as_now = retired_now and p.retire_spend_ratio is None and p.sources.get("spending_now_per_year") == "you said"
            _mark(p, "spending_per_year", "you said" if same_as_now or (p.retire_spend_ratio is not None and p.sources.get("retire_spend_ratio") == "you said") else "assumed",
                  "The same as you spend now, as you are retired. Say a figure if it differs." if retired_now and p.retire_spend_ratio is None else
                  f"About {round(ratio * 100)}% of what you spend now, a common starting point. Say the same, less, or a figure.")
        else:
            b = basics(p)["basics_per_year"]
            if after:
                guess = max(b, round(0.7 * after, -3))
                note = "Estimated as 70% of your take-home pay, and no less than typical basics."
                cap = estimates.high_earner_spend_cap(p.household_pay())
                if cap is not None and p.sources.get("spending_now_per_year") == "estimate" and guess > 0.8 * (p.spending_now_per_year or 0):
                    guess = max(b, round(0.8 * (p.spending_now_per_year or 0), -3))
                    note = "Estimated as 80% of your estimated spending now (BLS Consumer Expenditure Survey 2024), and no less than typical basics."
            else:
                guess = round(b * 1.25, -3)
                note = "Estimated as typical basics plus a quarter for wants."
            p.spending_per_year = guess
            _mark(p, "spending_per_year", "estimate", note)
    if p.emergency_months is None:
        monthly = (p.spending_now_per_year or 0) / 12
        p.emergency_months = round(p.savings.cash / monthly, 1) if monthly else 0.0
        _mark(p, "emergency_months", "estimate", "Your cash savings divided by a month of spending.")
    return p


def child_list(p: Profile) -> list[dict]:
    return [c.model_dump() for c in p.children]


def set_children(p: Profile, count: int | None = None, ages: list[int] | None = None, college: bool | None = None) -> None:
    old = list(p.children)
    keep = lambda i: ({k: getattr(old[i], k) for k in ("college_type", "college_share", "college_source", "sex")} if college is None and i < len(old) else {})  # noqa: E731
    if ages is not None:        # ages said again keep each child's own college choice, by position
        p.children = [Child(age=a, college=(college if college is not None else a < 22), **keep(i)) for i, a in enumerate(ages)]
    elif count is not None:
        if count != len(p.children):
            p.children = [Child(age=None, college=True if college is None else college, **keep(i)) for i in range(count)]
    elif college is not None:
        for c in p.children:
            c.college = college
