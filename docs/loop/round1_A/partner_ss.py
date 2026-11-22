"""Does the sim start the partner's Social Security too early when the partner is younger?"""
import sys, json, asyncio, copy, math
from pathlib import Path
import numpy as np
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE.parents[2])); sys.path.insert(0,str(HERE))
import invariants as I, recompute as R
from app import pipeline
from app.agents import markets as mk
async def go(prof):
    p=pipeline.prepare(copy.deepcopy(prof)); plan,ctx=await pipeline.tools_only_plan(p); return p,plan,ctx
def sim_path(inp, ss_path, paths=20000, seed=7):
    age,ra,hor=inp['age'],inp['retire_age'],inp['horizon_age']; n=hor-age
    def pad(xs):
        a=np.zeros(n); k=min(n,len(xs)); a[:k]=xs[:k]; return a
    extra=pad(inp['extra_by_year']); save=pad(inp['save_by_year']); inc=pad(inp['income_by_year'])
    cap={'careful':.5,'balanced':.75,'growth':1.0}[inp['risk']]
    rng=np.random.default_rng(seed); z1=rng.standard_normal((paths,n)); z2=rng.standard_normal((paths,n))
    rs=.05+.17*z1; rb=.018+.06*(.1*z1+math.sqrt(.99)*z2)
    ws=np.array([min(max((110-(age+t))/100,.2),cap) for t in range(n)])
    r=np.maximum(-.95,ws*rs+(1-ws)*rb); tr=inp['tax_rate']
    def ok(spend):
        w=np.full(paths,float(inp['savings'])); alive=np.ones(paths,bool)
        for t in range(n):
            a=age+t
            if a<ra: w=np.maximum(w-extra[t]+inc[t],0)*(1+r[:,t])+save[t]
            else:
                need=spend+extra[t]-inc[t]-ss_path[t]
                w=w-max(0,need)/(1-tr)+max(0,-need); alive&=w>=0; w=np.where(alive,np.maximum(w,0)*(1+r[:,t]),0)
        return alive.mean()
    lo,hi=0,1e6
    for _ in range(25):
        mid=(lo+hi)/2
        if ok(mid)>=.9: lo=mid
        else: hi=mid
    return lo
def pia(pay): return R.pia_monthly(pay)*12
if __name__=="__main__":
  for name in ['h11_partner_longer','h14_near_retire_pension_couple','h05_couple_mortgage']:
    prof=I.get_plans.H[name]; prof=copy.deepcopy(prof); prof['claim_age']=67  # fix both at 67 (rule of thumb)
    p,plan,ctx=asyncio.run(go(prof)); inp=mk.sim_inputs(ctx)
    n=inp['horizon_age']-inp['age']; age=inp['age']; page=p.partner_age
    own=pia(p.pay_per_year); par=pia(p.partner_pay_per_year or 0)
    f=R.ss_factor
    # app: household SS starts when the primary reaches ss_age (partner may be younger)
    app=np.array([ (own*f(67)+par*f(67))*(1-inp['ss_tax_rate']) if age+t>=inp['ss_age'] else 0 for t in range(n)])
    # correct: each person's benefit starts at 67 of their own age
    good=np.array([ ((own*f(67) if age+t>=67 else 0)+(par*f(67) if page+t>=67 else 0))*(1-inp['ss_tax_rate']) for t in range(n)])
    print(name,'age',age,'partner',page,'app_ss',inp['ss_per_year'],'my_total',round(own*f(67)+par*f(67)),'| count-on app-timing',round(sim_path(inp,app)),'correct timing',round(sim_path(inp,good)))
