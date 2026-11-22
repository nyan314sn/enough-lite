from pathlib import Path
f = Path(__file__).resolve().parents[3] / "tests/test_loop1_engine.py"
s = f.read_text(encoding="utf-8")
rep = [
('''    r = tax.retirement_years(180000, 0, {"pretax": 1500000, "roth": 300000, "taxable": 700000, "cash": 200000}, "NY", False, 0)
    assert r["tax_per_year_retired"] > 30000          # was $26,573 against about $33,000''',
 '''    # all pre-tax, no state income tax, no Social Security: the withdrawal less its own federal tax is the need
    r = tax.retirement_years(60000, 0, {"pretax": 1000000}, "TX", False, 0)
    w = r["gross_withdrawal_per_year"]
    assert abs(w - tax.federal_tax(w, "single") - 60000) < 60'''),
('''        ("H16", dict(age=66, has_partner=True, partner_age=64, state="TN", pay_per_year=0, retire_age=66,
                     savings=S(1200000, 300000, 400000, 100000), spending_per_year=110000, spending_now_per_year=120000,
                     social_security_per_year=55000, claim_age=67), "claim+2"),''',
 '''        ("H11c", dict(H11, claim_age=67), "claim+2"),'''),
]
for a, b in rep:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
f.write_text(s, encoding="utf-8")
print("ok")
