"""Print a readable transcript of one run: python peek.py p01"""
import json
import sys

from common import RUNS

r = json.loads((RUNS / f"{sys.argv[1]}.json").read_text(encoding="utf-8"))
print(r["status"], "turns", len(r["intake_turns"]), "plan_ok", r.get("plan_ok"), r.get("plan_error"), r.get("app_cost_usd"))
for t in r["intake_turns"]:
    q = (t.get("question") or {}).get("text")
    print(f"[i{t['n']}] YOU{'(click)' if t.get('clicked') else ''}: {t['user']}\n     APP: {t['reply']} || Q: {q} || missing={t.get('missing')}")
print("PLAN:", (r.get("plan") or {}).get("headline"))
for t in r["plan_turns"]:
    print(f"[a{t['n']}] YOU: {t['user']}\n     APP({t.get('kind')}/{t.get('status')}): {t['text']}")
