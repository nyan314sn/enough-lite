import json, statistics, collections, glob, os, re
from pathlib import Path
HERE = Path(__file__).parent
bm = json.load(open(HERE/"evalcopy"/"benchmark_results.json", encoding="utf-8")); rows = {r["id"]: r for r in bm["rows"]}
cases = {json.loads(l)["id"]: json.loads(l) for l in open(HERE/"evalcopy"/"cases.jsonl", encoding="utf-8")}
T = HERE/"tools_runs"; R2 = HERE.parent/"round2_A"/"eval_runs"
def t(i):
    f = T/(i+".json")
    if not f.exists(): return None
    d = json.load(open(f)); return None if "error" in d else d
def r2(i):
    f = R2/(i+".json")
    if not f.exists(): return None
    d = json.load(open(f, encoding="utf-8")); pl = [e for e in d["events"] if e.get("type")=="plan"]
    if not pl: return None
    p = pl[0]["plan"]; return dict(wants=p["wants"]["per_year"], verdict=p["verdict"], paid=p["needs"]["paid_of_100"])
errs = [i for i in cases if os.path.exists(T/(i+".json")) and t(i) is None]
print("errors", len(errs), errs[:5])
def stats(ids, get, label):
    g=[]; ag=0
    for i in ids:
        x = get(i)
        if x is None or i not in rows: continue
        opt = rows[i]["opt"]
        if not opt.get("wants"): continue
        g.append((x["wants"]-opt["wants"])/opt["wants"]*100); ag += (x["verdict"]=="works")==bool(opt.get("feasible"))
    n=len(g)
    print(f"{label:30s} n={n} median {statistics.median(g):+.1f}% medabs {statistics.median(abs(v) for v in g):.1f}% within25 {100*sum(abs(v)<=25 for v in g)/n:.0f}% agree {100*ag/n:.0f}%")
base = [i for i in cases if cases[i]["kind"]=="base" and t(i)]
cp = lambda i: cases[i]["profile"].get("has_partner") or cases[i]["profile"].get("partner_age")
for lab,f in (("all",lambda i:True),("couples",cp),("singles",lambda i:not cp(i))):
    ids=[i for i in base if f(i)]
    stats(ids,t,"round3 "+lab); stats(ids,r2,"round2 "+lab)
# paired change
for lab,f in (("all",lambda i:True),("couples",cp),("singles",lambda i:not cp(i))):
    d=[]
    for i in base:
        a,b=r2(i),t(i)
        if a and b and f(i) and a["wants"]>0: d.append((b["wants"]-a["wants"])/a["wants"]*100)
    print("paired r3 vs r2", lab, f"median {statistics.median(d):+.1f}% n={len(d)}")
tr=collections.Counter((r2(i)["verdict"],t(i)["verdict"]) for i in base if r2(i))
print(dict(tr))
# verdict rule
bad=0
for i in base:
    x=t(i); goal=x["goal"]
    exp="falls_short" if x["paid"] is not None and x["paid"]<90 else ("works" if x["wants"]>=goal else "close" if x["wants"]>=.9*goal else "below_goal")
    if exp!=x["verdict"]: bad+=1
print("verdict rule mismatches", bad, "of", len(base))
# direction checks
for kind,exp in (("savings_up","not_fall"),("retire_later","not_fall"),("debt_add","fall"),("pension_add","rise"),("match_full","rise"),("legacy_add","fall")):
    n=bad=0
    for i,c in cases.items():
        if c["kind"]!=kind: continue
        a,b=t(c["base_id"]),t(i)
        if not a or not b: continue
        n+=1; w0,w1=a["wants"],b["wants"]
        ok=(w1>=w0*.97) if exp in("not_fall","rise") else (w1<=w0*1.03)
        if not ok: bad+=1; print("   ",kind,c["base_id"],w0,w1)
    print(kind,"n",n,"wrong way",bad)
# consistency non-empty, F21, zeros
print("consistency non-empty:", sum(1 for i in cases if t(i) and t(i)["consistency"]))
nf=0
for i in cases:
    x=t(i)
    if x and x["ss"] and x["wants"]<x["ss"] and "less than your Social Security" not in x["headline"]: nf+=1
print("count-on below SS without explanation:", nf, "of", sum(1 for i in cases if t(i) and t(i)["ss"] and t(i)["wants"]<t(i)["ss"]))
# starting points
n=ms=bad=late=0
for i in cases:
    x=t(i)
    if not x or x["verdict"]!="falls_short": continue
    n+=1; sp=x["sp"] or []
    if any(s["makes_basics_safe"] for s in sp): ms+=1
    for s in sp:
        if s["makes_basics_safe"]!=(s["paid_of_100"]>=90): bad+=1
        m=re.match(r"Retire at (\d+)", s["title"])
        if m and int(m.group(1))>70: late+=1
    if "would make the basics safe" in x["headline"] and not any(s["makes_basics_safe"] for s in sp): print("  headline promise w/o safe", i)
print("falls_short",n,"with a safe starting point",ms,"flag mismatches",bad,"retire>70",late, "no starting points", sum(1 for i in cases if t(i) and t(i)["verdict"]=="falls_short" and not t(i)["sp"]))
