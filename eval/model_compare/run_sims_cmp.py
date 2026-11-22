"""Simulated users through one app, then judge them. Output stays in eval/model_compare/raw/sims_<arm>/.
  run_sims_cmp.py --arm anthropic --url http://127.0.0.1:8041 [--n 24] [--workers 3]"""
import argparse, json, sys, os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
HERE = Path(__file__).resolve().parent
SIM = HERE.parents[1] / "simusers"
sys.path.insert(0, str(SIM))
ap = argparse.ArgumentParser(); ap.add_argument("--arm", required=True); ap.add_argument("--url", required=True)
ap.add_argument("--n", type=int, default=24); ap.add_argument("--workers", type=int, default=3); ap.add_argument("--stop-usd", type=float, default=1.2)
a = ap.parse_args()
import common as sc
base = HERE / "raw" / f"sims_{a.arm}"; (base / "runs").mkdir(parents=True, exist_ok=True); (base / "judged").mkdir(exist_ok=True)
sc.RUNS, sc.JUDGED, sc.USAGE_FILE = base / "runs", base / "judged", base / "usage.json"
import run_sims, judge
run_sims.RUNS = sc.RUNS; run_sims.APP = a.url.rstrip("/"); run_sims.STOP["usd"] = a.stop_usd
judge.RUNS, judge.JUDGED = sc.RUNS, sc.JUDGED
ps = json.load(open(SIM / "personas.json", encoding="utf-8"))
hard = json.load(open(SIM / "personas_hard.json", encoding="utf-8"))
sel = ps[::2][: a.n - 4] + hard[:4]
print(len(sel), "personas:", [p["id"] for p in sel], flush=True)
def go(p):
    s = run_sims.run_persona(p, False)
    print(p["id"], s, flush=True)
with ThreadPoolExecutor(a.workers) as ex: list(ex.map(go, sel))
def jg(p):
    print("judge", p["id"], judge.judge_one(p, False), flush=True)
with ThreadPoolExecutor(a.workers) as ex: list(ex.map(jg, sel))
print("usage", sc.usage_cost())
