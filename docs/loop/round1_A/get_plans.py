import json, sys, urllib.request
from pathlib import Path
OUT = Path(__file__).parent / "plans"
OUT.mkdir(exist_ok=True)
URL = "http://127.0.0.1:8030"

def S(pretax=0, roth=0, taxable=0, cash=0):
    return {"pretax": pretax, "roth": roth, "taxable": taxable, "cash": cash}

H = {
 "h01_single_young": dict(age=28, state="TX", pay_per_year=70000, retire_age=65, savings=S(20000, 5000, 5000, 8000), spending_per_year=45000, spending_now_per_year=50000, home={"owns": False, "rent": 1500}),
 "h02_doctor_couple": dict(age=42, has_partner=True, partner_age=40, state="CA", pay_per_year=380000, partner_pay_per_year=150000, retire_age=62, savings=S(600000, 100000, 300000, 100000), spending_per_year=160000, spending_now_per_year=200000, home={"owns": True, "value": 1400000, "mortgage_balance": 700000, "mortgage_payment": 4800, "mortgage_rate": 0.04}, children=[{"age": 8}, {"age": 5}]),
 "h03_teacher_pension": dict(age=55, state="NY", pay_per_year=85000, retire_age=60, savings=S(250000, 20000, 30000, 25000), spending_per_year=55000, spending_now_per_year=65000, pensions=[{"who": "you", "per_year": 40000, "start_age": 60, "inflation_adjusted": True}], home={"owns": True, "value": 450000, "mortgage_balance": 0, "mortgage_payment": 0}),
 "h04_renter_loans": dict(age=33, state="IL", pay_per_year=62000, retire_age=67, savings=S(15000, 0, 2000, 3000), spending_per_year=40000, spending_now_per_year=48000, debts=[{"kind": "student", "balance": 45000, "rate": 0.065, "monthly_payment": 500}, {"kind": "credit_card", "balance": 8000, "rate": 0.24, "monthly_payment": 300}], home={"owns": False, "rent": 1700}),
 "h05_couple_mortgage": dict(age=48, has_partner=True, partner_age=47, state="OH", pay_per_year=90000, partner_pay_per_year=70000, retire_age=65, savings=S(300000, 50000, 40000, 30000), spending_per_year=85000, spending_now_per_year=105000, home={"owns": True, "value": 420000, "mortgage_balance": 180000, "mortgage_payment": 1900, "mortgage_rate": 0.045}, children=[{"age": 16, "college_type": "public"}, {"age": 13, "college_type": "private"}]),
 "h06_retiree_72": dict(age=72, state="FL", pay_per_year=0, retire_age=72, savings=S(400000, 100000, 150000, 50000), spending_per_year=60000, spending_now_per_year=65000, social_security_per_year=36000, claim_age=67, home={"owns": True, "value": 350000}),
 "h07_retiree_no_savings": dict(age=68, state="MI", pay_per_year=0, retire_age=68, savings=S(0, 0, 0, 5000), spending_per_year=28000, spending_now_per_year=30000, social_security_per_year=22000, claim_age=66, home={"owns": False, "rent": 1100}),
 "h08_low_income_low_savings": dict(age=45, state="GA", pay_per_year=32000, retire_age=67, savings=S(8000, 0, 0, 2000), spending_per_year=26000, spending_now_per_year=30000, home={"owns": False, "rent": 1000}),
 "h09_high_income_single": dict(age=50, state="NY", pay_per_year=450000, retire_age=60, savings=S(1500000, 300000, 700000, 200000), spending_per_year=180000, spending_now_per_year=230000, home={"owns": True, "value": 1200000}),
 "h10_ss_stated_late": dict(age=60, state="WA", pay_per_year=110000, retire_age=70, savings=S(500000, 50000, 100000, 40000), spending_per_year=70000, spending_now_per_year=85000, social_security_per_year=40000),
 "h11_partner_longer": dict(age=58, has_partner=True, partner_age=52, state="PA", pay_per_year=100000, partner_pay_per_year=80000, retire_age=62, partner_retire_age=67, savings=S(400000, 50000, 60000, 40000), spending_per_year=90000, spending_now_per_year=110000),
 "h12_match_debt": dict(age=38, has_partner=True, partner_age=36, state="CO", pay_per_year=95000, partner_pay_per_year=60000, retire_age=65, savings=S(60000, 10000, 10000, 10000), spending_per_year=70000, spending_now_per_year=90000, saving={"contrib_you": 3000, "match_rate": 0.5, "match_cap": 0.06}, debts=[{"kind": "credit_card", "balance": 15000, "rate": 0.22, "monthly_payment": 450}], children=[{"age": 4}], pets=[{"kind": "dog", "count": 1}]),
 "h13_kids_pets": dict(age=40, has_partner=True, partner_age=39, state="NC", pay_per_year=80000, partner_pay_per_year=45000, retire_age=65, savings=S(90000, 10000, 20000, 15000), spending_per_year=72000, spending_now_per_year=90000, children=[{"age": 10}, {"age": 7}, {"age": 3}], pets=[{"kind": "dog", "count": 2}, {"kind": "cat", "count": 1}], home={"owns": True, "value": 380000, "mortgage_balance": 250000, "mortgage_payment": 1800, "mortgage_rate": 0.05}),
 "h14_near_retire_pension_couple": dict(age=63, has_partner=True, partner_age=61, state="MA", pay_per_year=120000, partner_pay_per_year=40000, retire_age=65, savings=S(700000, 80000, 120000, 60000), spending_per_year=100000, spending_now_per_year=120000, pensions=[{"who": "partner", "per_year": 18000, "start_age": 62, "inflation_adjusted": False}]),
 "h15_early_retire_claim62": dict(age=61, state="AZ", pay_per_year=0, retire_age=61, savings=S(800000, 100000, 100000, 50000), spending_per_year=65000, spending_now_per_year=70000, claim_age=62),
 "h16_wealthy_retire_now": dict(age=66, has_partner=True, partner_age=64, state="TN", pay_per_year=0, retire_age=66, savings=S(1200000, 300000, 400000, 100000), spending_per_year=110000, spending_now_per_year=120000, social_security_per_year=55000, claim_age=67),
}

def post(profile):
    body = json.dumps({"profile": profile}).encode()
    req = urllib.request.Request(URL + "/api/plan", data=body, headers={"Content-Type": "application/json", "Accept": "text/event-stream", "X-Enough-Test": "1", "X-Session-Id": "auditA-" + str(abs(hash(json.dumps(profile, sort_keys=True))))[:8]}, method="POST")
    ev = []
    with urllib.request.urlopen(req, timeout=300) as r:
        buf = []
        for raw in r:
            line = raw.decode().rstrip("\r\n")
            if line == "":
                if buf:
                    ev.append(json.loads("\n".join(buf))); buf = []
            elif line.startswith("data:"):
                buf.append(line[5:].lstrip())
        if buf: ev.append(json.loads("\n".join(buf)))
    return ev

if __name__ == "__main__":
    names = sys.argv[1:] or list(H)
    for n in names:
        prof = H[n]
        for c in prof.get("children", []):
            pass
        ev = post(prof)
        (OUT / (n + ".json")).write_text(json.dumps({"profile": prof, "events": ev}, indent=1), encoding="utf-8")
        plan = [e for e in ev if e.get("type") == "plan"]
        print(n, [e.get("type") for e in ev][:3], len(ev), "plan" if plan else "NOPLAN")
