"""One variation across all baselines, before and after: python eval/reasonableness/one_var.py "pay off mortgage" """
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(tag):
    rows = [json.loads(x) for x in (HERE / f"results_{tag}.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    return {r["id"]: r for r in rows if "error" not in r}


def main():
    name = sys.argv[1]
    a, b = load("before"), load("after")
    for i in b:
        vb = next((v for v in a.get(i, {}).get("variations", []) if v["name"] == name and v.get("status") == "ok"), None)
        va = next((v for v in b[i]["variations"] if v["name"] == name and v.get("status") == "ok"), None)
        if not va:
            continue
        pb = b[i]["profile_brief"]
        working = (pb["retire_age"] or 0) > (pb["age"] or 0)
        x0 = f"{vb['fig']['count_on'] - a[i]['base']['count_on']:+8,.0f}/{(vb['fig']['basics_paid'] or 0) - (a[i]['base']['basics_paid'] or 0):+4d}" if vb else "      -"
        x1 = f"{va['fig']['count_on'] - b[i]['base']['count_on']:+8,.0f}/{(va['fig']['basics_paid'] or 0) - (b[i]['base']['basics_paid'] or 0):+4d}"
        print(f"{i:28s} {'work' if working else 'ret '} base {b[i]['base']['count_on']:>8,.0f}/{b[i]['base']['basics_paid']:>3}  before {x0}  after {x1}")


if __name__ == "__main__":
    main()
