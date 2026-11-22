import sys, copy, json, glob, asyncio, re
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE))
from app import pipeline
cases = {json.loads(l)["id"]: json.loads(l) for l in open(HERE/"evalcopy"/"cases.jsonl", encoding="utf-8")}
jobs = []
for f in sorted(glob.glob(str(HERE/"plans"/"*.json"))):
    d = json.load(open(f, encoding="utf-8")); pl = [e for e in d["events"] if e.get("type")=="plan"][0]["plan"]
    for x in pl.get("starting_points") or []: jobs.append((Path(f).stem, d["profile"], x))
n=0
for i, c in cases.items():
    if c["kind"] != "base": continue
    t = json.load(open(HERE/"tools_runs"/(i+".json")))
    if t["verdict"]=="falls_short" and t["sp"] and n < 40:
        n+=1
        for x in t["sp"]: jobs.append((i, c["profile"], x))
ok=bad=0
for name, prof, x in jobs:
    p = pipeline.prepare(copy.deepcopy(prof))
    ch = pipeline.parse_whatif(x["whatif_text"], p)
    q, notes = pipeline.apply_whatif(p, ch)
    pl, _ = asyncio.run(pipeline.tools_only_plan(q))
    r = (pl["needs"]["paid_of_100"], pl["wants"]["per_year"]); e = (x["paid_of_100"], x["count_on_per_year"])
    ra = pl.get("retire_age") or q.retire_age
    flag = []
    if r != e: flag.append("DIFF")
    if q.retire_age > 70: flag.append("past70")
    if q.age != prof["age"]: flag.append("age moved")
    if x["makes_basics_safe"] != (r[0] >= 90): flag.append("safe flag")
    if flag: bad+=1; print(name, x["title"], "app", e, "recompute", r, flag, flush=True)
    else: ok+=1
print("starting points checked", ok+bad, "reproduce", ok, "problems", bad)
