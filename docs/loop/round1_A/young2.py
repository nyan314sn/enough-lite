import sys, asyncio, copy
from pathlib import Path
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE.parents[2])); sys.path.insert(0,str(HERE))
from app import pipeline
from app.agents import markets as mk
for age in (18,19,20,21,22,23,24,25,30):
    prof=dict(age=age,state='TX',pay_per_year=45000,retire_age=65,savings={'pretax':0,'roth':0,'taxable':0,'cash':3000},spending_per_year=35000,spending_now_per_year=38000)
    p=pipeline.prepare(prof); plan,ctx=asyncio.run(pipeline.tools_only_plan(p)); inp=mk.sim_inputs(ctx)
    nb=plan['neighbors']
    print(age,'hor',inp['horizon_age'],'count',plan['wants']['per_year'],'chosen',nb['chosen']['name'][:26],'| cands',[(c['source'][:6],c['safe_spending_per_year']) for c in nb['candidates_tested']],'save',inp['save_by_year'][0],'ss',inp['ss_per_year'])
