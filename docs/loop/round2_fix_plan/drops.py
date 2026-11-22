"""Why did count-on fall to 0 for some eval cases? Prints the profile and both runs' key figures. Usage: drops.py ID ..."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
cases = {json.loads(x)["id"]: json.loads(x) for x in open(HERE / "evalcopy" / "cases.jsonl", encoding="utf-8")}


def plan(d, i):
    f = Path(d) / (i + ".json")
    ev = json.load(open(f, encoding="utf-8"))["events"]
    return next(e["plan"] for e in ev if e.get("type") == "plan")


for i in sys.argv[1:]:
    p = cases[i]["profile"]
    print("=" * 10, i, {k: p.get(k) for k in ("age", "partner_age", "retire_age", "pay_per_year", "partner_pay_per_year", "spending_now_per_year",
                                             "spending_per_year", "savings", "saving", "debts")})
    for lab, d in (("before", HERE.parent / "round2_A" / "eval_runs"), ("after", HERE / "eval_runs")):
        pl = plan(d, i)
        print(" ", lab, pl["verdict"], pl["count_on_per_year"], pl["needs"]["paid_of_100"], pl.get("saving"), pl["headline"][:160])
