import json, sys
n = sys.argv[1]
d = json.load(open(f"plans/{n}.json", encoding="utf-8"))
plan = [e for e in d["events"] if e.get("type") == "plan"][0]["plan"]
keys = sys.argv[2:] or ["verdict", "verdict_words", "headline", "needs", "wants", "wishes", "claim_age", "partner_claim_age", "already_claiming", "horizon_text", "starting_points", "saving", "assumptions", "actions", "text_source"]
for k in keys:
    v = plan.get(k)
    if isinstance(v, list):
        print(k + ":")
        for x in v: print("   -", x)
    else:
        print(k + ":", v)
