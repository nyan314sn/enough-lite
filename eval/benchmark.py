"""Compare lite plans with the full optimizer's saved results (plan "a") for the same households.

Benchmark files: output/synth_tree_full/raw/<id>.json first, else output/synth_tree/raw/<id>.json.
Note: the lite profile now holds more than the optimizer saw (big costs, parents' help, part-time work, inheritance; the
persona set had none, so a seeded share of cases carries them). summary["clean"] repeats the figures without those cases.
Measures
  wants gap %      (lite count-on - optimal count-on) / optimal; positive = lite promises more. Lite count-on is
                   wants.per_year (= count_on_per_year, basics included, since 2026-11-21); the optimizer's is its scorecard
                   wants.per_year (also basics included). Both are "what you can count on a year".
  verdict          lite "works" = wants.per_year >= spending goal; optimizer "works" = verdict.feasible
  claiming age     optimizer social_security_age vs the age lite names for claiming (if it names one)
  products         optimizer's product kinds vs the products lite's text recommends (per kind)

  python eval/benchmark.py     -> prints the distribution, writes eval/benchmark_results.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BENCH_FULL, BENCH_TREE, EVAL_DIR, dig, load_cases, load_run, pct, plan_text  # noqa: E402

PRODUCT_WORDS = {
    "term_life": r"term life|life insurance",
    "annuity": r"annuit|glwb|guaranteed lifetime|income for life",
    "ltc": r"long[- ]term care|\bltc\b",
    "disability": r"disability insurance",
    "hsa": r"\bhsa\b|health savings",
}
CLAIM_RE = re.compile(r"(?:claim|start|take|begin|delay)\w*[^.\n]{0,50}?(?:social security|benefit)[^.\n]{0,30}?(?:at|by|until|to|till)\s+(?:age\s+)?(6[2-9]|70)\b"
                      r"|social security[^.\n]{0,60}?(?:at|by|until|to)\s+(?:age\s+)?(6[2-9]|70)\b", re.I)


def product_kind(name: str) -> str:
    n = (name or "").lower()
    for k, rx in PRODUCT_WORDS.items():
        if k in n or re.search(rx, n):
            return k
    if any(w in n for w in ("fia", "rila", "va_", "glwb", "spia", "dia", "qlac")):
        return "annuity"
    return n


def load_bench(bid: str) -> dict | None:
    for base, tag in ((BENCH_FULL, "full"), (BENCH_TREE, "tree")):
        f = base / f"{bid}.json"
        if f.exists():
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            a = (d.get("plans") or {}).get("a")
            if a:
                return {"src": tag, "a": a}
    return None


def opt_summary(a: dict) -> dict:
    sc = a.get("scorecard") or a.get("scorecard_view") or {}
    v = a.get("verdict") or {}
    prods = set()
    for key in ("includes_products", "view_products"):
        for p in a.get(key) or []:
            prods.add(product_kind(p.get("kind") if isinstance(p, dict) else str(p)))
    return {"wants": (sc.get("wants") or {}).get("per_year"), "needs_paid": (sc.get("needs") or {}).get("paid_of_100"),
            "feasible": v.get("feasible"), "retire_age": a.get("retire_age"), "goal_age": v.get("goal_age"),
            "ss_age": a.get("social_security_age"), "products": sorted(prods)}


def lite_summary(case: dict, run: dict) -> dict:
    """Read the real plan fields: plan.verdict, claim_age, retire_age, spending_goal (no inferring)."""
    plan = dig(run)["plan"] or {}
    prof = case["profile"]
    text = plan_text(plan)
    # like for like: lite's count-on (wants.per_year, basics included, safe in 90 of 100) vs the optimizer's scorecard
    # wants.per_year (also what you can count on, basics included). Never the above-basics part.
    w = plan.get("count_on_per_year")
    if w is None:
        w = (plan.get("wants") or {}).get("per_year")
    goal = plan.get("spending_goal") or prof.get("spending_per_year")
    verdict = plan.get("verdict")
    prods = sorted({k for k, rx in PRODUCT_WORDS.items() if re.search(rx, text, re.I)})
    return {"wants": w, "needs_paid": (plan.get("needs") or {}).get("paid_of_100"), "verdict": verdict,
            "works": (verdict == "works") if verdict else None, "claim_age": plan.get("claim_age"),
            "partner_claim_age": plan.get("partner_claim_age"), "retire_age": plan.get("retire_age"),
            "goal": goal, "products": prods}


def compute() -> dict:
    rows = []
    for c in load_cases({"base"}):
        run = load_run(c["id"])
        if not run or run.get("status") != "ok":
            continue
        b = load_bench(c["bench_id"])
        if not b:
            continue
        o, l = opt_summary(b["a"]), lite_summary(c, run)
        row = {"id": c["id"], "src": b["src"], "label": c["label"], "stratum": c["stratum"], "opt": o, "lite": l,
               "retire_differs": o["retire_age"] is not None and o["retire_age"] != c["profile"]["retire_age"],
               "synthetic": list(c.get("synthetic") or [])}
        if l["wants"] is not None and o["wants"]:
            row["gap_pct"] = 100.0 * (l["wants"] - o["wants"]) / o["wants"]
        if l["works"] is not None and o["feasible"] is not None:
            row["verdict_agree"] = bool(l["works"]) == bool(o["feasible"])
        if l["claim_age"] is not None and o["ss_age"]:
            row["claim_diff"] = l["claim_age"] - o["ss_age"]
        row["product_pairs"] = {k: ((k in o["products"]), (k in l["products"])) for k in sorted(set(o["products"]) | set(l["products"]))}
        rows.append(row)
    s = summarize(rows)
    clean = [r for r in rows if not r["synthetic"]]
    s["clean"] = summarize(clean)      # households whose inputs the optimizer also had (no big cost, parents' help, part-time, inheritance)
    s["n_synthetic"] = len(rows) - len(clean)
    pos = [r for r in rows if r["lite"]["wants"] and r["opt"]["wants"]]
    s["both_positive"] = summarize(pos)    # wants is floored at 0, so the gap is only informative when both are above 0
    s["zero_wants"] = {"lite": sum(1 for r in rows if not r["lite"]["wants"]), "opt": sum(1 for r in rows if not r["opt"]["wants"]),
                       "lite_zero_opt_positive": sum(1 for r in rows if not r["lite"]["wants"] and r["opt"]["wants"])}
    return {"rows": rows, "summary": s}


def summarize(rows: list[dict]) -> dict:
    gaps = [r["gap_pct"] for r in rows if "gap_pct" in r]
    s: dict = {"n_compared": len(rows), "n_gap": len(gaps)}
    if gaps:
        ab = [abs(g) for g in gaps]
        s["gap"] = {"mean": sum(gaps) / len(gaps), "median": pct(gaps, .5), "p10": pct(gaps, .1), "p90": pct(gaps, .9),
                    "median_abs": pct(ab, .5), "within10": sum(a <= 10 for a in ab) / len(ab),
                    "within25": sum(a <= 25 for a in ab) / len(ab),
                    "lite_over_25": sum(g > 25 for g in gaps) / len(gaps), "lite_under_25": sum(g < -25 for g in gaps) / len(gaps)}
        s["gap_hist"] = hist(gaps)
    v = [r["verdict_agree"] for r in rows if "verdict_agree" in r]
    tab = {"both_work": 0, "both_fail": 0, "lite_works_opt_fails": 0, "lite_fails_opt_works": 0}
    for r in rows:
        if "verdict_agree" in r:
            lw, ow = bool(r["lite"]["works"]), bool(r["opt"]["feasible"])
            tab["both_work" if lw and ow else "both_fail" if not lw and not ow else "lite_works_opt_fails" if lw else "lite_fails_opt_works"] += 1
    s["verdict"] = {"n": len(v), "agree": (sum(v) / len(v)) if v else None, **tab}
    cd = [r["claim_diff"] for r in rows if "claim_diff" in r]
    s["claim"] = {"n_both": len(cd), "n_opt": sum(1 for r in rows if r["opt"]["ss_age"]),
                  "exact": (sum(d == 0 for d in cd) / len(cd)) if cd else None,
                  "within1": (sum(abs(d) <= 1 for d in cd) / len(cd)) if cd else None}
    per: dict = {}
    for r in rows:
        for k, (o, l) in r["product_pairs"].items():
            p = per.setdefault(k, {"both": 0, "opt_only": 0, "lite_only": 0})
            p["both" if o and l else "opt_only" if o else "lite_only"] += 1
    s["products"] = {"n_opt_with_products": sum(1 for r in rows if r["opt"]["products"]), "per_kind": per}
    s["retire_differs"] = sum(1 for r in rows if r["retire_differs"])
    return s


def hist(gaps: list[float]) -> dict:
    edges = [(-1e9, -50), (-50, -25), (-25, -10), (-10, 10), (10, 25), (25, 50), (50, 1e9)]
    names = ["< -50%", "-50 to -25", "-25 to -10", "-10 to +10", "+10 to +25", "+25 to +50", "> +50%"]
    return {n: sum(lo <= g < hi for g in gaps) for n, (lo, hi) in zip(names, edges)}


def main() -> None:
    out = compute()
    (EVAL_DIR / "benchmark_results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    s = out["summary"]
    print(f"compared {s['n_compared']} households")
    if "gap" in s:
        g = s["gap"]
        print(f"wants gap %: median {g['median']:.1f}, mean {g['mean']:.1f}, p10 {g['p10']:.1f}, p90 {g['p90']:.1f}; "
              f"within 10%: {100 * g['within10']:.0f}%, within 25%: {100 * g['within25']:.0f}%")
        print("histogram:", s["gap_hist"])
    print("verdict:", s["verdict"])
    print("claim age:", s["claim"])
    print("products:", s["products"])
    c = s["clean"]
    if "gap" in c:
        print(f"without the {s['n_synthetic']} cases with inputs the optimizer lacked ({c['n_compared']} left): median gap {c['gap']['median']:.1f}%, "
              f"within 25%: {100 * c['gap']['within25']:.0f}%, verdict agree {100 * (c['verdict']['agree'] or 0):.0f}%")


if __name__ == "__main__":
    main()
