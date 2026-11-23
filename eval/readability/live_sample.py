"""A small live sample: AI-written plan text, measured. Posts sample households to a running app's /api/plan
(header X-Enough-Test: 1, which needs ENOUGH_TEST_MODE=1 on that server) and scores the text it returns.

  python eval/readability/live_sample.py --port 8031 --tag live_after --ids doctor,s071,e24,young,e09

Costs about $0.01 a plan. Reads no key; the server holds it. Writes results_<tag>.json and prints a table.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure  # noqa: E402

ROOT = HERE.parents[1]


def post_plan(port: int, profile: dict) -> tuple[dict | None, list[dict]]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/plan", data=json.dumps({"profile": profile}).encode(),
                                 headers={"Content-Type": "application/json", "X-Enough-Test": "1"})
    plan, findings = None, []
    with urllib.request.urlopen(req, timeout=240) as r:
        for raw in r:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            ev = json.loads(line[5:])
            if ev["type"] == "plan":
                plan = ev["plan"]
            elif ev["type"] == "agent_done":
                findings.append({"agent": ev["agent"], **ev["finding"]})
    return plan, findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8031)
    ap.add_argument("--tag", default="live_after")
    ap.add_argument("--ids", default="doctor,s071,e24,young,e09")
    args = ap.parse_args()
    samples = {h["id"]: h for h in json.loads((ROOT / "app" / "data" / "sample_households.json").read_text(encoding="utf-8"))}
    items = []
    for sid in args.ids.split(","):
        plan, findings = post_plan(args.port, samples[sid]["profile"])
        if plan is None:
            print(sid, "no plan")
            continue
        out: list = []
        measure.walk(plan, "", out)
        for label, t in out:
            items.append({"type": measure.kind_of(label), "label": label, "text": t, "sample": sid})
        for f in findings:
            items.append({"type": "specialist headline", "label": f["agent"], "text": f["headline"], "sample": sid})
            for d in f.get("details") or []:
                items.append({"type": "specialist detail", "label": f["agent"], "text": d, "sample": sid})
        print(sid, "text_source:", plan.get("text_source"), "| headline:", plan["headline"])
    rows = measure.summarize(items)
    measure.print_rows(rows, f"Live AI text, tag={args.tag}")
    (HERE / f"results_{args.tag}.json").write_text(json.dumps({"rows": rows, "items": items}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
