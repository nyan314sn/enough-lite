import json,glob
for f in sorted(glob.glob("runs_early/*.json")):
    r=json.load(open(f,encoding="utf-8"))
    d={k:(v,s) for k,v,s in r["intake_turns"][-1]["fields"]}
    print(r["persona_id"], r["turns_to_plan"], "|", {k:d.get(k) for k in ("home","mortgage","state","retire_age")})
