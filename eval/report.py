"""Write eval/EVAL_REPORT.md from saved runs, checks, the benchmark and the judge's verdicts.

  python eval/report.py [--out eval/EVAL_REPORT.md] [--judge-file eval/judge_results.json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import benchmark  # noqa: E402
import checks  # noqa: E402
from common import REPO, EVAL_DIR, RUNS_DIR, dig, load_cases, load_run, pct, read_jsonl, usage_of  # noqa: E402

def _rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(p).name


DESC = {
    "stream": "the stream ended with a plan and no error",
    "three_parts": "plan has needs, wants and wishes",
    "needs_range": "needs paid is 0 to 100",
    "wants_bound": "wants within a sensible bound of income and savings",
    "number_check": "every number in the adviser's text is in a tool output or the profile",
    "family_pet": "family and pet costs appear when the profile has children or pets",
    "retire_cap": "retire_age kept as stated, claim ages 62 to 70, no age past 70 suggested",
    "contract": "verdict, goal, chart band and handoffs present and consistent with the markets numbers",
    "actions": "three actions, no forbidden advice",
    "cost": "total cost under the budget cap",
    "headline": "plan.headline is present and its dollar figures are the plan's own",
    "claim_age": "claim_age (and the partner's for a couple) present, 62 to 70",
    "debt_lever": "a debt at 7% or more -> a debt lever in plan.levers",
    "debt_in_actions": "...and the three actions name the debt",
    "match_lever": "an employer match not fully captured -> a match lever",
    "match_in_actions": "...and the three actions name the match",
    "college_event": "a child with college -> a College event in costs_by_age",
    "mortgage_event": "a mortgage that ends in the horizon -> a 'Mortgage paid off' event",
    "debts_event": "debts with payments -> a 'Debts paid off' event",
    "big_cost_event": "a big cost with a year -> its own event",
    "parents_event": "parents' help -> a 'Helping your parents' event",
    "medicare_event": "under 65 -> a 'Medicare starts' event",
    "legacy_reflected": "a legacy goal appears in the markets finding or the wishes",
    "pension_reflected": "a pension appears in findings, tools or text",
}
DIRNAME = {"savings_up": "+20% savings (wants must not fall)", "retire_later": "retire 2 years later (must not fall)",
           "debt_add": "add a $30k 7% debt (wants should fall)", "pension_add": "add a $24k pension (wants should rise)",
           "match_full": "capture the full match (wants should rise)", "legacy_add": "add a $200k legacy (wants should fall)"}


def table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def headline_numbers(res: dict, bm: dict, judge: dict | None, ok_runs: list[dict]) -> dict:
    """The figures of the before/after table, from checks results, benchmark results, judge results and ok runs."""
    s = bm["summary"]
    g, gp = s.get("gap") or {}, (s.get("both_positive") or {}).get("gap") or {}
    zw = s.get("zero_wants") or {}
    d = {}
    for kind in checks.EXPECT:
        xs = [x for x in res["direction"] if x["kind"] == kind]
        d[kind] = {"n": len(xs), "pass": sum(1 for x in xs if x["ok"]),
                   "moved": sum(1 for x in xs if x.get("moved")) if checks.EXPECT[kind] != "not_fall" else None}
    cases = res["cases"]
    core = sum(1 for r in cases.values() if all(r[k]["ok"] for k in checks.CORE_CHECKS if k in r))
    us = [usage_of(r) for r in ok_runs]
    jc = None
    if judge:
        its = judge["items"].values()
        jc = {k: sum(1 for x in its if x["verdict"] == k) for k in ("reasonable", "questionable", "wrong")}
    return {"n_base": len(cases), "core_pass": core, "wants0_lite": zw.get("lite"), "wants0_opt": zw.get("opt"),
            "n_gap": s.get("n_gap"), "gap_median": g.get("median"), "gap_median_abs": g.get("median_abs"),
            "gap_within25": g.get("within25"), "gap_median_both_pos": gp.get("median"),
            "n_both_pos": (s.get("both_positive") or {}).get("n_compared"),
            "verdict_agree": (s.get("verdict") or {}).get("agree"), "verdict_n": (s.get("verdict") or {}).get("n"),
            "direction": d, "judge": jc,
            "cost_per_plan": (sum(u["usd"] for u in us) / len(us)) if us else None,
            "tokens_per_plan": (sum(u["total_tokens"] for u in us) / len(us)) if us else None, "n_runs": len(us)}


def before_after(after: dict, before: dict | None) -> list[str]:
    def f(x, fmt):
        return "n/a" if x is None else fmt.format(x)
    pc = lambda x: f(None if x is None else 100 * x, "{:.0f}%")  # noqa: E731
    def row(label, get):
        return [label, get(before) if before else "n/a", get(after)]
    jd = lambda x: "not run" if not x.get("judge") else " / ".join(f"{k} {v}" for k, v in x["judge"].items())  # noqa: E731
    rows = [row("Base households run", lambda x: x["n_base"]),
            row("Passed every core check", lambda x: f"{x['core_pass']} of {x['n_base']}"),
            row("Lite wants = $0 (households)", lambda x: f"{x['wants0_lite']} of {x['n_gap'] or '?'}"),
            row("Optimizer count-on = $0 (households)", lambda x: x["wants0_opt"]),
            row("Median gap to optimizer (all)", lambda x: f(x["gap_median"], "{:+.1f}%")),
            row("Median absolute gap", lambda x: f(x["gap_median_abs"], "{:.1f}%")),
            row("Within 25% of optimizer", lambda x: pc(x["gap_within25"])),
            row("Median gap, both above $0", lambda x: f(x["gap_median_both_pos"], "{:+.1f}%") + f" (n={x['n_both_pos']})"),
            row("Verdict agreement (works or not)", lambda x: pc(x["verdict_agree"]) + f" of {x['verdict_n']}")]
    for kind in checks.EXPECT:
        rows.append(row(f"Direction: {DIRNAME[kind]}", lambda x, k=kind: (f"{x['direction'][k]['pass']} of {x['direction'][k]['n']} pass"
                                                                         + (f", {x['direction'][k]['moved']} moved" if x['direction'][k]['moved'] is not None else ""))))
    rows += [row("Judge split", jd), row("Cost per plan (run events)", lambda x: f(x["cost_per_plan"], "${:.4f}")),
             row("Tokens per plan", lambda x: f(x["tokens_per_plan"], "{:,.0f}"))]
    return table(["Measure", "Before fixes (runs_v2_pre_fix)", "After fixes"], rows).split("\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(EVAL_DIR / "EVAL_REPORT.md"))
    ap.add_argument("--judge-file", default=str(EVAL_DIR / "judge_results.json"))
    a = ap.parse_args()

    cases = load_cases()
    runs = {c["id"]: load_run(c["id"]) for c in cases}
    runs = {k: v for k, v in runs.items() if v}
    base_ids = [c["id"] for c in cases if c.get("kind", "base") == "base"]
    base_runs = [runs[i] for i in base_ids if i in runs]
    ok_runs = [r for r in runs.values() if r.get("status") == "ok"]
    L: list[str] = [f"# Enough Lite: evaluation report", "", f"Generated {time.strftime('%Y-%m-%d %H:%M')} from `{_rel(RUNS_DIR)}` ({len(runs)} saved runs).", ""]

    # ---- overview
    el = [r["elapsed_s"] for r in ok_runs]
    urls = sorted({r.get("url", "?") for r in runs.values()})
    L += ["## Run overview", "",
          table(["Item", "Value"], [
              ["Base households defined", len(base_ids)], ["Base households run", len(base_runs)],
              ["Runs ok / error (all kinds)", f"{len(ok_runs)} / {len(runs) - len(ok_runs)}"],
              ["Perturbed runs (direction subset)", sum(1 for r in runs.values() if r['kind'] != 'base')],
              ["Time per run, median / p90 / max (s)", f"{pct(el, .5):.1f} / {pct(el, .9):.1f} / {max(el):.1f}" if el else "n/a"],
              ["Server(s)", ", ".join(urls)]]), ""]

    # ---- before / after
    res = checks.evaluate_all()
    bm = benchmark.compute()
    jf0 = Path(a.judge_file)
    jdata = json.loads(jf0.read_text(encoding="utf-8")) if jf0.exists() else None
    after = headline_numbers(res, bm, jdata, ok_runs)
    bf = EVAL_DIR / "runs_v2_pre_fix" / "summary.json"
    before = json.loads(bf.read_text(encoding="utf-8")) if bf.exists() else None
    L += ["## Before fixes / After fixes", "",
          "Before: the 480 runs made before the engine fixes (kept in `eval/runs_v2_pre_fix/`; checks, benchmark and judge exactly as saved then, "
          "so the before wants figure meant the part above basics for lite and count-on for the optimizer). After: the same cases on the fixed engine, "
          "wants.per_year = count-on including basics, compared like for like.", ""] + before_after(after, before) + [""]

    # ---- checks
    n = len(res["cases"])
    rows = []
    fails_by = defaultdict(list)
    for k in checks.CHECKS:
        ap = [(i, r[k]) for i, r in res["cases"].items() if not r[k].get("na")]
        bad = [(i, x["detail"]) for i, x in ap if not x["ok"]]
        fails_by[k] = bad
        rows.append([f"`{k}`", DESC[k], len(ap) - len(bad), len(bad), len(ap), f"{100 * (len(ap) - len(bad)) / len(ap):.0f}%" if ap else "n/a"])
    allok = sum(1 for r in res["cases"].values() if all(v["ok"] for v in r.values()))
    coreok = sum(1 for r in res["cases"].values() if all(r[k]["ok"] for k in checks.CORE_CHECKS))
    warn = sum(1 for r in res["cases"].values() if r["cost"].get("warn"))
    L += ["## Automated checks", "",
          f"{n} base households checked. {coreok} passed every core check ({100 * coreok / n:.0f}%); {allok} passed every check including the new-input ones ({100 * allok / n:.0f}%)." if n else "No runs yet.",
          "New-input checks apply only to households whose profile has that input (the Applicable column).", "",
          table(["Check", "What it tests", "Pass", "Fail", "Applicable", "Pass rate"], rows), ""]
    if warn:
        L += [f"{warn} households cost more than ${checks.WARN_USD:.2f} (the plan expects $0.01 to $0.02).", ""]
    L += ["### Failures by type", ""]
    any_fail = False
    for k in checks.CHECKS:
        if fails_by[k]:
            any_fail = True
            L.append(f"**`{k}`** ({len(fails_by[k])})")
            for i, det in fails_by[k][:3]:
                L.append(f"- `{i}` ({res['by_id'].get(i, '')}): {det[:240]}")
            L.append("")
    if not any_fail:
        L += ["No failures.", ""]

    # ---- direction
    L += ["### Direction checks (up to 30 pairs per kind)", "",
          f"Noise: {int(100 * checks.NOISE_REL)}% of wants or ${checks.NOISE_ABS:,.0f}, and {checks.NOISE_NEEDS:.0f} points on the needs score. "
          "Fail means wants (or the needs score) moved the wrong way beyond noise. Moved means wants moved the expected way beyond noise.", ""]
    drows, dfail = [], []
    for kind in checks.EXPECT:
        xs = [x for x in res["direction"] if x["kind"] == kind]
        bad = [x for x in xs if not x["ok"]]
        dfail += bad
        mv = sum(1 for x in xs if x.get("moved"))
        drows.append([DIRNAME[kind], len(xs), len(xs) - len(bad), len(bad), mv if checks.EXPECT[kind] != "not_fall" else "n/a"])
    L += [table(["Perturbation", "Pairs", "Pass", "Fail", "Moved as expected"], drows), ""]
    for x in dfail[:12]:
        L.append(f"- `{x['id']}` ({x['kind']}): {x['detail']} (base {x['base']}, variant {x['variant']})")
    L.append("")

    # ---- benchmark
    s = bm["summary"]
    L += ["## Benchmark against the full optimizer", "",
          f"{s['n_compared']} households have both a lite plan and a saved optimizer plan (`output/synth_tree_full`, else `output/synth_tree`). "
          "Gap is (lite wants - optimal wants) / optimal wants; positive means lite promises more than the optimizer found safe.", ""]
    if "gap" in s:
        g = s["gap"]
        L += [table(["Wants gap", "Value"], [
            ["Median", f"{g['median']:+.1f}%"], ["Mean", f"{g['mean']:+.1f}%"], ["10th to 90th percentile", f"{g['p10']:+.1f}% to {g['p90']:+.1f}%"],
            ["Median absolute gap", f"{g['median_abs']:.1f}%"], ["Within 10%", f"{100 * g['within10']:.0f}%"],
            ["Within 25%", f"{100 * g['within25']:.0f}%"], ["Lite more than 25% above optimal", f"{100 * g['lite_over_25']:.0f}%"],
            ["Lite more than 25% below optimal", f"{100 * g['lite_under_25']:.0f}%"]]), "",
              table(["Gap bucket", "Households"], [[k, v] for k, v in s["gap_hist"].items()]), ""]
    v = s["verdict"]
    L += ["**Verdict (works or does not).** Lite works = wants at least the spending goal; optimizer works = its feasibility flag.", "",
          table(["Outcome", "Households"], [["Both say works", v["both_work"]], ["Both say does not work", v["both_fail"]],
                                            ["Lite works, optimizer does not", v["lite_works_opt_fails"]],
                                            ["Lite does not, optimizer works", v["lite_fails_opt_works"]]]),
          "", f"Agreement: {100 * v['agree']:.0f}% of {v['n']}." if v["agree"] is not None else "No verdicts to compare.", ""]
    c = s["claim"]
    L += [f"**Claiming age.** The optimizer names one for {c['n_opt']} households; lite names one too for {c['n_both']}. "
          + (f"Exact match {100 * c['exact']:.0f}%, within one year {100 * c['within1']:.0f}%." if c["exact"] is not None else "Nothing to compare."), ""]
    pk = s["products"]["per_kind"]
    L += [f"**Products.** The optimizer includes a product for {s['products']['n_opt_with_products']} households. "
          "Lite counts as naming a product when an action or line mentions it.", ""]
    if pk:
        L += [table(["Product", "Both", "Optimizer only", "Lite only"], [[k, p["both"], p["opt_only"], p["lite_only"]] for k, p in sorted(pk.items())]), ""]
    zw = s.get("zero_wants") or {}
    bp = s.get("both_positive") or {}
    if zw:
        L += [f"**Wants is floored at zero.** Lite shows $0 of wants for {zw['lite']} households and the optimizer for {zw['opt']}; "
              f"for {zw['lite_zero_opt_positive']} lite says $0 where the optimizer found something above 0, so the gap above is dominated by that. "
              + (f"Where both are above zero ({bp['n_compared']} households): median gap {bp['gap']['median']:+.1f}%, within 25% {100 * bp['gap']['within25']:.0f}%." if "gap" in bp else ""), ""]
    cl = s.get("clean") or {}
    if "gap" in cl:
        L += [f"**Without the {s['n_synthetic']} households that carry inputs the optimizer never had** (big costs, parents' help, part-time work, inheritance; the persona set holds none, so the harness adds them to a seeded share): "
              f"{cl['n_compared']} households, median gap {cl['gap']['median']:+.1f}%, median absolute gap {cl['gap']['median_abs']:.1f}%, within 25% {100 * cl['gap']['within25']:.0f}%, "
              f"verdict agreement {100 * (cl['verdict']['agree'] or 0):.0f}%.", ""]
    if s.get("retire_differs"):
        L += [f"Note: the optimizer's retirement age differs from the profile's for {s['retire_differs']} households.", ""]

    # ---- judge
    L += ["## AI judge", ""]
    jf = Path(a.judge_file)
    judge_usd = 0.0
    if jf.exists():
        j = json.loads(jf.read_text(encoding="utf-8"))
        judge_usd = j.get("usd", 0.0)
        items = j["items"]
        cnt = {k: sum(1 for x in items.values() if x["verdict"] == k) for k in ("reasonable", "questionable", "wrong", "unparsed")}
        L += [f"Model `{j.get('model')}` rated {len(items)} sampled households. Judge spend ${judge_usd:.4f} (cap $1.00).", "",
              table(["Verdict", "Count"], [[k, v] for k, v in cnt.items() if v or k != "unparsed"]), ""]
        for lab in ("wrong", "questionable"):
            sel = [(i, x) for i, x in items.items() if x["verdict"] == lab]
            if sel:
                L.append(f"**{lab.capitalize()}**")
                L += [f"- `{i}` ({x['label']}): {x['reason']}" for i, x in sel[:8]]
                L.append("")
    else:
        L += ["Not run yet (`python eval/judge.py`).", ""]

    # ---- cost
    us = [usage_of(r) for r in ok_runs]
    usd = sum(u["usd"] for u in us)
    base_us = [usage_of(r)["usd"] for r in base_runs if r.get("status") == "ok"]
    L += ["## Tokens and cost", ""]
    t0 = min((time.mktime(time.strptime(r["started"], "%Y-%m-%dT%H:%M:%S")) for r in runs.values() if r.get("started")), default=0) - 5
    mine = {"eval-" + "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in c["id"])[:55] for c in cases}   # the sessions run_eval.py used
    ur = [e for e in read_jsonl(EVAL_DIR.parent / "runs" / "usage.jsonl") if e.get("session") in mine and e.get("at", 0) >= t0]
    if ur:
        tin = sum(e["input_tokens"] for e in ur); tca = sum(e["cached_tokens"] for e in ur)
        tcw = sum(e.get("cache_write_tokens", 0) for e in ur); tout = sum(e["output_tokens"] for e in ur)
        uu = sum(e["cost_usd"] for e in ur)
        plans: dict = defaultdict(float)
        for e in ur:
            plans[e["run_id"]] += e["cost_usd"]
        pv = list(plans.values())
        L += ["From `runs/usage.jsonl` (the app's own meter), sessions run_eval.py used (one per case, `eval-<case id>`) since this evaluation began; plans run twice appear twice.", "",
              table(["Item", "Value"], [
                  ["Plans metered", len(plans)], ["Agent calls", len(ur)],
                  ["Input tokens (uncached)", f"{tin:,}"], ["Cached input tokens (reads)", f"{tca:,}"], ["Cache-write tokens", f"{tcw:,}"],
                  ["Output tokens", f"{tout:,}"], ["Total tokens", f"{tin + tca + tcw + tout:,}"],
                  ["App cost, all plans", f"${uu:.4f}"],
                  ["Cost per plan (mean / median / p90 / max)", f"${uu / len(pv):.4f} / ${pct(pv, .5):.4f} / ${pct(pv, .9):.4f} / ${max(pv):.4f}"],
                  ["Tokens per plan (mean)", f"{(tin + tca + tcw + tout) // len(pv):,}"],
                  ["Judge cost", f"${judge_usd:.4f}"], ["Total eval spend", f"${uu + judge_usd:.4f}"]]), ""]
        if len(plans) > len(runs):
            L += [f"The meter holds {len(plans)} plans for {len(runs)} saved runs. The extra {len(plans) - len(runs)} are plans run twice: the first runner "
                  "(started before the app was restarted) kept going while the second was started with --redo-errors. The later result was saved. "
                  "The first line of the cost table below (run events, one result per case) is the cost of the saved set; the meter table is what was spent.", ""]
        ag: dict = defaultdict(lambda: [0, 0, 0, 0, 0, 0.0, 0.0])
        for e in ur:
            q = ag[e["agent"]]
            q[0] += 1; q[1] += e["input_tokens"]; q[2] += e["cached_tokens"]; q[3] += e.get("cache_write_tokens", 0); q[4] += e["output_tokens"]
            q[5] += e["cost_usd"]; q[6] += e.get("seconds", 0)
        L += [table(["Agent", "Calls", "Input", "Cached", "Cache write", "Output", "Cost", "Share", "Cost per plan", "Mean seconds"],
                    [[k, q[0], f"{q[1]:,}", f"{q[2]:,}", f"{q[3]:,}", f"{q[4]:,}", f"${q[5]:.4f}", f"{100 * q[5] / uu:.0f}%", f"${q[5] / len(pv):.5f}", f"{q[6] / q[0]:.1f}"]
                     for k, q in sorted(ag.items(), key=lambda kv: -kv[1][5])]), ""]
    else:
        L += ["No `eval-*` sessions found in usage.jsonl; figures below come from the run events.", ""]
    tin, tca, tout = (sum(u[k] for u in us) for k in ("input", "cached", "output"))
    L += ["From the saved run events (cost events; cache writes are not itemised there):", "",
          table(["Item", "Value"], [
              ["Input tokens (uncached)", f"{tin:,}"], ["Cached input tokens", f"{tca:,}"], ["Output tokens", f"{tout:,}"],
              ["App cost, all runs", f"${usd:.4f}"],
              ["Cost per household (mean / median / max)", f"${usd / len(us):.4f} / ${pct([u['usd'] for u in us], .5):.4f} / ${max(u['usd'] for u in us):.4f}" if us else "n/a"],
              ["Cost per base household (mean)", f"${sum(base_us) / len(base_us):.4f}" if base_us else "n/a"]]), ""]

    # ---- app issues (written by hand after reading the failures)
    ai = EVAL_DIR / "app_issues.md"
    if ai.exists():
        L += [ai.read_text(encoding="utf-8").rstrip(), ""]
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
