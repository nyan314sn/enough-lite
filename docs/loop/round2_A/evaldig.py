import json, glob, os, re, sys, collections
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "round1_A"))
import numcheck
R1 = HERE.parent / "round1_A" / "eval_runs"; R2 = HERE / "eval_runs"


def load(d, i):
    x = json.load(open(d / (i + ".json"), encoding="utf-8"))
    pl = [e for e in x["events"] if e.get("type") == "plan"][0]["plan"]
    return x, pl


# (d) text source baseline round 1 vs round 2
for lab, d in (("round1", R1), ("round2", R2)):
    c = collections.Counter(); reasons = collections.Counter()
    for f in glob.glob(str(d / "*.json")):
        x = json.load(open(f, encoding="utf-8"))
        pl = [e for e in x["events"] if e.get("type") == "plan"][0]["plan"]
        ts = pl["text_source"]
        c["ai" if ts == "ai" else "second" if "second" in ts else "template"] += 1
        if ts.startswith("template"):
            reasons[re.sub(r"\$[\d,]+", "$N", ts)[:90]] += 1
    print(lab, dict(c)); print("   template reasons", reasons.most_common(4))
# (a) numcheck offenders by kind in round 2 vs round 1
for lab, d in (("round1", R1), ("round2", R2)):
    kinds = collections.Counter(); runs = 0; ex = []
    for f in sorted(glob.glob(str(d / "*.json"))):
        x = json.load(open(f, encoding="utf-8"))
        try:
            bad = numcheck.check(x)
        except Exception:
            continue
        if bad:
            runs += 1
            for b in bad:
                kinds[b[0]] += 1
            if len(ex) < 3: ex.append((os.path.basename(f), bad[:3]))
    print(lab, "runs with unlisted dollar figures", runs, dict(kinds)); print("   e.g.", ex)
# (c) transitions
rows = []
for f in glob.glob(str(R2 / "*.json")):
    i = os.path.basename(f)[:-5]
    if not (R1 / (i + ".json")).exists(): continue
    x2, p2 = load(R2, i); x1, p1 = load(R1, i)
    rows.append((i, p1["verdict"], p2["verdict"], p1["wants"]["per_year"], p2["wants"]["per_year"], p1["needs"]["paid_of_100"], p2["needs"]["paid_of_100"], bool(x2["profile"].get("has_partner")), x2["profile"]["age"], x2["profile"].get("partner_age"), x2["profile"].get("retire_age")))
print("works/close -> falls_short:")
for r in rows:
    if r[1] in ("works", "close") and r[2] == "falls_short": print("  ", r)
for i in ("S084", "S160", "S018", "S151", "S124"):
    for r in rows:
        if r[0] == i: print("  extreme", r)
