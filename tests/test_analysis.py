"""The plan's analysis (app/analysis.py): rule-of-thumb sanity checks on five realistic households.

- How sure: the 90-in-100 level is the plan's own count-on figure, and each scenario's own limit agrees with it.
- What could go wrong: a poor decade, higher inflation and a longer life are never better than the plan.
- What each choice is worth: each lever matches a direct rerun of the whole plan with that change (strategy kept).
- Where the money comes from: each year's parts add up to that year's spending (plus any income that is saved).
- Costs: each year's parts add up to the costs chart's total.
No live AI.
"""
from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from app import analysis, pipeline
from app.agents.base import RunCtx
from app.schemas import Analysis
from app.tools import neighbors

LITE = Path(__file__).resolve().parents[1]
CASES = {json.loads(x)["id"]: json.loads(x) for x in open(LITE / "eval" / "cases.jsonl", encoding="utf-8")}

BUS = {"age": 52, "has_partner": False, "state": "MI", "retire_age": 58, "pay_per_year": 52000, "job": "bus driver",
       "savings": {"pretax": 20000, "roth": 0, "taxable": 0, "cash": 10000}, "savings_known": True,
       "home": {"owns": False, "rent": 1300},
       "children": [{"age": 16, "college": True, "college_type": "public"}, {"age": 14, "college": True, "college_type": "public"}],
       "spending_now_per_year": 50400, "risk": "balanced",
       "sources": {"age": "you said", "retire_age": "you said", "pay_per_year": "you said", "spending_now_per_year": "you said"}}
GAP10 = {"age": 58, "partner_age": 48, "has_partner": True, "state": "OH", "retire_age": 65, "pay_per_year": 95000,
         "partner_pay_per_year": 60000, "savings": {"pretax": 450000, "roth": 50000, "taxable": 60000, "cash": 30000},
         "savings_known": True, "home": {"owns": True, "value": 350000, "mortgage_balance": 120000, "mortgage_payment": 1400},
         "spending_now_per_year": 90000, "risk": "balanced",
         "saving": {"contrib_you": 12000, "contrib_partner": 6000, "match_rate": 0.5, "match_cap": 0.06},
         "debts": [{"kind": "credit_card", "balance": 8000}], "sources": {"age": "you said"}}
HOUSEHOLDS = {"bus_driver": BUS, "retired_couple": CASES["E20_couple_both_retired"]["profile"],
              "single_parent": CASES["E09_single_mom_2_kids"]["profile"], "gap10": GAP10,
              "high_earner": CASES["E27_max_contributions_high_earner"]["profile"]}
_PLANS: dict[str, tuple[dict, RunCtx]] = {}


def plan_of(name: str) -> tuple[dict, RunCtx]:
    if name not in _PLANS:
        ctx = RunCtx(profile=pipeline.prepare(copy.deepcopy(HOUSEHOLDS[name])), use_ai=False, session="analysis")
        _PLANS[name] = (asyncio.run(pipeline.run_plan(ctx)), ctx)
    return _PLANS[name]


NAMES = list(HOUSEHOLDS)


@pytest.mark.parametrize("name", NAMES)
def test_analysis_is_in_the_plan_and_typed(name):
    plan, _ = plan_of(name)
    a = plan["analysis"]
    assert a is not None
    Analysis.model_validate(a)
    assert a["plan_count_on_per_year"] == plan["wants"]["per_year"] == plan["count_on_per_year"]
    assert a["plan_basics_paid_of_100"] == plan["needs"]["paid_of_100"]


@pytest.mark.parametrize("name", NAMES)
def test_how_sure_matches_the_plan_and_each_scenarios_limit(name):
    plan, ctx = plan_of(name)
    hs = plan["analysis"]["how_sure"]
    lv = {x["of_100"]: x["per_year"] for x in hs["levels"]}
    assert lv[90] == plan["wants"]["per_year"]
    assert lv[50] >= lv[75] >= lv[90] >= lv[95] >= 0
    ys = hs["curve_lasts_of_100"]
    assert all(a >= b for a, b in zip(ys, ys[1:])), "more spending never lasts in more scenarios"
    assert hs["goal_lasts_of_100"] == ctx.results["markets"]["goal_lasts_of_100"]
    # each scenario's own limit, found in one search, gives the same 90-in-100 point as the plan's own search
    sim, strat = ctx.kept["sim"], ctx.kept["strategy"]
    r = analysis.run_kept(sim, strat, neighbors._people(ctx.kept["person"], sim), detail=True)
    s = np.sort(r["_detail"]["max_spend"])[::-1]
    assert abs(max(0.0, float(s[int(np.ceil(0.9 * len(s))) - 1])) - plan["wants"]["per_year"]) <= 100
    assert r["safe_spending_per_year"] == plan["wants"]["per_year"]
    assert r["basics_paid_of_100"] == plan["needs"]["paid_of_100"]
    share_basics = round(float((s >= plan["needs"]["basics_per_year"]).mean()) * 100)
    assert abs(share_basics - plan["needs"]["paid_of_100"]) <= 1


@pytest.mark.parametrize("name", NAMES)
def test_stresses_are_never_better_than_the_plan(name):
    plan, ctx = plan_of(name)
    rows = {x["key"]: x for x in plan["analysis"]["stresses"]["rows"]}
    assert {"bad_decade", "inflation"} <= set(rows)
    for k, x in rows.items():
        assert x["what"].count(". ") == 0 and x["what"].endswith("."), "each stress is one plain sentence"
        if k in ("early_death", "late_death"):
            continue      # spending falls after a death too, so this one can go either way (its note says so)
        assert x["count_on_change"] <= 0 and x["basics_change"] <= 0, (k, x)
    couple = bool(ctx.profile.has_partner and ctx.profile.partner_age)
    assert ("long_partner" in rows) <= couple
    assert ("early_death" in rows) <= couple and ("late_death" in rows) <= couple
    if "early_death" in rows and rows["early_death"]["count_on_change"] > 0:
        assert rows["early_death"]["note"]


def _direct_rerun(ctx: RunCtx, lever_key: str, monkeypatch) -> dict:
    """The whole plan rerun with the lever's change, keeping the plan's strategy (the strategy test may only pick it)."""
    t = next(x for x in analysis.lever_tries(ctx.profile, ctx.results["markets"]) if x["key"] == lever_key)
    from app.agents import adviser
    newp = adviser._apply_try(ctx.profile, t)
    kept = ctx.kept["strategy"]["source"]
    real_pick = neighbors.pick
    monkeypatch.setattr(neighbors, "pick", lambda scored: next((c for c in scored if c["source"] == kept), real_pick(scored)))
    c2 = RunCtx(profile=newp, use_ai=False, options=False)
    asyncio.run(pipeline.run_plan(c2))
    monkeypatch.setattr(neighbors, "pick", real_pick)
    assert c2.kept["strategy"]["source"] == kept
    return c2.results["markets"]


@pytest.mark.parametrize("name", NAMES)
def test_levers_match_a_direct_rerun_and_respect_the_rules(name, monkeypatch):
    plan, ctx = plan_of(name)
    p = ctx.profile
    rows = plan["analysis"]["levers"]["rows"]
    keys = [x["key"] for x in rows]
    retired = (p.retire_age or 65) <= (p.age or 45)
    if retired:
        assert "retire" not in keys and "save" not in keys and "match" not in keys
    for x in rows:
        if x["key"] == "retire":
            assert int(x["title"].rsplit(" ", 1)[-1]) <= 70
    assert [x["count_on_change"] for x in rows] == sorted((x["count_on_change"] for x in rows), reverse=True)
    for x in rows:
        if x["key"] == "claim" or (x["key"] == "retire" and ctx.kept["strategy"]["annuities"]):
            continue     # the claiming age is the change itself; an annuity's purchase moves with retirement
        m2 = _direct_rerun(ctx, x["key"], monkeypatch)
        assert m2["safe_spending_per_year"] == x["count_on_per_year"], x
        assert m2["basics_paid_of_100"] == x["basics_paid_of_100"], x
        assert x["count_on_change"] == round(x["count_on_per_year"] - plan["wants"]["per_year"], -2)


@pytest.mark.parametrize("name", NAMES)
def test_sources_add_up_to_spending_and_agree_with_the_costs_chart(name):
    plan, ctx = plan_of(name)
    s = plan["analysis"]["sources"]
    costs = plan["costs_by_age"]
    ra = ctx.profile.retire_age
    first_death = ctx.kept["sim"].get("spend_drop_t")
    for t, age in enumerate(s["ages"]):
        parts = sum(x["values"][t] for x in s["series"])
        assert abs(parts - s["spending"][t] - s["surplus"][t]) <= 1, (age, parts, s["spending"][t], s["surplus"][t])
        assert all(x["values"][t] >= 0 for x in s["series"])
        if first_death is None or t < first_death:
            # one figure: the year's spending is the costs chart's total for that age
            assert abs(s["spending"][t] - costs["total"][costs["ages"].index(age)]) <= 1, age
    keys = {x["key"] for x in s["series"]}
    if (ra or 65) > (ctx.profile.age or 45):
        assert "pay" in keys


@pytest.mark.parametrize("name", NAMES)
def test_cost_parts_add_up_to_the_total(name):
    plan, _ = plan_of(name)
    c = plan["costs_by_age"]
    assert c["parts"], "the costs chart sends its parts"
    for t in range(len(c["ages"])):
        assert sum(x["values"][t] for x in c["parts"]) == c["total"][t]
        assert all(x["values"][t] >= 0 for x in c["parts"])
    labels = [x["label"] for x in c["parts"]]
    assert len(labels) == len(set(labels))


def test_bus_driver_sees_the_shortfall_plainly():
    plan, _ = plan_of("bus_driver")
    a = plan["analysis"]
    assert "no level of spending lasts" in a["how_sure"]["line"]
    assert any(x["key"] == "short" for x in a["sources"]["series"])
    assert "run out" in a["sources"]["line"]


def test_market_what_if_plans_skip_the_analysis():
    ctx = RunCtx(profile=pipeline.prepare(copy.deepcopy(HOUSEHOLDS["single_parent"])), use_ai=False, shock={"kind": "bad_decade"})
    plan = asyncio.run(pipeline.run_plan(ctx))
    assert plan["analysis"] is None


# ------------------------------------------------------------------ small plan fixes folded in with the analysis
def test_earnings_test_withholds_a_dollar_for_every_two_above_the_limit():
    from app.tools import socialsec
    p = {"who": "you", "age": 62, "pia": 24000, "spousal_pia": 0, "claim": 62, "chosen": True, "fixed": False, "pay": 60000, "work_until": 65}
    rows = socialsec.schedule([p], 6)["each_by_year"]["you"]
    own = 24000 * socialsec.estimates.claim_factor(62)
    cut = (60000 - socialsec.EARNINGS_TEST_LIMIT) / 2
    assert rows[0] == round(max(0.0, own - cut))
    assert rows[3] == round(own)          # stopped work at 65: the full benefit
    p2 = {**p, "pay": 20000}
    assert socialsec.schedule([p2], 2)["each_by_year"]["you"][0] == round(own)


def test_below_social_security_note_is_two_short_sentences_and_names_a_pay_deficit():
    from app.agents import adviser
    m = {"safe_spending_per_year": 10000, "social_security_per_year": 33000, "ss_tax_rate": 0.1, "health_extra_in_retirement": True,
         "social_security_survivor_per_year": 20000, "ss_starts_later": True, "inputs": {"save_per_year": 5000, "retire_age": 65, "age": 50}}
    note = adviser.below_ss_note(m).strip()
    sentences = [s for s in note.split(". ") if s]
    assert len(sentences) == 2 and all(len(s.split()) <= 25 for s in sentences), note
    m["inputs"]["save_per_year"] = -6000
    note = adviser.below_ss_note(m)
    assert "more now than your take-home pay" in note and "health" not in note


# ------------------------------------------------------------------ what could go wrong: consequence sentences
import re  # noqa: E402

JARGON = ("percentile", "monte carlo", "sequence", "sequence risk", "volatility", "standard deviation")


def _base_row(**kw) -> dict:
    row = {"key": "bad_decade", "title": "A poor first decade", "stress_years": 10, "to_age": None, "survivor_spend_pct": None,
           "plan_spend_per_year": 191000.0, "count_on_per_year": 187900.0, "basics_paid_of_100": 100, "basics_at_risk": False,
           "worst_runs_out_age": None, "worst_years_short": 0, "worst_gap_per_year": 0.0,
           "typical_runs_out_age": None, "typical_years_short": 0, "typical_gap_per_year": 0.0, "typical_income_per_year": 0.0,
           "typical_income_from": "", "typical_lasts": True}
    row.update(kw)
    return row


def _numbers(s: str) -> set[int]:
    return {int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", s)}


def _allowed(x: dict) -> set[int]:
    k = analysis._k
    figs = {int(k(x[f]).replace("$", "").replace(",", "")) for f in
            ("plan_spend_per_year", "count_on_per_year", "worst_gap_per_year", "typical_income_per_year") if x.get(f)}
    ints = {x.get(f) for f in ("worst_runs_out_age", "worst_years_short", "typical_runs_out_age", "typical_years_short",
                               "stress_years", "to_age", "survivor_spend_pct", "basics_paid_of_100") if x.get(f) is not None}
    return figs | ints | {100 - x["basics_paid_of_100"], 1, 10, 100}      # "1 in 10", "of 100"


def test_sentence_template_spending_still_holds():
    x = _base_row(plan_spend_per_year=191000, count_on_per_year=167000, worst_runs_out_age=88, worst_years_short=7, worst_gap_per_year=24000)
    s = analysis.sentence(x, couple=False)
    assert s == ("Your $191,000 a year still lasts in most paths. In the worst 1 in 10, savings "
                 "run out at 88, and you would cut about $24,000 a year for 7 years.")      # basics said once after the list
    assert "when you are 88" in analysis.sentence(x, couple=True)
    assert "Basics stay paid in 97 of 100 paths." in analysis.sentence({**x, "basics_paid_of_100": 97}, couple=False)
    assert "for 1 year." in analysis.sentence({**x, "worst_years_short": 1}, couple=False)


def test_sentence_template_spending_fails():
    x = _base_row(key="inflation", plan_spend_per_year=191000, count_on_per_year=187900, typical_runs_out_age=84, typical_years_short=11,
                  worst_runs_out_age=80, typical_income_per_year=58000, typical_income_from="Social Security and your pension")
    s = analysis.sentence(x, couple=False)
    assert s == ("Your $191,000 a year would run out at 84 in a typical path. You would have 11 years "
                 "with only Social Security and your pension, about $58,000 a year. Spending $188,000 instead would last.")


def test_sentence_template_small_effect():
    x = _base_row(key="late_death", stress_years=10, plan_spend_per_year=195000, count_on_per_year=191800)
    assert analysis.sentence(x, couple=True) == "The plan still works: you could spend about $192,000 a year instead of $195,000."
    s = analysis.sentence({**x, "count_on_per_year": 196000}, couple=True)
    assert s.endswith("you could still spend about $195,000 a year.")


def test_sentence_template_basics_at_risk_comes_first():
    x = _base_row(basics_paid_of_100=86, basics_at_risk=True, plan_spend_per_year=60000, count_on_per_year=52000, typical_runs_out_age=91)
    s = analysis.sentence(x, couple=False)
    assert s.startswith("Your basics would go unpaid in 14 of 100 market paths.")
    assert "In a typical path your savings run out at 91." in s and s.endswith("about $52,000 a year, down from $60,000.")


def test_sentence_early_death_keeps_the_survivor_note():
    x = _base_row(key="early_death", stress_years=10, survivor_spend_pct=75, plan_spend_per_year=195000, count_on_per_year=191800)
    assert analysis.sentence(x, couple=True).endswith("Spending drops to 75% for the one left.")
    assert "75%" not in analysis.sentence(_base_row(), couple=True)


@pytest.mark.parametrize("name", NAMES)
def test_sentences_use_only_computed_figures_and_stay_plain(name):
    plan, ctx = plan_of(name)
    st = plan["analysis"]["stresses"]
    top = st["top"]
    assert len(top) <= 3 and len(set(top)) == len(top)
    rows = {x["key"]: x for x in st["rows"]}
    assert set(top) <= set(rows)
    hurt = sorted((x for x in st["rows"] if x["count_on_change"] < 0 or x["basics_change"] < 0), key=lambda x: x["count_on_change"])
    assert top == [x["key"] for x in hurt[:3]]
    couple = bool(ctx.profile.has_partner and ctx.profile.partner_age)
    for x in st["rows"]:
        s = x["sentence"]
        if not plan["analysis"]["plan_count_on_per_year"]:
            assert s == ""
            continue
        assert s == analysis.sentence(x, couple)
        assert _numbers(s) <= _allowed(x), (x["key"], s, _numbers(s) - _allowed(x))
        assert len(s.split()) <= 45, s
        assert not s.startswith("If "), s      # the bold label names the risk; the sentence starts with the consequence
        assert not (set(re.findall(r"[a-z]+", x["label"].lower())) - {"you", "your", "the", "a", "for", "in", "to", "years", "year"}) <= set(re.findall(r"[a-z]+", s.lower())), (x["label"], s)
        assert not any(j in s.lower() for j in JARGON)
        assert x["count_on_drop"] == max(0.0, -x["count_on_change"])
        assert x["basics_at_risk"] == (x["basics_paid_of_100"] < 90)
        if x["worst_runs_out_age"] is not None:
            assert x["worst_years_short"] >= 1 and x["worst_gap_per_year"] >= 0
        if x["typical_runs_out_age"] is not None:     # a typical path that fails means the worst 1 in 10 fails too, no later
            assert x["worst_runs_out_age"] is not None and x["worst_runs_out_age"] <= x["typical_runs_out_age"]
            assert x["typical_income_per_year"] >= 0 and not x["typical_lasts"]


@pytest.mark.parametrize("name", ["retired_couple", "single_parent", "gap10"])
def test_run_out_age_and_years_short_agree_with_the_simulator(name):
    """An independent check: at the plan's count-on spending under a poor decade, the worst 1 in 10 runs out at age A when the
    chance of lasting is at least 90 of 100 up to A (before it) and no more than 90 of 100 through A."""
    plan, ctx = plan_of(name)
    row = next(x for x in plan["analysis"]["stresses"]["rows"] if x["key"] == "bad_decade")
    A = row["worst_runs_out_age"]
    assert A is not None, "this plan's worst 1 in 10 runs out under a poor decade"
    sim, strat = ctx.kept["sim"], ctx.kept["strategy"]
    people = neighbors._people(ctx.kept["person"], sim)
    P = float(plan["wants"]["per_year"])
    base = {**sim, "shock": {"kind": "bad_decade"}, "spend_per_year": P}

    def lasts(h):
        return analysis.run_kept({**base, "horizon_age": h}, strat, people)["chance_goal_lasts"]
    assert lasts(A) >= 0.895 and lasts(A + 1) <= 0.905
    assert row["worst_years_short"] == int(sim["horizon_age"]) - A
    assert A >= int(sim["age"])


def test_grouped_form_when_all_shown_risks_hold():
    mk = lambda key, y, age, gap, yrs: _base_row(key=key, stress_years=y, plan_spend_per_year=111000, count_on_per_year=104000,
                                                  worst_runs_out_age=age, worst_years_short=yrs, worst_gap_per_year=gap)
    rows = [mk("inflation", 10, 93, 40000, 5), mk("bad_decade", 10, 93, 37000, 5), mk("long_partner", None, 98, 39000, 5)]
    assert analysis.group_lead(rows) == "Your $111,000 a year holds up in most market paths under each of these. In the worst 1 in 10:"
    assert analysis.short_line(rows[0], couple=True) == "savings run out when you are 93; you would cut about $40,000 a year for 5 years."
    assert analysis.short_line(rows[0], couple=False).startswith("savings run out at 93;")
    assert "Basics stay paid in 97 of 100 paths." in analysis.short_line({**rows[0], "basics_paid_of_100": 97}, couple=False)
    # different verdicts (one fails, one is small): no group, full sentences
    assert analysis.group_lead([rows[0], {**rows[1], "typical_runs_out_age": 90}]) == ""
    assert analysis.group_lead([rows[0], _base_row()]) == ""
    assert analysis.group_lead(rows[:1]) == ""


def test_real_plan_groups_only_when_verdicts_match():
    plan, ctx = plan_of("retired_couple")
    st = plan["analysis"]["stresses"]
    shown = [x for x in st["rows"] if x["key"] in st["top"]]
    couple = True
    if all(x["kind"] == "holds" for x in shown):
        assert st["lead"] and all(x["short"] for x in shown)
        for x in shown:
            assert x["short"] == analysis.short_line(x, couple)
            assert _numbers(x["short"]) <= _allowed(x)
            assert "a year holds up" not in x["short"] and str(int(analysis._k(x["plan_spend_per_year"]).replace("$", "").replace(",", ""))) not in x["short"]
        assert _numbers(st["lead"]) <= _allowed(shown[0])
        assert len(st["lead"].split()) + sum(len(x["short"].split()) for x in shown) < 100
    else:
        assert st["lead"] == ""
