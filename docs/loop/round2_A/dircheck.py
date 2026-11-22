import json,glob,os
def wants(i):
    x=json.load(open(f"eval_runs/{i}.json",encoding="utf-8")); return [e for e in x["events"] if e.get("type")=="plan"][0]["plan"]["wants"]["per_year"]
for kind,exp in (("savings_up","not_fall"),("retire_later","not_fall"),("debt_add","fall"),("pension_add","rise"),("match_full","rise"),("legacy_add","fall")):
    n=bad=0; badl=[]
    for f in sorted(glob.glob(f"eval_runs/*__{kind}.json")):
        i=os.path.basename(f)[:-5]; b=i.split("__")[0]
        if not os.path.exists(f"eval_runs/{b}.json"): continue
        w0,w1=wants(b),wants(i); n+=1
        ok = (w1>=w0*0.97) if exp=="not_fall" else (w1<=w0*1.03) if exp=="fall" else (w1>=w0*0.97)
        if not ok: bad+=1; badl.append((b,w0,w1))
    print(kind,exp,"n",n,"wrong way (>3%)",bad,badl[:4])
