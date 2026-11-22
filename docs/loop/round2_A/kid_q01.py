import sys, copy, asyncio
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "round1_A"))
import invariants2 as I, hh2
from app import pipeline
from app.agents import markets as mk

for name in ("n15_low_income_parent", "n01_single_parent"):
    base = hh2.N[name]
    for lab, prof in (("base", base), ("kid+1", I.perturb(base, "kid+1(down)"))):
        p = pipeline.prepare(copy.deepcopy(prof))
        plan, ctx = asyncio.run(pipeline.tools_only_plan(p))
        c = ctx.results["family"]["costs"]
        inp = mk.sim_inputs(ctx)
        ms = ctx.results["money"]
        print(name, lab, "count", plan["wants"]["per_year"], "kids", len(p.children), "extra total", round(sum(c["extra_by_year"])), "home_pets", round(sum(c["home_pets"])), "college", round(sum(c["college"])),
              "after-tax", ctx.results["tax"]["after_tax_pay"], "credit", ctx.results["tax"]["child_tax_credit"], "save_now", ms["save_now"], "unspent", ms["unspent_pay_per_year"], "spend_now", p.spending_now_per_year, "spend_ret", p.spending_per_year, "basics", plan["needs"]["basics_per_year"], "chosen", plan["neighbors"]["chosen"]["name"])

q = I.random_profiles(40)["q01"]
print(q)
for lab, prof in (("base", q), ("retire+2", I.perturb(q, "retire+2"))):
    p = pipeline.prepare(copy.deepcopy(prof))
    plan, ctx = asyncio.run(pipeline.tools_only_plan(p))
    print("q01", lab, plan["wants"]["per_year"], plan["neighbors"]["chosen"]["name"], plan["neighbors"]["chosen"]["basics_paid_of_100"], plan["claim_age"], plan["partner_claim_age"], "SS", plan["social_security_per_year"], "hor", plan["horizon_age"])
    for c in plan["neighbors"]["candidates_tested"]:
        print("    ", c["source"], c["safe_spending_per_year"], c["basics_paid_of_100"], c["claim_age"], c["partner_claim_age"])
