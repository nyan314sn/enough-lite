"""Pull the plan object out of each saved /api/plan stream into web/src/testdata/plans.json (test fixtures for the plan page)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "..", "..", "web", "src", "testdata", "plans.json")
plans = {}
for sid in ("e11", "s011", "e27", "e24", "e09"):
    for blk in open(os.path.join(HERE, "fixtures", f"{sid}_plan_0.txt"), encoding="utf-8").read().split("\n\n"):
        if blk.startswith("data:") and '"type": "plan"' in blk:
            plans[sid] = json.loads(blk[5:])["plan"]
plans["e24_whatif"] = json.load(open(os.path.join(HERE, "fixtures", "e24_ask_0.txt"), encoding="utf-8"))["plan"]
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(plans, open(OUT, "w", encoding="utf-8"), separators=(",", ":"))
print({k: v["verdict"] for k, v in plans.items()}, os.path.getsize(OUT))
