import asyncio
from hh import *
from app.tools import costs
for k in ("S264", "S153"):
    p = pipeline.prepare(eval_cases([k])[k])
    m = costs.mortgage_end(p)
    plan, ctx = asyncio.run(pipeline.tools_only_plan(p))
    print(k, "age", p.age, "ra", p.retire_age, "mort", m, "goal", p.spending_per_year, "now", p.spending_now_per_year, "count", plan["count_on_per_year"], plan["headline"][:200])
