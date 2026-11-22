import json,glob,os,collections
C=collections.Counter(); ex=[]
for f in sorted(glob.glob('eval_runs/*.json')):
    d=json.load(open(f,encoding='utf-8')); plan=[e for e in d['events'] if e.get('type')=='plan'][0]['plan']
    titles=[a['title'] for a in plan['actions']]
    if any(t in('Check your plan once a year','Draw on taxable savings first') for t in titles):
        keys=[l['key'] for l in plan['levers']]
        txt=' '.join(a['title'].lower() for a in plan['actions'])
        missing=[k for k in keys if {'goal':'goal','debt':'debt','match':'match','emergency':'emergency','life':'life','disability':'disab','ltc':'care'}.get(k,k) not in txt]
        if missing:
            C['filler_while_lever_dropped']+=1
            for m in missing: C['dropped_'+m]+=1
            if len(ex)<4: ex.append((os.path.basename(f)[:-5],missing,titles))
print(C); print(ex)
