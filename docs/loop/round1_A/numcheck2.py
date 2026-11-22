import json,glob,os,sys,re
sys.path.insert(0,'.')
import numcheck
tot=0;n=0
for f in sorted(glob.glob('eval_runs/*.json')):
    d=json.load(open(f,encoding='utf-8'))
    if d.get('status')!='ok': continue
    n+=1
    plan=[e for e in d['events'] if e.get('type')=='plan'][0]['plan']
    lever_txt=' '.join(l['why'] for l in plan['levers'])
    bad=numcheck.check(d)
    bad=[b for b in bad if b[1].strip(' ,') not in lever_txt]
    if bad:
        tot+=1
        txts=[t for k,t in numcheck.texts(plan)]
        ctx=[ (b[1],[t[max(0,t.find(b[1].strip(' ,'))-70):t.find(b[1].strip(' ,'))+40] for t in txts if b[1].strip(' ,') in t][:1]) for b in bad]
        print(os.path.basename(f)[:-5],ctx)
print('runs',n,'with AI-text $ figures not in tool outputs/lever text:',tot)
