import sys, asyncio, copy
from pathlib import Path
import numpy as np
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE.parents[2])); sys.path.insert(0,str(HERE))
import partner_ss as P, recompute as R
from app.agents import markets as mk
prof=dict(age=62,has_partner=True,partner_age=37,state='TX',pay_per_year=0,partner_pay_per_year=0,retire_age=62,savings={'pretax':900000,'roth':0,'taxable':100000,'cash':50000},spending_per_year=70000,spending_now_per_year=70000,claim_age=67)
p,plan,ctx=asyncio.run(P.go(prof)); inp=mk.sim_inputs(ctx)
n=inp['horizon_age']-inp['age']; age=inp['age']; page=p.partner_age
own=R.pia_monthly(50980)*12*R.ss_factor(67); sp=R.pia_monthly(50980)*12*.5
net=1-inp['ss_tax_rate']
app=np.array([inp['ss_per_year']*net if age+t>=67 else 0 for t in range(n)])
good=np.array([(own if age+t>=67 else 0)*net+(sp if (age+t>=67 and page+t>=62) else 0)*net for t in range(n)])
print('SS app',inp['ss_per_year'],'horizon',inp['horizon_age'],'count-on app timing',round(P.sim_path(inp,app)),'spousal only once partner is 62:',round(P.sim_path(inp,good)))
