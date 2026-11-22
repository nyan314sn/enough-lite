"""Failures by check and by variation, side by side for two runs:
  python eval/reasonableness/breakdown.py before after"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def counts(tag: str) -> Counter:
    d = json.loads((HERE / f"check_{tag}.json").read_text(encoding="utf-8"))
    c = Counter()
    for k, xs in d["fails"].items():
        for x in xs:
            c[(k, x.get("where", "-") if k != "no_nan_or_negative" else ("chart below 0" if "chart" in x.get("detail", "") else "other"))] += 1
    return c


def main():
    tags = sys.argv[1:] or ["before"]
    cs = [counts(t) for t in tags]
    keys = sorted(set().union(*cs))
    print(f"{'check':30s} {'variation':26s} " + " ".join(f"{t:>7s}" for t in tags))
    for k in keys:
        print(f"{k[0]:30s} {k[1]:26s} " + " ".join(f"{c.get(k, 0):7d}" for c in cs))


if __name__ == "__main__":
    main()
