"""Invariant and sanity checks on a harness run (results_<tag>.jsonl). Prints pass rates and writes check_<tag>.json.

  python eval/reasonableness/check.py --tag before
  python eval/reasonableness/check.py --tag after --compare before

Tolerances (Monte Carlo noise; every run shares the same seed and paths, so noise is small):
  count_on: $500 or 2% of the larger figure, whichever is more; basics paid: 2 of 100.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOL_ABS, TOL_REL, TOL_BASICS = 500.0, 0.02, 2
VERDICT_SAFE = 90


def tol(a: float, b: float) -> float:
    return max(TOL_ABS, TOL_REL * max(abs(a), abs(b)))


def verdict_of(f: dict) -> str:
    if f["basics_paid"] is not None and f["basics_paid"] < VERDICT_SAFE:
        return "falls_short"
    if f["count_on"] >= f["goal"]:
        return "works"
    if f["count_on"] >= 0.9 * f["goal"]:
        return "close"
    return "below_goal"


def plan_checks(f: dict, where: str, fails: dict, counts: Counter, rid: str):
    """Checks that hold for any plan (baseline or variation)."""
    def chk(name, ok, detail=""):
        counts[name + ":n"] += 1
        if not ok:
            fails[name].append({"id": rid, "where": where, "detail": detail})
    chk("verdict_consistent", verdict_of(f) == f["verdict"], f"{f['verdict']} vs {verdict_of(f)} (count_on {f['count_on']}, goal {f['goal']}, basics {f['basics_paid']})")
    chk("basics_in_0_100", f["basics_paid"] is not None and 0 <= f["basics_paid"] <= 100, str(f["basics_paid"]))
    nums = [f["count_on"], f["basics_per_year"], f["goal"], f["ss_per_year"]]
    chk("no_nan_or_negative", all(isinstance(x, (int, float)) and math.isfinite(x) and x >= 0 for x in nums) and f["chart_min"] >= 0
        and not f["bad_numbers"], f"{nums} chart_min={f['chart_min']} bad={f['bad_numbers'][:3]}")
    if f.get("how_sure"):
        hs = f["how_sure"]
        chk("how_sure_ordered", all(hs[i] >= hs[i + 1] for i in range(len(hs) - 1)) and abs(hs[2] - f["count_on"]) < 1, str(hs))


def run(tag: str) -> dict:
    rows = [json.loads(x) for x in (HERE / f"results_{tag}.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = list({r["id"]: r for r in rows}.values())
    fails: dict[str, list] = defaultdict(list)
    counts: Counter = Counter()
    status = Counter()
    info: dict[str, list] = defaultdict(list)
    n_var = 0
    for r in rows:
        if "error" in r:
            fails["baseline_error"].append({"id": r["id"], "detail": r["error"]})
            continue
        b = r["base"]
        rid = r["id"]
        plan_checks(b, "base", fails, counts, rid)
        if b["ss_per_year"] > 0 and b["count_on"] < b["ss_per_year"]:
            counts["count_on_below_ss"] += 1
            reason = b["headline"].split("That is because ", 1)[-1] if "That is because" in b["headline"] else "(no reason given)"
            info["count_on_below_ss"].append({"id": rid, "count_on": b["count_on"], "ss": b["ss_per_year"], "why": reason})
            counts["below_ss_explained:n"] += 1
            if "That is because" not in b["headline"]:
                fails["below_ss_explained"].append({"id": rid, "detail": b["headline"][:200]})
        byname = {v["name"]: v for v in r["variations"] if v.get("status") == "ok"}
        if "savings -50%" in byname and "savings +50%" in byname and r["profile_brief"]["savings"] >= 5000:
            counts["savings_moves_count_on:n"] += 1
            if all(abs(byname[k]["fig"]["count_on"] - b["count_on"]) < 100 and byname[k]["fig"]["basics_paid"] == b["basics_paid"]
                   for k in ("savings -50%", "savings +50%")):
                fails["savings_moves_count_on"].append({"id": rid, "detail": f"savings {r['profile_brief']['savings']:,.0f}: halving or adding half "
                                                        f"leaves count_on {b['count_on']:,.0f} and basics {b['basics_paid']} unchanged"})
        for v in r["variations"]:
            status[v.get("status")] += 1
            if v.get("status") != "ok":
                if v.get("status") in ("error", "parse_miss"):
                    fails["variation_" + v["status"]].append({"id": rid, "where": v["name"], "detail": v.get("why")})
                else:
                    info["not_run"].append({"id": rid, "where": v["name"], "status": v.get("status"), "why": v.get("why")})
                continue
            n_var += 1
            f = v["fig"]
            plan_checks(f, v["name"], fails, counts, rid)
            t = tol(f["count_on"], b["count_on"])
            dc, db = f["count_on"] - b["count_on"], (f["basics_paid"] or 0) - (b["basics_paid"] or 0)
            e = v.get("expect")
            name = None
            if e in ("up", "up_basics"):
                name = "direction_up"
                counts[name + ":n"] += 1
                ok = (dc >= -t or e == "up_basics") and db >= -TOL_BASICS
                if not ok:
                    fails[name].append({"id": rid, "where": v["name"], "detail": f"count_on {b['count_on']:.0f}->{f['count_on']:.0f}, basics {b['basics_paid']}->{f['basics_paid']}, claim {b['claim_age']}->{f['claim_age']}, strat {b['strategy_source']}->{f['strategy_source']}"})
            elif e in ("down", "down_basics"):
                name = "direction_down"
                counts[name + ":n"] += 1
                ok = (dc <= t or e == "down_basics") and db <= TOL_BASICS
                if not ok:
                    fails[name].append({"id": rid, "where": v["name"], "detail": f"count_on {b['count_on']:.0f}->{f['count_on']:.0f}, basics {b['basics_paid']}->{f['basics_paid']}, claim {b['claim_age']}->{f['claim_age']}, strat {b['strategy_source']}->{f['strategy_source']}"})
            # spending goal changes never move what you can count on (it is a property of the money, not the wish)
            if v["name"].startswith("spend retired"):
                counts["goal_change_keeps_count_on:n"] += 1
                if abs(dc) > t:
                    fails["goal_change_keeps_count_on"].append({"id": rid, "where": v["name"], "detail": f"count_on {b['count_on']:.0f}->{f['count_on']:.0f}"})
            if v["name"] == "savings +$100k":
                ytr = max(0, (r["profile_brief"]["retire_age"] or 65) - (r["profile_brief"]["age"] or 45))
                yrs = max(1, (b["horizon_age"] or 95) - max(r["profile_brief"]["age"] or 45, r["profile_brief"]["retire_age"] or 65))
                # $100k grown at 0-4% real a year until retirement, spread over the retirement years at the 90-of-100 level
                lo = 100_000 * 0.5 / yrs if b["basics_paid"] and b["basics_paid"] >= 50 else 0
                hi = 100_000 * 1.04 ** ytr * 0.09
                counts["magnitude_100k:n"] += 1
                info["magnitude_100k"].append({"id": rid, "dc": round(dc), "pct_of_100k": round(dc / 1000, 2), "ytr": ytr, "yrs": yrs})
                if not (lo - t <= dc <= hi + t):
                    fails["magnitude_100k"].append({"id": rid, "detail": f"+$100k -> count_on {dc:+.0f} (bounds {lo:.0f}..{hi:.0f}, {ytr} yrs to retire, {yrs} retired)"})
            if v.get("fresh"):
                fr = v["fresh"]
                counts["whatif_equals_fresh:n"] += 1
                if abs(fr["count_on"] - f["count_on"]) > tol(fr["count_on"], f["count_on"]) or abs((fr["basics_paid"] or 0) - (f["basics_paid"] or 0)) > TOL_BASICS:
                    fails["whatif_equals_fresh"].append({"id": rid, "where": v["name"], "detail": f"whatif {f['count_on']:.0f}/{f['basics_paid']} claim {f['claim_age']} ({f['strategy_source']}) vs fresh {fr['count_on']:.0f}/{fr['basics_paid']} claim {fr['claim_age']} ({fr['strategy_source']})"})
            if v["name"] == "claim at retirement":
                info["claim_at_retirement"].append({"id": rid, "label": r["label"], "plan_claim": b["claim_age"], "retire": b["retire_age"],
                                                    "savings": r["profile_brief"]["savings"], "count_on_plan": b["count_on"], "count_on_early": f["count_on"],
                                                    "basics_plan": b["basics_paid"], "basics_early": f["basics_paid"],
                                                    "median_at_retirement": b["median_at_retirement"]})
                counts["claim_choice_not_worse:n"] += 1
                # the plan's claiming age is chosen to make count_on largest with the basics safe: claiming at retirement
                # should never beat it on both counts (beyond noise)
                if dc > t and db >= 0 or (db > TOL_BASICS and dc >= -t):
                    fails["claim_choice_not_worse"].append({"id": rid, "detail": f"plan claims {b['claim_age']}: {b['count_on']:.0f}/{b['basics_paid']}; claiming at {f['claim_age']}: {f['count_on']:.0f}/{f['basics_paid']}"})
    summary = {}
    for k in sorted({k.split(":")[0] for k in counts if k.endswith(":n")}):
        n = counts[k + ":n"]
        summary[k] = {"n": n, "fail": len(fails.get(k, [])), "pass_rate": round(1 - len(fails.get(k, [])) / n, 4) if n else None}
    for k in fails:
        if k not in summary:
            summary[k] = {"n": None, "fail": len(fails[k])}
    # the claiming age: how often the plan delays past the retirement age, and what the delay is worth
    ca = info.get("claim_at_retirement", [])
    late = [x for x in ca if x["plan_claim"] > max(62, x["retire"] or 0)]
    low = [x for x in late if x["savings"] < 25_000]

    def gain(x):
        return (x["count_on_plan"] - x["count_on_early"]) / max(1.0, x["count_on_early"])
    claim_stats = {"baselines_with_choice": len(ca), "plan_claims_after_retiring": len(late),
                   "median_gain_pct": round(100 * sorted(gain(x) for x in late)[len(late) // 2], 1) if late else None,
                   "low_savings_delayed": len(low),
                   "low_savings_examples": [{k: x[k] for k in ("id", "label", "plan_claim", "retire", "savings", "median_at_retirement",
                                                               "count_on_plan", "count_on_early", "basics_plan", "basics_early")} for x in low[:20]],
                   "early_better_basics": sum(1 for x in late if (x["basics_early"] or 0) > (x["basics_plan"] or 0) + TOL_BASICS)}
    reasons = Counter()
    for x in info.get("count_on_below_ss", []):
        for part in x["why"].rstrip(".").split(" and "):
            reasons[part.strip()] += 1
    claim_stats["below_ss_reasons"] = dict(reasons.most_common())
    res = {"tag": tag, "baselines": len(rows), "variations_run": n_var, "status": dict(status), "summary": summary,
           "count_on_below_ss": counts["count_on_below_ss"], "claim_stats": claim_stats, "fails": fails, "info": info}
    (HERE / f"check_{tag}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="before")
    ap.add_argument("--compare", default="")
    ap.add_argument("--show", type=int, default=6)
    a = ap.parse_args()
    res = run(a.tag)
    old = run(a.compare)["summary"] if a.compare else {}
    print(f"{a.tag}: {res['baselines']} baselines, {res['variations_run']} variations run; status {res['status']}")
    print(f"count_on below Social Security: {res['count_on_below_ss']} baselines")
    cs = res["claim_stats"]
    print(f"claiming: {cs['plan_claims_after_retiring']} of {cs['baselines_with_choice']} plans claim after retiring "
          f"(median gain {cs['median_gain_pct']}% over claiming at retirement); {cs['low_savings_delayed']} of them have under $25k saved; "
          f"claiming at retirement pays the basics more often in {cs['early_better_basics']}")
    print(f"why count_on is below Social Security (reasons named in the headline): {cs['below_ss_reasons']}")
    for k, s in res["summary"].items():
        o = old.get(k)
        prev = f"   (was {o['fail']}/{o['n']})" if o else ""
        print(f"  {k:30s} fail {s['fail']:4d} / {s['n']}  pass {s.get('pass_rate')}{prev}")
    for k, xs in res["fails"].items():
        print(f"\n== {k} ({len(xs)})")
        for x in xs[: a.show]:
            print("  ", x)


if __name__ == "__main__":
    main()
