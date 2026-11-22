import sys, copy, asyncio
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE))
import invariants2 as I, hh2
from app import pipeline
from app.agents import markets as mk
def go(prof):
    p = pipeline.prepare(copy.deepcopy(prof)); plan, ctx = asyncio.run(pipeline.tools_only_plan(p)); return p, plan, ctx
r = I.random_profiles(40, seed=21)["q36"]; print("q36", r)
for lab, pr in (("base", r), ("retire+2", I.perturb(r, "retire+2"))):
    p, plan, ctx = go(pr); inp = mk.sim_inputs(ctx)
    print(lab, "count", plan["wants"]["per_year"], "claims", plan["claim_age"], plan["partner_claim_age"], "horizon", inp["horizon_age"], "death_t", inp["ss_first_death_t"], "ss_work", inp["ss_work_by_year"][:8], "ss", inp["ss_by_year"][:12:3], "save", inp["save_by_year"][:10:3], "income", inp["income_by_year"][:10:3], "ret", inp["retire_age"], [c["source"]+":"+str(c["safe_spending_per_year"]) for c in plan["neighbors"]["candidates_tested"] if c["source"].startswith("rule")][:12], plan["neighbors"]["chosen"]["source"] if plan["neighbors"].get("chosen") else None)
