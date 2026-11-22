"""Fetch the audit's 16 household plans from this fix's own server on :8034 (with AI) into ./plans, then run the
audit's recompute on them. Usage: get_plans_8034.py"""
import json, sys, runpy
from pathlib import Path
HERE = Path(__file__).parent
A = HERE.parent / "round1_A"
sys.path.insert(0, str(A))
import get_plans as G
G.URL = "http://127.0.0.1:8034"
OUT = HERE / "plans"
OUT.mkdir(exist_ok=True)
for n, prof in G.H.items():
    ev = G.post(prof)
    (OUT / (n + ".json")).write_text(json.dumps({"profile": prof, "events": ev}, indent=1), encoding="utf-8")
    plan = [e for e in ev if e.get("type") == "plan"]
    print(n, "plan" if plan else "NOPLAN", flush=True)
