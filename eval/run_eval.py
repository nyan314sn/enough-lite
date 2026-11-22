"""Run cases against the lite app: POST /api/plan, read the SSE stream to the end, save eval/runs/<id>.json.

Resumable (finished cases are skipped), at most 3 workers, --limit, a dollar stop (--max-usd).
The app is never started or stopped here; give its address with --url.

Examples
  python eval/run_eval.py --url http://127.0.0.1:8791 --limit 3        (against the mock)
  python eval/run_eval.py --kinds base --workers 3                       (the real app, base cases)
  python eval/run_eval.py --header X-Enough-Test=1 --workers 3 --max-usd 3   (the live app in test mode)
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DEFAULT_URL, RUNS_DIR, load_cases, load_run, run_path, usage_of  # noqa: E402

_lock = threading.Lock()
_spent = {"usd": 0.0}


def post_plan(url: str, profile: dict, headers: dict, timeout: float) -> tuple[list[dict], str | None]:
    """POST /api/plan and read the whole SSE stream. Returns (events, error)."""
    body = json.dumps({"profile": profile}).encode()
    h = {"Content-Type": "application/json", "Accept": "text/event-stream", **headers}
    req = urllib.request.Request(url.rstrip("/") + "/api/plan", data=body, headers=h, method="POST")
    events: list[dict] = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            buf: list[str] = []
            for raw in resp:
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if line == "":
                    _flush(buf, events)
                    buf = []
                elif line.startswith("data:"):
                    buf.append(line[5:].lstrip())
            _flush(buf, events)
    except urllib.error.HTTPError as e:
        return events, f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
    except Exception as e:  # noqa: BLE001
        return events, f"{type(e).__name__}: {e}"
    return events, None


def _flush(buf: list[str], events: list[dict]) -> None:
    if not buf:
        return
    try:
        events.append(json.loads("\n".join(buf)))
    except json.JSONDecodeError:
        events.append({"type": "unparsed", "raw": "\n".join(buf)[:500]})


def run_case(case: dict, args, headers: dict) -> dict:
    t0 = time.time()
    events, err = [], None
    for attempt in range(args.retries + 1):
        # one session per case: the app caps each session (about $0.50), and the eval's cost is read back by session in usage.jsonl
        sid = "eval-" + "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in case["id"])[:55]
        events, err = post_plan(args.url, case["profile"], {**headers, "X-Session-Id": sid}, args.timeout)
        if err and err.startswith("HTTP 429"):
            time.sleep(5 * (attempt + 1))
            continue
        break
    elapsed = round(time.time() - t0, 2)
    types = [e.get("type") for e in events]
    if err is None and "error" in types:
        err = "; ".join(e.get("message", "") for e in events if e.get("type") == "error")[:300]
    ok = err is None and "plan" in types and "done" in types
    rec = {"id": case["id"], "kind": case.get("kind", "base"), "base_id": case.get("base_id", case["id"]),
           "status": "ok" if ok else "error", "error": err, "elapsed_s": elapsed,
           "started": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t0)),
           "url": args.url, "profile": case["profile"], "events": events}
    rec["usage"] = usage_of(rec)
    tmp = run_path(case["id"]).with_suffix(".tmp")
    tmp.write_text(json.dumps(rec), encoding="utf-8")
    tmp.replace(run_path(case["id"]))
    with _lock:
        _spent["usd"] += rec["usage"]["usd"]
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="run at most N not-yet-done cases")
    ap.add_argument("--kinds", default="base,savings_up,retire_later")
    ap.add_argument("--ids", default="", help="comma list of case ids to run")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--max-usd", type=float, default=8.0, help="stop starting new cases past this total")
    ap.add_argument("--redo-errors", action="store_true", help="re-run cases whose saved run has status error")
    ap.add_argument("--force", action="store_true", help="re-run everything chosen")
    ap.add_argument("--header", action="append", default=[], help="K=V header, repeatable")
    args = ap.parse_args()
    args.workers = max(1, min(3, args.workers))
    headers = dict(h.split("=", 1) for h in args.header)

    RUNS_DIR.mkdir(exist_ok=True)
    cases = load_cases(set(args.kinds.split(",")))
    if args.ids:
        want = set(args.ids.split(","))
        cases = [c for c in cases if c["id"] in want]
    todo = []
    for c in cases:
        r = None if args.force else load_run(c["id"])
        if r and (r.get("status") == "ok" or (r.get("status") == "error" and not args.redo_errors)):
            continue
        todo.append(c)
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(cases)} cases chosen, {len(todo)} to run, {args.workers} workers, {args.url}")
    if not todo:
        return 0

    done = fails = 0
    stop = False
    with ThreadPoolExecutor(args.workers) as ex:
        futs = {}
        it = iter(todo)
        def submit():
            c = next(it, None)
            if c is not None:
                futs[ex.submit(run_case, c, args, headers)] = c["id"]
        for _ in range(args.workers):
            submit()
        while futs:
            for f in as_completed(list(futs)):
                cid = futs.pop(f)
                r = f.result()
                done += 1
                fails += r["status"] != "ok"
                u = r["usage"]
                print(f"[{done}/{len(todo)}] {cid} {r['status']} {r['elapsed_s']}s tokens={u['total_tokens']} ${u['usd']:.4f}"
                      + (f"  ERR {r['error']}" if r["error"] else ""), flush=True)
                if _spent["usd"] >= args.max_usd and not stop:
                    stop = True
                    print(f"spend ${_spent['usd']:.2f} reached --max-usd; no new cases", flush=True)
                if not stop:
                    submit()
                break
    print(f"finished: {done - fails} ok, {fails} errors, ${_spent['usd']:.4f} spent this session")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
