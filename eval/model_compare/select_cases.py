"""Pick the ~80 households: 60 from eval/cases.jsonl (stratified, seed 409) + the 15 admin samples + 5 named edge cases."""
import json, random, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "selection.json"
rng = random.Random(409)
cs = [json.loads(l) for l in open(ROOT / "eval/cases.jsonl", encoding="utf-8") if l.strip()]
base = [c for c in cs if c.get("kind") == "base"]
def stratum(g, s): return [c for c in base if c["group"] == g and c["stratum"]["savings"] == s]
def spread(pool, n):
    # stratify by age band then take n
    by = {}
    for c in pool: by.setdefault(c["stratum"]["age_band"], []).append(c)
    for v in by.values(): rng.shuffle(v)
    out, groups = [], list(by.values())
    while len(out) < n and any(groups):
        for g in groups:
            if g and len(out) < n: out.append(g.pop())
    return out
chosen = spread(stratum("scf", "low"), 24) + spread(stratum("scf", "high"), 24) + spread(stratum("edge", "low") + stratum("edge", "high"), 12)
named = ["E03_no_savings", "E14_age_79_retired", "E12_early_retiree_45_underfunded", "E13_early_retiree_45_underfunded", "N08_pension_takes_lump_sum", "E26_heloc_and_boat", "E05_very_wealthy"]
have = {c["id"] for c in chosen}
extra = [c for c in base if c["id"] in named and c["id"] not in have][:5]
if len(extra) < 5:
    more = [c for c in base if c["group"] == "edge" and c["id"] not in have and c not in extra]
    rng.shuffle(more); extra += more[: 5 - len(extra)]
items = [{"id": c["id"], "source": "cases", "group": c["group"], "savings": c["stratum"]["savings"], "label": c.get("label", ""), "profile": c["profile"]} for c in chosen + extra]
for h in json.load(open(ROOT / "app/data/sample_households.json", encoding="utf-8")):
    items.append({"id": "sample_" + h["id"], "source": "samples", "group": "sample", "savings": h.get("tier"), "label": h["name"], "profile": h["profile"]})
OUT.write_text(json.dumps(items, indent=1), encoding="utf-8")
print(len(items), "households ->", OUT)
