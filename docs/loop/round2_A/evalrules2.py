import json, glob, os, re, sys, collections
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "round1_A"))
os.chdir(HERE)
import numcheck
files = sorted(glob.glob("eval_runs/*.json"))
C = collections.Counter(); ex = collections.defaultdict(list)


def flag(k, name, info=""):
    C[k] += 1
    if len(ex[k]) < 4:
        ex[k].append((name, info))


n = 0
for f in files:
    d = json.load(open(f, encoding="utf-8")); name = os.path.basename(f)[:-5]
    if d.get("status") != "ok":
        flag("status_error", name, d.get("error")); continue
    plan = [e for e in d["events"] if e.get("type") == "plan"][0]["plan"]; prof = d["profile"]; n += 1
    paid = plan["needs"]["paid_of_100"]; v = plan["verdict"]; cnt = plan["wants"]["per_year"]; basics = plan["needs"]["basics_per_year"]; goal = plan["spending_goal"]
    exp = "falls_short" if (paid is not None and paid < 90) else ("works" if cnt >= goal else ("close" if cnt >= .9 * goal else "below_goal"))
    if exp != v: flag("verdict_rule_mismatch", name, (paid, cnt, goal, v))
    C["verdict_" + v] += 1
    if f"${cnt:,.0f}" not in plan["headline"]: flag("headline_count_mismatch", name, cnt)
    ab = max(0, round(cnt - basics, -2))
    if abs(plan["wants"]["above_basics_per_year"] - ab) > .5: flag("above_basics_mismatch", name)
    if plan["count_on_per_year"] != cnt: flag("count_on_field_mismatch", name)
    titles = [a["title"].lower() for a in plan["actions"]]
    if len(set(titles)) < len(titles): flag("duplicate_action", name)
    keys = [l["key"] for l in plan["levers"]]
    txt = " ".join(a["title"] + " " + a["why"] for a in plan["actions"]).lower()
    if "debt" in keys and "debt" not in txt: flag("debt_lever_no_action", name)
    if "match" in keys and "match" not in txt: flag("match_lever_no_action", name)
    if "emergency" in keys and "emergency" not in txt: flag("emergency_lever_dropped", name)
    if "emergency" in keys and "emergency" not in txt and "check your plan once a year" in txt: flag("filler_while_emergency_dropped", name)
    if "check your plan once a year" in txt: flag("filler_present", name)
    if any(re.match(r"^\s*(keep|continue|stay)\b", t) for t in titles): flag("status_line_action", name, titles)
    nl = plan["needs"]["line"].lower()
    if paid is not None and paid < 90 and re.search(r"you pay them|paid every|paid in all", nl): flag("needs_line_implies_paid", name)
    # claim age display
    ca = prof.get("claim_age")
    if ca is not None and plan["claim_age"] != ca: flag("claim_age_shown_differs", name, (ca, plan["claim_age"], prof["age"]))
    pca = prof.get("partner_claim_age")
    if pca is not None and plan.get("partner_claim_age") != pca: flag("partner_claim_shown_differs", name, (pca, plan.get("partner_claim_age")))
    # close text
    wl = (plan["wants"]["line"] + " " + plan["wishes"]["line"] + " " + plan["headline"]).lower()
    if v in ("close", "below_goal", "works") and "falls short" in wl: flag("says_falls_short_when_not", name, v)
    if "little room" in wl and ab >= .25 * basics: flag("little_room_but_25pct_above", name, (ab, basics))
    # starting points
    sp = plan.get("starting_points") or []
    if v == "falls_short" and not sp: flag("falls_short_no_starting_points", name)
    if v != "falls_short" and sp: flag("starting_points_not_falls_short", name)
    if sp and "would change that" in plan["headline"] and all(x["paid_of_100"] < 90 for x in sp): flag("headline_promises_fix_but_none_fixes", name)
    for x in sp:
        m1 = re.match(r"Retire at (\d+)", x["title"])
        if m1:
            new = int(m1.group(1))
            if new > 70: flag("starting_point_retire_past_70", name, new)
            if new - plan["retire_age"] > 2: flag("starting_point_retire_more_than_2_later", name, (plan["retire_age"], new))
            if new <= plan["retire_age"]: flag("starting_point_not_later", name)
        if x["paid_of_100"] <= (paid or 0) and x["count_on_per_year"] < 1.05 * cnt: flag("starting_point_no_help", name)
    if plan["retire_age"] != prof.get("retire_age") and prof.get("retire_age") is not None: flag("retire_age_changed", name, (prof.get("retire_age"), plan["retire_age"]))
    # assumptions present, today's dollars
    if not plan.get("assumptions") or "today's dollars" not in plan["assumptions"][0]: flag("assumptions_missing", name)
    # horizon text
    if prof.get("has_partner") and plan["horizon_text"].startswith("until") and plan["horizon_age"] <= 100: flag("until_partner_used_when_h<=100", name)
    # worth-checking rules
    wc = {w["kind"] for w in plan["worth_checking"]}
    sv = sum((prof.get("savings") or {}).values())
    if "income_annuity" in wc and (prof.get("has_partner") or prof.get("pensions")): flag("annuity_fired_partner_or_pension", name)
    if "income_annuity" in wc and sv < 200000: flag("annuity_fired_low_savings", name)
    try:
        bad = numcheck.check(d)
        if bad: flag("dollar_figure_not_in_tool_outputs", name, bad[:2])
    except Exception as e:
        flag("numcheck_err", name, str(e)[:50])
    ts = plan["text_source"]
    flag("text_" + ("ai_first" if ts == "ai" else "ai_second" if "second" in ts else "template"), name, ts[:60])
    for e in d["events"]:
        if e.get("type") == "agent_done" and str(e["finding"].get("source", "")).startswith("template"):
            flag("agent_template_" + e["agent"], name)
print("runs ok analysed:", n)
for k, vv in sorted(C.items()):
    print(f"{k:50s} {vv:4d}  {ex[k][:2]}")
