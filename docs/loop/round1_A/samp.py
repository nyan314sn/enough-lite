import json,glob,os
c=0
for f in sorted(glob.glob('eval_runs/S*.json')):
    d=json.load(open(f,encoding='utf-8'))
    if d.get('status')!='ok': continue
    plan=[e for e in d['events'] if e.get('type')=='plan'][0]['plan']
    paid=plan['needs']['paid_of_100']
    if paid is not None and paid<90 and c<12:
        c+=1; print(os.path.basename(f)[:-5],paid,'|',plan['needs']['line'],'||',plan['wants']['line'][:110])
