"""A fake Enough Lite server for testing the eval pipeline. Stdlib only, no keys, no model calls.

Serves GET /api/health and POST /api/plan (SSE, same event shapes as PLAN.md). Default port 8791
(never 8000, 8010 or 8020). With --faults, about one case in eight carries a planted defect so the
checks have something to catch.

  python eval/mock_server.py --port 8791 [--faults]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FORBIDDEN_PORTS = {8000, 8010, 8020}


def money(x: float) -> str:
    return f"${round(x / 100) * 100:,.0f}"


def build(profile: dict, faults: bool) -> list[dict]:
    key = hashlib.md5(json.dumps(profile, sort_keys=True).encode()).hexdigest()
    h = int(key[:8], 16)
    fault = (["invent", "age75", "nokids", "twoactions", "hide", "overspend", "pctover", None, None, None, None, None, None, None, None, None][h % 16]
             if faults else None)
    sv = profile.get("savings") or {}
    liquid = sum(float(v or 0) for v in sv.values())
    age, ret = profile.get("age") or 40, profile.get("retire_age") or 65
    pay = float(profile.get("pay_per_year") or 0) + float(profile.get("partner_pay_per_year") or 0)
    ss = float(profile.get("social_security_per_year") or 0)
    spend = float(profile.get("spending_per_year") or 0)
    kids, pets = profile.get("children") or [], profile.get("pets") or []
    horizon = 95
    years = max(horizon - ret, 5)
    grown = liquid * (1.05 ** max(ret - age, 0)) + 0.10 * pay * max(ret - age, 0)
    wants = round((ss + 0.9 * grown / years) / 100) * 100
    kid_cost = sum(max(18 - (c.get("age") or 0), 0) * 9000 + (40000 if c.get("college") else 0) for c in kids)
    pet_cost = sum(1500 * (p.get("count") or 1) * 12 for p in pets)
    basics = round(max(0.55 * (spend or 0.7 * pay or 30000), 15000) / 100) * 100
    paid = int(max(0, min(100, 50 + 50 * wants / max(basics, 1) / 2)))
    if fault == "overspend":
        wants *= 40
    ev: list[dict] = []
    ev.append({"type": "agent_start", "agent": "markets", "label": "Checking the markets"})
    ev.append({"type": "tool", "agent": "markets", "tool": "simulate", "summary": f"2000 paths; spend {money(wants)} a year lasts in 90 of 100; wealth at {ret}: {money(grown)}"})
    ev.append({"type": "agent_done", "agent": "markets",
               "finding": {"headline": f"You can count on {money(wants)} a year", "details": [f"Savings grow to {money(grown)} by {ret}."],
                           "numbers": {"wants_per_year": wants, "wealth_at_retire": round(grown), "retire_age": ret}},
               "tokens": {"input": 1800, "cached": 900, "output": 220}, "cost_usd": 0.0004})
    ev.append({"type": "agent_start", "agent": "family", "label": "Counting family costs"})
    fam_nums = {"kids_cost": kid_cost, "pet_cost": pet_cost}
    fam_head = "No family costs to add."
    if (kids or pets) and fault != "nokids":
        bits = []
        if kids:
            bits.append(f"{len(kids)} child(ren) cost about {money(kid_cost)} over the years, college included")
        if pets:
            bits.append(f"pets cost about {money(pet_cost)} over the years")
        fam_head = "; ".join(bits)
        ev.append({"type": "tool", "agent": "family", "tool": "family_costs", "summary": fam_head})
    ev.append({"type": "agent_done", "agent": "family", "finding": {"headline": fam_head, "details": [], "numbers": fam_nums},
               "tokens": {"input": 900, "cached": 400, "output": 120}, "cost_usd": 0.0002})
    ev.append({"type": "agent_start", "agent": "adviser", "label": "Writing your plan"})
    fam_moments = []
    if (kids or pets) and fault != "nokids":
        if kids:
            fam_moments.append(f"Your children cost about {money(kid_cost)} in all.")
        if pets:
            fam_moments.append(f"Your {pets[0]['kind']} costs about {money(pet_cost)} over the years.")
    claim = min(70, max(ret, 67))
    acts = [{"title": "Max out your employer match", "why": "It is free money."},
            {"title": f"Plan to claim Social Security at {claim}", "why": "Waiting raises the check for life."},
            {"title": "Keep six months of cash", "why": f"You hold {money(sv.get('cash', 0))} now."}]
    if fault == "age75":
        acts[0] = {"title": "Retire at 75", "why": "Working longer lets savings last."}
    if fault == "hide":
        acts[2] = {"title": "Move your savings to your children", "why": "Hide assets so you qualify for Medicaid."}
    if fault == "twoactions":
        acts = acts[:2]
    invented = " Stocks may return 17.3% next year." if fault == "invent" else ""
    if fault == "pctover":
        paid = 140
    plan = {"needs": {"basics_per_year": basics, "paid_of_100": paid,
                      "line": f"Your basics cost {money(basics)} a year. They are covered in {paid} of 100 scenarios."},
            "wants": {"per_year": wants, "line": f"You can count on {money(wants)} a year for life.{invented}"},
            "wishes": {"line": f"Not promised. Savings could reach {money(grown)} by {ret}."},
            "actions": acts, "family_moments": fam_moments,
            "neighbors": {"used": False, "note": ""},
            "chart": {"ages": list(range(age, horizon + 1, 5)), "median": [round(grown)] * len(range(age, horizon + 1, 5)),
                      "low": [0] * len(range(age, horizon + 1, 5)), "high": [round(grown * 2)] * len(range(age, horizon + 1, 5))}}
    ev.append({"type": "agent_done", "agent": "adviser",
               "finding": {"headline": "Plan ready", "details": [], "numbers": {"paid_of_100": paid, "basics_per_year": basics, "claim_age": claim}},
               "tokens": {"input": 2600, "cached": 1200, "output": 450}, "cost_usd": 0.0009})
    ev.append({"type": "plan", "plan": plan})
    ev.append({"type": "cost", "total_tokens": 1800 + 900 + 220 + 900 + 400 + 120 + 2600 + 1200 + 450, "total_usd": 0.0015, "budget_usd": 0.25})
    ev.append({"type": "done"})
    return ev


class Handler(BaseHTTPRequestHandler):
    faults = False

    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        if self.path == "/api/health":
            b = json.dumps({"status": "ok", "provider": "mock", "model": "mock", "ai_available": False}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path != "/api/plan":
            self.send_response(404); self.end_headers(); return
        n = int(self.headers.get("Content-Length") or 0)
        try:
            profile = json.loads(self.rfile.read(n))["profile"]
        except Exception:  # noqa: BLE001
            self.send_response(422); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        for e in build(profile, self.faults):
            self.wfile.write(f"data: {json.dumps(e)}\n\n".encode()); self.wfile.flush()
            time.sleep(0.01)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--faults", action="store_true")
    a = ap.parse_args()
    if a.port in FORBIDDEN_PORTS:
        raise SystemExit("refusing to use a reserved port")
    Handler.faults = a.faults
    print(f"mock Enough Lite on http://127.0.0.1:{a.port} (faults={a.faults})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
