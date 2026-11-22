"""Checks on the live plans (plans/*.json): verdict rule, needs line, headline, below-SS note, horizon text, saving,
starting points (recomputed in-process on the person's numbers), assumptions facts, action sanity."""
import sys, json, re, glob, os, asyncio, copy
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "round1_A"))
import lib2 as L
from app import pipeline
from app.tools import costs

issues = []


def flag(name, msg):
    issues.append((name, msg)); print("  FLAG", name, msg)


async def go(prof):
    p = pipeline.prepare(copy.deepcopy(prof))
    plan, ctx = await pipeline.tools_only_plan(p)
    return p, plan, ctx


def money(x):
    return f"${x:,.0f}"


for f in sorted(glob.glob(str(HERE / "plans" / "*.json"))):
    name = os.path.basename(f)[:-5]
    d = json.load(open(f, encoding="utf-8")); prof = d["profile"]
    plan = [e for e in d["events"] if e.get("type") == "plan"][0]["plan"]
    cnt, goal, paid, basics = plan["wants"]["per_year"], plan["spending_goal"], plan["needs"]["paid_of_100"], plan["needs"]["basics_per_year"]
    v = plan["verdict"]
    print(name, v, "count", cnt, "goal", goal, "paid", paid, "text", plan.get("text_source"))
    exp = "falls_short" if (paid is not None and paid < 90) else ("works" if cnt >= goal else ("close" if cnt >= .9 * goal else "below_goal"))
    if exp != v:
        flag(name, f"verdict {v} expected {exp}")
    nl = plan["needs"]["line"]
    if paid is not None and paid < 90 and re.search(r"paid in all|are paid in \d+ of 100 scenarios\.$", nl) and "only" not in nl and "not paid" not in nl:
        flag(name, "needs line implies paid " + nl)
    if f"${cnt:,.0f}" not in plan["headline"]:
        flag(name, "headline lacks count-on")
    ss = plan.get("social_security_per_year") or 0
    if cnt < ss:
        print("   count-on below SS:", plan["headline"][-170:])
    # already claiming
    atxt = " ".join(a["title"] + " " + a["why"] for a in plan["actions"]).lower()
    if plan.get("already_claiming") and re.search(r"when to (start|claim)|plan to claim|claim social security at", atxt):
        flag(name, "claiming advice though already claiming: " + atxt[:120])
    # claim age shown vs profile
    if prof.get("claim_age") is not None and plan["claim_age"] != prof["claim_age"] and not (prof["age"] >= prof["claim_age"] and False):
        flag(name, f"claim shown {plan['claim_age']} vs stated {prof['claim_age']}")
    if prof.get("partner_claim_age") is not None and plan.get("partner_claim_age") != prof["partner_claim_age"]:
        flag(name, f"partner claim shown {plan.get('partner_claim_age')} vs stated {prof['partner_claim_age']}")
    # horizon text
    ht = plan["horizon_text"]
    if prof.get("has_partner"):
        print("   horizon", ht, "age", prof["age"], "partner", prof.get("partner_age"), "h", plan["horizon_age"])
    elif ht != f"to age {plan['horizon_age']}":
        flag(name, "horizon text " + ht)
    # saving
    p, plan2, ctx = asyncio.run(go(prof))
    sv = plan["saving"]
    working = p.retire_age > p.age
    if working:
        c = costs.contributions(p)
        mt = costs.match_info(p)
        accounts = c["you"] + c["partner"]
        parts = accounts + c["other"] + (mt.get("match") or 0) + sv["unspent_pay_per_year"]
        if abs(max(0, parts) - sv["per_year"]) > 1.5 and not (p.partner_pay_per_year and False):
            print(f"   saving: per_year {sv['per_year']} vs parts {parts:,.0f} {sv}")
        # my own unspent pay
        tx = ctx.results["tax"]
        after = tx["after_tax_pay"]
        left = after - p.spending_now_per_year - (c["you"] + c["partner"] + c["other"])
        print(f"   saving per_year {sv['per_year']:,} accounts {sv['accounts_per_year']:,} other {sv['other_per_year']:,} match {sv['match_per_year']:,} unspent {sv['unspent_pay_per_year']:,} | my after-tax {after:,} left {left:,.0f}")
    else:
        if sv["per_year"] != 0:
            flag(name, f"retired but saving {sv}")
    # starting points
    sp = plan.get("starting_points") or []
    if v == "falls_short" and not sp:
        print("   falls_short with NO starting points")
    if v != "falls_short" and sp:
        flag(name, "starting points though not falls_short")
    for x in sp:
        title = x["title"]
        mod = copy.deepcopy(prof)
        m1 = re.match(r"Retire at (\d+)", title); m2 = re.match(r"Spend \$([\d,]+) a year less now", title)
        if m1:
            new = int(m1.group(1))
            mod["retire_age"] = new
            if mod.get("partner_retire_age") is not None and prof.get("has_partner"):
                pass
            if new > 70 or new <= prof["retire_age"]:
                flag(name, f"starting point {title} (stated {prof['retire_age']})")
            if new - prof["retire_age"] > 2:
                flag(name, f"starting point '{title}' is {new - prof['retire_age']} years later than stated {prof['retire_age']} (plan says up to 2)")
        elif m2:
            less = float(m2.group(1).replace(",", ""))
            pp = pipeline.prepare(copy.deepcopy(prof))
            pp.spending_now_per_year = max(0, pp.spending_now_per_year - less); pp.sources["spending_now_per_year"] = "you said"
            _, pl2, _ = asyncio.run(go(pp.model_dump()))
            r = (pl2["needs"]["paid_of_100"], pl2["wants"]["per_year"])
            print(f"   start '{title}': app {(x['paid_of_100'], x['count_on_per_year'])} recompute {r}")
            continue
        elif "Claim Social Security at 70" in title:
            mod["claim_age"] = 70
        _, pl2, _ = asyncio.run(go(mod))
        r = (pl2["needs"]["paid_of_100"], pl2["wants"]["per_year"])
        ok = r == (x["paid_of_100"], x["count_on_per_year"])
        print(f"   start '{title}': app {(x['paid_of_100'], x['count_on_per_year'])} recompute {r} {'OK' if ok else 'DIFF'}; age kept {pl2.get('retire_age')}; fixes basics? {r[0] >= 90}")
        if not ok:
            flag(name, f"starting point '{title}' differs from recompute")
    if sp and all((x["paid_of_100"] < 90) for x in sp) and "would change that" in plan["headline"]:
        flag(name, "headline says starting points 'show what would change that' but none makes the basics safe: " + "; ".join(x["result"] for x in sp))
print("ISSUES", len(issues))
