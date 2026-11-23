import json,sys
r=json.load(open(f"runs_early/{sys.argv[1]}.json",encoding="utf-8"))
for t in r["intake_turns"]:
    q=(t.get("question") or {}).get("text")
    print(f"[{t['n']}] YOU: {t['user']}\n   APP: {t['reply']}\n   Q: {q} missing={t.get('missing')}")
print([f for f in r["intake_turns"][-1]["fields"]])
print((r.get("plan") or {}).get("headline"))
