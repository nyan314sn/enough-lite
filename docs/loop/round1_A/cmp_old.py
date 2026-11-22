import json,glob,os,statistics as st
old='../../../eval/runs'; new='eval_runs'
rows=[]
for f in sorted(glob.glob(new+'/*.json')):
    n=os.path.basename(f); o=os.path.join(old,n)
    if not os.path.exists(o): continue
    a=json.load(open(o,encoding='utf-8')); b=json.load(open(f,encoding='utf-8'))
    try:
        pa=[e for e in a['events'] if e.get('type')=='plan'][0]['plan']; pb=[e for e in b['events'] if e.get('type')=='plan'][0]['plan']
    except Exception: continue
    rows.append((n[:-5],pa['wants']['per_year'],pb['wants']['per_year'],pa['verdict'],pb['verdict'],pa['needs']['paid_of_100'],pb['needs']['paid_of_100'],pa['claim_age'],pb['claim_age']))
print('compared',len(rows))
d=[(r[2]-r[1])/max(r[1],1) for r in rows if r[1]>0]
print('count-on change median %.2f%%, mean %.2f%%'%(100*st.median(d),100*st.mean(d)),'| identical',sum(1 for r in rows if r[1]==r[2]),'| >5% diff',sum(1 for x in d if abs(x)>.05))
print('verdict changed',sum(1 for r in rows if r[3]!=r[4]),'| claim changed',sum(1 for r in rows if r[7]!=r[8]))
big=sorted(rows,key=lambda r:-abs(r[2]-r[1])/max(r[1],1))[:6]
for r in big: print(r)
vc=[r for r in rows if r[3]!=r[4]][:5]
for r in vc: print('verdict change',r)
dec=[r for r in rows if r[1]>0 and (r[2]-r[1])/r[1]<-0.05]
print('decreases >5%:',len(dec)); 
for r in dec[:8]: print(r)
