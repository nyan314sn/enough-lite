import asyncio, sys
from hh import *
from app import analysis
from app.agents import adviser
from app.agents.base import RunCtx
from app.agents.family import Family
from app.agents.longevity import Longevity
from app.agents.tax import Tax
from app.agents.markets import sim_inputs
from app.tools import neighbors
key = sys.argv[1]
prof = eval_cases([key])[key]
p = pipeline.prepare(prof)
plan, ctx = asyncio.run(pipeline.tools_only_plan(p))
strat = ctx.kept["strategy"]
print("strat", strat["name"], strat["claim_age"], strat["annuities"], "saving", plan["saving"], "goal", p.spending_per_year, "basics", plan["needs"])
for ra in range(62, 68):
    newp = adviser._apply_try(p, {"ch": {"retire_age": ra}})
    c2 = RunCtx(profile=newp, use_ai=False, options=False)
    for sp in (Longevity(), Family(), Tax()):
        c2.results[sp.name] = sp.compute(c2)
    s = sim_inputs(c2)
    r = neighbors.score(newp.model_dump(), s, neighbors.adapt(strat, s["age"], ra))
    t = ra - s["age"]
    print(ra, "safe", r["safe_spending_per_year"], "paid", r["basics_paid_of_100"], "ss", r["social_security_per_year"], "claim", r["claim_age"], r.get("partner_claim_age"),
          "save", s["save_by_year"][t-3:t+1], "extra", s["extra_by_year"][t-1:t+4], "basics", s["basics_per_year"], "goal", newp.spending_per_year, "pra", newp.partner_retire_age,
          "med_ret", r["median_at_retirement"])
