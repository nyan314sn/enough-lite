import json,sys
from pathlib import Path
r=json.load(open(f"runs/{sys.argv[1]}.json",encoding="utf-8"))
for t in r["intake_turns"][:int(sys.argv[2])]:
    q=(t.get("question") or {}).get("text")
    print(f"[i{t['n']}] YOU: {t['user']}\n   APP: {t['reply'][:330]}\n   Q: {q}")
print("turns",r["turns_to_plan"])
L=json.load(open(f"lens/sim4-{sys.argv[1]}.json",encoding="utf-8")); print(L["text"]); print(L["result"])
