"""Eval case ids whose plans the last two fixes can change: stated Social Security in a couple, pensions or part-time pay."""
import json
from pathlib import Path
HERE = Path(__file__).parent
ids = []
for f in sorted((HERE / "eval_runs").glob("*.json")):
    prof = json.load(open(f, encoding="utf-8")).get("profile") or {}
    stated_couple = prof.get("social_security_per_year") and prof.get("has_partner")
    if stated_couple or prof.get("pensions") or prof.get("part_time"):
        ids.append(f.stem)
print(",".join(ids))
