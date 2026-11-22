import sys, json, copy, asyncio, re
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "round1_A"))
import lib2 as L
from app import pipeline
from app.tools import estimates, tax


def plan_file(n):
    d = json.load(open(HERE / "plans" / (n + ".json"), encoding="utf-8"))
    return d["profile"], [e for e in d["events"] if e.get("type") == "plan"][0]["plan"], d["events"]


def inproc(prof):
    p = pipeline.prepare(copy.deepcopy(prof))
    plan, ctx = asyncio.run(pipeline.tools_only_plan(p))
    return p, plan, ctx


# F2 already claiming
for n in ("h06_retiree_72", "h07_retiree_no_savings", "n04_already_claiming"):
    prof, plan, _ = plan_file(n)
    txt = " ".join(a["title"] + " " + a["why"] for a in plan["actions"])
    print("F2", n, "stated claim", prof.get("claim_age"), "shown", plan["claim_age"], "already", plan["already_claiming"], "| claim advice in actions:", bool(re.search(r"when to start|claim", txt, re.I)))

# F3 years worked: age 35 retire 45 pay 150k
print("F3 SS age35 retire45 pay150k at 67:", round(estimates.social_security(150000, 67, estimates.career_years(45))["per_year"], -2), "(round1 app 48,300, ~39,500 right). Mine:", round(L.pia_year(150000, 45 - 22)))

# F4 single parent
p, plan, ctx = inproc(dict(age=34, state="CA", pay_per_year=60000, retire_age=65, savings={"pretax": 10000, "roth": 0, "taxable": 0, "cash": 3000}, spending_per_year=40000, spending_now_per_year=45000, children=[{"age": 5}, {"age": 8}]))
t = ctx.results["tax"]
print("F4 single parent 2 kids: federal", t["federal_tax"], "(round1 4,952)", "filing", t["filing"], "credit", t["child_tax_credit"])

# F11 young: age 20 horizon vs timeline end
p, plan, ctx = inproc(dict(age=20, state="TX", pay_per_year=40000, retire_age=65, savings={"pretax": 0, "roth": 0, "taxable": 0, "cash": 2000}, spending_per_year=30000, spending_now_per_year=32000))
cb = plan["costs_by_age"]
print("F11 age20: horizon", plan["horizon_age"], "timeline last age", cb["ages"][-1])
p, plan, ctx = inproc(dict(age=25, state="TX", pay_per_year=40000, retire_age=65, savings={"pretax": 0, "roth": 0, "taxable": 0, "cash": 2000}, spending_per_year=30000, spending_now_per_year=32000))
print("F11 age25: horizon", plan["horizon_age"], "timeline last age", plan["costs_by_age"]["ages"][-1])

# F14 h09
prof, plan, ev = plan_file("h09_high_income_single")
fin = {e["agent"]: e["finding"] for e in ev if e.get("type") == "agent_done"}
tx = fin["tax"]["numbers"]
print("F14 h09 gross withdrawal/yr", tx["gross_withdrawal_per_year"], "rate", tx["effective_rate_on_withdrawals"], "(round1 26,573 vs ~33,000)")

# F15, F16, F18: text
prof, plan, ev = plan_file("h01_single_young")
print("F15 h01 tax text:", [x for x in fin["tax"].get("details", [])] if False else "")
tf = {e["agent"]: e["finding"] for e in plan_file("h01_single_young")[2] if e.get("type") == "agent_done"}["tax"]
print("   h01 tax headline/details:", tf.get("headline"), tf.get("details"))
for n in ("h01_single_young", "h14_near_retire_pension_couple"):
    prof, plan, _ = plan_file(n)
    print("F16", n, plan["verdict"], "|", plan["wants"]["line"], "| wishes:", plan["wishes"]["line"], "| above basics", plan["wants"]["above_basics_per_year"], "basics", plan["needs"]["basics_per_year"])

# F17 h13 timeline
prof, plan, _ = plan_file("h13_kids_pets")
cb = plan["costs_by_age"]
print("F17 h13 timeline ages40-70:", [(a, t) for a, t in zip(cb["ages"], cb["total"]) if 55 <= a <= 68])

# F18 grammar
prof, plan, ev = plan_file("h01_single_young")
lf = {e["agent"]: e["finding"] for e in ev if e.get("type") == "agent_done"}["longevity"]
print("F18 longevity:", lf.get("headline"), lf.get("details"))

# F20 h12 emergency
prof, plan, _ = plan_file("h12_match_debt")
print("F20 h12 levers:", [(l["key"], l["why"]) for l in plan["levers"] if l["key"] == "emergency"], "exact cash", prof["savings"]["cash"], "spend now", prof["spending_now_per_year"], "-> exact short", round(3 * prof["spending_now_per_year"] / 12 - prof["savings"]["cash"]))

# F21 h15 neighbour
prof, plan, _ = plan_file("h15_early_retire_claim62")
print("F21 h15 note:", plan["neighbors"]["note"][:200])
for n in ("h07_retiree_no_savings", "h08_low_income_low_savings"):
    prof, plan, _ = plan_file(n)
    print("F21", n, "count", plan["wants"]["per_year"], "SS", plan["social_security_per_year"], "headline:", plan["headline"][-150:])

# F19/F9 actions
for n in ("h03_teacher_pension", "h10_ss_stated_late", "h04_renter_loans", "h14_near_retire_pension_couple"):
    prof, plan, _ = plan_file(n)
    print("F9/F19", n, [a["title"] for a in plan["actions"]], "levers", [l["key"] for l in plan["levers"]])

# retiree spending rule
base = dict(age=70, state="TX", pay_per_year=0, retire_age=70, savings={"pretax": 300000, "roth": 0, "taxable": 50000, "cash": 20000}, social_security_per_year=28000, claim_age=67)
for lab, extra in (("now 50k, none else", dict(spending_now_per_year=50000)), ("now 50k ratio .8", dict(spending_now_per_year=50000, retire_spend_ratio=0.8)),
                   ("now 3k (slip)", dict(spending_now_per_year=3000)), ("goal 52k only", dict(spending_per_year=52000)), ("nothing", dict())):
    p, plan, ctx = inproc({**base, **extra})
    print("RETIREE", lab, "-> now", p.spending_now_per_year, "retire spending", p.spending_per_year, "|", p.notes.get("spending_per_year", "")[:70], "|", p.notes.get("spending_now_per_year_set_aside", "")[:60])
# a working person: ratio .8
p, plan, ctx = inproc(dict(age=50, state="TX", pay_per_year=90000, retire_age=65, savings={"pretax": 300000, "roth": 0, "taxable": 50000, "cash": 20000}, spending_now_per_year=70000))
print("WORKER now 70k -> retire spending", p.spending_per_year)

# state SS: effect of the 8-state list on a CO 68-year-old
import lib2
prof, plan, _ = plan_file("n07_state_taxes_ss_CO")
print("STATE n07 CO assumptions:", [a for a in plan["assumptions"] if "state taxes" in a])
sv = prof["savings"]
r1 = L.ret_rate(62000, 34000, sv, "CO", False, 1)
lib2.SS_STATES.discard("CO")
r2 = L.ret_rate(62000, 34000, sv, "CO", False, 1)
print("   CO ss tax rate with state taxing SS", round(r1[1], 4), "wd rate", round(r1[0], 4), "| if exempt (as Colorado does at 65+)", round(r2[1], 4), round(r2[0], 4))
