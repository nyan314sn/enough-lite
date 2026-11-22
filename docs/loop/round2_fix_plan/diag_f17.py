"""Audit F17: the costs timeline for h13 (round 1 audit A). Usage: diag_f17.py"""
import asyncio
import os
import sys
from pathlib import Path

os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["ENOUGH_RUN_LOG"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from app import pipeline  # noqa: E402


def S(a, b, c, d):
    return {"pretax": a, "roth": b, "taxable": c, "cash": d}


H13 = dict(age=40, has_partner=True, partner_age=39, state="NC", pay_per_year=80000, partner_pay_per_year=45000, retire_age=65,
           savings=S(90000, 10000, 20000, 15000), spending_per_year=72000, spending_now_per_year=90000,
           children=[{"age": 10}, {"age": 7}, {"age": 3}], pets=[{"kind": "dog", "count": 2}, {"kind": "cat", "count": 1}],
           home={"owns": True, "value": 380000, "mortgage_balance": 250000, "mortgage_payment": 1800, "mortgage_rate": 0.05})
plan, ctx = asyncio.run(pipeline.tools_only_plan(pipeline.prepare(H13)))
c = plan["costs_by_age"]
for a, t, b in zip(c["ages"], c["total"], c["basics"]):
    if 55 <= a <= 70:
        print(a, t, b)
print([e for e in c["events"]])
