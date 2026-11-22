import json,sys
sys.path.insert(0,'.')
import recompute as R
LC=json.load(open(R.DATA/'life_costs.json',encoding='utf-8'))
prof,plan,fin=R.load('plans/h13_kids_pets.json')
ca=plan['costs_by_age']; ages=ca['ages']; tot=ca['total']
print({k:LC['child_rearing'][k]['typical'] for k in LC['child_rearing']}, LC['child'], LC['college']['in_state']['typical'], LC['pets']['dog']['annual']['typical'], LC['pets']['dog']['lifespan']['typical'],LC['pets']['cat']['annual']['typical'],LC['pets']['cat']['lifespan']['typical'])
kids=[10,7,3]; n=3
def band_cost(a):
    for k,v in LC['child_rearing'].items():
        lo,hi=map(int,k.split('-'))
        if lo<=a<=hi: return v['typical']*(0.76 if n>=3 else 1)
    return 0
dog=LC['pets']['dog']['annual']['typical']*2; cat=LC['pets']['cat']['annual']['typical']
pet_years_dog=round(LC['pets']['dog']['lifespan']['typical']/2); pet_years_cat=round(LC['pets']['cat']['lifespan']['typical']/2)
col=LC['college']['in_state']['typical']
def hp(t):
    x=sum(band_cost(k+t) for k in kids if k+t<LC['child']['independence_age'])
    x+= dog if t<pet_years_dog else 0
    x+= cat if t<pet_years_cat else 0
    return x
def cl(t): return sum(col for k in kids if 18<=k+t<22)
hp0=hp(0); 
# mortgage drop: payment 1800*12 - smoc_free*12 ; years_left? use plan event
ev={e['label']:e for e in ca['events']}
drop=15400
for t in (0,5,8,12,18,22,25):
    core=90000-hp0-cl(0)
    mine=core+hp(t)+cl(t)-(drop if t>=18 else 0)
    print('age',40+t,'app',tot[t],'mine',round(mine),'diff %.1f%%'%(100*(tot[t]-mine)/mine))
