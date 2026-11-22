"""Candidates for an eval run's profile and its variant (tools only). Usage: diag2.py base_id variant_id"""
import sys, json, asyncio, copy
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2]))
from app import pipeline
for rid in sys.argv[1:]:
    prof = json.load(open(HERE / "eval_runs" / f"{rid}.json", encoding="utf-8"))["profile"]
    p = pipeline.prepare(copy.deepcopy(prof))
    plan, ctx = asyncio.run(pipeline.tools_only_plan(p))
    nb = ctx.results["neighbors"]
    print(rid, "count_on", plan["wants"]["per_year"], "paid", plan["needs"]["paid_of_100"], "chosen", nb["chosen"]["source"])
    for c in sorted(nb["candidates_tested"], key=lambda c: -c["safe_spending_per_year"])[:6]:
        print(f"   {c['source']:40s} paid {c['basics_paid_of_100']:>3} safe {c['safe_spending_per_year']:>9,.0f}")
