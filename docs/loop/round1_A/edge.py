import sys, json, asyncio, copy
from pathlib import Path
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE.parents[2])); sys.path.insert(0,str(HERE))
import invariants as I, recompute as R
from app import pipeline
from app.agents import markets as mk
def S(a,b,c,d): return {"pretax":a,"roth":b,"taxable":c,"cash":d}
cases={
 'fire_35_to_45': dict(age=35,state='TX',pay_per_year=150000,retire_age=45,savings=S(300000,50000,200000,50000),spending_per_year=60000,spending_now_per_year=70000),
 'fire_partner_gap25': dict(age=62,has_partner=True,partner_age=37,state='TX',pay_per_year=0,partner_pay_per_year=0,retire_age=62,savings=S(900000,0,100000,50000),spending_per_year=70000,spending_now_per_year=70000),
 'partner_older_claiming': dict(age=60,has_partner=True,partner_age=70,state='FL',pay_per_year=0,retire_age=60,savings=S(500000,0,100000,30000),spending_per_year=60000,spending_now_per_year=60000,social_security_per_year=30000,claim_age=62),
 'single_parent_hoh': dict(age=34,state='CA',pay_per_year=60000,retire_age=65,savings=S(10000,0,0,3000),spending_per_year=40000,spending_now_per_year=45000,children=[{'age':5},{'age':8}]),
}
for name,prof in cases.items():
    p=pipeline.prepare(copy.deepcopy(prof)); plan,ctx=asyncio.run(pipeline.tools_only_plan(p)); inp=mk.sim_inputs(ctx)
    pay=p.pay_per_year or 0; mine=R.pia_monthly(pay if pay else 50980)*12*R.ss_factor(inp['ss_age'])
    print(name,'verdict',plan['verdict'],'count',plan['wants']['per_year'],'basics',plan['needs']['basics_per_year'],'SS app',inp['ss_per_year'],'ss_age',inp['ss_age'],'claim shown',plan['claim_age'],plan['partner_claim_age'],'already',plan['already_claiming'],'| pay-based single-person SS mine',round(mine))
    t=ctx.results['tax']
    print('   tax', {k:t[k] for k in t if k in('federal_tax','state_tax','after_tax_pay','tax_per_year_retired','effective_rate_on_withdrawals')}, 'h', ctx.results['longevity']['horizon_age'], 'wd',[ (a['title']) for a in plan['actions']])
