import asyncio
from hh import *
from app import analysis, pipeline
from app.agents import adviser
from app.agents.base import RunCtx
from app.agents.family import Family
from app.agents.longevity import Longevity
from app.agents.tax import Tax
from app.agents.markets import sim_inputs
from app.tools import neighbors
prof = example()
p = pipeline.prepare(prof)
print("children", [(c.age, c.college) for c in p.children])
plan, ctx = asyncio.run(pipeline.tools_only_plan(p))
strat = ctx.kept["strategy"]
print("strat", strat["name"], strat["claim_age"], strat["annuities"], [round(x,2) for x in strat["stock_path"][:25]])
for ra in (62, 63, 64, 65):
    newp = adviser._apply_try(p, {"ch": {"retire_age": ra}})
    c2 = RunCtx(profile=newp, use_ai=False, options=False)
    for sp in (Longevity(), Family(), Tax()):
        c2.results[sp.name] = sp.compute(c2)
    s = sim_inputs(c2)
    r = neighbors.score(newp.model_dump(), s, strat)
    print(ra, "safe", r["safe_spending_per_year"], "ss", r["social_security_per_year"], "claim", r["claim_age"], "ssp", newp.social_security_per_year,
          "save", s["save_by_year"][:2], "extra", s["extra_by_year"][15:22], "h", s["horizon_age"], "tax", round(s["tax_rate"],3), "sstax", s["ss_tax_rate"],
          "basics", s["basics_per_year"], "drop", s["spend_drop_t"], "ss_by", [round(x) for x in s["ss_by_year"][18:30:3]])
