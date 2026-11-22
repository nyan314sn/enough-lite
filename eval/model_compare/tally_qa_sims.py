import json, collections, glob, statistics as st
from mc_common import *
out = {"qa": {}, "sims": {}}
for arm in ("anthropic", "openai"):
    res = json.load(open(HERE/"raw"/f"qa_{arm}.json")); jd = json.load(open(HERE/"raw"/f"qa_judged_{arm}.json"))
    cats = collections.defaultdict(lambda: [0,0,0,0])   # n, kind_ok, judge_correct, both
    errs = 0
    for k, r in res.items():
        c = cats[r["cat"]]; c[0]+=1
        kind_ok = bool((r["kind"] in r["expected_kinds"]) or (r["cat"]=="refuse" and r.get("emergency")))
        jc = jd[k]["verdict"] == "correct"
        c[1]+=kind_ok; c[2]+=jc; c[3]+= (kind_ok and jc)
        errs += bool(r["err"])
    tot = [sum(c[i] for c in cats.values()) for i in range(4)]
    verdicts = collections.Counter(v["verdict"] for v in jd.values())
    out["qa"][arm] = {"by_cat": {k: dict(zip(["n","kind_ok","judge_correct","handled_correct"], v)) for k, v in cats.items()}, "total": dict(zip(["n","kind_ok","judge_correct","handled_correct"], tot)), "verdicts": dict(verdicts), "http_errors": errs,
        "secs_median": st.median(r["secs"] for r in res.values()), "usd": sum(r.get("cost_usd") or 0 for r in res.values())}
    # sims
    runs = {}; judged = {}
    for f in (HERE/"raw"/f"sims_{arm}"/"runs").glob("*.json"): r = json.load(open(f, encoding="utf-8")); runs[r["persona_id"]] = r
    for f in (HERE/"raw"/f"sims_{arm}"/"judged").glob("*.json"): judged[f.stem] = json.load(open(f, encoding="utf-8"))
    reached = [r for r in runs.values() if r.get("reached_missing_empty")]
    turns = [r["turns_to_plan"] for r in reached if r.get("turns_to_plan")]
    shares = [j["accuracy"]["share"] for j in judged.values() if j["accuracy"]["share"] is not None]
    nf = sum(len(j["accuracy"]["fields"]) for j in judged.values()); okf = sum(f["ok"] for j in judged.values() for f in j["accuracy"]["fields"])
    causes = collections.Counter(w.get("cause") for j in judged.values() for w in (j["accuracy"].get("why") or []) if isinstance(w, dict))
    issues = collections.Counter((i["type"], i["severity"]) for j in judged.values() for i in j["issues"])
    p0 = sum(1 for j in judged.values() for i in j["issues"] if i["severity"] == "P0")
    byf = collections.defaultdict(lambda: [0,0])
    for j in judged.values():
        for f in j["accuracy"]["fields"]: byf[f["field"]][1]+=1; byf[f["field"]][0]+=f["ok"]
    plan_t = [t for r in runs.values() for t in r.get("plan_turns", [])]
    out["sims"][arm] = {"personas": len(runs), "status": dict(collections.Counter(r["status"] for r in runs.values())), "reached_plan": len(reached), "plan_ok": sum(1 for r in runs.values() if r.get("plan_ok")),
        "turns_mean": st.mean(turns) if turns else None, "turns_median": st.median(turns) if turns else None,
        "field_accuracy": okf/max(nf,1), "fields": nf, "persona_mean_share": st.mean(shares) if shares else None,
        "wrong_causes": dict(causes), "issues_total": sum(issues.values()), "P0": p0, "P1": sum(v for (t,s),v in issues.items() if s=="P1"),
        "issue_types": {f"{t}/{s}": v for (t,s),v in issues.items()},
        "made_up_figures": causes.get("assumed_default",0)+causes.get("person_never_said",0)+causes.get("never_asked",0),
        "app_misparsed": causes.get("app_misparsed",0), "unstated_assumption_issues": sum(v for (t,s),v in issues.items() if t=="unstated_assumption"),
        "field_acc_by_field": {k: f"{a}/{n}" for k,(a,n) in byf.items() if a<n},
        "plan_turn_kinds": dict(collections.Counter(t.get("kind") for t in plan_t)),
        "usd_app_sum": sum((r.get("app_cost_usd") or 0) for r in runs.values())}
json.dump(out, open(HERE/"results_qa_sims.json","w"), indent=1); print(json.dumps(out, indent=1))
