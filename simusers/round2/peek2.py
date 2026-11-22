import json
import sys

r = json.load(open(sys.argv[1], encoding="utf-8"))
print(r["status"], r.get("turns_to_plan"), r.get("plan_ok"))
for t in r["plan_turns"]:
    print("U:", t["user"], "\nA:", t["text"][:200], t.get("kind"), t.get("status"))
