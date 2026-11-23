"""Tally round 4 and the model-compare baseline into one JSON/printout."""
import json, statistics, collections, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIM = HERE.parent
BASE = SIM.parent / "eval" / "model_compare" / "raw" / "sims_anthropic"
sys.path.insert(0, str(SIM))
import judge as J
ps = {p["id"]: p for p in json.loads((SIM / "personas.json").read_text(encoding="utf-8")) + json.loads((SIM / "personas_hard.json").read_text(encoding="utf-8")) + json.loads((SIM / "personas_hs.json").read_text(encoding="utf-8"))}


def load(d):
    out = {}
    for f in sorted(Path(d).glob("*.json")):
        out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return out


def tally(runs, judged, ids=None):
    ids = [i for i in (ids or runs) if i in runs]
    n = len(ids)
    reached = [i for i in ids if runs[i].get("plan_ok")]
    turns = [runs[i]["turns_to_plan"] for i in ids if runs[i].get("turns_to_plan")]
    fields = ok = 0
    never = said_wrong = est_wrong = 0
    p0 = p1 = 0
    p0l, p1l = [], []
    for i in ids:
        r = runs[i]
        prof = r.get("final_profile") or {}
        sc = J.score_profile(ps[i], prof) if prof else []
        fields += len(sc)
        ok += sum(f["ok"] for f in sc)
        for f in sc:
            if not f["ok"]:
                if f["source"] == "you said":
                    said_wrong += 1
                elif f["source"] in ("estimate", "assumed", "default"):
                    est_wrong += 1
        j = judged.get(i)
        if j:
            for w in [x for x in (j["accuracy"].get("why") or []) if isinstance(x, dict)]:
                if w.get("cause") in ("never_asked", "person_never_said", "assumed_default"):
                    never += 1
            for it in j["issues"]:
                if it["severity"] == "P0":
                    p0 += 1; p0l.append((i, it))
                elif it["severity"] == "P1":
                    p1 += 1; p1l.append((i, it))
    return dict(n=n, reached=len(reached), turns_mean=round(statistics.mean(turns), 1) if turns else None,
                turns_median=statistics.median(turns) if turns else None, fields=fields, correct=ok,
                acc=round(100 * ok / fields, 1) if fields else None, never_given_wrong=never, wrong_but_said=said_wrong,
                wrong_marked_estimate=est_wrong, p0=p0, p1=p1, p0l=p0l, p1l=p1l)


sel24 = None
brun, bj = load(BASE / "runs"), load(BASE / "judged")
# baseline: reached = plan_ok (build) or reached_missing_empty
for r in brun.values():
    r.setdefault("plan_ok", r.get("reached_missing_empty"))
runs, judged = load(HERE / "runs"), load(HERE / "judged")
eruns, ejudged = load(HERE / "runs_early"), load(HERE / "judged_early")
hs = [p for p in ps if p.startswith("s")]
base24 = [i for i in runs if not i.startswith("s")]
res = dict(before=tally(brun, bj), after=tally(runs, judged, base24), hs=tally(runs, judged, hs), early=tally(eruns, ejudged))
res["early"]["person_messages_mean"] = round(statistics.mean(r.get("person_messages", 0) for r in eruns.values()), 1) if eruns else None
res["early"]["escape_presses_mean"] = round(statistics.mean(r.get("escape_presses", 0) for r in eruns.values()), 1) if eruns else None
# lens
lens = load(HERE / "lens")
def lt(items):
    items = list(items)
    n = len(items)
    if not n:
        return {}
    g = lambda k: sum(1 for x in items if (x["result"].get(k) or "").lower().startswith("y"))
    return dict(n=n, a=g("a"), b=g("b"), c=g("c"), all3=sum(1 for x in items if all((x["result"].get(k) or "").lower().startswith("y") for k in "abc")),
                grade_mean=round(statistics.mean(x["grade"] for x in items), 1), grade_max=max(x["grade"] for x in items))
res["lens_hs_normal"] = lt(v for k, v in lens.items() if v["id"].startswith("s") and v["path"] == "normal")
res["lens_hs_early"] = lt(v for k, v in lens.items() if v["id"].startswith("s") and v["path"] == "early")
res["lens_base_normal"] = lt(v for k, v in lens.items() if not v["id"].startswith("s") and v["path"] == "normal")
res["lens_base_early"] = lt(v for k, v in lens.items() if not v["id"].startswith("s") and v["path"] == "early")
res["lens_all"] = lt(lens.values())
res["lens_by_kind"] = {k: lt(v for v in lens.values() if v["kind"] == k) for k in ("works", "close", "short", "basics")}
res["lens_confusing"] = [(v["id"], v["path"], v["result"].get("confusing")) for v in lens.values() if v["result"].get("confusing")]
res["lens_no"] = [(v["id"], v["path"], v["kind"], {k: v["result"].get(k) for k in "abc"}) for v in lens.values() if not all((v["result"].get(k) or "").lower().startswith("y") for k in "abc")]
print(json.dumps({k: ({kk: vv for kk, vv in v.items() if kk not in ("p0l", "p1l")} if isinstance(v, dict) else v) for k, v in res.items()}, indent=1))
print("\nP0/P1 issues, after (24) / hs / early:")
for name in ("after", "hs", "early"):
    for sev, key in (("P0", "p0l"), ("P1", "p1l")):
        for i, it in res[name][key]:
            print(name, sev, i, it["ref"], it["type"], "|", (it.get("quote") or "")[:90], "|", (it.get("note") or "")[:130])
failed = [(i, r["status"], r.get("plan_error")) for d in (runs, eruns) for i, r in d.items() if not r.get("plan_ok")]
print("no plan:", failed)
json.dump({k: v for k, v in res.items()}, open(HERE / "tally.json", "w"), indent=1, default=str)
