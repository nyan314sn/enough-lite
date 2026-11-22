"""Scores the What If reader on eval/whatif_phrasing/cases.jsonl.

  rules   the rules only (no model call): the same order as pipeline.ask (safety refusals, then parse_whatif, then the
          change's own checks in apply_whatif). Free and deterministic.
  ai      the rules, then the AI fallback (app/whatif_ai.py) where the rules found nothing or only part. The model's
          reading becomes the What If the confirm chip would run; that is what is scored. Live model calls: costs money.

Run:  python eval/whatif_phrasing/run.py rules [--out results_rules.json]
      python eval/whatif_phrasing/run.py ai --out results_ai.json
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
APP_ROOT = Path(os.environ.get("WHATIF_APP_ROOT") or ROOT)
sys.path.insert(0, str(APP_ROOT))

from app import ask_plan, pipeline, safety  # noqa: E402
from app.agents import parser as _parser  # noqa: E402
from app.schemas import Profile  # noqa: E402

HH = {h["id"]: h["profile"] for h in json.loads((ROOT / "app" / "data" / "sample_households.json").read_text(encoding="utf-8"))}


def load_cases() -> list[dict]:
    return [json.loads(x) for x in (HERE / "cases.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def base_of(hid: str) -> Profile:
    return pipeline._clean_profile_text(pipeline.prepare(copy.deepcopy(HH[hid])))


def outcome(ch: dict, base: Profile) -> dict:
    """The change dict in plain terms (see make_cases.py)."""
    out: dict = {}
    for k in ("retire_age", "partner_retire_age", "claim_age", "state", "risk", "emergency_months", "insurance", "match_full"):
        if k in ch:
            out[k] = ch[k]
    if ch.get("_partner_now"):
        out["partner_now"] = True
    if "downsize" in ch:
        out["downsize"] = ch["downsize"] or "default"
    if "pay_off" in ch:
        out["pay_off"] = sorted(ch["pay_off"])
    if "shock" in ch:
        s = ch["shock"]
        out["shock"] = f"fall:{round(s['size'] * 100)}:{s['when']}" if s["kind"] == "fall" else s["kind"]
    if ch.get("_spend_now"):
        out["spend_now_less"] = ch.get("_spend_less") or round((base.spending_now_per_year or 0) * ch.get("_spend_less_pct", 0), 2)
    elif "spending_per_year" in ch:
        out["spending_goal"] = ch["spending_per_year"]
    elif "_spend_less" in ch or "_spend_less_pct" in ch:
        cut = ch.get("_spend_less") or (base.spending_per_year or 0) * ch["_spend_less_pct"]
        out["spending_goal"] = round((base.spending_per_year or 0) - cut, 2)
    if "_extra_per_year" in ch:
        out["save_more_per_year"] = ch["_extra_per_year"]
    elif "save_rate" in ch:
        out["save_rate"] = ch["save_rate"]
    elif "saving_contrib_you" in ch:
        pay = base.pay_per_year or base.household_pay() or 1
        out["save_rate"] = round(ch["saving_contrib_you"] / pay, 3)
    if "part_time" in ch:
        out["part_time"] = {"per_year": ch["part_time"]["per_year"], "until_age": ch["part_time"].get("until_age")}
    if "children" in ch:
        if ch.get("_college_each"):
            col = []
            for i, (a, b) in enumerate(zip(base.children, ch["children"])):
                ta, tb = a.college_type or "public", b.get("college_type") or "public"
                if not b.get("college", True):
                    tb = "none"
                if not a.college:
                    ta = "none"
                if (ta, a.college_share) != (tb, b.get("college_share", 1.0)):
                    col.append([i, tb, b.get("college_share", 1.0)])
            out["college"] = col
        else:
            out["children_added"] = len(ch["children"]) - len(base.children)
    if "pets" in ch:
        before = {p.kind: p.count for p in base.pets}
        after: dict = {}
        for p in ch["pets"]:
            after[p["kind"]] = after.get(p["kind"], 0) + p["count"]
        out["pets"] = {k: after.get(k, 0) for k in sorted(set(before) | set(after)) if after.get(k, 0) != before.get(k, 0)}
    return out


def rules_read(text: str, base: Profile) -> tuple[object, dict]:
    """("refuse" | "clarify" | "none" | outcome dict, the change dict) on the rules alone, in pipeline.ask's order. A change
    the plan's own checks then turn down (savings too small, an age already past) carries "_rejected": the reading is
    scored as read, and the reply is a clarify."""
    q = _parser.fix_words(text)
    if safety.is_medicaid_hiding(q) or safety.is_refusable(q) or safety.guard(q).flagged:
        return "refuse", {}
    clean = safety.guard(q).clean
    ch = pipeline.parse_whatif(clean, base)
    if ch.get("_say"):
        return "clarify", ch
    if not ch:
        if safety.is_single_investment(clean.lower()) or ask_plan.CRYPTO.search(clean):
            return "refuse", ch
        return "none", ch
    out = outcome(ch, base)
    if pipeline._same_as_plan(ch, base):
        return {**out, "_rejected": "same"}, ch
    try:
        _, notes = pipeline.apply_whatif(base.model_copy(deep=True), copy.deepcopy(ch))
    except Exception as e:  # noqa: BLE001
        return f"error:{type(e).__name__}", ch
    if notes.get("_say"):
        return {**out, "_rejected": notes["_say"][:80]}, ch
    return out, ch


def close(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= max(1.0, 0.01 * abs(b)) if abs(b) >= 1 else abs(a - b) <= 0.005
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(close(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
    return a == b


def correct(got, exp) -> bool:
    if exp == "clarify":
        return got in ("clarify", "none") or (isinstance(got, dict) and "_rejected" in got)
    if exp == "refuse":
        return got == "refuse"
    return isinstance(got, dict) and close({k: v for k, v in got.items() if k != "_rejected"}, exp)


async def ai_read(text: str, base: Profile, rules_got, ch: dict, session: str):
    """The rules, then the second reader exactly as pipeline.ask calls it (whatif_ai.fallback) where the rules found
    nothing or only part. Returns (outcome, how, cost). The cost is read from the meter, so a call that fails still counts."""
    from app import llm, whatif_ai
    q = safety.guard(_parser.fix_words(text)).clean
    if rules_got in ("refuse", "clarify") or rules_got is None:
        return rules_got, "rules", 0.0
    partial = isinstance(rules_got, dict) and bool(whatif_ai.missed_topics(q, ch))
    if not (rules_got == "none" or partial):
        return rules_got, "rules", 0.0
    before = llm.METER.spent()
    r = await whatif_ai.fallback(q, base, ch if partial else {}, session, True)
    cost = llm.METER.spent() - before
    if r is None:
        return rules_got, ("ai_none" if cost else "rules"), cost
    phrase = (r.get("pending_change") or {}).get("whatif")
    if not phrase:
        return "clarify", ("ai_clarify" if cost else "cannot"), cost
    got, _ = rules_read(phrase, base)
    return got, "ai_confirm", cost


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "rules"
    out_path = HERE / (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else f"results_{mode}.json")
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
    cases = load_cases()
    if only:
        cases = [c for c in cases if c["id"] in only]
    rows, total_cost, t0 = [], 0.0, time.time()
    for c in cases:
        base = base_of(c["household"])
        got, ch = rules_read(c["text"], base)
        how, cost = "rules", 0.0
        if mode == "ai":
            got, how, cost = asyncio.run(ai_read(c["text"], base, got, ch, "eval-whatif"))
            total_cost += cost
        rows.append({"id": c["id"], "household": c["household"], "split": c.get("split", "tune"), "type": c["type"], "tags": c["tags"], "text": c["text"],
                     "expected": c["expected"], "got": got, "how": how, "ok": correct(got, c["expected"]), "cost_usd": round(cost, 6)})
    by_type: dict = defaultdict(lambda: [0, 0])
    by_tag: dict = defaultdict(lambda: [0, 0])
    by_split: dict = defaultdict(lambda: [0, 0])
    by_scope: dict = defaultdict(lambda: [0, 0])
    for r in rows:
        by_split[r["split"]][0] += r["ok"]
        by_split[r["split"]][1] += 1
        scope = f'{r["split"]}:{"change" if isinstance(r["expected"], dict) else r["expected"]}'
        by_scope[scope][0] += r["ok"]
        by_scope[scope][1] += 1
        by_type[r["type"]][0] += r["ok"]
        by_type[r["type"]][1] += 1
        for t in r["tags"]:
            by_tag[t][0] += r["ok"]
            by_tag[t][1] += 1
    n_ok = sum(r["ok"] for r in rows)
    summary = {"mode": mode, "cases": len(rows), "correct": n_ok, "accuracy": round(n_ok / max(1, len(rows)), 3),
               "by_split": {k: {"correct": v[0], "cases": v[1], "accuracy": round(v[0] / v[1], 3)} for k, v in sorted(by_split.items())},
               "by_expected": {k: {"correct": v[0], "cases": v[1]} for k, v in sorted(by_scope.items())},
               "by_type": {k: {"correct": v[0], "cases": v[1]} for k, v in sorted(by_type.items())},
               "by_tag": {k: {"correct": v[0], "cases": v[1]} for k, v in sorted(by_tag.items())},
               "ai_calls": sum(1 for r in rows if r["how"].startswith("ai")), "cost_usd": round(total_cost, 4), "seconds": round(time.time() - t0, 1)}
    out_path.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    for r in rows:
        if not r["ok"]:
            print(f"FAIL {r['id']} {r['split']} [{r['household']}] {r['text']!r}: expected {r['expected']} got {r['got']} ({r['how']})")


if __name__ == "__main__":
    main()
