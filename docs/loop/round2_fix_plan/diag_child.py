"""Audit 2A: does adding a child raise count-on for a single parent? Usage: diag_child.py"""
import asyncio
import copy
import os
import sys
from pathlib import Path

os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["ENOUGH_RUN_LOG"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from app import pipeline  # noqa: E402

N01 = dict(age=36, state="OH", pay_per_year=55000, retire_age=67, savings={"pretax": 15000, "roth": 0, "taxable": 2000, "cash": 4000},
           spending_per_year=38000, spending_now_per_year=44000, children=[{"age": 4}, {"age": 9}], home={"owns": False, "rent": 1300},
           sources={"spending_now_per_year": "you said", "spending_per_year": "you said"})


async def main():
    base = pipeline.prepare(copy.deepcopy(N01))
    plan0, ctx0 = await pipeline.tools_only_plan(base)
    ch = pipeline.parse_whatif("What if we have another child", base)
    newp, notes = pipeline.apply_whatif(base, ch)
    plan1, ctx1 = await pipeline.tools_only_plan(newp)
    for n, pl, c in (("base", plan0, ctx0), ("child", plan1, ctx1)):
        ms = c.results["money"]
        fam = c.results["family"]
        print(n, "count-on", pl["wants"]["per_year"], "save_now", ms["save_now"], "unspent", ms["unspent_pay_per_year"],
              "extra first 5", c.results["family"]["costs"]["extra_by_year"][:5], "spend now", c.profile.spending_now_per_year,
              "fam per_year", fam["per_year"][:3])


asyncio.run(main())
