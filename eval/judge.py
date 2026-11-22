"""AI judge: Claude Haiku 5.5 reads a 40-case sample (profile + plan) and rates it
reasonable / questionable / wrong, with one reason. Spend is capped at $1.

Key: ANTHROPIC_API_KEY from the environment or .env in the project folder or the folder above (never printed).
Model: JUDGE_MODEL env var, default claude-haiku-5-5. Prices (per million tokens, prompts up to 100K):
JUDGE_PRICE_IN=0.10 and JUDGE_PRICE_OUT=0.50 by default.
Resumable: ids already in eval/judge_results.json are skipped.

  python eval/judge.py [--n 40] [--seed 409] [--cap-usd 1.0] [--mock]
--mock uses a fake judge (no network, no key) to test the pipeline.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import EVAL_DIR, dig, load_cases, load_project_env, load_run  # noqa: E402

RESULTS = EVAL_DIR / "judge_results.json"
MODEL = os.environ.get("JUDGE_MODEL", "claude-haiku-5-5")
PRICE_IN = float(os.environ.get("JUDGE_PRICE_IN", "0.10")) / 1e6
PRICE_OUT = float(os.environ.get("JUDGE_PRICE_OUT", "0.50")) / 1e6
LABELS = ("reasonable", "questionable", "wrong")

SYSTEM = """You are a careful, fee-only retirement planner reviewing advice an AI tool gave one household.
You get the household profile (JSON) and the plan the tool produced. Money figures are per year in US dollars.
In the plan: "needs" are the basics, with a score of how many of 100 market scenarios pay for them; "wants.per_year" is the
spending the household can count on each year, basics INCLUDED (wants.above_basics_per_year is the part above them; verdict falls_short only when basics are paid in under 90 of 100 scenarios, below_goal when basics are safe but the goal is above what lasts, close within 10% of the goal); "wishes" is what is not promised; there are three actions.
Rate the plan:
- reasonable: a careful planner would sign off on it.
- questionable: plausible, but something is off, thin, or hard to defend.
- wrong: a careful planner would call it unreasonable, unsafe, or contradicted by the profile (for example a figure far
  too high or low for the savings and income, advice that ignores stated children or pets, advice to retire past 70,
  or advice to hide assets).
Reply with JSON only: {"verdict": "reasonable" | "questionable" | "wrong", "reason": "one short sentence"}"""


def compact_plan(plan: dict) -> dict:
    p = {k: v for k, v in (plan or {}).items() if k != "chart"}
    ch = (plan or {}).get("chart") or {}
    ages, med = ch.get("ages") or [], ch.get("median") or []
    if ages and med:
        step = max(1, len(ages) // 6)
        p["chart_median_wealth_by_age"] = {str(a): m for a, m in list(zip(ages, med))[::step]}
    return p


def pick(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    cs = [c for c in load_cases({"base"}) if (r := load_run(c["id"])) and r.get("status") == "ok" and dig(r)["plan"]]
    rng.shuffle(cs)
    by: dict = {}
    for c in cs:
        by.setdefault(tuple(c["stratum"].values()), []).append(c)
    out, groups = [], list(by.values())
    while len(out) < n and any(groups):
        for g in groups:
            if g and len(out) < n:
                out.append(g.pop())
    return out


def parse(text: str) -> tuple[str, str]:
    m = re.search(r"\{.*\}", text, re.S)
    try:
        j = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        j = {}
    v = str(j.get("verdict", "")).lower().strip()
    if v not in LABELS:
        v = next((l for l in LABELS if l in text.lower()), "unparsed")
    return v, str(j.get("reason", text[:200])).strip()


def fake_judge(case: dict, plan: dict) -> tuple[str, str, int, int]:
    w = (plan.get("wants") or {}).get("per_year") or 0
    spend = case["profile"].get("spending_per_year") or 0
    v = "reasonable" if w >= 0.8 * spend else "questionable"
    return v, "mock judge: compared wants with the spending goal", 1500, 40


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=409)
    ap.add_argument("--cap-usd", type=float, default=1.0)
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    cap = min(a.cap_usd, 1.0)

    done = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {"items": {}, "usd": 0.0, "model": MODEL}
    if a.mock:
        done = {"items": {}, "usd": 0.0, "model": "mock"}
    client = None
    if not a.mock:
        load_project_env()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY not set (environment, or .env in the project folder or the folder above)")
            return 2
        import anthropic
        client = anthropic.Anthropic()
    sample = pick(a.n, a.seed)
    print(f"judging {len(sample)} cases with {done['model'] if a.mock else MODEL}, cap ${cap:.2f}")
    for c in sample:
        if c["id"] in done["items"]:
            continue
        plan = dig(load_run(c["id"]))["plan"]
        if done["usd"] + 0.01 > cap:     # one call costs well under a cent; keep a safety margin
            print(f"cap reached at ${done['usd']:.4f}; stopping")
            break
        if a.mock:
            v, reason, tin, tout = fake_judge(c, plan)
        else:
            prompt = "PROFILE\n" + json.dumps(c["profile"]) + "\n\nPLAN\n" + json.dumps(compact_plan(plan))
            kw = dict(model=MODEL, max_tokens=400, system=SYSTEM, messages=[{"role": "user", "content": prompt}])
            try:
                r = client.messages.create(thinking={"type": "disabled"}, **kw)
            except anthropic.BadRequestError:
                r = client.messages.create(**kw)
            text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
            v, reason = parse(text)
            tin, tout = r.usage.input_tokens, r.usage.output_tokens
        usd = tin * PRICE_IN + tout * PRICE_OUT
        done["usd"] += usd
        done["items"][c["id"]] = {"verdict": v, "reason": reason, "input_tokens": tin, "output_tokens": tout,
                                  "usd": usd, "label": c["label"]}
        print(f"  {c['id']}: {v} - {reason[:90]}")
        if not a.mock:
            RESULTS.write_text(json.dumps(done, indent=1), encoding="utf-8")
    out = EVAL_DIR / ("judge_results_mock.json" if a.mock else "judge_results.json")
    out.write_text(json.dumps(done, indent=1), encoding="utf-8")
    cnt = {l: sum(1 for x in done["items"].values() if x["verdict"] == l) for l in (*LABELS, "unparsed")}
    print(f"verdicts {cnt}; judge spend ${done['usd']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
