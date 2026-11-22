"""Run the selected households against one app, one plan at a time (single-user timing). Resumable.
  run_plans.py --arm anthropic --url http://127.0.0.1:8041 [--limit N]"""
import argparse, json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[0]), str(HERE.parents[1])]
import run_eval, common  # noqa
ap = argparse.ArgumentParser(); ap.add_argument("--arm", required=True); ap.add_argument("--url", required=True)
ap.add_argument("--limit", type=int, default=0); ap.add_argument("--max-usd", type=float, default=1.0)
a = ap.parse_args()
out = HERE / "raw" / f"plans_{a.arm}"; out.mkdir(parents=True, exist_ok=True)
items = json.loads((HERE / "selection.json").read_text(encoding="utf-8"))
if a.limit: items = items[: a.limit]
spent = 0.0
for it in items:
    f = out / f"{it['id']}.json"
    if f.exists(): continue
    t0 = time.time()
    ev, err = run_eval.post_plan(a.url, it["profile"], {"X-Enough-Test": "1", "X-Session-Id": f"cmp-{a.arm}-{it['id']}"[:60]}, 240)
    secs = round(time.time() - t0, 2)
    plan = next((e["plan"] for e in ev if e.get("type") == "plan"), None)
    rec = {"id": it["id"], "arm": a.arm, "seconds": secs, "error": err, "status": "ok" if plan and not err else "error", "events": ev, "profile": it["profile"]}
    rec["usage"] = common.usage_of(rec)
    f.write_text(json.dumps(rec), encoding="utf-8")
    spent += rec["usage"]["usd"]
    print(a.arm, it["id"], rec["status"], secs, f"${rec['usage']['usd']:.4f}", plan.get("text_source") if plan else err, flush=True)
    if spent > a.max_usd: print("stop: spend cap"); break
print(a.arm, "done, spent", round(spent, 4))
