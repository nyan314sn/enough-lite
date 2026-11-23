"""Loop round 1 engine fixes (audit A, logic and math; audit B plan-side items): Social Security per person, survivor
step-down, already claiming, years-worked dilution, working-year tax, monotone count-on, assumptions, verdicts, actions,
the needs line, horizon wording, retired spending, absurd spending, plain words, withdrawal gross-up, starting points."""
from __future__ import annotations

import asyncio
import re
import copy

import pytest

from app import household, pipeline, safety
from app.agents import adviser
from app.agents.base import RunCtx
from app.schemas import Profile
from app.tools import costs, estimates, neighbors, socialsec, tax


def S(pretax=0, roth=0, taxable=0, cash=0):
    return {"pretax": pretax, "roth": roth, "taxable": taxable, "cash": cash}


def plan_for(profile):
    p = pipeline.prepare(copy.deepcopy(profile))
    ctx = RunCtx(profile=p, use_ai=False)
    plan = asyncio.run(pipeline.run_plan(ctx))
    return plan, ctx


H11 = dict(age=58, has_partner=True, partner_age=52, state="PA", pay_per_year=100000, partner_pay_per_year=80000, retire_age=62,
           partner_retire_age=67, savings=S(400000, 50000, 60000, 40000), spending_per_year=90000, spending_now_per_year=110000)
GAP25 = dict(age=62, has_partner=True, partner_age=37, state="TX", pay_per_year=0, partner_pay_per_year=0, retire_age=62,
             savings=S(900000, 0, 100000, 50000), spending_per_year=70000, spending_now_per_year=70000, claim_age=67)
H06 = dict(age=72, state="FL", pay_per_year=0, retire_age=72, savings=S(400000, 100000, 150000, 50000), spending_per_year=60000,
           spending_now_per_year=65000, social_security_per_year=36000, claim_age=67, home={"owns": True, "value": 350000})
H13 = dict(age=40, has_partner=True, partner_age=39, state="NC", pay_per_year=80000, partner_pay_per_year=45000, retire_age=65,
           savings=S(90000, 10000, 20000, 15000), spending_per_year=72000, spending_now_per_year=90000,
           children=[{"age": 10}, {"age": 7}, {"age": 3}], pets=[{"kind": "dog", "count": 2}, {"kind": "cat", "count": 1}],
           home={"owns": True, "value": 380000, "mortgage_balance": 250000, "mortgage_payment": 1800, "mortgage_rate": 0.05})


# ------------------------------------------------------------------ F1, F12, F13: Social Security per person
def test_each_person_starts_at_their_own_claiming_age():
    p = pipeline.prepare(dict(H11, claim_age=67))
    out = household.ss_household(p, 40)
    you, partner = out["people"]
    assert out["claims"] == {"you": 67, "partner": 67}
    s = out["by_year"]
    assert s[8] == 0 and s[9] > 0                  # you reach 67 in 9 years
    assert s[14] < s[15]                           # your partner reaches 67 in 15 years
    assert s[15] == pytest.approx(you["pia"] + partner["pia"], abs=2)


def test_spousal_share_is_half_the_workers_full_benefit_with_no_delayed_credit():
    worker = {"who": "you", "age": 60, "pia": 30000.0, "spousal_pia": 0.0, "claim": 70, "fixed": False}
    spouse = {"who": "partner", "age": 60, "pia": 0.0, "spousal_pia": 15000.0, "claim": 70, "fixed": False}
    assert socialsec.amount(spouse, 70) == (0.0, 15000.0)                 # no delayed credit
    assert socialsec.amount(spouse, 67) == (0.0, 15000.0)
    assert socialsec.amount(spouse, 62)[1] == pytest.approx(15000 * 0.65)  # reduced before 67
    s = socialsec.schedule([worker, spouse], 15, None)["by_year"]
    assert s[10] == round(30000 * 1.24 + 15000)


def test_survivor_keeps_the_larger_benefit_after_the_first_death():
    a = {"who": "you", "age": 70, "fixed": True, "amount": 30000.0, "claim": 67}
    b = {"who": "partner", "age": 68, "fixed": True, "amount": 12000.0, "claim": 67}
    s = socialsec.schedule([a, b], 30, None, first_death_t=15)["by_year"]
    assert s[14] == 42000 and s[15] == 30000 and s[29] == 30000


def test_gap25_couple_partner_does_not_draw_at_42_and_the_horizon_reads_sensibly():
    plan, ctx = plan_for(GAP25)
    m = ctx.results["markets"]
    by = m["social_security_by_year"]
    partner = next(x for x in household.ss_people(ctx.profile) if x["who"] == "partner")
    first_partner = partner["claim"] - 37
    assert by[5] > 0                                     # you claim at 67
    assert by[5] == by[first_partner - 1]               # nothing extra before your partner's own claiming age
    assert "until your partner is" in plan["horizon_text"] and "119" not in plan["horizon_text"]
    assert not any("to age 119" in a for a in plan["assumptions"])
    assert plan["wants"]["per_year"] < 49200            # was overstated before the fix


def test_h11_count_on_no_longer_overstated():
    plan, _ = plan_for(H11)
    assert plan["wants"]["per_year"] < 95300            # the audit's correct-timing figure was $89,900 (no survivor step-down)


# ------------------------------------------------------------------ F2: already claiming
def test_stated_claim_age_kept_and_no_claiming_advice_when_already_claiming():
    plan, _ = plan_for(H06)
    assert plan["claim_age"] == 67 and plan["already_claiming"] is True
    assert not any("social security" in a["title"].lower() for a in plan["actions"])
    assert not any("claim" in (x.get("whatif_text") or "").lower() for x in plan["levers"])


# ------------------------------------------------------------------ F3: fewer than 35 years
def test_estimate_dilutes_for_fewer_than_35_years():
    assert estimates.career_years(45) == 23 and estimates.career_years(65) == 35
    full = estimates.pia_per_year(150000)
    short = estimates.pia_per_year(150000, estimates.career_years(45))
    assert short < 0.86 * full
    p = pipeline.prepare(dict(age=35, state="TX", pay_per_year=150000, retire_age=45, savings=S(300000, 50000, 200000, 50000),
                              spending_per_year=60000, spending_now_per_year=70000))
    assert p.social_security_per_year < 45000


# ------------------------------------------------------------------ F4: working-year tax
def test_child_credit_head_of_household_and_401k_deduction():
    plain = tax.working_years(60000, 0, "TX", False)
    parent = tax.working_years(60000, 0, "TX", False, children_under_17=2)
    assert parent["filing"] == "head_of_household" and parent["federal_tax"] < plain["federal_tax"] - 4000
    with401k = tax.working_years(60000, 0, "TX", False, pretax_contrib=6000)
    assert with401k["federal_tax"] < plain["federal_tax"] and with401k["payroll_tax"] == plain["payroll_tax"]
    p = pipeline.prepare(H13)
    assert costs.work_tax(p)["federal_tax"] < 10504 - 4000      # 3 children; the audit found $10,504, about $6,000 too high


def test_withdrawal_tax_grosses_up_so_the_net_is_the_need():
    # all pre-tax, no state income tax, no Social Security: the withdrawal less its own federal tax is the need
    r = tax.retirement_years(60000, 0, {"pretax": 1000000}, "TX", False, 0)
    w = r["gross_withdrawal_per_year"]
    assert abs(w - tax.federal_tax(w, "single") - 60000) < 60


def test_states_that_exempt_social_security():
    assert tax.state_exempts_ss("PA") and tax.state_exempts_ss("NY") and not tax.state_exempts_ss("CO")
    co = tax.retirement_years(40000, 40000, {"cash": 10000}, "CO", True, 2)
    ny = tax.retirement_years(40000, 40000, {"cash": 10000}, "NY", True, 2)
    assert ny["social_security_tax_per_year"] <= co["social_security_tax_per_year"]


# ------------------------------------------------------------------ F5: count-on never falls when inputs rise
def _perturb(profile, kind):
    p = copy.deepcopy(profile)
    if kind == "pay+20%":
        p["pay_per_year"] *= 1.2
        if p.get("partner_pay_per_year"):
            p["partner_pay_per_year"] *= 1.2
    elif kind == "savings+20%":
        p["savings"] = {k: v * 1.2 for k, v in p["savings"].items()}
    elif kind == "retire+2":
        p["retire_age"] += 2
    elif kind == "claim+2":
        p["claim_age"] += 2
    return p


# the audit's flagged cases (round1_A/invariants.py: r02 and r11 are its seeded random households) and a few more
R02 = dict(age=62, state="IL", retire_age=65, pay_per_year=120000, savings=S(300000, 50000, 100000, 50000), spending_per_year=45000,
           spending_now_per_year=60000)
MONO = [("H11", H11, "pay+20%"), ("H13", H13, "pay+20%"), ("H13", H13, "savings+20%"), ("H11", H11, "retire+2"),
        ("H11c", dict(H11, claim_age=67), "claim+2"),
        ("R02", R02, "pay+20%"), ("R02", R02, "savings+20%")]


@pytest.mark.parametrize("name,profile,kind", MONO, ids=[f"{a}-{c}" for a, _, c in MONO])
def test_count_on_does_not_fall_when_inputs_rise(name, profile, kind):
    base = plan_for(profile)[0]["wants"]["per_year"]
    up = plan_for(_perturb(profile, kind))[0]["wants"]["per_year"]
    assert up >= base * 0.99, (name, kind, base, up)


def test_pick_uses_a_fixed_bar_so_more_candidates_never_lower_the_pick():
    a = [{"source": "rule", "basics_paid_of_100": 96, "safe_spending_per_year": 60000},
         {"source": "x", "basics_paid_of_100": 100, "safe_spending_per_year": 55000}]
    assert neighbors.pick(a)["safe_spending_per_year"] == 60000


def test_grid_is_scored_for_every_household():
    plan, ctx = plan_for(H13)
    srcs = [c["source"] for c in ctx.results["neighbors"]["candidates_tested"]]
    assert {f"rule-claim-{c}" for c in range(62, 71)} <= set(srcs)


# ------------------------------------------------------------------ F6, F7: assumptions and the saving figure
def test_assumptions_state_the_numbers_used():
    plan, ctx = plan_for(H13)
    text = " ".join(plan["assumptions"])
    assert "today's dollars" in text and "5.0%" in text and "1.8%" in text and "85%" in text
    assert "no raises" in text and "Yearly saving" in text and "larger Social Security check" in text
    sv = plan["saving"]
    assert sv["per_year"] == ctx.results["money"]["save_now"] and sv["unspent_pay_per_year"] >= 0
    assert f"${sv['per_year']:,.0f}" in text


# ------------------------------------------------------------------ F8: one meaning for falls short
def test_verdicts():
    assert adviser.verdict({"spending_goal_per_year": 100000, "safe_spending_per_year": 70000, "basics_paid_of_100": 100}) == "below_goal"
    assert adviser.verdict({"spending_goal_per_year": 100000, "safe_spending_per_year": 95000, "basics_paid_of_100": 100}) == "close"
    assert adviser.verdict({"spending_goal_per_year": 10000, "safe_spending_per_year": 95000, "basics_paid_of_100": 80}) == "falls_short"


# ------------------------------------------------------------------ F9: a real lever before filler
def test_third_action_is_the_next_lever_before_filler():
    goal = {"key": "goal", "title": "Set your spending goal nearer the safe level", "why": "g"}
    match = {"key": "match", "title": "Save enough to get the full employer match", "why": "m"}
    emerg = {"key": "emergency", "title": "Build an emergency fund of three months", "why": "e"}

    class A:
        def __init__(self, t):
            self.t = t

        def model_dump(self):
            return {"title": self.t, "why": "x"}
    out = adviser.order_actions([goal, match, emerg], [A("Set your spending goal lower"), A("Check your plan once a year")])
    assert [a["title"] for a in out] == [goal["title"], match["title"], emerg["title"]]
    out = adviser.order_actions([goal], [A("Keep your spending goal at or below $55,000"), A("Claim later")])
    assert all(not a["title"].lower().startswith("keep your spending") for a in out)


# ------------------------------------------------------------------ F10: the needs line follows basics paid
@pytest.mark.parametrize("paid", [0, 40, 95, 100])
def test_needs_line_is_built_from_paid(paid):
    line = adviser.needs_line({"basics_paid_of_100": paid}, 30000)
    if paid < 90:
        assert "starts there" in line and (str(paid) in line or "not paid in any" in line)
    else:
        assert "paid in" in line and "only" not in line


def test_plan_needs_line_matches_paid():
    plan, _ = plan_for(dict(age=68, state="MI", pay_per_year=0, retire_age=68, savings=S(0, 0, 0, 5000), spending_per_year=28000,
                            spending_now_per_year=30000, social_security_per_year=22000, claim_age=66, home={"owns": False, "rent": 1100}))
    assert plan["needs"]["line"] == adviser.needs_line({"basics_paid_of_100": plan["needs"]["paid_of_100"]}, plan["needs"]["basics_per_year"])


# ------------------------------------------------------------------ F11: arrays cover the whole horizon
def test_arrays_reach_the_horizon_for_the_young():
    plan, ctx = plan_for(dict(age=20, state="TX", pay_per_year=40000, retire_age=65, savings=S(1000), spending_per_year=30000,
                              spending_now_per_year=32000))
    assert plan["costs_by_age"]["ages"][-1] == plan["horizon_age"]


# ------------------------------------------------------------------ B P0-1: starting points when the basics are not safe
def test_starting_points_when_basics_are_not_safe():
    bus = dict(age=52, state="MI", pay_per_year=52000, retire_age=58, savings=S(20000, 0, 5000, 5000), spending_now_per_year=50400,
               spending_per_year=40000)
    plan, _ = plan_for(bus)
    assert plan["verdict"] == "falls_short"
    pts = plan["starting_points"]
    assert 1 <= len(pts) <= 3
    for x in pts:
        if x["title"].startswith("Retire at"):
            assert int(re.match(r"Retire at (\d+)", x["title"]).group(1)) <= 70
    first = plan["actions"][0]
    # round 4: the first move is the best starting point itself, said as an action (never "Make your needs safe first")
    assert first["title"] == pts[0]["action_title"] and first["whatif_text"] == pts[0]["whatif_text"]
    assert "Start there" not in first["why"] and "$0 a year" not in first["why"]


# ------------------------------------------------------------------ B P0-2: already retired
def test_retired_couple_spends_what_they_spend_now():
    p = pipeline.prepare(dict(age=71, has_partner=True, partner_age=69, state="FL", retire_age=71, pay_per_year=0,
                              savings=S(500000, 0, 100000, 50000), spending_now_per_year=72000,
                              sources={"spending_now_per_year": "you said"}))
    assert p.spending_per_year == 72000
    plan, _ = plan_for(p.model_dump())
    assert plan["already_retired"] and plan["costs_by_age"]["now_per_year"] == 72000
    assert not any("Before Medicare" in n for n in plan["costs_by_age"]["notes"])


# ------------------------------------------------------------------ B P0-4: absurd spending is set aside
def test_spending_of_100_a_year_is_set_aside():
    p = pipeline.prepare(dict(age=30, state="TX", pay_per_year=95000, retire_age=65, savings=S(0, 0, 0, 8000), spending_per_year=100,
                              spending_now_per_year=100, sources={"spending_per_year": "you said", "spending_now_per_year": "you said"}))
    assert p.spending_per_year > 10000 and p.spending_now_per_year > 10000
    assert p.sources["spending_per_year"] == "estimate"
    assert household.basics(p)["basics_per_year"] > 10000


# ------------------------------------------------------------------ B P1-11: no machinery words
def test_number_check_rejects_tool_output_words():
    r = safety.number_check("According to the tool output, that figure looks wrong.", set())
    assert not r.ok
    assert safety.number_check("You can count on this.", set()).ok


def test_plain_neighbour_note():
    plan, ctx = plan_for(H13)
    note = ctx.results["neighbors"]["note"]
    assert "rule of thumb" not in note.lower() and "library" not in note.lower()


# ------------------------------------------------------------------ F18, F21
def test_longevity_grammar():
    from app.agents.longevity import Longevity
    r = {"horizon_age": 95, "chance_alive_at_horizon": 0.25, "chance_someone_reaches_90": 0.4}
    _, d = Longevity().template(r)
    assert "you reach 90" in " ".join(d) and "you reaches" not in " ".join(d)


def test_count_on_below_social_security_is_explained():
    m = {"safe_spending_per_year": 20000, "social_security_per_year": 22000, "ss_tax_rate": 0.05, "health_extra_in_retirement": True}
    h = adviser.headline(m, 18000)
    assert "less than your Social Security of $22,000" in h
    assert "tax" in adviser.below_ss_why(m)


# ------------------------------------------------------------------ eval direction checks after the fix
S139 = {"age": 66, "partner_age": 72, "has_partner": True, "state": "IN", "retire_age": 67, "pay_per_year": 51000, "partner_pay_per_year": 0,
        "savings": S(23400, 2800, 277100, 11900), "home": {"owns": True, "value": 220000, "mortgage_balance": 48100, "mortgage_payment": 715,
        "mortgage_rate": 0.065}, "spending_per_year": 55000, "social_security_per_year": 39600, "risk": "growth", "partner_retire_age": 72}


def test_stated_figure_for_the_one_not_yet_claiming_is_read_at_67():
    p = pipeline.prepare(S139)
    you, partner = household.ss_people(p)
    assert partner["fixed"] and not you["fixed"]
    assert socialsec.amount(you, 69)[0] > socialsec.amount(you, 67)[0]      # a later start earns the delayed credit
    base = plan_for(S139)[0]["wants"]["per_year"]
    later = plan_for(dict(S139, retire_age=69))[0]["wants"]["per_year"]
    assert later >= base * 0.99


def test_a_pension_never_raises_the_tax_rate_before_it_starts():
    young = dict(age=45, state="TX", pay_per_year=40000, retire_age=50, savings=S(150000, 0, 50000, 10000), spending_per_year=45000,
                 spending_now_per_year=40000)
    base = plan_for(young)[0]["wants"]["per_year"]
    more = plan_for(dict(young, pensions=[{"who": "you", "per_year": 24000, "start_age": 65}]))[0]["wants"]["per_year"]
    assert more >= base * 0.99
