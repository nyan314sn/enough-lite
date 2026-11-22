import sys, json, asyncio, copy
from pathlib import Path
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE.parents[2])); sys.path.insert(0,str(HERE))
import invariants as I
from app import pipeline
from app.agents import markets as mk
async def go(prof):
    p=pipeline.prepare(copy.deepcopy(prof)); plan,ctx=await pipeline.tools_only_plan(p); return p,plan,ctx
base=dict(I.get_plans.H); base.update(I.random_profiles(40))
for name in sys.argv[1:]:
    kind=None
    if ':' in name: name,kind=name.split(':')
    prof=base[name]
    if kind: prof=I.perturb(prof,kind)
    p,plan,ctx=asyncio.run(go(prof))
    inp=mk.sim_inputs(ctx); nb=plan['neighbors']
    print(name,kind,'count',plan['wants']['per_year'],'chosen',nb['chosen']['name'],'basics',nb['chosen']['basics_paid_of_100'],'claim',plan['claim_age'])
    print('  ss',inp['ss_per_year'],inp['ss_age'],'sstax',inp['ss_tax_rate'],'wdrate',inp['tax_rate'],'save_now',inp['save_by_year'][0],'spend',inp['spend_per_year'],'basics',inp['basics_per_year'],'ret',inp['retire_age'],'age',inp['age'],'sav',inp['savings'])
    print('  p.spending_now',p.spending_now_per_year,'goal',p.spending_per_year,'pay',p.pay_per_year,p.partner_pay_per_year,'ppart',p.partner_age,p.partner_retire_age, 'ss_src',p.sources.get('social_security_per_year'))
    print('  cands',[(c['source'][:10],c['basics_paid_of_100'],c['safe_spending_per_year'],c['claim_age']) for c in nb['candidates_tested']])
