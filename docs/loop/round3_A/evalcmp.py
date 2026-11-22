"""Gap to the optimizer: round 1 runs vs round 2 runs, same benchmark rows (saved optimizer results)."""
import json, os, statistics, collections
from pathlib import Path
HERE = Path(__file__).parent
bm = json.load(open(HERE / "evalcopy" / "benchmark_results.json", encoding="utf-8"))
rows = {r["id"]: r for r in bm["rows"]}
cases = {json.loads(l)["id"]: json.loads(l) for l in open(HERE / "evalcopy" / "cases.jsonl", encoding="utf-8")}


def load(dirp, i):
    f = Path(dirp) / (i + ".json")
    if not f.exists():
        return None
    d = json.load(open(f, encoding="utf-8"))
    if d.get("status") != "ok":
        return None
    pl = [e for e in d["events"] if e.get("type") == "plan"]
    return pl[0]["plan"] if pl else None


R1 = HERE / "eval_runs"; R2 = HERE / "eval_runs"


def stats(ids, dirp, label):
    gaps, agree, n = [], 0, 0
    for i in ids:
        pl = load(dirp, i)
        if pl is None or i not in rows:
            continue
        opt = rows[i]["opt"]
        if not opt.get("wants"):
            continue
        g = (pl["wants"]["per_year"] - opt["wants"]) / opt["wants"] * 100
        gaps.append(g); n += 1
        agree += (pl["verdict"] == "works") == bool(opt.get("feasible"))
    if not gaps:
        print(label, "no data"); return
    print(f"{label:34s} n={n:3d} median gap {statistics.median(gaps):+6.1f}% | median abs {statistics.median(abs(x) for x in gaps):5.1f}% | within25 {100*sum(abs(x)<=25 for x in gaps)/n:4.0f}% | verdict agree {100*agree/n:4.0f}%")


have = [i for i in rows if (R2 / (i + ".json")).exists() and (R1 / (i + ".json")).exists()]
print("rows with both runs:", len(have))
for lab, f in (("all", lambda c: True), ("couples", lambda c: c["profile"].get("has_partner") or c["profile"].get("partner_age")),
               ("singles", lambda c: not (c["profile"].get("has_partner") or c["profile"].get("partner_age"))),
               ("couples, both working<ret", lambda c: (c["profile"].get("has_partner")) and (c["profile"].get("retire_age", 0) > c["profile"].get("age", 0)))):
    ids = [i for i in have if f(cases[i])]
    stats(ids, R1, "round1 " + lab); stats(ids, R2, "round2 " + lab)
# paired change
d = []
for i in have:
    a, b = load(R1, i), load(R2, i)
    if a and b and a["wants"]["per_year"] > 0:
        d.append((b["wants"]["per_year"] - a["wants"]["per_year"]) / a["wants"]["per_year"] * 100)
cp = [(i) for i in have if cases[i]["profile"].get("has_partner")]
dc = []; ds = []
for i in have:
    a, b = load(R1, i), load(R2, i)
    if a and b and a["wants"]["per_year"] > 0:
        (dc if cases[i]["profile"].get("has_partner") else ds).append((b["wants"]["per_year"] - a["wants"]["per_year"]) / a["wants"]["per_year"] * 100)
print(f"paired change round2 vs round1 count-on: all median {statistics.median(d):+.1f}% (n={len(d)}); couples {statistics.median(dc):+.1f}% (n={len(dc)}); singles {statistics.median(ds):+.1f}% (n={len(ds)})")
big = sorted(((x, i) for x, i in [((load(R2, i)["wants"]["per_year"] - load(R1, i)["wants"]["per_year"]) / max(1, load(R1, i)["wants"]["per_year"]) * 100, i) for i in have if load(R1, i) and load(R2, i)]))
print("largest drops:", [(round(x), i) for x, i in big[:8]]); print("largest rises:", [(round(x), i) for x, i in big[-5:]])
v = collections.Counter()
for i in have:
    a, b = load(R1, i), load(R2, i)
    if a and b: v[(a["verdict"], b["verdict"])] += 1
print("verdict transitions r1->r2:", dict(v))
