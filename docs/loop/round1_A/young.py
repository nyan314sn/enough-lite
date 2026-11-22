import sys, asyncio, copy
from pathlib import Path
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE.parents[2])); sys.path.insert(0,str(HERE))
from app import pipeline
from app.agents import markets as mk
for age in (20,22,25):
    prof=dict(age=age,state='TX',pay_per_year=45000,retire_age=65,savings={'pretax':0,'roth':0,'taxable':0,'cash':3000},spending_per_year=35000,spending_now_per_year=38000)
    p=pipeline.prepare(prof); plan,ctx=asyncio.run(pipeline.tools_only_plan(p)); inp=mk.sim_inputs(ctx)
    ca=plan['costs_by_age']
    print(age,'horizon',plan['horizon_age'],'n=',plan['horizon_age']-age,'len(extra)',len(inp['extra_by_year']),'timeline ages',ca['ages'][0],ca['ages'][-1],'len',len(ca['ages']),'| count-on',plan['wants']['per_year'],'chart last age',plan['chart']['ages'][-1])
    print('   extra tail',inp['extra_by_year'][-8:])
