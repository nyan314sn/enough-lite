import json,glob,collections,sys
sys.path.insert(0,"..")
import judge as J
ps={p["id"]:p for f in ("personas","personas_hard","personas_hs") for p in json.load(open(f"../{f}.json",encoding="utf-8"))}
c=collections.Counter(); 
for d in ("runs_early","runs"):
  c=collections.Counter()
  for f in glob.glob(d+"/*.json"):
    r=json.load(open(f,encoding="utf-8")); i=r["persona_id"]
    if d=="runs" and i[0]=="s": pass
    for x in J.score_profile(ps[i],r.get("final_profile") or {}):
        if not x["ok"]: c[(x["field"],x["source"])]+=1
  print(d,sorted(c.items(),key=lambda a:-a[1]))
