import sys, copy, asyncio
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE))
import lib2 as L
from app import pipeline
from app.agents import markets as mk

prof = dict(age=55, has_partner=True, partner_age=70, state="TX", pay_per_year=100000, partner_pay_per_year=60000, retire_age=65, partner_retire_age=66,
            savings={"pretax": 600000, "roth": 0, "taxable": 100000, "cash": 40000}, spending_per_year=90000, spending_now_per_year=100000)
p = pipeline.prepare(copy.deepcopy(prof))
plan, ctx = asyncio.run(pipeline.tools_only_plan(p))
inp = mk.sim_inputs(ctx)
print("count-on", plan["wants"]["per_year"], "claims", plan["claim_age"], plan["partner_claim_age"], "already partner", plan["partner_already_claiming"])
print("ss_by_year first 12 years (you 55..):", inp["ss_by_year"][:12], "retire at", inp["retire_age"])
# my sim: credit the benefit while still working (as a person who claims would receive it)
import numpy as np
n = inp["horizon_age"] - inp["age"]
base_safe, _ = L.sim(inp, inp["ss_by_year"], ss_tax_rate=inp["ss_tax_rate"], paths=12000)
# variant: add partner's benefit received during working years into save_by_year
inp2 = dict(inp); sv = list(inp["save_by_year"])
t_ret = inp["retire_age"] - inp["age"]
for t in range(t_ret):
    sv[t] = sv[t] + inp["ss_by_year"][t] * (1 - inp["ss_tax_rate"])
inp2["save_by_year"] = sv
safe2, _ = L.sim(inp2, inp["ss_by_year"], ss_tax_rate=inp["ss_tax_rate"], paths=12000)
print("my sim as the app does", round(base_safe), "| crediting benefits received while you still work", round(safe2), f"({(safe2-base_safe)/base_safe:+.1%})")
