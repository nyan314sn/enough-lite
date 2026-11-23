"""Loop round 2 plan fixes: one figure everywhere (saving, spending now, Social Security), starting points that help,
lever What Ifs, assumptions, odd copy, short adviser finding, assumed saving marked; audit 2A engine items (Social
Security while working, the survivor's spending, the deficit, tax details, a new child)."""
from __future__ import annotations

import asyncio
import copy
import re

from app import pipeline
from app.agents import adviser, intake_fields
from app.agents.base import RunCtx, money
from app.agents.longevity import Longevity
from app.schemas import Profile
from app.tools import costs, simulate, tax


def S(pretax=0, roth=0, taxable=0, cash=0):
    return {"pretax": pretax, "roth": roth, "taxable": taxable, "cash": cash}


def plan_for(profile):
    p = pipeline.prepare(copy.deepcopy(profile))
    ctx = RunCtx(profile=p, use_ai=False)
    plan = asyncio.run(pipeline.run_plan(ctx))
    return plan, ctx


BUS = dict(age=52, state="MI", pay_per_year=52000, retire_age=58, savings=S(20000, 0, 5000, 5000), spending_now_per_year=50400,
           spending_per_year=40000, children=[{"age": 16}, {"age": 14}])
PARENT = dict(age=38, state="TX", pay_per_year=74000, retire_age=65, savings=S(15000, 0, 4000, 3000), children=[{"age": 6}, {"age": 9}],
              home={"owns": False, "rent": 1400})
TEACHERS = dict(age=47, has_partner=True, partner_age=49, state="OH", pay_per_year=68000, partner_pay_per_year=82000, retire_age=60,
                savings=S(150000, 20000, 20000, 20000), spending_now_per_year=78000, children=[{"age": 15}, {"age": 12}],
                pensions=[{"who": "you", "per_year": 36000, "start_age": 60}])
SWE_SKIP = dict(age=30, state="TX", pay_per_year=95000, retire_age=65, savings=S(4800, 800, 1600, 800),
                saving={"match_rate": 1.0, "match_cap": 0.04}, debts=[{"kind": "student", "balance": 45000, "rate": 0.065}])
RETIRED = dict(age=71, has_partner=True, partner_age=69, state="FL", retire_age=71, pay_per_year=0, savings=S(500000, 0, 100000, 40000),
               spending_now_per_year=72000, social_security_per_year=48000, sources={"spending_now_per_year": "you said",
                                                                                    "social_security_per_year": "you said"})


# ------------------------------------------------------------------ item 1: one figure everywhere
def test_one_figure_everywhere_for_the_b_households():
    for prof in (BUS, PARENT, TEACHERS, SWE_SKIP, RETIRED):
        plan, ctx = plan_for(prof)
        assert plan["consistency"] == [], plan["consistency"]
        p = ctx.profile
        # the panel's "Yearly saving" shows the plan's figure
        if (p.retire_age or 65) > (p.age or 45) and plan["saving"]["per_year"] > 0:
            shown = intake_fields._saving_display(p)
            assert money(plan["saving"]["per_year"]) in shown, (shown, plan["saving"])
            assert money(plan["saving"]["per_year"]) in " ".join(plan["assumptions"])
        # the panel's "Costs now" is the plan's spending now, estimate or not
        assert plan["costs_by_age"]["now_per_year"] == round(p.spending_now_per_year)


def test_social_security_in_the_answers_and_the_plan_are_both_named_with_their_ages():
    plan, ctx = plan_for(SWE_SKIP)          # an estimate at 67; the kept plan may start it later
    p = ctx.profile
    b = adviser.ss_basis(p, ctx.results["markets"])
    text = " ".join(plan["assumptions"])
    assert money(b["panel_per_year"]) in text and money(b["plan_per_year"]) in text
    if not b["same"]:
        assert f"at {b['claim_age']}" in text
        if "Social Security of" in plan["headline"]:
            assert f"starts at {b['claim_age']}" in plan["headline"]
    assert f"at {b['panel_age']}" in intake_fields._ss_display(p)


def test_saving_assumed_is_marked_wherever_shown():
    plan, ctx = plan_for(PARENT)
    assert plan["saving"]["assumed"] is True
    assert "assumed" in intake_fields._saving_display(ctx.profile)
    line = next(a for a in plan["assumptions"] if "save about" in a or "take-home" in a)
    assert "assumed" in line
    nums = ctx.findings["markets"]["numbers"]
    assert "saving_per_year_assumed" in nums and "saving_per_year" not in nums
    plan2, ctx2 = plan_for(dict(PARENT, saving={"contrib_you": 6000}))
    assert plan2["saving"]["assumed"] is False and "saving_per_year" in ctx2.findings["markets"]["numbers"]


# ------------------------------------------------------------------ item 2 and audit 2A P1-3: starting points
def test_starting_points_each_help_and_run_as_a_what_if():
    plan, ctx = plan_for(BUS)
    assert plan["verdict"] == "falls_short"
    base_paid, base_safe = plan["needs"]["paid_of_100"], plan["count_on_per_year"]
    pts = plan["starting_points"]
    assert pts
    for x in pts:
        assert x["whatif_text"]
        assert not (x["paid_of_100"] == 0 and x["count_on_per_year"] == 0)
        assert x["paid_of_100"] > base_paid or x["count_on_per_year"] > base_safe
        for m in re.finditer(r"Retire at (\d+)", x["whatif_text"]):
            assert ctx.profile.age < int(m.group(1)) <= 70
    safe = any(x["makes_basics_safe"] for x in pts)
    assert ("would fix it" in plan["headline"]) == safe
    assert "Starting points:" not in plan["actions"][0]["why"]
    # a retire or claim point is read by the What If parser the same way
    for x in pts:
        if re.fullmatch(r"Retire at \d+|Claim Social Security at 70", x["whatif_text"]):
            ch = pipeline.parse_whatif(x["whatif_text"], ctx.profile)
            assert ch.get("retire_age") or ch.get("claim_age") == 70


def test_starting_points_never_offer_a_point_that_does_nothing():
    plan, _ = plan_for(dict(PARENT, spending_now_per_year=61000, spending_per_year=54000))
    for x in plan["starting_points"]:
        assert " now." in x["result"] and "against" in x["result"]


def test_retire_later_steps_one_or_two_years_first():
    p = pipeline.prepare(copy.deepcopy(PARENT))
    tries = adviser._tries(p, {"claim_age": 67, "inputs": {"basics_per_year": 30000}})
    ages = [t["ch"]["retire_age"] for t in tries if t["key"] == "retire"]
    assert ages == [66, 67]
    assert any(t["key"] == "spend_now" and t["text"].endswith("less now") for t in tries)


# ------------------------------------------------------------------ item 3: lever What Ifs
def test_lever_what_ifs_never_past_or_for_the_retired():
    retired = Profile(age=71, retire_age=71)
    assert not adviser.lever_ok(retired, "What if I retire at 60")
    assert not adviser.lever_ok(retired, "What if I retire at 75")
    working = Profile(age=56, retire_age=62)
    assert not adviser.lever_ok(working, "Retire at 55")
    assert not adviser.lever_ok(working, "Retire at 72")
    assert adviser.lever_ok(working, "Retire at 63")
    assert not adviser.lever_ok(working, "What if we have another child")
    assert adviser.lever_ok(Profile(age=35, retire_age=65), "What if we have another child")
    plan, ctx = plan_for(RETIRED)
    assert all(adviser.lever_ok(ctx.profile, x["whatif_text"]) for x in plan["levers"])


# ------------------------------------------------------------------ item 4: assumptions
def test_assumptions_in_order_and_plain():
    plan, _ = plan_for(TEACHERS)
    a = plan["assumptions"]
    assert a[0].startswith("All figures are in today's dollars")
    assert "above inflation" in a[1] and "market test" in " ".join(a[:3])
    text = " ".join(a)
    assert "2,000" not in text and "annuit" not in text and "scenarios" not in text
    idx = {k: next(i for i, x in enumerate(a) if k in x) for k in ("save about", "Social Security", "After the first death", "Medicare", "Tax uses", "The plan runs")}
    assert idx["save about"] < idx["Social Security"] < idx["After the first death"] < idx["Medicare"] < idx["Tax uses"] < idx["The plan runs"]
    assert "75% of what the two of you spend" in text


# ------------------------------------------------------------------ item 5: odd copy
def test_no_debt_in_family_moments_and_no_stale_college_note():
    plan, ctx = plan_for(dict(SWE_SKIP, children=[{"age": 3, "college_type": "private", "college_share": 1.0}],
                              notes={"college": "Assumed public college, paid in full. Say private, a share, or none."},
                              sources={"college": "assumed"}))
    assert not any("owe" in m for m in plan["family_moments"])
    assert "college" not in ctx.profile.notes


def test_longevity_says_one_horizon_and_no_age_past_100():
    r = {"horizon_age": 98, "horizon_text": "until your partner is 96"}
    head, det = Longevity().tidy(r, "Plan to 98, with your partner's plan running to age 96.",
                                 ["There is a 1 in 4 chance your partner reaches 104.", "Plan for a long life."])
    assert head == "Plan for your money to last until your partner is 96."
    assert det == ["Plan for a long life."]


def test_wants_and_wishes_lines_do_not_contradict_the_numbers():
    plan, ctx = plan_for(TEACHERS)
    m, basics = ctx.results["markets"], plan["needs"]["basics_per_year"]
    bad = adviser.AdviserOut(needs_line="x", wants_line="You can count on $1 a year; this is about the basics, with $39,000 above them.",
                             wishes_line="Your goal is below what lasts, so the goal is above what is safe.", actions=adviser.template(ctx).actions)
    out = adviser.guard_lines(ctx, bad)
    if not adviser.wants_thin(m, basics):
        assert "about the basics" not in out.wants_line
    assert "below what lasts" not in out.wishes_line


# ------------------------------------------------------------------ item 6: adviser finding
def test_adviser_finding_is_two_sentences_at_most():
    plan, ctx = plan_for(TEACHERS)
    f = ctx.findings["adviser"]
    assert len(f["details"]) <= 2
    assert all(d.count(". ") == 0 for d in f["details"])


# ------------------------------------------------------------------ audit 2A P1-1, P1-2: the simulation
def test_social_security_already_paid_counts_while_working():
    base = dict(age=55, retire_age=65, horizon_age=95, savings=300000, save_per_year=10000, spend_per_year=60000,
                ss_per_year=28000, ss_age=55, ss_by_year=[28000] * 40, basics_per_year=30000, chart=False)
    without = simulate.simulate(**base)
    with_ss = simulate.simulate(**base, ss_work_by_year=[28000] * 40)
    assert with_ss["safe_spending_per_year"] > without["safe_spending_per_year"] * 1.05


def test_spending_steps_down_after_the_first_death():
    base = dict(age=65, retire_age=65, horizon_age=95, savings=600000, save_per_year=0, spend_per_year=70000,
                ss_per_year=40000, ss_age=65, basics_per_year=40000, chart=False)
    same = simulate.simulate(**base)
    step = simulate.simulate(**base, spend_drop_t=15)
    assert step["safe_spending_per_year"] > same["safe_spending_per_year"]
    assert step["basics_paid_of_100"] >= same["basics_paid_of_100"]


def test_couple_with_a_partner_already_claiming():
    prof = dict(age=55, has_partner=True, partner_age=70, state="TX", pay_per_year=100000, partner_pay_per_year=60000, retire_age=65,
                partner_retire_age=66, savings=S(600000, 0, 100000, 40000), spending_per_year=90000, spending_now_per_year=100000)
    plan, ctx = plan_for(prof)
    assert plan["partner_already_claiming"] and plan["count_on_per_year"] > 75000      # was $71,231 with the benefit dropped


# ------------------------------------------------------------------ audit 2A P2s
def test_additional_medicare_tax():
    lo = tax.working_years(200000, 0, "TX", False)["payroll_tax"]
    hi = tax.working_years(300000, 0, "TX", False)["payroll_tax"]
    # 1.45% Medicare on the extra 100k plus 0.9% above 200k (Social Security tax is already capped)
    assert round(hi - lo) == round(100000 * 0.0145 + 100000 * 0.009)


def test_colorado_exempts_social_security_from_65():
    assert tax.state_exempts_ss("CO", 66) and not tax.state_exempts_ss("CO", 60) and not tax.state_exempts_ss("CO")
    assert not tax.state_exempts_ss("CT", 70) and tax.state_exempts_ss("TX")


def test_catch_up_60_to_63_is_larger():
    p60 = Profile(age=61, pay_per_year=200000, state="TX", retire_age=65, saving={"contrib_you": 40000})
    p55 = Profile(age=55, pay_per_year=200000, state="TX", retire_age=65, saving={"contrib_you": 40000})
    assert costs.work_tax(p60)["pretax_contributions"] - costs.work_tax(p55)["pretax_contributions"] == 11750 - 8500


def test_spending_above_take_home_is_drawn_from_savings():
    p = pipeline.prepare(dict(age=40, state="TX", pay_per_year=40000, retire_age=65, savings=S(50000), spending_now_per_year=60000,
                              sources={"spending_now_per_year": "you said"}))
    sv = costs.saving_now(p)
    assert sv["per_year"] < 0
    assert "None, as spending now" in intake_fields._saving_display(p)
    plan, _ = plan_for(p.model_dump())
    assert any("takes that from your savings" in a for a in plan["assumptions"])


def test_a_new_child_does_not_raise_count_on_for_a_single_parent():
    prof = dict(age=36, state="OH", pay_per_year=55000, retire_age=67, savings=S(15000, 0, 2000, 4000), spending_per_year=38000,
                spending_now_per_year=44000, children=[{"age": 4}, {"age": 9}], sources={"spending_now_per_year": "you said"})
    base = pipeline.prepare(prof)
    plan0, _ = asyncio.run(pipeline.tools_only_plan(base))
    newp, notes = pipeline.apply_whatif(base, pipeline.parse_whatif("What if we have another child", base))
    plan1, _ = asyncio.run(pipeline.tools_only_plan(newp))
    assert newp.spending_now_per_year > base.spending_now_per_year
    assert plan1["count_on_per_year"] <= plan0["count_on_per_year"]


def test_count_on_below_social_security_is_always_explained():
    m = {"safe_spending_per_year": 20000, "social_security_per_year": 22000}
    assert "less than your Social Security" in adviser.headline(m, 18000)       # the comparison is on the headline
    assert "That is because" in adviser.below_ss_why(m)      # the reason is its own short sentence (R18)


def test_low_value_actions_are_left_out():
    p = Profile(age=55, retire_age=65, pay_per_year=60000)
    m = {"levers": [{"key": "match", "title": "Get the full match", "why": "x", "whatif_text": "", "numbers": {"match_missed_per_year": 50}}],
         "spending_goal_per_year": 1, "safe_spending_per_year": 2, "basics_paid_of_100": 100}
    assert not any(x["key"] == "match" for x in adviser.ranked_levers(p, m))
    assert adviser.STATUS_RE.match("Keep the plan of a similar household") and not adviser.STATUS_RE.match("Keep about 60% of savings in stocks now")
