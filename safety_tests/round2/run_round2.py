"""Runs attacks_round2.jsonl with the existing kit's judge, without changing the kit.

Usage (a later round, against a running server):
  python safety_tests\\round2\\run_round2.py [BASE_URL] [--dry-run] [--timeout S] [--ids R2-0*]
It points run_attacks at attacks_round2.jsonl, writes round2_results.jsonl and round2_summary.md next to the kit, drops the
"every category has a case" rule, and adds three optional case keys: plan_override, raw_body and extra_headers.
--dry-run only validates the file (no server, no AI).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
sys.path.insert(0, str(KIT))
import run_attacks as kit  # noqa: E402

kit.CORPUS = KIT / "attacks_round2.jsonl"
_validate = kit.validate


def validate(cases):
    return [e for e in _validate(cases) if not e.startswith("no cases in category")]


kit.validate = validate
_build_body = kit.build_body
_http = kit.http
_current = {}


_BASE_HEADERS = {}


def build_body(case, profile=None, pending=None):
    if not _BASE_HEADERS:
        _BASE_HEADERS.update(kit.EXTRA_HEADERS)
    kit.EXTRA_HEADERS.clear()
    kit.EXTRA_HEADERS.update(_BASE_HEADERS)
    kit.EXTRA_HEADERS.update(case.get("extra_headers", {}))
    if case.get("raw_body") is not None:
        _current["body"] = case["raw_body"]
        return case["raw_body"]
    body = _build_body(case, profile, pending)
    if case.get("plan_override") is not None:
        body["plan"] = case["plan_override"]
    return body


def http(method, url, body=None, timeout=60):
    # a string body is sent as it is (NaN, Infinity); other bodies as JSON
    if isinstance(body, str):
        import time
        import urllib.error
        import urllib.request
        req = urllib.request.Request(url, data=body.encode(), method=method, headers={"Content-Type": "application/json", **kit.EXTRA_HEADERS})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw, status = r.read(), r.status
        except urllib.error.HTTPError as e:
            try:
                raw = e.read()
            except OSError:     # the server closed the connection while sending its 413
                raw = b""
            status = e.code
        except Exception as e:  # noqa: BLE001
            return {"status": 0, "json": None, "raw": f"{type(e).__name__}: {e}", "secs": round(time.time() - t0, 2)}
        text = raw.decode("utf-8", "replace")
        try:
            js = json.loads(text)
        except ValueError:
            js = None
        return {"status": status, "json": js, "raw": text, "secs": round(time.time() - t0, 2)}
    return _http(method, url, body, timeout)


kit.build_body = build_body
kit.http = http

if __name__ == "__main__":
    if "--out" not in sys.argv:
        sys.argv += ["--out", "round2_"]
    kit.main()
