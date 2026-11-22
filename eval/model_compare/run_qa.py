"""Send the QA messages to one app with each of 5 households' own plan. Resumable. run_qa.py --arm anthropic --url ..."""
import argparse, json, sys, time, urllib.request, urllib.error
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from qa_messages import CASES
ap = argparse.ArgumentParser(); ap.add_argument("--arm", required=True); ap.add_argument("--url", required=True)
a = ap.parse_args()
HH = ["doctor", "e24", "e09", "e20", "young"]
plans = {}
for h in HH:
    r = json.load(open(HERE / "raw" / f"plans_{a.arm}" / f"sample_{h}.json", encoding="utf-8"))
    plans[h] = (r["profile"], next(e["plan"] for e in r["events"] if e.get("type") == "plan"))
out = HERE / "raw" / f"qa_{a.arm}.json"
res = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
for i, (cat, msg, kinds) in enumerate(CASES):
    key = str(i)
    if key in res: continue
    hh = HH[i % len(HH)]
    prof, plan = plans[hh]
    body = json.dumps({"question": msg, "profile": prof, "plan": plan}).encode()
    req = urllib.request.Request(a.url + "/api/ask", data=body, method="POST",
        headers={"Content-Type": "application/json", "X-Enough-Test": "1", "X-Session-Id": f"qa-{a.arm}-{i}"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as r: j = json.loads(r.read())
        err = None
    except urllib.error.HTTPError as e: j, err = {}, f"HTTP {e.code} {e.read()[:150]!r}"
    except Exception as e: j, err = {}, repr(e)
    res[key] = {"i": i, "cat": cat, "msg": msg, "hh": hh, "expected_kinds": kinds, "secs": round(time.time() - t0, 2), "err": err,
        "kind": j.get("kind"), "status": j.get("status"), "intent": j.get("intent"), "emergency": j.get("emergency"),
        "text": j.get("text"), "changes": j.get("changes") or j.get("pending_change"), "cost_usd": j.get("cost_usd"), "tokens": j.get("tokens")}
    print(a.arm, i, cat, res[key]["kind"], res[key]["status"], res[key]["secs"], flush=True)
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
