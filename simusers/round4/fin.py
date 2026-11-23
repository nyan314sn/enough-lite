import json
t=json.load(open("tally.json"))
for k,v in t["lens_by_kind"].items(): print(k,{x:v[x] for x in ("n","a","b","c","all3")})
print(sum(json.loads(l)["usd"] for l in open("cost_log.jsonl")))
print([ (i,p,r) for i,p,r in [(x[0],x[1],x[3]) for x in t["lens_no"]] if r["a"] is None])
