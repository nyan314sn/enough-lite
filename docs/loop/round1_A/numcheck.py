import json,re,sys,glob,os
MONEY=re.compile(r'\$\s?(\d[\d,]*(?:\.\d+)?)\s?(k|thousand|million|m)?\b',re.I)
def nums(obj,out):
    if isinstance(obj,bool) or obj is None: return
    if isinstance(obj,(int,float)): out.add(float(obj)); return
    if isinstance(obj,dict):
        for k,v in obj.items(): nums(v,out)
    elif isinstance(obj,list):
        for v in obj: nums(v,out)
def texts(plan):
    t=[('headline',plan['headline']),('needs',plan['needs']['line']),('wants',plan['wants']['line']),('wishes',plan['wishes']['line'])]
    for a in plan['actions']: t.append(('action',a['title']+' '+a['why']))
    return t
def check(run):
    ev=run['events']; plan=[e for e in ev if e.get('type')=='plan'][0]['plan']
    allowed=set()
    for e in ev:
        if e.get('type')=='agent_done': nums(e['finding'].get('numbers'),allowed)
        if e.get('type')=='tool': nums(e,allowed)
    nums(run['profile'],allowed)
    nums({k:v for k,v in plan.items() if k not in('actions','headline')},allowed)
    for e in ev:
        if e.get('type')=='tool':
            for m in MONEY.finditer(e.get('summary','')): allowed.add(float(m.group(1).replace(',','')))
    bad=[]
    for kind,t in texts(plan):
        for m in MONEY.finditer(t):
            v=float(m.group(1).replace(',','')); mult={'k':1e3,'thousand':1e3,'million':1e6,'m':1e6}.get((m.group(2) or '').lower(),1)
            v*=mult
            ok=any(abs(v-a)<=max(1.0,0.0005*abs(a)) for a in allowed) or any(abs(v-a/12)<=1.5 for a in allowed) or any(abs(v-a*12)<=12 for a in allowed)
            if not ok: bad.append((kind,m.group(0),t[:0]))
    return bad
if __name__=='__main__':
    tot=0
    for f in sorted(glob.glob(sys.argv[1])):
        d=json.load(open(f,encoding='utf-8'))
        if 'events' not in d: continue
        try: bad=check(d)
        except Exception as e: print(f,'ERR',e); continue
        if bad: tot+=1; print(os.path.basename(f),bad)
    print('runs with unmatched $ figures:',tot)
