"""Mean change in count_on and basics by variation, and the retire-age failures with their base context.
  python eval/reasonableness/deltas.py before"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "before"
    rows = [json.loads(x) for x in (HERE / f"results_{tag}.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = list({r["id"]: r for r in rows}.values())
    d = defaultdict(list)
    for r in rows:
        if "error" in r:
            continue
        b = r["base"]
        for v in r["variations"]:
            if v.get("status") == "ok":
                f = v["fig"]
                d[v["name"]].append((f["count_on"] - b["count_on"], (f["basics_paid"] or 0) - (b["basics_paid"] or 0),
                                     f["count_on"] < b["count_on"] - max(500, 0.02 * b["count_on"])))
    print(f"{'variation':26s} {'n':>4s} {'mean d_count_on':>16s} {'mean d_basics':>14s} {'lower':>6s}")
    for k in sorted(d):
        xs = d[k]
        print(f"{k:26s} {len(xs):4d} {sum(x[0] for x in xs) / len(xs):16,.0f} {sum(x[1] for x in xs) / len(xs):14.1f} {sum(x[2] for x in xs):6d}")
    chk = json.loads((HERE / f"check_{tag}.json").read_text(encoding="utf-8"))
    by = {r["id"]: r for r in rows}
    print("\nretire-age direction failures:")
    for k in ("direction_up", "direction_down"):
        for x in chk["fails"].get(k, []):
            if x.get("where", "").startswith("retire"):
                b = by[x["id"]]["base"]
                print(f"  {x['id']:12s} {x['where']:10s} verdict {b['verdict']:<11s} save_now {b['save_now']:>8} | {x['detail'][:90]}")


if __name__ == "__main__":
    main()
