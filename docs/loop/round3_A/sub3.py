import json, statistics
from pathlib import Path
HERE = Path(__file__).parent
bm = json.load(open(HERE/"evalcopy"/"benchmark_results.json", encoding="utf-8")); rows = {r["id"]: r for r in bm["rows"]}
cases = {json.loads(l)["id"]: json.loads(l) for l in open(HERE/"evalcopy"/"cases.jsonl", encoding="utf-8")}
def t(i):
    f=HERE/"tools_runs"/(i+".json"); return json.load(open(f)) if f.exists() else None
g={}
for i,c in cases.items():
    if c["kind"]!="base" or not t(i) or i not in rows or not rows[i]["opt"].get("wants"): continue
    p=c["profile"]; couple=bool(p.get("has_partner") or p.get("partner_age"))
    if not couple: continue
    gap=(t(i)["wants"]-rows[i]["opt"]["wants"])/rows[i]["opt"]["wants"]*100
    ret = p.get("retire_age",0)<=p.get("age",0)
    gapage = abs((p.get("partner_age") or p["age"])-p["age"])
    for k in (("retired" if ret else "working"), ("agegap>=6" if gapage>=6 else "agegap<6"), ("pay>0 partner" if p.get("partner_pay_per_year") else "partner nopay"), ("claim stated" if p.get("claim_age") is not None else "claim default")):
        g.setdefault(k,[]).append(gap)
for k,v in sorted(g.items()): print(f"{k:16s} n={len(v):3d} median {statistics.median(v):+6.1f}%  p25 {sorted(v)[len(v)//4]:+6.1f} p75 {sorted(v)[3*len(v)//4]:+6.1f}")
