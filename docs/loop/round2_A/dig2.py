import json
for i in ("E04_no_savings_no_ss","E08_sole_provider_3_kids"):
    x=json.load(open(f"eval_runs/{i}.json",encoding="utf-8"))
    pl=[e for e in x["events"] if e.get("type")=="plan"][0]["plan"]
    print(i,pl["text_source"],pl["verdict"])
    for a in pl["actions"]: print("  -",a["title"],"|",a["why"])
    for s in pl.get("starting_points",[]): print("  SP",s["title"],s["result"])
