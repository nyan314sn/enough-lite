"""Look at one baseline closely: the plan's figures and every strategy the picker tested. Tools only.

  python eval/reasonableness/probe.py sample:e11
  python eval/reasonableness/probe.py sample:doctor --set spending_now_per_year=160000 --set spending_per_year=140000
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402  (sets the no-model environment)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--candidates", action="store_true")
    a = ap.parse_args()
    item = next(x for x in harness.load_baselines() if x["id"] == a.id)
    prof = json.loads(json.dumps(item["profile"]))
    for kv in a.set:
        k, v = kv.split("=", 1)
        prof[k] = json.loads(v)
    from app import pipeline
    base = pipeline._clean_profile_text(pipeline.prepare(prof))
    plan, ctx = asyncio.run(harness._run(base, options=True))
    f = harness.figures(plan, ctx)
    f.pop("bad_numbers")
    print(json.dumps(f, indent=1))
    ms = ctx.results["money"]
    print("save_by_year[:5]", ms["save_by_year"][:5], "unspent", ms["unspent_pay_per_year"])
    print("ss by year", ctx.results["markets"].get("social_security_by_year", [])[:40])
    if a.candidates:
        for c in plan["neighbors"]["candidates_tested"]:
            print(f"  {c['source']:28s} basics {c['basics_paid_of_100']:3d} count_on {c['safe_spending_per_year']:>9,.0f} claim {c['claim_age']}")
    lv = ((plan.get("analysis") or {}).get("levers") or {}).get("rows") or []
    for x in lv:
        print("  lever", x["title"], x["count_on_change"], x["basics_change"])


if __name__ == "__main__":
    main()
