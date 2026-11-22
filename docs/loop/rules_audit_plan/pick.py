import json
from hh import ROOT
cases = [json.loads(l) for l in open(ROOT / "docs/loop/round3_A/evalcopy/cases.jsonl", encoding="utf-8")]
n = 0
for c in cases:
    if c["kind"] != "base": continue
    p = c["profile"]
    if (p.get("retire_age") or 0) <= (p.get("age") or 0) or (p.get("retire_age") or 0) > 64: continue
    pay = (p.get("pay_per_year") or 0) + (p.get("partner_pay_per_year") or 0)
    if pay <= 0: continue
    h = p.get("home") or {}
    print(c["id"], p.get("age"), p.get("partner_age"), p.get("retire_age"), pay, p.get("spending_now_per_year"), p.get("spending_per_year"),
          h.get("mortgage_balance"), len(p.get("children") or []), p.get("state"))
    n += 1
    if n > 40: break
