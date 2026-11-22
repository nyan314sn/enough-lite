import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
print([ (e.get("type")) for e in d["events"]])
pl=[e for e in d["events"] if e.get("type")=="plan"][0]
print(list(pl.keys()))
plan=pl["plan"]
print(list(plan.keys()))
for k in ("headline","consistency","saving","social_security_per_year","starting_points","assumptions","needs"):
    print(k, json.dumps(plan.get(k),indent=0)[:1500])
print(json.dumps(plan["costs_by_age"])[:600])
