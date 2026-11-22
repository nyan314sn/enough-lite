"""One-figure rule: panel (completed profile) vs plan, 15 varied households, independent recompute of saving."""
import sys, copy, json, asyncio, re
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE))
import lib2 as L
import get_plans as G, hh2
from app import pipeline
from app.tools import tax
S = hh2.S
A = {}
A.update(G.H); A.update(hh2.N)
def strip(n, drop=("spending_per_year","spending_now_per_year"), **extra):
    d = copy.deepcopy(A[n]); [d.pop(k, None) for k in drop]; d.update(extra); return d
C = {
 "c01_skip_spend_single": strip("h01_single_young"),
 "c02_skip_spend_couple": strip("h05_couple_mortgage"),
 "c03_skip_all_spend_ss_retiree": strip("n04_already_claiming", drop=("spending_per_year","spending_now_per_year")),
 "c04_est_ss_late_claim": dict(A["h03_teacher_pension"], claim_age=70),
 "c05_skip_goal_only": strip("h09_high_income_single", drop=("spending_per_year",)),
 "c06_skip_now_only": strip("h13_kids_pets", drop=("spending_now_per_year",)),
 "c07_deficit": dict(age=34, state="OH", pay_per_year=16500, retire_age=67, savings=S(20000,0,0,10000), spending_per_year=15000, spending_now_per_year=28000),
 "c08_partner_claim70": A["n10_partner_claim70"],
 "c09_ss_stated_claim_late": dict(age=60, state="WA", pay_per_year=110000, retire_age=70, savings=S(500000,50000,100000,40000), spending_per_year=70000, spending_now_per_year=85000, social_security_per_year=40000, claim_age=69),
 "c10_two_earners_skip": strip("n02_gap10_couple"),
 "c11_match": A["h12_match_debt"],
 "c12_partner_retired_working_self": dict(age=58, has_partner=True, partner_age=66, state="TX", pay_per_year=90000, partner_pay_per_year=0, retire_age=64, savings=S(400000,0,100000,40000), spending_per_year=70000, spending_now_per_year=80000, social_security_per_year=45000),
 "c13_skip_young_kids": strip("n01_single_parent"),
 "c14_already_ret_est": dict(age=67, state="NY", pay_per_year=0, retire_age=67, savings=S(500000,50000,100000,40000)),
 "c15_catchup_62": dict(age=62, state="CA", pay_per_year=250000, retire_age=66, savings=S(900000,100000,200000,50000), spending_per_year=120000, saving={"contrib_you": 36000}),
}
def capf(a):
    lim = tax.limits_2027(); return lim["401k_limit"] + (lim["401k_catch_up_60_to_63"] if 60<=a<=63 else lim["401k_catch_up_50_plus"] if a>=50 else 0)
out = {}
for n, prof in C.items():
    p = pipeline.prepare(copy.deepcopy(prof))
    try:
        ev = G.post(prof)
    except Exception as e:
        print(n, "POST ERR", e); continue
    plan = [e for e in ev if e.get("type") == "plan"][0]["plan"]
    sv = plan["saving"]; now = plan["costs_by_age"]["now_per_year"]
    issues = []
    if plan["consistency"]: issues.append(f"consistency non-empty: {plan['consistency']}")
    if p.spending_now_per_year and now != round(p.spending_now_per_year): issues.append(f"now {now} vs {p.spending_now_per_year}")
    # independent saving
    exp = None
    if p.retire_age > p.age:
        rate = p.save_rate if p.save_rate is not None else 0
        cy = p.saving.contrib_you if p.saving.contrib_you is not None else rate * (p.pay_per_year or 0)
        cp = p.saving.contrib_partner if p.saving.contrib_partner is not None else rate * (p.partner_pay_per_year or 0)
        oth = (p.saving.other_per_month or 0) * 12
        pre = min(cy, capf(p.age)) if (p.pay_per_year or 0) > 0 else 0
        if p.has_partner and (p.partner_pay_per_year or 0) > 0: pre += min(cp, capf(p.partner_age))
        kids = sum(1 for k in p.children if k.age is not None and k.age < 17)
        w = L.work_tax(p.pay_per_year or 0, p.partner_pay_per_year or 0, p.state, p.has_partner, kids, pre, addl_medicare=True)
        after = (p.pay_per_year or 0) + (p.partner_pay_per_year or 0) - w["fed"] - w["state"] - w["fica"]
        unspent = after - (p.spending_now_per_year or 0) - (cy + cp + oth) if p.spending_now_per_year else 0
        pw = bool(p.has_partner and p.partner_age and (p.partner_pay_per_year or 0) > 0 and p.partner_age < (p.partner_retire_age or p.retire_age))
        match = sv["match_per_year"]
        tot = cy + oth + match + (cp if pw else 0) + (unspent if (pw or not (p.partner_pay_per_year or 0)) else 0)
        exp = round(tot)
        if abs(exp - sv["per_year"]) > 150: issues.append(f"saving plan {sv['per_year']} vs mine {exp}")
    # SS
    txt = plan["headline"] + " " + " ".join(plan["assumptions"])
    ssp = plan["social_security_per_year"]
    panel_ss = round(p.social_security_per_year or 0)
    if panel_ss and ("$%s" % f"{panel_ss:,}") not in txt and abs(panel_ss - ssp) >= 100: issues.append(f"panel SS {panel_ss} not named; plan {ssp}")
    ppl = L.ss_people(p.model_dump())
    mine_ss = round(sum(x["pia"] * L.cf(x["claim"]) for x in ppl[:1]))
    print(f"{n:34s} spend_now {p.spending_now_per_year} [{p.sources.get('spending_now_per_year')}] plan_now {now} | saving plan {sv['per_year']} mine {exp} assumed {sv.get('assumed')} | SS panel {panel_ss} [{p.sources.get('social_security_per_year')}] plan {ssp} claim {plan['claim_age']} mine(you own at claim) {mine_ss} | {'OK' if not issues else issues}", flush=True)
    out[n] = dict(issues=issues)
print("households with issues:", sum(1 for v in out.values() if v["issues"]), "of", len(out))
