"""Print one baseline's variations as a table: python eval/reasonableness/show.py --tag before sample:e11"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--tag", default="before")
    a = ap.parse_args()
    rows = {json.loads(x)["id"]: json.loads(x) for x in (HERE / f"results_{a.tag}.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}
    for i in a.ids:
        r = rows[i]
        b = r["base"]
        print(f"\n{i} {r['label']}  {r['profile_brief']}")
        print(f"  BASE count_on {b['count_on']:>9,.0f} basics {b['basics_paid']:>3} verdict {b['verdict']:<11} claim {b['claim_age']} "
              f"ss {b['ss_per_year']:,.0f} goal {b['goal']:,.0f} save_now {b['save_now']} strat {b['strategy_source']}")
        for v in r["variations"]:
            if v.get("status") != "ok":
                print(f"  {v['name']:<24} {v.get('status')}: {str(v.get('why'))[:90]}")
                continue
            f = v["fig"]
            fr = v.get("fresh")
            print(f"  {v['name']:<24} count_on {f['count_on']:>9,.0f} ({f['count_on'] - b['count_on']:+8,.0f}) basics {f['basics_paid']:>3} "
                  f"({(f['basics_paid'] or 0) - (b['basics_paid'] or 0):+3d}) claim {f['claim_age']} {f['verdict']:<11} {f['strategy_source']}"
                  + (f"  fresh {fr['count_on']:,.0f}" if fr else ""))


if __name__ == "__main__":
    main()
