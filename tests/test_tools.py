import time

from app.tools import estimates, family_costs, lifetable, neighbors, simulate, sources, tax


def test_horizon_couple_longer_than_single():
    single = lifetable.horizon(65)
    couple = lifetable.horizon(65, partner_age=63)
    assert 88 <= single["horizon_age"] <= 100
    assert couple["horizon_age"] > single["horizon_age"]
    assert couple["chance_alive_at_horizon"] <= 0.25


def test_survival_decreases():
    s = lifetable.survival(60)
    assert s[0] == 1.0 and all(a >= b for a, b in zip(s, s[1:]))


def test_simulate_fast_seeded_and_sensible():
    args = dict(age=45, retire_age=65, horizon_age=95, savings=500000, save_per_year=20000, spend_per_year=70000,
                ss_per_year=30000, ss_age=67, tax_rate=0.12, basics_per_year=40000)
    t = time.time()
    a = simulate.simulate(**args)
    assert time.time() - t < 1.0
    assert a == simulate.simulate(**args)  # same seed, same answer
    assert a["paths"] == 2000
    richer = simulate.simulate(**{**args, "savings": 1500000})
    assert richer["chance_goal_lasts"] >= a["chance_goal_lasts"]
    assert richer["safe_spending_per_year"] > a["safe_spending_per_year"]
    assert a["basics_paid_of_100"] >= a["goal_lasts_of_100"]
    assert len(a["chart"]["ages"]) == len(a["chart"]["median"]) == len(a["chart"]["low"]) == len(a["chart"]["high"])


def test_annuity_income_helps_basics():
    args = dict(age=65, retire_age=65, horizon_age=97, savings=600000, save_per_year=0, spend_per_year=60000,
                ss_per_year=25000, ss_age=67, tax_rate=0.1, basics_per_year=45000)
    plain = simulate.simulate(**args, chart=False)
    ann = simulate.simulate(**args, annuities=[{"share": 0.3, "payout_rate": 0.08, "buy_age": 65, "start_age": 65}], chart=False)
    assert ann["basics_paid_of_100"] >= plain["basics_paid_of_100"]


def test_rule_of_thumb_stock_share():
    assert simulate.stock_share("balanced", 45) == 0.65
    assert simulate.stock_share("careful", 30) == 0.5
    assert simulate.stock_share("growth", 100) == 0.2


def test_family_costs():
    r = family_costs.family_path(45, [{"age": 5, "college": True}, {"age": 12, "college": False}], [{"kind": "dog", "count": 2}])
    assert r["this_year"] > 0 and r["college_total"] > 0
    assert r["ends_at_age"] == 45 + (18 + 4 - 1 - 5)   # the younger child's last college year
    assert any("dogs" in m for m in r["moments"])
    b = family_costs.basics_per_year("CT", 2, 65, {"owns": True})
    assert 20000 < b["basics_per_year"] < 100000


def test_tax():
    assert tax.federal_tax(30000, "married_joint") < 1000
    w = tax.working_years(150000, 0, "FL", True)
    assert w["state_tax"] == 0 and 0.1 < w["effective_rate_working"] < 0.3
    r = tax.retirement_years(80000, 30000, {"pretax": 500000, "roth": 0, "taxable": 0, "cash": 0}, "CT", True, 2)
    assert 0 < r["effective_rate_on_withdrawals"] < 0.3
    assert r["withdrawal_order"] == ["taxable", "pre-tax", "Roth"]


def test_estimates():
    e = estimates.pay_estimate("doctor", "CT")
    assert e and e["pay_per_year"] > 150000
    ss, early, late = (estimates.social_security(60000, a) for a in (67, 62, 70))
    assert early["per_year"] < ss["per_year"] < late["per_year"]
    assert abs(estimates.claim_factor(62) - 0.70) < 0.001 and abs(estimates.claim_factor(70) - 1.24) < 0.001


def test_sources_search():
    hits = sources.search("401(k) contribution limit 2027")
    assert hits and "25,500" in " ".join(h["text"] for h in hits)
    assert all(h["url"].startswith("https://") for h in hits)
    assert sources.search("best pizza in town") == []


# ------------------------------------------------------------------ neighbours
def _person(**kw):
    p = {"age": 45, "partner_age": 43, "has_partner": True, "retire_age": 65, "pay_per_year": 150000, "partner_pay_per_year": 0,
         "savings": {"pretax": 400000, "roth": 50000, "taxable": 100000, "cash": 20000}, "home": {"owns": True, "mortgage_balance": 200000},
         "social_security_per_year": 50000, "spending_per_year": 90000, "children": [{"age": 8}], "risk": "balanced", "state": "CT"}
    p.update(kw)
    return p


def _sim(person):
    return {"age": person["age"], "retire_age": person["retire_age"], "horizon_age": 95, "savings": 570000, "save_per_year": 15000,
            "spend_per_year": person["spending_per_year"], "ss_per_year": person["social_security_per_year"], "ss_age": 67,
            "extra_by_year": [], "tax_rate": 0.12, "risk": "balanced", "basics_per_year": 45000}


def test_nearest_neighbour_finds_itself():
    row = neighbors.library()["rows"][10]
    hits = neighbors.nearest(row["features"], k=5)
    assert hits[0][0]["id"] == row["id"] and hits[0][1] < 1e-6
    assert [d for _, d in hits] == sorted(d for _, d in hits)


def test_nearest_prefers_similar_age():
    young = neighbors.nearest(neighbors.features_of(_person(age=30, partner_age=30, retire_age=65)), k=5)
    old = neighbors.nearest(neighbors.features_of(_person(age=70, partner_age=68, retire_age=70, pay_per_year=0)), k=5)
    assert sum(nb["features"]["age"] for nb, _ in young) / 5 < sum(nb["features"]["age"] for nb, _ in old) / 5


def test_pick_basics_first():
    cands = [{"source": "a", "basics_paid_of_100": 80, "safe_spending_per_year": 150000},
             {"source": "b", "basics_paid_of_100": 99, "safe_spending_per_year": 90000},
             {"source": "c", "basics_paid_of_100": 98, "safe_spending_per_year": 95000},
             {"source": "rule", "basics_paid_of_100": 90, "safe_spending_per_year": 120000}]
    assert neighbors.pick(cands)["source"] == "c"   # within 1 point of the best basics, then the most to spend


def test_strategies_scored_whole_and_basics_first():
    p = _person()
    r = neighbors.test_strategies(p, _sim(p))
    srcs = [c["source"] for c in r["candidates_tested"]]
    assert "rule" in srcs and sum(not s.startswith("rule") for s in srcs) == 5 and any(s.startswith("rule-claim-") for s in srcs)   # 5 neighbours, the rule, and the fixed grid
    best = max(c["basics_paid_of_100"] for c in r["candidates_tested"])
    assert r["chosen"]["basics_paid_of_100"] >= best - neighbors.BASICS_GUARD
    assert "simple plans" in r["note"]   # plain words, no "rule of thumb" (round 1 UI audit)


def test_low_confidence_when_basics_unsafe():
    p = _person(spending_per_year=400000, pay_per_year=40000)
    sim = {**_sim(p), "savings": 10000, "save_per_year": 0, "ss_per_year": 10000, "basics_per_year": 200000}
    r = neighbors.test_strategies(p, sim)
    assert r["low_confidence"] and neighbors.LOW_NOTE in r["note"]


def test_low_confidence_when_unlike_library():
    p = _person(age=99, partner_age=20, retire_age=99, pay_per_year=5e7, spending_per_year=3e6,
                savings={"pretax": 9e8, "roth": 9e8, "taxable": 9e8, "cash": 9e8}, children=[{"age": 1}] * 9)
    r = neighbors.test_strategies(p, {**_sim(p), "age": 99, "retire_age": 99, "horizon_age": 105})
    assert r["mean_distance"] > r["distance_p95"] and r["low_confidence"]


def test_low_confidence_when_products_matter_and_none_held():
    p = _person()
    r = neighbors.test_strategies(p, _sim(p), products_matter=True, wanted_kind="a_product_nobody_has")
    assert "no similar household holds that product" in r["low_confidence_reasons"]


# ------------------------------------------------------------------ derived figures the text may quote
def test_derived_figures_and_numbers_you_may_use(doctor_profile):
    import asyncio

    from app import pipeline, safety
    from app.agents.base import figure_lines, fmt_figure
    plan, ctx = asyncio.run(pipeline.tools_only_plan(pipeline.prepare(doctor_profile)))
    m = ctx.findings["markets"]["numbers"]
    assert m["gap_per_year"] == max(0, m["spending_goal_per_year"] - m["safe_spending_per_year"])
    assert m["goal_runs_out_of_100"] == 100 - m["goal_lasts_of_100"]
    assert m["safe_spending_per_month"] == round(m["safe_spending_per_year"] / 12) and m["scenarios"] == 2000
    t = ctx.findings["tax"]["numbers"]
    assert t["total_tax_working"] == t["federal_tax"] + t["state_tax"] + t["payroll_tax"]
    lon = ctx.findings["longevity"]["numbers"]
    assert lon["years_to_plan"] == lon["horizon_age"] - lon["age_now"]
    assert ctx.findings["family"]["numbers"]["basics_per_month"] == round(ctx.findings["family"]["numbers"]["basics_per_year"] / 12)
    # the derived figures are legitimate: text that quotes them passes the check
    allowed = safety.allowed_numbers(m, t)
    text = (f"Your goal is ${m['gap_per_year']:,.0f} a year above safe spending, about ${m['safe_spending_per_month']:,.0f} a month. "
            f"Tax takes ${t['total_tax_working']:,.0f} of pay. It fails in {m['goal_runs_out_of_100']} of 100 scenarios.")
    assert safety.number_check(text, allowed).ok
    # formats people read
    assert fmt_figure("safe_spending_per_year", 286000) == "$286,000"
    assert fmt_figure("goal_lasts_of_100", 96) == "96 of 100"
    assert fmt_figure("horizon_age", 95) == "age 95" and fmt_figure("years_to_plan", 29) == "29 years"
    assert fmt_figure("effective_rate_working", 0.223) == "22%"
    assert "- spending goal per year: $%s" % f"{m['spending_goal_per_year']:,.0f}" in figure_lines(m)
