"""Before vs after, as round3_A/evalcmp3.py: gap to the optimizer, within 25%, verdict agreement, direction checks."""
import json, statistics, os, re
from pathlib import Path
HERE = Path(__file__).parent
EV = HERE.parent / "round3_A" / "evalcopy"
bm = json.load(open(EV / "benchmark_results.json", encoding="utf-8")); rows = {r["id"]: r for r in bm["rows"]}
cases = {json.loads(l)["id"]: json.loads(l) for l in open(EV / "cases.jsonl", encoding="utf-8")}
def load(d, i):
    f = HERE / d / (i + ".json")
    if not f.exists(): return None
    x = json.load(open(f)); return None if "error" in x else x
for d in ("runs_before", "runs_after"):
    print("=====", d, "errors", sum(1 for i in cases if (HERE / d / (i + ".json")).exists() and load(d, i) is None))
    base = [i for i in cases if cases[i]["kind"] == "base" and load(d, i)]
    cp = lambda i: cases[i]["profile"].get("has_partner") or cases[i]["profile"].get("partner_age")
    for lab, f in (("all", lambda i: True), ("couples", cp), ("singles", lambda i: not cp(i))):
        g = []; ag = 0
        for i in base:
            if not f(i) or i not in rows or not rows[i]["opt"].get("wants"): continue
            x, opt = load(d, i), rows[i]["opt"]
            g.append((x["wants"] - opt["wants"]) / opt["wants"] * 100); ag += (x["verdict"] == "works") == bool(opt.get("feasible"))
        n = len(g)
        print(f"{lab:8s} n={n} median {statistics.median(g):+.1f}% medabs {statistics.median(abs(v) for v in g):.1f}% within25 {100*sum(abs(v)<=25 for v in g)/n:.0f}% agree {100*ag/n:.0f}%")
    for kind, exp in (("savings_up","not_fall"),("retire_later","not_fall"),("debt_add","fall"),("pension_add","rise"),("match_full","rise"),("legacy_add","fall")):
        n = bad = 0; ex = []
        for i, c in cases.items():
            if c["kind"] != kind: continue
            a, b = load(d, c["base_id"]), load(d, i)
            if not a or not b: continue
            n += 1; w0, w1 = a["wants"], b["wants"]
            ok = (w1 >= w0 * .97) if exp in ("not_fall", "rise") else (w1 <= w0 * 1.03)
            if not ok: bad += 1; ex.append((c["base_id"], w0, w1))
        print(f"  {kind} n {n} wrong way {bad} {ex[:4]}")
    print("  consistency non-empty:", sum(1 for i in cases if load(d, i) and load(d, i)["consistency"]))
    fs = [i for i in cases if load(d, i) and load(d, i)["verdict"] == "falls_short"]
    print("  falls_short", len(fs), "with a safe starting point", sum(1 for i in fs if any(s["makes_basics_safe"] for s in load(d, i)["sp"] or [])),
          "no starting points", sum(1 for i in fs if not load(d, i)["sp"]))
# paired change, and what moved most
ch = []
for i in cases:
    a, b = load("runs_before", i), load("runs_after", i)
    if a and b and cases[i]["kind"] == "base" and a["wants"] > 0: ch.append(((b["wants"] - a["wants"]) / a["wants"] * 100, i, a["wants"], b["wants"], a["verdict"], b["verdict"]))
print("paired after vs before: median %+.2f%%, unchanged %d of %d" % (statistics.median(x[0] for x in ch), sum(1 for x in ch if abs(x[0]) < 0.05), len(ch)))
mort = [x for x in ch if ((cases[x[1]]["profile"].get("home") or {}).get("mortgage_balance") or 0) > 0]
print("with a mortgage: n %d median %+.1f%%" % (len(mort), statistics.median(x[0] for x in mort) if mort else 0))
for x in sorted(ch)[:6] + sorted(ch)[-3:]: print("  %+.1f%% %s %s -> %s %s -> %s" % x)
