"""Judge simulated runs with a second Haiku. Usage: python judge.py [--ids p01,p02] [--force]

Writes judged/<id>.json: {issues:[{ref,type,severity,quote,note}], accuracy:{fields:[...], share, wrong:[...]}}.
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor

from common import JUDGED, RUNS, haiku, load_personas, normalize_turns, parse_json

TYPES = {
    "dead_end": "the reply moves nothing forward and asks nothing specific (no next question, no result, no useful options)",
    "ignored_correction": "the person corrected a figure or fact and the app did not apply it or acknowledge it",
    "unstated_assumption": "the app assumed or estimated something (see NEW ASSUMED FIELDS) and the reply did not say so in plain words",
    "repeated_question": "the app asks again for something the person already gave (not a deliberate confirm)",
    "misunderstanding": "the app understood the message wrongly (wrong field, wrong meaning, wrong action, e.g. changed something the person did not ask to change)",
    "confusing": "the reply is confusing, jargon-heavy, or hard for an ordinary person to act on",
    "contradiction": "the reply or stored fact contradicts a fact the person already stated (compare with the person's true situation)",
}
SYSTEM = f"""You audit a retirement-planning chat app by reading a test conversation. A simulated person with a known true situation chatted with it.
For each app turn in the TURNS TO JUDGE, decide whether it has any of these issues:
{json.dumps(TYPES, indent=1)}
Severity: P0 = the person is stuck, wrong money data is stored silently, or the app does the wrong thing; P1 = clear friction or an unstated assumption that changes the result; P2 = minor.
Check EVERY number or fact the app echoes ("I noted that you have saved $160,000") against the user's words and the TRUE SITUATION: an echoed figure that differs from what the person just said is a P0 misunderstanding. A person who complains "it still says X" after correcting means ignored_correction (P0). A question the app never asks but the plan needs, or a plan built on wrong stored data, is a P0 if the reply does not flag it. A change proposal that sets the wrong field (e.g. pay changed when the person talked about spending) is a P0 misunderstanding. Be strict but fair: a reply that says what it understood and asks one specific question is fine. Not an issue: the simulated person's own odd behaviour. Judge only the app. Quote the exact words (under 25 words) from the app reply or the user message that show the issue.
Output ONLY a JSON array (empty [] if none) of objects: {{"ref": "<turn ref>", "type": "<one of the type keys>", "severity": "P0|P1|P2", "quote": "...", "note": "one short sentence on why"}}."""


def render(turns, upto, lo):
    lines = []
    for t in turns[:upto]:
        tag = "JUDGE" if lo <= turns.index(t) < upto else "context"
        lines.append(f"--- turn {t['ref']} ({tag}, {t['phase']}) ---\nUSER{'(clicked a button)' if t.get('clicked') else ''}: {t['user']}\n"
                     f"APP: {t['app']}" + (f"\nAPP ASKS: {t['question']}" if t.get("question") else "")
                     + (f"\nBUTTONS: {t['chips']}" if t.get("chips") else "")
                     + (f"\nNEW ASSUMED FIELDS (source assumed/estimate): {t['new_assumed']}" if t.get("new_assumed") else "")
                     + (f"\nKIND: {t.get('kind')} {t.get('status') or ''}" if t.get("kind") else ""))
    return "\n".join(lines)


def num(x, default=None):
    try:
        return float(x)
    except Exception:
        return default


def close(a, b, tol):
    a, b = num(a), num(b)
    if a is None or b is None:
        return False
    return abs(a - b) <= max(abs(b) * tol, 1500 if abs(b) < 20000 else 0)


def score_profile(p, prof):
    """Deterministic check of the final profile against the hidden truth. Returns a list of {field, ok, got, truth, source}."""
    t = p["truth"]
    src = prof.get("sources", {}) or {}
    out = []

    def add(field, ok, got, truth, source=None):
        out.append(dict(field=field, ok=bool(ok), got=got, truth=truth, source=source))
    add("age", prof.get("age") == t["age"], prof.get("age"), t["age"], src.get("age"))
    add("partner_age", prof.get("partner_age") == t["partner_age"], prof.get("partner_age"), t["partner_age"], src.get("partner_age"))
    add("state", (prof.get("state") or "") == t["state"], prof.get("state"), t["state"], src.get("state"))
    add("retire_age", prof.get("retire_age") == t["retire_age"], prof.get("retire_age"), t["retire_age"], src.get("retire_age"))
    add("pay_per_year", close(prof.get("pay_per_year"), t["pay_per_year"], 0.10), prof.get("pay_per_year"), t["pay_per_year"], src.get("pay_per_year"))
    if t.get("partner_pay_per_year"):
        add("partner_pay", close(prof.get("partner_pay_per_year"), t["partner_pay_per_year"], 0.10), prof.get("partner_pay_per_year"), t["partner_pay_per_year"], src.get("partner_pay_per_year"))
    sv = prof.get("savings") or {}
    got_s = sum(num(sv.get(k), 0) for k in ("pretax", "roth", "taxable", "cash"))
    tr_s = sum(t["savings"].values())
    add("savings_total", close(got_s, tr_s, 0.10), got_s, tr_s, src.get("savings"))
    h, th = prof.get("home") or {}, t["home"]
    add("home_owns", bool(h.get("owns")) == bool(th["owns"]), h.get("owns"), th["owns"], src.get("home"))
    if th["owns"]:
        add("mortgage_balance", close(h.get("mortgage_balance") or 0, th["mortgage_balance"], 0.10), h.get("mortgage_balance"), th["mortgage_balance"])
    add("children", sorted(c.get("age") for c in prof.get("children") or []) == sorted(t["children_ages"]),
        sorted(c.get("age") for c in prof.get("children") or []), sorted(t["children_ages"]), src.get("children"))
    add("pets", sum(x.get("count", 1) for x in prof.get("pets") or []) == sum(x["count"] for x in t["pets"]),
        sum(x.get("count", 1) for x in prof.get("pets") or []), sum(x["count"] for x in t["pets"]))
    gd, td = sum(num(d.get("balance"), 0) for d in prof.get("debts") or []), sum(d["balance"] for d in t["debts"])
    add("debts_total", close(gd, td, 0.15) if td else gd == 0, gd, td)
    gp, tp = sum(num(x.get("per_year"), 0) for x in prof.get("pensions") or []), sum(x["per_year"] for x in t["pensions"])
    add("pension_per_year", close(gp, tp, 0.10) if tp else gp == 0, gp, tp)
    add("spending_now", close(prof.get("spending_now_per_year"), t["spending_now_per_year"], 0.20), prof.get("spending_now_per_year"), t["spending_now_per_year"], src.get("spending_now_per_year"))
    return out


def judge_one(p, force=False):
    out = JUDGED / f"{p['id']}.json"
    rp = RUNS / f"{p['id']}.json"
    if not rp.exists():
        return "norun"
    if out.exists() and not force:
        return "skip"
    run = json.loads(rp.read_text(encoding="utf-8"))
    turns = normalize_turns(run)
    issues = []
    truth = json.dumps(p["truth"])
    for lo in range(0, len(turns), 3):
        hi = min(lo + 3, len(turns))
        user = (f"TRUE SITUATION of the simulated person (hidden from the app): {truth}\nPersonality: {p['personality']}\n\n"
                f"CONVERSATION:\n{render(turns, hi, lo)}\n\nJudge only turns {', '.join(t['ref'] for t in turns[lo:hi])}. Output the JSON array.")
        try:
            res = parse_json(haiku("judge", SYSTEM, user, max_tokens=1000))
        except Exception:
            res = None
        for it in res or []:
            if isinstance(it, dict) and it.get("type") in TYPES:
                issues.append({k: it.get(k) for k in ("ref", "type", "severity", "quote", "note")})
    prof = run.get("final_profile_after_change") or run.get("final_profile") or {}
    fields = score_profile(p, prof) if prof else []
    wrong = [f for f in fields if not f["ok"]]
    why = None
    if wrong:
        user = (f"TRUE SITUATION: {truth}\nPersonality: {p['personality']}\n\nCONVERSATION:\n{render(turns, len(turns), 0)}\n\n"
                f"WRONG PROFILE FIELDS (got vs truth, source = how the app tagged it): {json.dumps(wrong)}\n\n"
                "For each wrong field say why in a few words, choosing a cause: never_asked (app never asked), person_never_said (person did not state it), "
                "app_misparsed (person said it, app stored something else), correction_lost, person_guessed_wrong (person's own wrong guess), "
                "assumed_default (app used a typical value), simulator_inconsistent (the simulated person said something different from the truth), "
                "other. Output ONLY a JSON array of {\"field\":..., \"cause\":..., \"note\":...}.")
        try:
            why = parse_json(haiku("judge", "You explain profile errors in a test of a chat app. Be exact and brief.", user, max_tokens=1000))
        except Exception:
            why = None
    out.write_text(json.dumps(dict(persona_id=p["id"], issues=issues, accuracy=dict(
        fields=fields, share=(sum(f["ok"] for f in fields) / len(fields)) if fields else None, why=why)), indent=1), encoding="utf-8")
    return f"{len(issues)} issues"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    ps = load_personas()
    if a.ids:
        want = set(a.ids.split(","))
        ps = [p for p in ps if p["id"] in want]

    def go(p):
        s = judge_one(p, a.force)
        print(p["id"], s, flush=True)
    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(go, ps))


if __name__ == "__main__":
    main()
