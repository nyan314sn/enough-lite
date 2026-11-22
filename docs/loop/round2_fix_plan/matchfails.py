"""The eval's match_lever failures: how much match each one misses. Usage: matchfails.py"""
import json
from pathlib import Path

HERE = Path(__file__).parent
res = json.load(open(HERE / "evalcopy" / "checks_results.json", encoding="utf-8"))
for i, r in res["cases"].items():
    if not r["match_lever"].get("na") and not r["match_lever"]["ok"]:
        ev = json.load(open(HERE / "eval_runs" / (i + ".json"), encoding="utf-8"))["events"]
        nums = next(e["finding"]["numbers"] for e in ev if e.get("type") == "agent_done" and e["agent"] == "markets")
        print(i, nums.get("match_missed_per_year"), nums.get("years_to_retire"), r["match_lever"]["detail"][:80])
