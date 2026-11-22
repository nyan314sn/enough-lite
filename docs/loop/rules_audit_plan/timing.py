import asyncio, time
from hh import *
from app.agents.markets import sim_inputs
from app.tools import neighbors
for key in ("S054", "S233", "S264"):
    prof = eval_cases([key])[key]
    p = pipeline.prepare(prof)
    t0 = time.time(); plan, ctx = asyncio.run(pipeline.tools_only_plan(p)); t1 = time.time()
    sim = ctx.kept["sim"]
    t2 = time.time(); res = neighbors.test_strategies(ctx.kept["person"], sim); t3 = time.time()
    print(key, plan["verdict"], "plan s", round(t1 - t0, 1), "test_strategies s", round(t3 - t2, 2), "n", len(res["candidates_tested"]),
          "analysis s", (plan.get("analysis") or {}).get("seconds"), "sp", [(x["title"], x["paid_of_100"]) for x in plan["starting_points"]])
