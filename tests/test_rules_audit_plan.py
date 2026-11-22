"""Plan and engine fixes from the live product-rules audit (2026-11-22, docs/PRODUCT_RULES.md "Live audit" column).

R12: the "where the money comes from" chart counts pay before savings while you work; the yearly saving is take-home
pay less spending; saving What Ifs work from that same figure and move what you can count on; retiring a year later
never lowers it, and the "What each choice is worth" table and the What If agree. Saving levers are not offered to
retirees or people with no pay. R18: the falls-short note is two plain sentences. R6: the retirement age and the Social
Security start age can be changed from the plan page, with a confirm; market growth and "no raises" say they are fixed.
"""
import asyncio
import copy
import json
from pathlib import Path

import pytest

from app import analysis, ask_plan, pipeline
from app.agents import adviser
from app.tools import costs

ROOT = Path(__file__).resolve().parents[1]

# the example doctor as the live audit answered it: $310,000 pay, $2,900 a month mortgage, $5,000 a month spending now
EXAMPLE = {
    "age": 45, "partner_age": 43, "has_partner": True, "state": "CT", "retire_age": 62, "pay_per_year": 310000.0,
    "partner_pay_per_year": 0.0, "job": "doctor", "partner_sex": "female",
    "savings": {"pretax": 552000.0, "roth": 92000.0, "taxable": 184000.0, "cash": 92000.0}, "savings_known": True,
    "home": {"owns": True, "value": 850000.0, "mortgage_balance": 420000.0, "mortgage_payment": 2900.0},
    "children": [{"age": 13, "college": True, "college_type": "public", "college_source": "you said"},
                 {"age": 10, "college": True, "college_type": "private", "college_source": "you said"},
                 {"age": 6, "college": True}],
    "pets": [{"kind": "dog", "count": 2}], "spending_now_per_year": 60000.0, "risk": "balanced",
    "sources": {k: "you said" for k in ("age", "partner_age", "state", "retire_age", "pay_per_year", "partner_pay_per_year",
                                        "savings", "home", "children", "pets", "spending_now_per_year", "risk")},
    "notes": {"mortgage_balance_said": "yes", "mortgage_payment_said": "yes"},
}
# five eval households still at work: a high earner with a mortgage, couples with children and a mortgage, a single
EVAL_IDS = ("E27_max_contributions_high_earner", "S054", "N02_business_owner_sale", "S071", "S056")


def eval_profile(i: str) -> dict:
    for line in open(ROOT / "docs/loop/round3_A/evalcopy/cases.jsonl", encoding="utf-8"):
        c = json.loads(line)
        if c["id"] == i:
            return copy.deepcopy(c["profile"])
    raise KeyError(i)


_PLANS: dict = {}


def plan_for(key: str):
    if key not in _PLANS:
        prof = copy.deepcopy(EXAMPLE) if key == "example" else eval_profile(key)
        base = pipeline.prepare(prof)
        plan, ctx = asyncio.run(pipeline.tools_only_plan(base))
        _PLANS[key] = (prof, base, plan, ctx)
    return _PLANS[key]


def ask(q: str, prof: dict, pending=None) -> dict:
    return asyncio.run(pipeline.ask(q, prof, "t", use_ai=False, pending=pending))


# ------------------------------------------------------------------ R12: saving and where the money comes from
def test_example_yearly_saving_is_pay_less_tax_less_spending():
    _, base, plan, _ = plan_for("example")
    wt = costs.work_tax(base)
    sv = plan["saving"]
    # $310,000 less tax is the take-home pay; less $60,000 spending now, the rest is saved (the 401(k) part included)
    assert wt["gross_pay"] == 310000
    assert sv["per_year"] == round(wt["after_tax_pay"] - 60000)
    assert sv["accounts_per_year"] == 31000 and sv["unspent_pay_per_year"] == sv["per_year"] - 31000
    assert "$" + f"{sv['per_year']:,}" in " ".join(plan["assumptions"])


@pytest.mark.parametrize("key", ("example",) + EVAL_IDS)
def test_while_working_pay_covers_spending_before_savings(key):
    _, base, plan, ctx = plan_for(key)
    src = plan["analysis"]["sources"]
    series = {s["key"]: s["values"] for s in src["series"]}
    sim = ctx.kept["sim"]
    left = ctx.results["money"]["flows"]["pay_left_by_year"]
    age, ra = base.age, base.retire_age
    for t, a in enumerate(src["ages"]):
        if a >= ra:
            break
        drawn = series.get("savings", [0] * len(src["ages"]))[t]
        # savings pay only what take-home pay left after spending cannot: never while that pay covers the costs on top
        assert drawn == round(max(0.0, max(0.0, sim["extra_by_year"][t]) - left[t])), (key, a)
        if left[t] >= max(0.0, sim["extra_by_year"][t]):
            assert drawn == 0, (key, a)
            ss = series.get("ss_you", [0] * 200)[t] + series.get("ss_partner", [0] * 200)[t]
            assert series.get("pay", [0] * 200)[t] + ss >= src["spending"][t], (key, a)       # pay covers the spending
    if key == "example":
        t53 = 53 - age
        assert series.get("savings", [0] * 100)[t53] == 0 and series["pay"][t53] == src["spending"][t53] + src["surplus"][t53]
        # college comes out of the pay left over after spending now; the rest is saved
        assert src["surplus"][t53] == ctx.results["money"]["flows"]["pay_left_by_year"][t53] - sim["extra_by_year"][t53] > 0


def test_saving_more_moves_count_on_and_uses_the_plans_saving_figure():
    prof, base, plan, _ = plan_for("example")
    r = ask("what if I save $500 more a month", prof)
    assert r["kind"] == "whatif"
    assert r["plan"]["count_on_per_year"] > plan["count_on_per_year"]
    assert "$6,000 more a year" in r["text"] and "of pay" in r["text"] and "spend that much less now" in r["text"]
    total = r["plan"]["saving"]["per_year"]
    assert f"${total:,}" in r["text"] and total > plan["saving"]["per_year"]
    r2 = ask("Save 15% of my pay", prof)           # the "Save 5% more of pay" chip
    assert r2["kind"] == "whatif" and r2["plan"]["count_on_per_year"] > plan["count_on_per_year"]
    assert "$15,500 more a year" in r2["text"]


# ------------------------------------------------------------------ retire later: monotone, one engine path
@pytest.mark.parametrize("key", ("example",) + EVAL_IDS)
def test_retiring_later_never_lowers_count_on_and_table_matches_whatif(key):
    prof, base, plan, ctx = plan_for(key)
    ages = [a for a in range(62, 68) if a > base.age]
    deficit = plan["saving"]["per_year"] < 0       # spending above take-home pay: a later age adds years of drawing on savings
    seen = []
    for a in ages:
        if a == base.retire_age:
            v = plan["count_on_per_year"]
        else:
            v = analysis.rerun_with(ctx, {"key": "retire", "title": "", "ch": {"retire_age": a}})["safe_spending_per_year"]
            if key == "example" or a == base.retire_age + 1:
                r = ask(f"what if I retire at {a}", prof)
                assert r["kind"] == "whatif" and r["plan"]["count_on_per_year"] == v, (key, a)
                if deficit and a > base.retire_age:
                    assert pipeline.DEFICIT_LATER in r["text"]      # the stated reason when a later age does not help
        seen.append(v)
    for x, y in zip(seen, seen[1:]):
        # never lower; with a deficit it may fall a little, and the reason is said
        assert y >= x or (deficit and y >= 0.97 * x), (key, list(zip(ages, seen)))
    rows = {x["key"]: x for x in plan["analysis"]["levers"]["rows"]}
    if "retire" in rows and base.retire_age + 1 in ages:
        assert rows["retire"]["count_on_change"] == round(seen[ages.index(base.retire_age + 1)] - plan["count_on_per_year"], -2)


def test_mortgage_is_left_out_of_retirement_spending_whatever_the_retirement_age():
    _, base, plan, _ = plan_for("example")
    assert costs.mortgage_separate(base)
    assert any("leaves out the mortgage" in a for a in plan["assumptions"])
    goals = {pipeline.apply_whatif(base, {"retire_age": a})[0].spending_per_year for a in (63, 64, 65)}
    assert goals == {base.spending_per_year}


# ------------------------------------------------------------------ saving levers: not for retirees or people with no pay
def test_no_saving_levers_for_a_retiree(retiree_profile):
    base = pipeline.prepare(copy.deepcopy(retiree_profile))
    assert not ask_plan.can_save(base)
    assert all("save" not in c.lower() for c in ask_plan.useful_whatifs(base))
    r = ask("what if I save $500 more a month", retiree_profile)
    assert r["kind"] == "clarify" and "no pay to save from" in r["text"]
    assert all("save" not in c.lower() for c in r["quick_answers"])
    r = ask("Save 5% of my pay", retiree_profile)
    assert r["kind"] == "clarify"
    r = ask("retire at 65", retiree_profile)
    assert r["kind"] == "clarify" and "already 67 and retired" in r["text"]
    assert r["quick_answers"] and all("retire" not in c.lower() for c in r["quick_answers"])
    plan, _ = asyncio.run(pipeline.tools_only_plan(base))
    assert all(x["key"] != "save" for x in plan["analysis"]["levers"]["rows"])


def test_no_saving_levers_for_someone_with_no_pay():
    prof = {"age": 50, "retire_age": 60, "pay_per_year": 0, "state": "OH", "savings": {"pretax": 300000}, "savings_known": True,
            "spending_now_per_year": 40000, "sources": {"pay_per_year": "you said", "spending_now_per_year": "you said"}}
    r = ask("what if I save $500 more a month", prof)
    assert r["kind"] == "clarify" and "no pay" in r["text"]
    assert ask_plan.save_chip(pipeline.prepare(copy.deepcopy(prof))) == "What if I spend $500 less a month"


# ------------------------------------------------------------------ a partner who stops working
def test_wife_stops_working_with_no_pay_is_explained_not_asked_for_an_age():
    prof, *_ = plan_for("example")
    r = ask("what if my wife stops working", prof)
    assert r["kind"] == "clarify" and "no pay for your wife" in r["text"] and "At what age" not in r["text"]


def test_wife_stops_working_with_pay_stops_her_pay_now():
    prof = copy.deepcopy(EXAMPLE)
    prof.update(partner_pay_per_year=60000.0, partner_retire_age=62)
    prof["sources"]["partner_retire_age"] = "you said"
    base = pipeline.prepare(copy.deepcopy(prof))
    assert (base.partner_pay_per_year or 0) > 0
    plan, _ = asyncio.run(pipeline.tools_only_plan(base))
    r = ask("what if my wife stops working", prof)
    assert r["kind"] == "whatif" and "your wife stops working now" in r["text"]
    assert r["profile"]["partner_retire_age"] == base.partner_age
    assert r["plan"]["count_on_per_year"] <= plan["count_on_per_year"]


# ------------------------------------------------------------------ R18: the note below Social Security
def test_below_social_security_note_is_two_plain_sentences():
    m = {"safe_spending_per_year": 20000, "social_security_per_year": 37000, "ss_tax_rate": 0.1, "health_extra_in_retirement": True,
         "ss_starts_later": True, "social_security_survivor_per_year": 20000}
    note = adviser.below_ss_note(m).strip()
    sentences = [s for s in note.split(". ") if s]
    assert len(sentences) == 2 and all(len(s.split()) <= 22 for s in sentences), note
    assert "The reasons:" not in note and note.count(" and ") <= 1
    assert "less than your Social Security of $37,000" in note


# ------------------------------------------------------------------ R6: the plan's own choices can be changed
def test_assumptions_say_what_is_fixed_and_offer_changes():
    prof, base, plan, _ = plan_for("example")
    text = " ".join(plan["assumptions"])
    assert "They are fixed" in text and "This is fixed" in text
    qs = {c["q"] for c in plan["assumption_changes"]}
    assert qs == {adviser.CHANGE_RETIRE_Q, adviser.CHANGE_CLAIM_Q}


def test_social_security_start_age_changes_with_a_confirm():
    prof, base, plan, _ = plan_for("example")
    r = ask(adviser.CHANGE_CLAIM_Q, prof)
    assert r["kind"] == "clarify" and "Set my Social Security start age to 70" in r["quick_answers"]
    r = ask("Set my Social Security start age to 70", prof)
    assert r["kind"] == "change" and r["status"] == "confirm" and r["pending_change"]["facts"] == {"claim_age": 70}
    done = ask("Yes, rebuild", prof, pending=r["pending_change"])
    assert done["kind"] == "change" and done["status"] == "applied"
    assert done["profile"]["claim_age"] == 70 and done["plan"]["claim_age"] == 70
    bad = ask("Yes, rebuild", prof, pending={"facts": {"claim_age": 75}})
    assert bad.get("status") != "applied"


def test_retirement_age_change_asks_for_the_age():
    prof, *_ = plan_for("example")
    r = ask(adviser.CHANGE_RETIRE_Q, prof)
    assert r["kind"] == "change" and r["status"] == "ask" and r["pending_change"] == {"ask": "retire_age"}
