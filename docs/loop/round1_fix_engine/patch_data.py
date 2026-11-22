import json
from pathlib import Path
D = Path(__file__).resolve().parents[3] / "app/data"
f = D / "tax_rules.json"
d = json.loads(f.read_text(encoding="utf-8"))
d["child_tax_credit"] = {
    "per_child_under_17": 2200, "refundable_max_per_child": 1700, "refundable_earned_income_floor": 2500,
    "refundable_rate": 0.15, "phaseout_start": {"married_joint": 400000, "other": 200000}, "phaseout_per_1000": 50,
    "source": "IRC section 24 as amended by Public Law 119-21 (2025): $2,200 a qualifying child under 17, indexed from 2026; "
              "refundable part up to $1,700 (2025 figure), 15% of earnings above $2,500; phase-out of $50 per $1,000 above "
              "$400,000 (married filing jointly) or $200,000 (others). https://www.irs.gov/credits-deductions/individuals/child-tax-credit . "
              "The 2027 indexed amounts were not checked; the 2025-2026 figures are used."}
f.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
g = D / "state_tax.json"
s = json.loads(g.read_text(encoding="utf-8"))
s["taxes_social_security"] = {
    "states": ["CO", "CT", "MN", "MT", "NM", "RI", "UT", "VT"],
    "note": "States that tax some Social Security benefits in 2026 (West Virginia finished its phase-out in 2026). All other "
            "states exempt it. Most of these eight also exempt it below an income limit, which is not modelled. "
            "Source: Tax Foundation, 'Does Your State Tax Social Security Benefits?' (2025) and state revenue pages; "
            "not re-checked line by line.",
    "url": "https://taxfoundation.org/data/all/state/states-that-tax-social-security-benefits/"}
g.write_text(json.dumps(s, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("ok")
