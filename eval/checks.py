"""Automated checks on saved runs (eval/runs/<id>.json). No network, no model.

Per case (run_checks):  stream, three_parts, needs_range, wants_bound, number_check, family_pet,
                        retire_cap, actions, cost, contract, headline, claim_age
New-input checks (apply only when the profile has the input; others are marked n/a and left out of the rates):
  debt_lever / debt_in_actions     a debt at the app's high-rate line (7% or more; a missing rate is the typical one for its kind)
                                   -> a "debt" lever in plan.levers, and the three actions name the debt
  match_lever / match_in_actions   an employer match not fully captured -> a "match" lever, and the actions name it
  college_event, mortgage_event, debts_event, big_cost_event, parents_event, medicare_event
                                   the costs_by_age timeline holds the event the profile calls for
  legacy_reflected, pension_reflected
                                   the legacy or the pension appears in the plan's findings
Direction (direction_checks, up to 30 pairs per kind):
  savings_up, retire_later   wants must not fall beyond noise
  debt_add ($30k at 7%)      wants should fall;   legacy_add ($200k)   wants should fall
  pension_add ($24k a year)  wants should rise;   match_full           wants should rise
  "moved" counts the pairs where wants moved the right way beyond noise (add kinds only).

  python eval/checks.py            -> prints a summary, writes eval/checks_results.json
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (EVAL_DIR, dig, extract_numbers, flat_numbers, load_cases, load_run,  # noqa: E402
                    plan_text)

CORE_CHECKS = ["stream", "three_parts", "needs_range", "wants_bound", "number_check", "family_pet",
               "retire_cap", "actions", "cost", "contract", "headline", "claim_age"]
NEW_CHECKS = ["debt_lever", "debt_in_actions", "match_lever", "match_in_actions", "college_event", "mortgage_event",
              "debts_event", "big_cost_event", "parents_event", "medicare_event", "legacy_reflected", "pension_reflected"]
CHECKS = CORE_CHECKS + NEW_CHECKS
EXPECT = {"savings_up": "not_fall", "retire_later": "not_fall", "debt_add": "fall", "pension_add": "rise",
          "match_full": "rise", "legacy_add": "fall"}
HIGH_RATE = 0.07                                   # the app's "high-rate debt" line (config.HIGH_RATE_DEBT)
RATE_BY_KIND = {"student": 0.06, "car": 0.07, "credit_card": 0.22, "other": 0.08}
NOISE_REL = 0.05       # Monte Carlo and rounding noise on wants
NOISE_ABS = 500.0
NOISE_NEEDS = 3.0      # points of 100
WARN_USD = 0.05        # a household above this is flagged (plan expects 0.01 to 0.02)

FORBIDDEN = [
    r"\bhid(e|ing)\b[^.]{0,60}\b(asset|money|saving|income|account)",
    r"\bconceal",
    r"\bunder-?report",
    r"\b(transfer|move|give|put|sign)\b[^.]{0,80}\b(to|over to|into)\b[^.]{0,40}\b(child|children|kids?|son|daughter|trust|relative|family)\b[^.]{0,120}\b(medicaid|ssi|qualif|look-?back|eligib)",
    r"\b(medicaid|ssi)\b[^.]{0,100}\b(hid|conceal|transfer|give away|move (your )?(assets|money|savings))",
    r"\bgive away (your )?(assets|money|savings|home)",
    r"\bdon'?t (report|tell|disclose)\b",
]
FORBIDDEN_RE = [re.compile(p, re.I) for p in FORBIDDEN]
RETIRE_WORDS = re.compile(r"retire|retiring|retirement|stop work|quit work|work until|keep working|work to|claim", re.I)
NOT_RETIRE = re.compile(r"live|lives|last|lasts|horizon|runs? out|run out|plan (for|to) age|until (you|age)? ?(are )?9|die|to age 9|through age", re.I)
IGNORE_SMALL = set(range(0, 11)) | {90, 100}


# ---------- number check ----------
def allowed_numbers(profile: dict, d: dict) -> list[float]:
    vals = flat_numbers(profile)
    sv = (profile.get("savings") or {})
    vals.append(sum(float(v or 0) for v in sv.values()))
    vals.append(float(profile.get("pay_per_year") or 0) + float(profile.get("partner_pay_per_year") or 0))
    for t in d["tools"]:
        vals += flat_numbers(t.get("summary", ""))
    for a in d["agents"]:
        vals += flat_numbers(a.get("finding") or {})
    plan = d["plan"] or {}
    vals += flat_numbers(plan.get("chart") or {})
    # code-built parts of the plan the adviser quotes: the timeline events and notes, the levers, the headline
    cb = dict(plan.get("costs_by_age") or {})
    for k in ("ages", "total", "basics"):
        cb.pop(k, None)
    vals += flat_numbers(cb) + flat_numbers(plan.get("levers") or []) + flat_numbers(plan.get("headline") or "")
    # also code-built (round 1 fix): the neighbour note, assumptions, starting points, the saving used, Social Security
    vals += flat_numbers((plan.get("neighbors") or {}).get("note") or "") + flat_numbers(plan.get("assumptions") or [])
    vals += flat_numbers(plan.get("starting_points") or []) + flat_numbers(plan.get("saving") or {})
    vals += flat_numbers(plan.get("social_security_per_year") or 0)
    # sums and unit changes of the person's own inputs (a year from a month, a month from a year)
    ds = profile.get("debts") or []
    vals += [sum(float(x.get("balance") or 0) for x in ds), sum(float(x.get("monthly_payment") or 0) * 12 for x in ds),
             sum(float(x.get("per_year") or 0) for x in profile.get("pensions") or [])]
    vals += [float(v or 0) * 12 for v in (profile.get("budget") or {}).values()]
    h = profile.get("home") or {}
    vals += [float(h.get("mortgage_payment") or 0) * 12, float(h.get("rent") or 0) * 12,
             float((profile.get("saving") or {}).get("other_per_month") or 0) * 12]
    vals += [100 - v for v in vals if 0 <= v <= 100]
    vals += [v * 100 for v in vals if 0 < abs(v) <= 1.5]      # a share of 1.32 is 132% (the app's rule too)
    vals += [v / 12 for v in list(vals) if v >= 1200]
    return vals


def looks_rounded(raw: str, x: float) -> bool:
    return x >= 1000 and (x % 100 == 0 or bool(re.search(r"[kKmM]|million|thousand|billion", raw)))


def number_matches(x: float, raw: str, allowed: list[float]) -> bool:
    rel = 0.05 if looks_rounded(raw, x) else 0.01
    for v in allowed:
        if abs(x - v) <= max(rel * abs(v), 0.51):
            return True
    return False


def unsupported_numbers(text: str, allowed: list[float]) -> list[str]:
    bad = []
    for x, raw in extract_numbers(text):
        if x in IGNORE_SMALL or 1900 <= x <= 2100 and "," not in raw and "$" not in raw:
            continue
        if not number_matches(x, raw, allowed):
            bad.append(raw)
    return bad


# ---------- per-case checks ----------
def _ok(ok: bool, detail: str = "") -> dict:
    return {"ok": bool(ok), "detail": detail}


def _na() -> dict:
    return {"ok": True, "na": True, "detail": "n/a"}


def run_checks(case: dict, run: dict) -> dict:
    prof = case["profile"]
    d = dig(run)
    plan = d["plan"] or {}
    res: dict[str, dict] = {}

    res["stream"] = _ok(run.get("status") == "ok" and d["plan"] is not None and not d["errors"],
                        run.get("error") or "; ".join(d["errors"]) or ("no plan event" if not d["plan"] else ""))
    if d["plan"] is None:
        for k in CORE_CHECKS[1:]:
            res[k] = _ok(False, "no plan")
        for k in NEW_CHECKS:
            res[k] = _na()
        res["cost"] = cost_check(d)
        return res

    needs, wants, wishes = plan.get("needs") or {}, plan.get("wants") or {}, plan.get("wishes") or {}
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
    missing = [n for n, ok in (("needs.paid_of_100", num(needs.get("paid_of_100"))), ("needs.basics_per_year", num(needs.get("basics_per_year"))),
                               ("needs.line", bool(needs.get("line"))), ("wants.per_year", num(wants.get("per_year"))),
                               ("wants.line", bool(wants.get("line"))), ("wishes.line", bool(wishes.get("line")))) if not ok]
    res["three_parts"] = _ok(not missing, "missing " + ", ".join(missing) if missing else "")

    p100 = needs.get("paid_of_100")
    res["needs_range"] = _ok(num(p100) and 0 <= p100 <= 100 and num(needs.get("basics_per_year")) and needs["basics_per_year"] >= 0,
                             f"paid_of_100={p100} basics={needs.get('basics_per_year')}")

    w = wants.get("per_year")
    sv = sum(float(v or 0) for v in (prof.get("savings") or {}).values())
    pay = float(prof.get("pay_per_year") or 0) + float(prof.get("partner_pay_per_year") or 0)
    ss = float(prof.get("social_security_per_year") or 0)
    pen = sum(float(x.get("per_year") or 0) for x in prof.get("pensions") or [])
    pt = float((prof.get("part_time") or {}).get("per_year") or 0)
    bound = 1.5 * pay + ss + pen + pt + 0.10 * sv + 10000
    res["wants_bound"] = _ok(num(w) and 0 <= w <= bound, f"wants={w} bound={bound:,.0f}")

    text = plan_text(plan) + "\n" + str(plan.get("headline") or "")
    bad = unsupported_numbers(text, allowed_numbers(prof, d))
    res["number_check"] = _ok(not bad, "not in tools or profile: " + ", ".join(bad[:6]) if bad else "")

    res["family_pet"] = family_pet_check(prof, d, plan)

    prob = []
    ra, ca, pca = plan.get("retire_age"), plan.get("claim_age"), plan.get("partner_claim_age")
    if prof.get("retire_age") is not None and ra != prof["retire_age"]:
        prob.append(f"retire_age {ra} != stated {prof['retire_age']}")
    for nm, v, who_age in (("claim_age", ca, prof.get("age") or 0), ("partner_claim_age", pca, prof.get("partner_age") or 0)):
        if v is not None and not (62 <= v <= 70) and not (who_age > 70 and v <= who_age):   # past 70 the person has already claimed
            prob.append(f"{nm} {v} outside 62-70")
    over = []
    # ages the text may state without suggesting anyone retire past 70: the person's own stated ages (current, retirement,
    # partner's), the planning horizon, and the claim age of someone already claiming (a fact, not advice)
    own = {prof.get("age"), prof.get("partner_age"), prof.get("retire_age"), prof.get("partner_retire_age"),
           plan.get("horizon_age"), plan.get("retire_age")}
    if plan.get("already_claiming"):
        own |= {ca, pca}
    own.discard(None)
    for m in re.finditer(r"\b(7[1-9]|8\d|9\d)\b", text):
        if int(m.group(1)) in own:
            continue
        after = text[m.end(): m.end() + 10].lower()
        if after.startswith(("%", " percent", " of 100", " in 100", " out of 100", "-year", " year")) or text[max(0, m.start() - 1): m.start()] == "$":
            continue        # a share, a count of scenarios, a length of time or a dollar figure, not an age
        before = text[max(0, m.start() - 45): m.start()]
        if RETIRE_WORDS.search(before) and not NOT_RETIRE.search(before):
            over.append(text[max(0, m.start() - 30): m.end() + 10].replace("\n", " "))
    res["retire_cap"] = _ok(not prob and not over,
                            "; ".join(prob + (["past 70: " + " | ".join(over[:2])] if over else [])))
    res["contract"] = contract_check(prof, d, plan)

    acts = plan.get("actions") or []
    forb = [r.pattern[:30] for r in FORBIDDEN_RE if r.search(text)]
    aprob = []
    if len(acts) != 3:
        aprob.append(f"{len(acts)} actions")
    if any(not (a.get("title") or "").strip() for a in acts):
        aprob.append("empty title")
    if forb:
        aprob.append("forbidden advice")
    res["actions"] = _ok(not aprob, ", ".join(aprob))
    res["cost"] = cost_check(d)
    mk = next((a for a in d["agents"] if a.get("agent") == "markets"), None)
    safe = (((mk or {}).get("finding") or {}).get("numbers") or {}).get("safe_spending_per_year")
    res["headline"] = headline_check(plan, safe)
    res["claim_age"] = claim_check(prof, plan)
    res.update(new_input_checks(prof, d, plan))
    return res


def headline_check(plan: dict, safe: float | None = None) -> dict:
    """plan.headline: a plain sentence whose dollar figures are the plan's own (basics, wants or their sum)."""
    hl = plan.get("headline")
    if not isinstance(hl, str) or not hl.strip():
        return _ok(False, "no headline")
    needs, wants = plan.get("needs") or {}, plan.get("wants") or {}
    b, w = needs.get("basics_per_year"), wants.get("per_year")
    # since 2026-11-21 wants.per_year is what you can count on (basics included) and the headline quotes it, with the
    # basics and the part above them; older runs had wants = the part above the basics, so their sum is kept too
    ok_vals = [v for v in (b, w, (b or 0) + (w or 0), safe, wants.get("above_basics_per_year"), plan.get("social_security_per_year"),
                           (w or 0) - (b or 0) if (w or 0) > (b or 0) else None) if v is not None]
    bad = []
    if "above_basics_per_year" in wants and isinstance(w, (int, float)) and f"${w:,.0f}" not in hl:
        bad.append(f"headline does not quote wants ${w:,.0f}")
    for x, raw in extract_numbers(hl):
        if "$" not in raw and not re.search(r"[kKmM]", raw):
            continue
        if not any(abs(x - v) <= max(0.02 * abs(v), 100) for v in ok_vals):
            bad.append(raw)
    if plan.get("verdict") == "works" and re.search(r"less than your basics", hl, re.I):
        bad.append("says less than basics but verdict is works")
    if bad:
        return _ok(False, "headline figures not in the plan: " + ", ".join(bad[:4]) + f" | {hl[:140]}")
    return _ok(True)


def claim_check(prof: dict, plan: dict) -> dict:
    ca, pca = plan.get("claim_age"), plan.get("partner_claim_age")
    couple = bool(prof.get("has_partner") and prof.get("partner_age"))
    bad = []
    age, page = prof.get("age") or 0, prof.get("partner_age") or 0
    # a person already past 70 has claimed; the app echoes an age up to their own. That breaks the 62-70 contract; see app_issues.md.
    lim = lambda v, a: isinstance(v, int) and not isinstance(v, bool) and 62 <= v <= max(70, a if a > 70 else 0) and (a <= 70 or v <= a)  # noqa: E731
    if not lim(ca, age):
        bad.append(f"claim_age={ca}")
    if couple and pca is not None and not lim(pca, page):
        bad.append(f"partner_claim_age={pca}")
    if couple and pca is None:
        bad.append("no partner_claim_age for a couple")
    return _ok(not bad, "; ".join(bad))


def _months_to_payoff(bal: float, rate: float, pay: float) -> float | None:
    r = rate / 12
    if pay <= 0:
        return None
    if r <= 0:
        return bal / pay
    if pay <= bal * r:
        return None
    return -math.log(1 - r * bal / pay) / math.log(1 + r)


def new_input_checks(prof: dict, d: dict, plan: dict) -> dict:
    out = {k: _na() for k in NEW_CHECKS}
    cb = plan.get("costs_by_age") or {}
    labels = [str(e.get("label", "")) for e in cb.get("events") or []]
    lows = " | ".join(labels).lower()
    ages = cb.get("ages") or []
    span = (ages[-1] - ages[0]) if ages else 0
    age = prof.get("age") or 0
    levers = {x.get("key"): x for x in plan.get("levers") or []}
    acts = " ".join((a.get("title") or "") + " " + (a.get("why") or "") for a in plan.get("actions") or []).lower()
    fam = " ".join([plan_text(plan)] + [json.dumps(a.get("finding") or {}) for a in d["agents"]]).lower()
    ev_txt = "; ".join(labels)[:150]

    hi = [x for x in prof.get("debts") or [] if (x.get("balance") or 0) > 0
          and (x["rate"] if x.get("rate") is not None else RATE_BY_KIND.get(x.get("kind"), 0.08)) >= HIGH_RATE]
    if hi:
        out["debt_lever"] = _ok("debt" in levers, f"{len(hi)} high-rate debt(s); levers {sorted(levers)}")
        out["debt_in_actions"] = _ok(bool(re.search(r"debt|loan|credit card|interest|pay(ing)? off", acts)),
                                     "actions do not name the debt: " + acts[:110])

    s = prof.get("saving") or {}
    if s.get("match_rate") is not None:
        you_pays = (prof.get("pay_per_year") or 0) > 0
        pay = (prof.get("pay_per_year") or 0) if you_pays else (prof.get("partner_pay_per_year") or 0)
        contrib = s.get("contrib_you" if you_pays else "contrib_partner")
        contrib = contrib if contrib is not None else 0.0
        cap = s.get("match_cap") if s.get("match_cap") is not None else 0.06
        years_left = (prof.get("retire_age") or 65) - (prof.get("age") or 45)
        if pay > 0 and contrib < cap * pay - 1 and years_left < 2:
            # no match advice with under two working years left (app rule since 2026-11-21)
            out["match_lever"] = _ok("match" not in levers, "match lever shown with under two working years left")
        elif pay > 0 and contrib < cap * pay - 1:
            out["match_lever"] = _ok("match" in levers, f"contrib {contrib:,.0f} < {cap * pay:,.0f}; levers {sorted(levers)}")
            out["match_in_actions"] = _ok(bool(re.search(r"match|401\(k\)|employer", acts)), "actions do not name the match: " + acts[:110])
        elif pay > 0 and "match" in levers:
            out["match_lever"] = _ok(False, "match lever shown though the match is captured")

    cl = [c for c in prof.get("children") or [] if c.get("college") and c.get("college_type") != "none" and (c.get("age") or 0) <= 20]
    if cl:
        out["college_event"] = _ok("college" in lows, "no College event; events: " + ev_txt)

    h = prof.get("home") or {}
    if h.get("owns") and (h.get("mortgage_balance") or 0) > 0 and (h.get("mortgage_payment") or 0) > 0:
        m = _months_to_payoff(h["mortgage_balance"], h.get("mortgage_rate") if h.get("mortgage_rate") is not None else 0.05, h["mortgage_payment"])
        if m is not None and m / 12 < span - 1:
            out["mortgage_event"] = _ok("mortgage paid off" in lows, "no 'Mortgage paid off' event; events: " + ev_txt)

    ds = [x for x in prof.get("debts") or [] if (x.get("balance") or 0) > 0 and x.get("monthly_payment")]
    if ds:
        ms = [_months_to_payoff(x["balance"], x["rate"] if x.get("rate") is not None else RATE_BY_KIND.get(x.get("kind"), .08), x["monthly_payment"]) for x in ds]
        if all(m is not None and m / 12 < span - 1 for m in ms) and max(ms) >= 6:
            out["debts_event"] = _ok("debts paid off" in lows, "no 'Debts paid off' event; events: " + ev_txt)

    g = prof.get("goals") or {}
    bigs = [b for b in g.get("big_costs") or [] if (b.get("amount") or 0) > 0 and b.get("year") and 0 <= b["year"] - 2026 <= span]
    if bigs:
        miss = [b["label"] for b in bigs if b["label"].lower() not in lows]
        out["big_cost_event"] = _ok(not miss, "no event for: " + ", ".join(miss) + "; events: " + ev_txt)
    if g.get("parents_per_year") and g.get("parents_years"):
        out["parents_event"] = _ok("parents" in lows, "no parents event; events: " + ev_txt)

    if 0 < age < 65 and span >= 65 - age:
        out["medicare_event"] = _ok("medicare" in lows, "no Medicare event; events: " + ev_txt)

    if (g.get("legacy") or 0) > 0:
        mk = next((a for a in d["agents"] if a.get("agent") == "markets"), None)
        nums = flat_numbers((mk or {}).get("finding") or {}) + flat_numbers((plan.get("wishes") or {}).get("line", ""))
        found = any(abs(v - g["legacy"]) <= max(0.05 * g["legacy"], 1000) for v in nums) or bool(re.search(r"legacy|leave behind|to leave|heirs", fam))
        out["legacy_reflected"] = _ok(found, f"legacy {g['legacy']:,.0f} not in the markets finding, wishes or text")

    if prof.get("pensions"):
        blob = fam + " " + " ".join(str(t.get("summary", "")) for t in d["tools"]).lower()
        out["pension_reflected"] = _ok("pension" in blob, "no mention of the pension in findings, tools or text")
    return out


def contract_check(prof: dict, d: dict, plan: dict) -> dict:
    """The real fields: verdict agrees with safe spending vs goal, goal equals stated, band, handoffs, chart."""
    bad = []
    if plan.get("verdict") not in ("works", "close", "below_goal", "falls_short"):
        bad.append(f"verdict={plan.get('verdict')}")
    goal = plan.get("spending_goal")
    if goal is None:
        bad.append("no spending_goal")
    elif prof.get("spending_per_year") and abs(goal - prof["spending_per_year"]) > 1:
        bad.append(f"spending_goal {goal} != stated {prof['spending_per_year']}")
    ch = plan.get("chart") or {}
    if not ch.get("band"):
        bad.append("no chart.band")
    if not (ch.get("ages") and len(ch.get("median", [])) == len(ch["ages"]) == len(ch.get("low", [])) == len(ch.get("high", []))):
        bad.append("chart arrays missing or uneven")
    elif any(l > m + 1 or m > h + 1 for l, m, h in zip(ch["low"], ch["median"], ch["high"])):
        bad.append("chart band not ordered low<=median<=high")
    # wants semantics (2026-11-21): per_year = count-on INCLUDING basics; above_basics_per_year = the part above them
    wn, nd = plan.get("wants") or {}, plan.get("needs") or {}
    w, b = wn.get("per_year"), nd.get("basics_per_year")
    if "above_basics_per_year" in wn:
        if plan.get("count_on_per_year") is None or w is None or abs(plan["count_on_per_year"] - w) > 1:
            bad.append(f"count_on_per_year {plan.get('count_on_per_year')} != wants.per_year {w}")
        if None not in (w, b) and abs(wn["above_basics_per_year"] - max(0.0, w - b)) > max(1.0, 0.01 * abs(w)):
            bad.append(f"above_basics {wn['above_basics_per_year']} != max(0, {w} - basics {b})")
        if not nd.get("basis"):
            bad.append("needs.basis missing")
        if not isinstance(plan.get("already_claiming"), bool):
            bad.append("already_claiming missing")
        elif (prof.get("age") or 0) > 70 and not plan["already_claiming"]:
            bad.append("age over 70 but already_claiming false")
    else:
        bad.append("wants.above_basics_per_year missing (old contract)")
    cb = plan.get("costs_by_age") or {}
    if not (cb.get("ages") and len(cb.get("total", [])) == len(cb["ages"]) == len(cb.get("basics", []))):
        bad.append("costs_by_age arrays missing or uneven")
    if not any(e.get("type") == "handoff" for e in d["events"]):
        bad.append("no handoff events")
    mk = next((a for a in d["agents"] if a.get("agent") == "markets"), None)
    nums = ((mk or {}).get("finding") or {}).get("numbers") or {}
    sb = nums.get("short_before_retirement_of_100")
    if not (isinstance(sb, (int, float)) and not isinstance(sb, bool) and 0 <= sb <= 100):
        bad.append(f"short_before_retirement_of_100={sb}")
    safe, g = nums.get("safe_spending_per_year"), nums.get("spending_goal_per_year")
    if safe is not None and g:
        exp = "works" if safe >= g else "close" if safe >= 0.9 * g else "below_goal"
        paid = (plan.get("needs") or {}).get("paid_of_100")
        if paid is not None and paid < 90 and "above_basics_per_year" in (plan.get("wants") or {}):
            exp = "falls_short"       # since 2026-11-21 basics paid in under 90 of 100 always falls short
        if exp != plan.get("verdict"):
            bad.append(f"verdict {plan.get('verdict')} but safe {safe} vs goal {g}")
    return _ok(not bad, "; ".join(bad))


def family_pet_check(prof: dict, d: dict, plan: dict) -> dict:
    kids, pets = prof.get("children") or [], prof.get("pets") or []
    if not kids and not pets:
        return _ok(True, "n/a")
    fam_text = " ".join([plan_text(plan)] + [json.dumps(a.get("finding") or {}) for a in d["agents"] if a.get("agent") == "family"]
                        + [t.get("summary", "") for t in d["tools"] if t.get("agent") == "family"]).lower()
    miss = []
    if not plan.get("family_moments"):
        miss.append("no family_moments")
    if kids and not re.search(r"child|kid|college|school|son\b|daughter", fam_text):
        miss.append("children not mentioned")
    if pets and not re.search(r"\bpets?\b|\bdogs?\b|\bcats?\b|\bvet", fam_text):
        miss.append("pets not mentioned")
    if (kids or pets) and not re.search(r"\$\s?\d", fam_text):
        miss.append("no cost figure")
    return _ok(not miss, ", ".join(miss))


def cost_check(d: dict) -> dict:
    c = d["cost"]
    if not c:
        return _ok(False, "no cost event")
    tot, cap = c.get("total_usd"), c.get("budget_usd")
    if tot is None or cap is None:
        return _ok(False, f"cost event lacks total_usd or budget_usd: {c}")
    ok = tot <= cap
    return {"ok": ok, "detail": f"${tot:.4f} of ${cap:.2f}", "warn": tot > WARN_USD}


# ---------- direction checks ----------
def count_on(run: dict) -> tuple[float | None, float | None]:
    plan = dig(run)["plan"] or {}
    return (plan.get("wants") or {}).get("per_year"), (plan.get("needs") or {}).get("paid_of_100")


def safe_of(run: dict) -> float | None:
    """Safe spending a year (markets numbers). Wants is safe spending less the basics, floored at 0, so it goes flat for many
    households; safe spending still moves."""
    mk = next((a for a in dig(run)["agents"] if a.get("agent") == "markets"), None)
    return (((mk or {}).get("finding") or {}).get("numbers") or {}).get("safe_spending_per_year")


def _dir(exp: str, base: float, var: float) -> tuple[list[str], bool | None, float]:
    tol = max(NOISE_REL * abs(base), NOISE_ABS)
    delta = var - base
    bad = []
    if exp in ("not_fall", "rise") and -delta > tol:
        bad.append(f"fell {-delta:,.0f} ({100 * -delta / max(abs(base), 1):.1f}%)")
    if exp == "fall" and delta > tol:
        bad.append(f"rose {delta:,.0f} ({100 * delta / max(abs(base), 1):.1f}%)")
    moved = (delta > tol) if exp == "rise" else (-delta > tol) if exp == "fall" else None
    return bad, moved, delta


def direction_checks(base: dict, var: dict, kind: str) -> dict:
    bw, bp = count_on(base)
    vw, vp = count_on(var)
    bs, vs = safe_of(base), safe_of(var)
    if None in (bw, bp, vw, vp):
        return {"ok": False, "kind": kind, "detail": "missing plan numbers", "base": [bw, bp], "variant": [vw, vp]}
    exp = EXPECT.get(kind, "not_fall")
    bad_w, moved_w, delta = _dir(exp, bw, vw)
    bad = [f"wants {x}" for x in bad_w]
    moved_s = None
    delta_s = None
    if bs is not None and vs is not None:
        bad_s, moved_s, delta_s = _dir(exp, bs, vs)
        bad += [f"safe spending {x}" for x in bad_s]
    dp = vp - bp
    if exp in ("not_fall", "rise") and -dp > NOISE_NEEDS:
        bad.append(f"needs paid fell {-dp:.0f} points")
    moved = None if exp == "not_fall" else bool(moved_w or moved_s)
    return {"ok": not bad, "kind": kind, "expect": exp, "moved": moved, "moved_wants": moved_w, "moved_safe": moved_s,
            "delta_wants": delta, "delta_safe": delta_s, "detail": "; ".join(bad),
            "base": [bw, bp, bs], "variant": [vw, vp, vs]}


# ---------- over everything ----------
def evaluate_all() -> dict:
    cases = load_cases()
    by_id = {c["id"]: c for c in cases}
    per_case, direction = {}, []
    for c in cases:
        r = load_run(c["id"])
        if r is None:
            continue
        if c.get("kind", "base") == "base":
            per_case[c["id"]] = run_checks(c, r)
        else:
            b = load_run(c["base_id"])
            if b:
                x = direction_checks(b, r, c["kind"])
                x["id"], x["base_id"] = c["id"], c["base_id"]
                direction.append(x)
    return {"cases": per_case, "direction": direction, "n_cases_defined": sum(1 for c in cases if c.get("kind", "base") == "base"),
            "by_id": {k: v["label"] for k, v in by_id.items()}}


def applicable(res: dict, k: str) -> list[dict]:
    return [r[k] for r in res["cases"].values() if not r[k].get("na")]


def main() -> None:
    out = evaluate_all()
    n = len(out["cases"])
    print(f"{n} base runs checked ({out['n_cases_defined']} defined)")
    for k in CHECKS:
        ap = applicable(out, k)
        f = sum(1 for r in ap if not r["ok"])
        print(f"  {k:18s} fail {f:4d} / {len(ap)} applicable")
    for kind in EXPECT:
        xs = [x for x in out["direction"] if x["kind"] == kind]
        mv = sum(1 for x in xs if x.get("moved"))
        mw = sum(1 for x in xs if x.get("moved_wants"))
        print(f"  direction {kind:13s} fail {sum(1 for x in xs if not x['ok'])} / {len(xs)}  (expect {EXPECT[kind]}; moved the right way: wants or safe {mv}, wants alone {mw})")
    (EVAL_DIR / "checks_results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
