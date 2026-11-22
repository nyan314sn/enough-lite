"""Show the candidates for a household before and after a perturbation. Usage: diag.py name kind"""
import sys, asyncio, copy
from pathlib import Path
HERE = Path(__file__).parent
A = HERE.parent / "round1_A"
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(A))
import invariants as I
import get_plans
from app import pipeline

base = dict(get_plans.H)
base.update(I.random_profiles(40))
name, kind = sys.argv[1], sys.argv[2]
for prof in (base[name], I.perturb(base[name], kind)):
    p = pipeline.prepare(copy.deepcopy(prof))
    plan, ctx = asyncio.run(pipeline.tools_only_plan(p))
    nb = ctx.results["neighbors"]
    print("count_on", plan["wants"]["per_year"], "basics", plan["needs"]["basics_per_year"], "chosen", nb["chosen"]["source"], "goal", plan["spending_goal"])
    for c in sorted(nb["candidates_tested"], key=lambda c: -c["safe_spending_per_year"]):
        print(f"   {c['source']:40s} paid {c['basics_paid_of_100']:>3} safe {c['safe_spending_per_year']:>9,.0f} claim {c['claim_age']}")
