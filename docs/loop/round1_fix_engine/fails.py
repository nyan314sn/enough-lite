"""Show a few failing checks from evalcopy/checks_results.json. Usage: fails.py check_name [n]"""
import json, sys
from pathlib import Path
d = json.load(open(Path(__file__).parent / "evalcopy" / "checks_results.json", encoding="utf-8"))
name, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5
rows = d.get("cases") or d.get("rows") or d
if isinstance(rows, dict):
    rows = list(rows.values()) if not isinstance(next(iter(rows.values())), str) else []
k = 0
for r in rows:
    c = (r.get("checks") or r).get(name) if isinstance(r, dict) else None
    if isinstance(c, dict) and c.get("ok") is False:
        print(r.get("id"), "|", str(c.get("detail") or c.get("why") or c)[:300])
        k += 1
        if k >= n:
            break
print("keys:", list(d)[:10] if isinstance(d, dict) else type(d))
