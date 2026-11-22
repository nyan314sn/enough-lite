import sys, copy, asyncio, json
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE))
import numpy as np
import lib2 as L
from app import pipeline
from app.agents import markets as mk
prof = dict(age=55, has_partner=True, partner_age=70, state="TX", pay_per_year=100000, partner_pay_per_year=60000, retire_age=65, partner_retire_age=66,
            savings={"pretax": 600000, "roth": 0, "taxable": 100000, "cash": 40000}, spending_per_year=90000, spending_now_per_year=100000)
p = pipeline.prepare(copy.deepcopy(prof))
plan, ctx = asyncio.run(pipeline.tools_only_plan(p))
inp = mk.sim_inputs(ctx)
print("count-on", plan["wants"]["per_year"], "safe?", plan["claim_age"], plan["partner_claim_age"], "horizon", inp["horizon_age"], "death_t", inp["ss_first_death_t"])
print("ss_by_year", inp["ss_by_year"][:3], inp["ss_by_year"][-3:], "work", inp["ss_work_by_year"][:12])
print("save_by_year", inp["save_by_year"][:12], "income", inp["income_by_year"][:12], "spend", inp["spend_per_year"], "tax", inp["tax_rate"], inp["ss_tax_rate"])
print([ (c["source"], c["safe_spending_per_year"]) for c in plan["neighbors"]["candidates_tested"]][:20])
print("chosen", plan["neighbors"].get("chosen") or {k:v for k,v in plan["neighbors"].items() if k!="candidates_tested"})
n = inp["horizon_age"]-inp["age"]; t_ret=inp["retire_age"]-inp["age"]
for label, spd in (("none",None),("75%",.75)):
    inp2=dict(inp); sv=list(inp["save_by_year"])
    for t in range(t_ret): sv[t]+=inp["ss_work_by_year"][t]*(1-inp["ss_tax_rate"])
    inp2["save_by_year"]=sv
    s,_=L.sim(inp2, inp["ss_by_year"], ss_tax_rate=inp["ss_tax_rate"], paths=12000, survivor_spend=spd, death=inp["ss_first_death_t"])
    print("my sim, SS in working years, survivor", label, round(s))
# no ss in working years 
s,_=L.sim(inp, inp["ss_by_year"], ss_tax_rate=inp["ss_tax_rate"], paths=12000, survivor_spend=.75, death=inp["ss_first_death_t"]); print("my sim, no working SS, 75%", round(s))
