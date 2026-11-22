"""Plan metrics per arm + number equality across arms. Writes results_plans.json."""
import json, statistics as st
from mc_common import *
import common as ec, checks
from tests import test_product_rules as rules
sel = {i["id"]: i for i in json.loads((HERE / "selection.json").read_text(encoding="utf-8"))}
P = {a: load_plans(a) for a in ("anthropic", "openai")}
common_ids = sorted(i for i in sel if all(i in P[a] and P[a][i]["plan"] for a in P))
PRICES = {"anthropic": (0.10, 0.01, 0.125, 0.50), "openai": (0.10, 0.01, 0.10, 0.50)}

def texts_of(plan, events):
    out = [" ".join([(plan.get("needs") or {}).get("line", ""), (plan.get("wants") or {}).get("line", ""), (plan.get("wishes") or {}).get("line", "")]
                    + [x.get("title", "") + " " + x.get("why", "") for x in plan.get("actions") or []] + list(plan.get("family_moments") or []))]
    for e in events:
        if e.get("type") == "agent_done":
            f = e.get("finding") or {}
            out.append(" ".join([f.get("headline") or "", *(f.get("details") or [])]))
    return out

def tier(i):
    pl = P["anthropic"][i]["plan"]; sp = P["anthropic"][i]["profile"].get("spending_per_year") or 0
    if (pl["needs"].get("paid_of_100") or 0) < 90: return "struggling"
    return "average" if (pl["wants"].get("per_year") or 0) < 0.9 * sp else "comfortable"

def pct(xs, q):
    return ec.pct(xs, q)

rows = {a: {} for a in P}
for a in P:
    for i in sel:
        r = P[a].get(i)
        if not r: continue
        plan = r["plan"]
        row = {"status": r["status"], "seconds": r["seconds"], "usd": r["usage"]["usd"], "tokens": {k: r["usage"][k] for k in ("input", "cached", "output")}}
        if plan:
            case = {"id": i, "profile": r["profile"], "kind": "base", "base_id": i}
            try:
                res = checks.run_checks(case, r)
                row["number_check"] = res["number_check"]["ok"]; row["number_detail"] = res["number_check"].get("detail", "")[:120]
                row["core_ok"] = all(res[k]["ok"] for k in checks.CORE_CHECKS)
                row["failed_core"] = [k for k in checks.CORE_CHECKS if not res[k]["ok"]]
            except Exception as e:
                row["number_check"] = None; row["check_error"] = repr(e)[:100]
            ts = str(plan.get("text_source"))
            row["text_source"] = ts
            row["adviser_template"] = ts.startswith("template")
            row["adviser_second_try"] = "second try" in ts
            ag = [e for e in r["events"] if e.get("type") == "agent_done"]
            row["agent_templates"] = sum(1 for e in ag if str((e.get("finding") or {}).get("source", "")).startswith("template"))
            row["agents"] = len(ag)
            row["jargon"] = [h for t in texts_of(plan, r["events"]) for h in rules._bad_words(t, rules.JARGON + rules.HYPE + rules.LATIN)]
        rows[a][i] = row

def num_leaves(o, path=""):
    out = {}
    if isinstance(o, bool) or o is None: return out
    if isinstance(o, (int, float)): out[path] = float(o)
    elif isinstance(o, dict):
        for k, v in o.items(): out.update(num_leaves(v, f"{path}.{k}"))
    elif isinstance(o, list):
        for n, v in enumerate(o): out.update(num_leaves(v, f"{path}[{n}]"))
    return out
SKIP = ("tokens", "cost", "seconds", "text_source", "elapsed")
diffs = {}
for i in common_ids:
    A, O = num_leaves(strip_text(P["anthropic"][i]["plan"])), num_leaves(strip_text(P["openai"][i]["plan"]))
    d = [p for p in set(A) | set(O) if not any(s in p for s in SKIP) and (p not in A or p not in O or abs(A[p] - O[p]) > 1e-6 * max(1, abs(A[p])))]
    # chart is stripped by strip_text; compare it separately
    ca, co = (P["anthropic"][i]["plan"].get("chart") or {}), (P["openai"][i]["plan"].get("chart") or {})
    if ca != co: d.append("chart")
    if d: diffs[i] = sorted(d)[:12]

def summ(a, ids):
    rs = [rows[a][i] for i in ids if i in rows[a] and rows[a][i]["status"] == "ok" and "text_source" in rows[a][i]]
    secs = [r["seconds"] for r in rs]
    n = len(rs)
    tot = lambda k: sum(r["tokens"][k] for r in rs)
    return {"n": n, "failed_runs": sum(1 for i in ids if i in rows[a] and rows[a][i]["status"] != "ok"),
        "number_check_pass": sum(1 for r in rs if r.get("number_check")) / max(n, 1),
        "core_checks_all_pass": sum(1 for r in rs if r.get("core_ok")) / max(n, 1),
        "adviser_template": sum(r["adviser_template"] for r in rs), "adviser_second_try": sum(r["adviser_second_try"] for r in rs),
        "plans_with_any_agent_template": sum(1 for r in rs if r["agent_templates"] > 0), "agent_templates_total": sum(r["agent_templates"] for r in rs), "agents_total": sum(r["agents"] for r in rs),
        "jargon_hits": sum(len(r["jargon"]) for r in rs), "plans_with_jargon": sum(1 for r in rs if r["jargon"]),
        "sec_median": pct(secs, .5), "sec_p90": pct(secs, .9), "sec_max": max(secs) if secs else None, "sec_mean": st.mean(secs) if secs else None,
        "tok_in_per_plan": tot("input") / max(n, 1), "tok_cached_per_plan": tot("cached") / max(n, 1), "tok_out_per_plan": tot("output") / max(n, 1),
        "usd_per_plan_app": sum(r["usd"] for r in rs) / max(n, 1)}
out = {"n_common": len(common_ids), "number_diffs": diffs, "arms": {}}
tiers = {i: tier(i) for i in common_ids}
for a in P:
    out["arms"][a] = {"all": summ(a, common_ids), **{t: summ(a, [i for i in common_ids if tiers[i] == t]) for t in ("comfortable", "average", "struggling")}}
out["tier_counts"] = {t: sum(1 for v in tiers.values() if v == t) for t in ("comfortable", "average", "struggling")}
# plans where both AI text (neither template) for fair text comparison
out["both_ai_text"] = sum(1 for i in common_ids if not rows["anthropic"][i].get("adviser_template") and not rows["openai"][i].get("adviser_template"))
(HERE / "results_plans.json").write_text(json.dumps({"summary": out, "rows": rows}, indent=1), encoding="utf-8")
print(json.dumps(out, indent=1))
