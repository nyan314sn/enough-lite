"""Remove from results_<tag>.jsonl the baselines that have a given variation, and print their ids (to rerun them).
  python eval/reasonableness/drop_ids.py after "pay off mortgage" """
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
tag, name = sys.argv[1], sys.argv[2]
path = HERE / f"results_{tag}.jsonl"
keep, ids = [], []
for line in path.read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    if any(v["name"] == name for v in r.get("variations", [])):
        ids.append(r["id"])
    else:
        keep.append(line)
path.write_text("\n".join(keep) + "\n", encoding="utf-8")
print(",".join(ids))
