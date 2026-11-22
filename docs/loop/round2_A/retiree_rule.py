import sys, copy, asyncio
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2]))
from app import pipeline

base = dict(age=70, state="TX", pay_per_year=0, retire_age=70, savings={"pretax": 300000, "roth": 0, "taxable": 50000, "cash": 20000}, social_security_per_year=28000, claim_age=67)
S = {"spending_now_per_year": "you said"}
cases = (("now 50k said", dict(spending_now_per_year=50000, sources=S)),
         ("now 50k said, ratio .8 said", dict(spending_now_per_year=50000, retire_spend_ratio=0.8, sources={**S, "retire_spend_ratio": "you said"})),
         ("now 3k (slip) said", dict(spending_now_per_year=3000, sources=S)),
         ("now 7k said (just above a quarter?)", dict(spending_now_per_year=7000, sources=S)),
         ("goal 52k said only", dict(spending_per_year=52000, sources={"spending_per_year": "you said"})),
         ("goal 3k said (slip)", dict(spending_per_year=3000, sources={"spending_per_year": "you said"})))
for lab, extra in cases:
    p = pipeline.prepare({**base, **extra})
    print("RETIREE", lab, "-> now", p.spending_now_per_year, "retire spending", p.spending_per_year, "|", p.notes.get("spending_per_year", "")[:80], "|", (p.notes.get("spending_now_per_year_set_aside") or p.notes.get("spending_per_year_set_aside") or "")[:50])
w = dict(age=50, state="TX", pay_per_year=90000, retire_age=65, savings={"pretax": 300000, "roth": 0, "taxable": 50000, "cash": 20000}, spending_now_per_year=70000, sources=S)
p = pipeline.prepare(w)
print("WORKER now 70k said -> retire spending", p.spending_per_year, p.notes.get("spending_per_year", "")[:60])
