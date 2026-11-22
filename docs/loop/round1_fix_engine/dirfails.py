"""Failing direction checks. Usage: dirfails.py"""
import json
from pathlib import Path
d = json.load(open(Path(__file__).parent / "evalcopy" / "checks_results.json", encoding="utf-8"))
for r in d["direction"]:
    if not r["ok"]:
        print(json.dumps(r)[:500])
