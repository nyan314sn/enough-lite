"""How the What If parser reads the starting points' texts. Usage: diag_parse.py"""
import os
import sys
from pathlib import Path

os.environ["ANTHROPIC_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from app import pipeline  # noqa: E402

p = pipeline.prepare(dict(age=52, state="MI", pay_per_year=52000, retire_age=58, savings={"pretax": 20000, "roth": 0, "taxable": 5000, "cash": 5000},
                          spending_now_per_year=50400, spending_per_year=40000, sources={"spending_now_per_year": "you said", "spending_per_year": "you said"}))
r = pipeline.prepare(dict(age=71, state="FL", retire_age=71, pay_per_year=0, savings={"pretax": 300000, "roth": 0, "taxable": 0, "cash": 0},
                          spending_now_per_year=72000, sources={"spending_now_per_year": "you said"}))
for prof, texts in ((p, ["Retire at 60", "Spend $5,000 a year less now", "Spend $5,000 a year less", "Save $200 a month more",
                         "Claim Social Security at 70", "Spend $34,000 a year in retirement",
                         "Retire at 60, spend $5,000 a year less now and claim Social Security at 70"]),
                    (r, ["Spend $5,000 a year less", "Spend $61,000 a year"])):
    for t in texts:
        ch = pipeline.parse_whatif(t, prof)
        newp, notes = pipeline.apply_whatif(prof, ch) if ch else (prof, {})
        print(f"{t!r:80} -> {ch} | now {newp.spending_now_per_year} goal {newp.spending_per_year} ra {newp.retire_age}")
