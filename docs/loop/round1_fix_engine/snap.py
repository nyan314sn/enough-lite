"""Snapshot key figures for the audit households (tools only, no AI). Usage: snap.py out.json"""
import sys, json, asyncio, copy
from pathlib import Path
HERE = Path(__file__).parent
A = HERE.parent / "round1_A"
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(A))
import get_plans
from app import pipeline

def S(a,b,c,d): return {"pretax":a,"roth":b,"taxable":c,"cash":d}
H = dict(get_plans.H)
H["gap25"] = dict(age=62,has_partner=True,partner_age=37,state='TX',pay_per_year=0,partner_pay_per_year=0,retire_age=62,savings=S(900000,0,100000,50000),spending_per_year=70000,spending_now_per_year=70000,claim_age=67)
H["gap25_noclaim"] = dict(age=62,has_partner=True,partner_age=37,state='TX',pay_per_year=0,partner_pay_per_year=0,retire_age=62,savings=S(900000,0,100000,50000),spending_per_year=70000,spending_now_per_year=70000)
H["fire_35_45"] = dict(age=35,state="TX",pay_per_year=150000,retire_age=45,savings=S(300000,50000,200000,50000),spending_per_year=60000,spending_now_per_year=70000)
H["single_parent"] = dict(age=34,state='CA',pay_per_year=60000,retire_age=65,savings=S(10000,0,0,3000),spending_per_year=40000,spending_now_per_year=45000,children=[{'age':5},{'age':8}])
out = {}
for name, prof in H.items():
    if prof is None: continue
    p = pipeline.prepare(copy.deepcopy(prof))
    plan, ctx = asyncio.run(pipeline.tools_only_plan(p))
    t = ctx.results["tax"]; m = ctx.results["markets"]
    out[name] = {"count_on": plan["wants"]["per_year"], "verdict": plan["verdict"], "basics_paid": plan["needs"]["paid_of_100"],
                 "claim": plan["claim_age"], "pclaim": plan["partner_claim_age"], "already": plan["already_claiming"],
                 "horizon": plan["horizon_age"], "ss": m.get("social_security_per_year"), "fed_tax": t["federal_tax"],
                 "after_tax": t["after_tax_pay"], "save_now": ctx.results["money"]["save_now"], "strategy": m.get("strategy"),
                 "actions": [a["title"] for a in plan["actions"]], "headline": plan["headline"]}
    print(name, json.dumps(out[name]))
json.dump(out, open(HERE / sys.argv[1], "w"), indent=1)
