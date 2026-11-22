"""A small live sample, one plan at a time, on a quiet app: AI text jargon (R18) and plan time and fallbacks (R23).

    python eval/jargon_sample.py --url http://127.0.0.1:8102 --n 20 --out <file.json>

Plans run one after another, so the times are those of a single user. Nothing is written to eval/runs.
Start the app with ENOUGH_TEST_MODE=1 and send the header X-Enough-Test: 1 (this script does).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

import common  # noqa: E402
import run_eval  # noqa: E402
from tests import test_product_rules as rules  # noqa: E402

FIRST = ["S051", "S133", "S147"]      # the three cases that left jargon in the first live run


def texts_of(plan: dict, events: list[dict]) -> list[str]:
    out = [" ".join([(plan.get("needs") or {}).get("line", ""), (plan.get("wants") or {}).get("line", ""), (plan.get("wishes") or {}).get("line", "")]
                    + [a.get("title", "") + " " + a.get("why", "") for a in plan.get("actions") or []])]
    for e in events:
        if e.get("type") == "agent_done":
            f = e.get("finding") or {}
            out.append(" ".join([f.get("headline") or "", *(f.get("details") or [])]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8102")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cases = {c["id"]: c for c in common.load_cases()}
    base = [i for i, c in cases.items() if c.get("kind", "base") == "base" and i not in FIRST]
    step = max(1, len(base) // max(1, a.n - len(FIRST)))
    ids = FIRST + base[::step][: a.n - len(FIRST)]
    rows = []
    for cid in ids[: a.n]:
        t0 = time.time()
        events, err = run_eval.post_plan(a.url, cases[cid]["profile"], {"X-Enough-Test": "1", "X-Session-Id": "sample-" + cid}, 240)
        secs = round(time.time() - t0, 1)
        plan = next((e["plan"] for e in events if e.get("type") == "plan"), None)
        if not plan:
            rows.append({"id": cid, "error": err or "no plan", "seconds": secs})
            continue
        texts = texts_of(plan, events)
        hits = [h for t in texts for h in rules._bad_words(t, rules.JARGON + rules.HYPE + rules.LATIN)]
        rows.append({"id": cid, "seconds": secs, "text_source": plan.get("text_source"), "hits": hits,
                     "agent_sources": {e["agent"]: (e.get("finding") or {}).get("source", "")[:20] for e in events if e.get("type") == "agent_done"},
                     "usd": sum(e.get("cost_usd") or 0 for e in events if e.get("type") == "agent_done")})
        print(cid, secs, plan.get("text_source"), hits, flush=True)
    Path(a.out).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    ok = [r for r in rows if "error" not in r]
    secs = sorted(r["seconds"] for r in ok)
    fb = [r for r in ok if str(r["text_source"]).startswith("template")]
    print(f"{len(ok)} plans, hits {sum(len(r['hits']) for r in ok)}, adviser template fallbacks {len(fb)}, "
          f"median {secs[len(secs)//2]} s, max {secs[-1]} s, usd {sum(r['usd'] for r in ok):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
