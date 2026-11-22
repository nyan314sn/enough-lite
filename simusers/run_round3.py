"""Round 3 simulated-user test: 40 original personas + 8 hard ones, 3 to 5 plan-chat turns each, plan chat judged too.
Reuses run_sims.py, judge.py, report.py, common.py unchanged (patched at run time). Outputs go to simusers/round3/.

Usage: python run_round3.py --url http://127.0.0.1:8074 [--stage run|judge|report|all] [--ids h01,p01] [--workers 4] [--stop-usd 3]
"""
import argparse
import inspect
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import common

HERE = Path(__file__).resolve().parent
OUT = HERE / "round3"
RUNS2, JUDGED2 = OUT / "runs", OUT / "judged"
RUNS2.mkdir(parents=True, exist_ok=True)
JUDGED2.mkdir(parents=True, exist_ok=True)
common.RUNS, common.JUDGED, common.USAGE_FILE = RUNS2, JUDGED2, OUT / "usage.json"


def all_personas():
    ps = json.loads((HERE / "personas.json").read_text(encoding="utf-8"))
    hp = HERE / "personas_hard.json"
    if hp.exists():
        ps += json.loads(hp.read_text(encoding="utf-8"))
    return ps


common.load_personas = all_personas
import run_sims  # noqa: E402
import judge  # noqa: E402

run_sims.RUNS, run_sims.load_personas = RUNS2, all_personas
judge.RUNS, judge.JUDGED, judge.load_personas = RUNS2, JUDGED2, all_personas


def plan_intents2(p, rng):
    """3 to 5 plan-chat messages: What Ifs and questions; a correction when the persona has one."""
    asks = p.get("plan_asks") or []
    intents = []
    if asks:
        for a in asks[:2]:
            intents.append(("whatif", f"Ask this What If in your own words: {a}"))
        for a in asks[2:]:
            intents.append(("question", f"Ask about this, in your personality: {a}"))
        return intents[:5]
    intents.append(("whatif", "Test a What If that fits your goal (retire at a different age, save more, spend a set amount, pay off a debt)."))
    intents.append(("whatif", "Test a second, different What If."))
    intents.append(("question", "Ask one question about the plan or its numbers, in your personality."))
    if rng.random() < 0.6:
        intents.append(("question", "Ask a different follow-up, e.g. what to do first, or about risk."))
    if rng.random() < 0.3:
        intents.append(("question", "Ask what the plan assumes about you."))
    return intents


# allow up to 12 plan-chat turns (the original stops at 6, too few once confirmations are counted)
src = inspect.getsource(run_sims.run_persona).replace("n < 6", "n < 12")
exec(compile(src, "run_sims_patched", "exec"), run_sims.__dict__)
run_sims.plan_intents = plan_intents2

ADD = """
PLAN-CHAT TURNS (phase plan, refs a1, a2 ...) also count. For these judge: (1) correct figures: any dollar figure, age or percentage the app quotes must be consistent with the person's situation and with earlier turns; (2) dead ends: a reply that answers nothing or ignores the question (including 'From the source' quotes that do not answer it); (3) changes made without confirmation: KIND/status 'applied' on a turn where the person only asked a question or a What If, or an applied change when the person had not confirmed, is a P0 misunderstanding; a proposal (status pending/confirm) is fine; (4) a What If must answer the question asked (a changed result or a plain reason it cannot), and must not change the wrong input; the baseline plan must remain unchanged by a What If. A What If that applies the wrong number (e.g. retire age 62 when asked 64) is P0."""
judge.SYSTEM = judge.SYSTEM + ADD


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--stage", default="all")
    ap.add_argument("--ids")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--stop-usd", type=float, default=3.0)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    run_sims.APP = a.url.rstrip("/")
    run_sims.STOP["usd"] = a.stop_usd
    ps = all_personas()
    if a.ids:
        want = set(a.ids.split(","))
        ps = [p for p in ps if p["id"] in want]
    if a.stage in ("run", "all"):
        def go(p):
            print(p["id"], p["name"], run_sims.run_persona(p, a.force), flush=True)
        with ThreadPoolExecutor(a.workers) as ex:
            list(ex.map(go, ps))
    if a.stage in ("judge", "all"):
        def gj(p):
            print(p["id"], judge.judge_one(p, a.force), flush=True)
        with ThreadPoolExecutor(a.workers) as ex:
            list(ex.map(gj, ps))
    if a.stage in ("report", "all"):
        import report
        report.RUNS, report.JUDGED, report.HERE, report.load_personas, report.APP = RUNS2, JUDGED2, OUT, all_personas, run_sims.APP
        report.main()
    print({k: v["usd"] for k, v in common.usage_cost().items()})


if __name__ == "__main__":
    main()
