"""Direct rule checks: 401(k) catch-up 60-63, CO exemption, additional Medicare boundary, earnings test with claim while working."""
import sys, copy, asyncio, json
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE))
import lib2 as L
from app import pipeline
from app.tools import costs, tax
from app.agents import markets as mk

def run(prof):
    p = pipeline.prepare(copy.deepcopy(prof)); plan, ctx = asyncio.run(pipeline.tools_only_plan(p)); return p, plan, ctx
S = lambda a=0,b=0,c=0,d=0: {"pretax":a,"roth":b,"taxable":c,"cash":d}
print("limits", tax.limits_2027())
for age in (49, 50, 59, 60, 63, 64):
    prof = dict(age=age, state="TX", pay_per_year=300000, retire_age=age+5, savings=S(500000,0,100000,30000), spending_per_year=90000, spending_now_per_year=100000, saving={"contrib_you": 40000})
    p, plan, ctx = run(prof)
    c = costs.contributions(p); wt = costs.work_tax(p, c)
    lim = tax.limits_2027()
    exp = lim["401k_limit"] + (11750 if 60<=age<=63 else 7500 if age>=50 else 0)
    mine = L.work_tax(300000, 0, "TX", False, 0, min(40000, exp))
    print(f"catch-up age {age}: contrib {c['you']:,.0f} cap expected {exp:,.0f}; app fed {wt['federal_tax']:,.0f} mine(pretax=min(40000,cap)) {mine['fed']:,.0f}; saving {plan['saving']}")
# CO exemption
for age in (63,64,65,66):
    prof = dict(age=age, state="CO", pay_per_year=0, retire_age=age, savings=S(500000,0,100000,30000), spending_per_year=60000, spending_now_per_year=60000, social_security_per_year=34000, claim_age=min(age,67))
    p, plan, ctx = run(prof); tx = ctx.results["tax"]
    print("CO age", age, "ss tax rate", tx["social_security_tax_rate"], "withdraw rate", round(tx["effective_rate_on_withdrawals"],4), "state_exempts", tax.state_exempts_ss("CO", age))
for st in ("CO","UT","VT","MN","TX"):
    print(st, [tax.state_exempts_ss(st, a) for a in (60,64,65,70)])
# earnings test: claims at 62 while working at 80k until 67
prof = dict(age=64, state="TX", pay_per_year=80000, retire_age=67, savings=S(300000,0,50000,30000), spending_per_year=50000, spending_now_per_year=60000, social_security_per_year=20000, claim_age=62)
p, plan, ctx = run(prof); inp = mk.sim_inputs(ctx)
print("EARNINGS TEST case: ss_work_by_year", inp["ss_work_by_year"][:5], "save_by_year", inp["save_by_year"][:4], "claim", plan["claim_age"], "already", plan["already_claiming"])
