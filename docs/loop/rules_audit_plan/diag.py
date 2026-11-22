import asyncio, json, sys
from hh import *
from app import analysis, pipeline
from app.tools import costs

def plan_of(prof):
    p = pipeline.prepare(prof)
    plan, ctx = asyncio.run(pipeline.tools_only_plan(p))
    return p, plan, ctx

prof = example_full()
p, plan, ctx = plan_of(prof)
print("spend now", p.spending_now_per_year, "goal", p.spending_per_year, "count on", plan["wants"]["per_year"], "saving", plan["saving"])
wt = costs.work_tax(p)
print("work tax", {k: v for k, v in wt.items() if not isinstance(v, (list, dict))})
src = plan["analysis"]["sources"]
for a in (45, 50, 53, 57, 61, 62):
    t = a - 45
    print(a, "spend", src["spending"][t], {s["key"]: s["values"][t] for s in src["series"]}, "surplus", src["surplus"][t])
lv = plan["analysis"]["levers"]["rows"]
print("levers", [(x["title"], x["count_on_change"]) for x in lv])
base = plan["wants"]["per_year"]
for ra in range(62, 68):
    r = asyncio.run(pipeline.ask(f"what if I retire at {ra}", prof, "t", use_ai=False))
    tt = {"key": "retire", "title": "", "ch": {"retire_age": ra}}
    tab = analysis.rerun_with(ctx, tt)["safe_spending_per_year"] if ra != 62 else base
    print("retire", ra, "whatif", r.get("plan", {}).get("wants", {}).get("per_year"), "table", tab, "|", r["text"][:120])
for q in ["what if I save $500 more a month", "save 5% more of pay", "what if my wife stops working"]:
    r = asyncio.run(pipeline.ask(q, prof, "t", use_ai=False))
    print(q, "->", r.get("plan", {}).get("wants", {}).get("per_year"), r["text"][:300])
