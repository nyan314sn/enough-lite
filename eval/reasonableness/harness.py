"""Reasonableness audit of the plan engine: tools only, no model call, no token cost.

For each baseline (the 300 base cases in eval/cases.jsonl and the 15 admin sample households) this builds the plan the
way the app does (pipeline.prepare, then pipeline.run_plan with use_ai=False), then about 20 one-change variations:

- What Ifs go through the plan chat's own path (pipeline.parse_whatif on the words, pipeline.apply_whatif, then
  run_plan with the base plan's kept strategy, pipeline.kept_for), exactly as pipeline.ask does;
- changes of an answer (pay, savings, a debt, a pension, a mortgage, spending now) go through the "change" path
  (ask_intent._apply_change, then a fresh plan), exactly as ask_intent.pending_step does.

Every run uses the simulation's fixed seed (simulate.SEED) and the same horizon, so the baseline and each variation see
the same 2,000 market paths (common random numbers): differences are the change, not noise.

Usage (from the project root):
  python eval/reasonableness/harness.py --tag before --workers 4
  python eval/reasonableness/harness.py --tag after --workers 4 --limit 20
Writes eval/reasonableness/results_<tag>.jsonl (one line per baseline). check.py reads it.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# REASON_APP_ROOT: a folder holding another copy of app/ (the code before the fixes), for the "before" run
sys.path.insert(0, os.environ.get("REASON_APP_ROOT") or str(ROOT))
# no model, no run log, no key: the harness never spends a token
for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "PORTKEY_API_KEY"):
    os.environ[k] = ""
os.environ["ENOUGH_RUN_LOG"] = "0"
os.environ["ENOUGH_TEST_MODE"] = "0"


def load_baselines() -> list[dict]:
    out = []
    with open(ROOT / "eval" / "cases.jsonl", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if c.get("kind") == "base":
                out.append({"id": c["id"], "label": c.get("label", ""), "source": "cases", "profile": c["profile"]})
    from app import samples
    for h in samples.load():
        out.append({"id": "sample:" + h["id"], "label": h["name"], "source": "samples", "profile": h["intake"]["profile"]})
    return out


# ------------------------------------------------------------------ figures read from a plan
def figures(plan: dict, ctx) -> dict:
    m = ctx.results["markets"]
    ms = ctx.results.get("money") or {}
    a = plan.get("analysis") or {}
    hs = (a.get("how_sure") or {}).get("levels")
    return {
        "count_on": float(plan["wants"]["per_year"]),
        "basics_paid": plan["needs"]["paid_of_100"],
        "basics_per_year": float(plan["needs"]["basics_per_year"]),
        "goal": float(plan["spending_goal"] or 0),
        "goal_lasts": m.get("goal_lasts_of_100"),
        "verdict": plan["verdict"],
        "claim_age": plan["claim_age"],
        "partner_claim_age": plan["partner_claim_age"],
        "already_claiming": plan["already_claiming"],
        "ss_per_year": float(plan.get("social_security_per_year") or 0),
        "retire_age": plan["retire_age"],
        "horizon_age": plan["horizon_age"],
        "strategy": m.get("strategy"),
        "strategy_source": ((plan.get("neighbors") or {}).get("chosen") or {}).get("source"),
        "save_now": ms.get("save_now"),
        "median_at_retirement": m.get("median_at_retirement"),
        "stock_share_now": m.get("stock_share_now"),
        "headline": plan["headline"] + (" " + plan["headline_why"] if plan.get("headline_why") else ""),
        "how_sure": [x["per_year"] for x in hs] if hs else None,
        "starting_points": len(plan.get("starting_points") or []),
        "chart_min": min([*plan["chart"]["low"], *plan["chart"]["median"]], default=0),
        "bad_numbers": bad_numbers(plan),
    }


def bad_numbers(x, path="plan", out=None, depth=0):
    """Paths to NaN, infinite or negative money figures in the plan (a few keys may be negative by design)."""
    out = [] if out is None else out
    if depth > 8 or len(out) > 10:
        return out
    if isinstance(x, dict):
        for k, v in x.items():
            bad_numbers(v, f"{path}.{k}", out, depth + 1)
    elif isinstance(x, list):
        for i, v in enumerate(x[:200]):
            bad_numbers(v, f"{path}[{i}]", out, depth + 1)
    elif isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        out.append(path)
    elif isinstance(x, (int, float)) and not isinstance(x, bool) and x < 0:
        name = path.lower()
        # changes and differences are signed by design
        if not any(s in name for s in ("change", "delta", "diff", "save_now", "surplus", "offset", "gap", "saving.per_year", "unspent_pay", "-1")):
            out.append(f"{path}={x}")
    return out


# ------------------------------------------------------------------ the variations
def variations(p) -> list[dict]:
    """One change each. kind 'whatif' = words through the plan chat; kind 'change' = facts through the answers path.
    expect: 'up' (never lowers count_on / basics beyond noise), 'down' (never raises), None (report only)."""
    from app.tools import costs
    age, ra = int(p.age or 45), int(p.retire_age or 65)
    working = ra > age and p.household_pay() > 0
    retired = ra <= age
    goal = float(p.spending_per_year or 0)
    out = []
    sv = p.savings
    tot = sv.total
    if tot > 0:
        for pct in (-50, -25, 25, 50):
            f = 1 + pct / 100
            out.append({"name": f"savings {pct:+d}%", "kind": "change", "expect": "up" if pct > 0 else "down",
                        "facts": {"savings.pretax": sv.pretax * f, "savings.roth": sv.roth * f, "savings.taxable": sv.taxable * f,
                                  "savings.cash": sv.cash * f}})
    out.append({"name": "savings +$100k", "kind": "change", "expect": "up",
                "facts": {"savings.pretax": sv.pretax, "savings.roth": sv.roth, "savings.taxable": sv.taxable + 100_000,
                          "savings.cash": sv.cash}})
    if working:
        for pct in (-20, 20):
            f = 1 + pct / 100
            facts = {"pay_per_year": round((p.pay_per_year or 0) * f)}
            if p.has_partner and (p.partner_pay_per_year or 0) > 0:
                facts["partner_pay_per_year"] = round(p.partner_pay_per_year * f)
            out.append({"name": f"pay {pct:+d}%", "kind": "change", "expect": "up" if pct > 0 else "down", "facts": facts})
    if not retired:
        for d in (-3, -1, 1, 3):
            x = ra + d
            if x > 70 or x <= age:
                continue
            out.append({"name": f"retire {d:+d}", "kind": "whatif", "expect": "up" if d > 0 else "down",
                        "text": f"What if I retire at {x}", "want": "retire_age", "value": x})
    if goal > 0:
        for pct in (20, 10):
            out.append({"name": f"spend retired -{pct}%", "kind": "whatif", "expect": "up_basics",
                        "text": f"What if I spend {pct}% less", "want": "spending_per_year"})
        for pct in (10, 20):
            out.append({"name": f"spend retired +{pct}%", "kind": "whatif", "expect": "down_basics",
                        "text": f"What if I spend ${round(goal * pct / 100):,} a year more", "want": "spending_per_year"})
    if working and (p.spending_now_per_year or 0) > 0:
        out.append({"name": "spend now +10%", "kind": "change", "expect": "down",
                    "facts": {"spending_now_per_year": round(p.spending_now_per_year * 1.1)}})
    for r in ("careful", "growth"):
        if (p.risk or "balanced") != r:
            out.append({"name": f"risk {r}", "kind": "whatif", "expect": None, "text": f"What if I choose a {r} mix", "want": "risk"})
    if p.home.owns and p.home.mortgage_balance <= 0:
        # a retiree's stated spending holds the mortgage and falls when it ends (costs.family_side): no direction to expect
        out.append({"name": "add $300k mortgage", "kind": "change", "expect": "down" if not retired else None,
                    "facts": {"home.owns": True, "home.mortgage_balance": 300_000.0, "home.has_mortgage": True}})
    if p.home.owns and p.home.mortgage_balance > 0 and tot >= p.home.mortgage_balance:
        out.append({"name": "pay off mortgage", "kind": "whatif", "expect": None, "text": "What if I pay off the mortgage", "want": "pay_off"})
    card = next((d for d in p.debts if d.kind == "credit_card"), None)
    # $30,000 more on cards at 22%, paid off over the standard 5 years, on top of any card debt and its payment
    new_pay = costs.standard_payment(30_000.0, 0.22, costs.TERM_YEARS["credit_card"])
    out.append({"name": "add $30k card debt", "kind": "change", "expect": "down",
                "facts": {"debts": [{"kind": "credit_card", "balance": 30_000.0 + (card.balance if card else 0),
                                     "rate": (card.rate or 0.22) if card else 0.22,
                                     "monthly_payment": round(new_pay + ((card.monthly_payment or 0) if card else 0), 2)}]}})
    hi = [d for d in p.debts if d.balance > 0 and (d.rate or 0) >= costs.HIGH_RATE]
    if hi and tot >= sum(d.balance for d in hi):
        out.append({"name": "pay off high-rate debt", "kind": "whatif", "expect": "up", "text": "What if I pay off my high-rate debt", "want": "pay_off"})
    if not any(x.who == "you" for x in p.pensions):
        out.append({"name": "add $20k pension", "kind": "change", "expect": "up",
                    "facts": {"pensions": [{"who": "you", "per_year": 20_000.0, "start_age": max(ra, age)}]}})
    if not retired and age <= 50:
        out.append({"name": "add a child", "kind": "whatif", "expect": "down", "text": "What if we have another child", "want": "children"})
    if p.has_partner and p.partner_age and (p.partner_pay_per_year or 0) > 0 and (p.partner_retire_age or 65) > p.partner_age:
        out.append({"name": "partner stops work", "kind": "whatif", "expect": "down", "text": "What if my partner stops working",
                    "want": "partner_retire_age"})
    return out


def claim_variation(p, fig: dict) -> dict | None:
    """Claim Social Security when you retire (62 at the earliest, 70 at the latest) instead of at the plan's age."""
    if fig["already_claiming"] or fig["claim_age"] is None or fig["ss_per_year"] <= 0:
        return None
    age, ra = int(p.age or 45), int(p.retire_age or 65)
    x = min(70, max(62, ra, age))
    if x == fig["claim_age"]:
        return None
    return {"name": "claim at retirement", "kind": "whatif", "expect": None, "text": f"What if I claim Social Security at {x}",
            "want": "claim_age", "value": x}


# ------------------------------------------------------------------ running one baseline
async def _run(profile, fixed=None, shock=None, options=False):
    from app import pipeline
    from app.agents.base import RunCtx
    ctx = RunCtx(profile=profile, use_ai=False, options=options, fixed=fixed, shock=shock)
    plan = await pipeline.run_plan(ctx)
    return plan, ctx


async def one_variation(v: dict, raw: dict, base, old_ctx, fresh: bool) -> dict:
    from app import ask_intent, pipeline
    from app.schemas import Profile
    rec = {"name": v["name"], "kind": v["kind"], "expect": v["expect"]}
    if v["kind"] == "whatif":
        ch = pipeline.parse_whatif(v["text"], base)
        rec["parsed"] = {k: val for k, val in ch.items() if not k.startswith("_")}
        if ch.get("_say"):
            rec.update(status="refused", why=ch["_say"][:160])
            return rec
        if v.get("want") and v["want"] not in ch:
            rec.update(status="parse_miss", why=f"{v['want']} not in {sorted(ch)}")
            return rec
        if pipeline._same_as_plan(ch, base):
            rec.update(status="same_as_plan")
            return rec
        newp, notes = pipeline.apply_whatif(base, ch)
        if notes.get("_say"):
            rec.update(status="refused", why=notes["_say"][:160])
            return rec
        plan, ctx = await _run(newp, fixed=pipeline.kept_for(ch, old_ctx), shock=ch.get("shock"))
        rec["fig"] = figures(plan, ctx)
        if fresh:
            # the same changed profile built as a fresh plan (what "change my answers" would give)
            p2, c2 = await _run(pipeline.prepare(newp.model_dump()))
            rec["fresh"] = {k: figures(p2, c2)[k] for k in ("count_on", "basics_paid", "verdict", "claim_age", "strategy_source")}
    else:
        facts = ask_intent.checked_pending_facts(dict(v["facts"]), base)
        if facts is None:
            rec.update(status="refused", why="checked_pending_facts refused the change")
            return rec
        newp = ask_intent._apply_change(dict(facts), raw)
        newp = Profile.model_validate(newp.model_dump())
        pipeline.validate_profile(newp)
        plan, ctx = await _run(newp)
        rec["fig"] = figures(plan, ctx)
    rec["status"] = "ok"
    return rec


async def one_baseline(item: dict, fresh: bool) -> dict:
    from app import pipeline
    t0 = time.time()
    raw = item["profile"]
    base = pipeline._clean_profile_text(pipeline.prepare(raw))
    # the plan the person sees. Its starting points and analysis never change the plan's figures, so they are left out
    # for speed (options=False), and "how sure" is worked out with the analysis's own function on the kept strategy
    plan, ctx = await _run(base, options=False)
    from app import analysis
    from app.tools import neighbors
    people = neighbors._people(ctx.kept["person"], ctx.kept["sim"])
    plan["analysis"] = {"how_sure": analysis.how_sure(ctx.kept["sim"], ctx.kept["strategy"], people, ctx.results["markets"])[0]}
    fig = figures(plan, ctx)
    p = base
    out = {"id": item["id"], "label": item["label"], "source": item["source"],
           "profile_brief": {"age": p.age, "partner_age": p.partner_age, "retire_age": p.retire_age, "pay": p.household_pay(),
                             "savings": p.savings.total, "spend_now": p.spending_now_per_year, "goal": p.spending_per_year,
                             "state": p.state, "owns": p.home.owns, "mortgage": p.home.mortgage_balance,
                             "debts": sum(d.balance for d in p.debts), "children": len(p.children)},
           "base": fig, "variations": []}
    vs = variations(p)
    cv = claim_variation(p, fig)
    if cv:
        vs.append(cv)
    for v in vs:
        try:
            out["variations"].append(await one_variation(v, raw, base, ctx, fresh))
        except Exception as e:  # noqa: BLE001
            out["variations"].append({"name": v["name"], "kind": v["kind"], "expect": v["expect"], "status": "error",
                                      "why": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-800:]})
    out["seconds"] = round(time.time() - t0, 1)
    return out


def work(item: dict, fresh: bool) -> dict:
    try:
        return asyncio.run(one_baseline(item, fresh))
    except Exception as e:  # noqa: BLE001
        return {"id": item["id"], "label": item["label"], "source": item["source"], "error": f"{type(e).__name__}: {e}",
                "trace": traceback.format_exc()[-1500:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="before")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--no-fresh", action="store_true", help="skip the What-If-equals-fresh-plan check (faster)")
    ap.add_argument("--fresh-every", type=int, default=5, help="run the fresh-plan check on every Nth baseline and every sample")
    args = ap.parse_args()
    workers = max(1, min(4, args.workers))
    items = load_baselines()
    if args.ids:
        want = set(args.ids.split(","))
        items = [x for x in items if x["id"] in want]
    if args.limit:
        items = items[: args.limit]
    path = HERE / f"results_{args.tag}.jsonl"
    done = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                if "error" not in r:
                    done.add(r["id"])
            except json.JSONDecodeError:
                pass
    todo = [x for x in items if x["id"] not in done]
    import app
    print(f"{len(items)} baselines, {len(todo)} to run, {workers} workers -> {path.name}; app from {Path(app.__file__).parent}", flush=True)
    t0 = time.time()
    with open(path, "a", encoding="utf-8") as f, ProcessPoolExecutor(workers) as ex:
        order = {x["id"]: i for i, x in enumerate(load_baselines())}
        fresh = {x["id"]: (not args.no_fresh) and (x["source"] == "samples" or order[x["id"]] % max(1, args.fresh_every) == 0) for x in todo}
        futs = {ex.submit(work, x, fresh[x["id"]]): x["id"] for x in todo}
        for i, fu in enumerate(as_completed(futs), 1):
            r = fu.result()
            f.write(json.dumps(r) + "\n")
            f.flush()
            n = len(r.get("variations", []))
            print(f"[{i}/{len(todo)}] {r['id']} {r.get('seconds', '?')}s {n} variations" + (f" ERROR {r['error']}" if "error" in r else ""),
                  flush=True)
    print(f"finished in {round(time.time() - t0)}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
