"""Households for the rules-audit plan checks: the example doctor (answered as the live walk did) and 5 eval households."""
import asyncio, copy, json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from app import pipeline
from app.agents import intake

EXAMPLE = ("I'm 45, a doctor in Connecticut earning $310,000. My wife, 43, stays home with our kids, 13, 10 and 6, and our 2 dogs. "
           "We have $920,000 saved and owe $420,000 on our $850,000 home. "
           "The oldest will go to a state school, the middle one private. I'd like to retire at 62.")
RULES = [(r"about right", "That's about right"), (r"wife work|partner work", "Not working"), (r"mortgage payment", "$2,900"),
         (r"owe anything", "No other debts"), (r"spend in a year", None)]

def example(spend="$5,000 a month", turns=8):
    r = asyncio.run(intake.run(EXAMPLE, {}, use_ai=False))
    for _ in range(turns):
        q = (r.question.text if r.question else "") or ""
        ans = next((a for rx, a in RULES if re.search(rx, q, re.I)), "skip")
        ans = spend if ans is None else ans
        r = asyncio.run(intake.run(ans, r.profile, use_ai=False))
        if ans == spend:
            break
    return r.profile

def eval_cases(ids):
    cases = {json.loads(l)["id"]: json.loads(l) for l in open(ROOT / "docs/loop/round3_A/evalcopy/cases.jsonl", encoding="utf-8")}
    return {i: copy.deepcopy(cases[i]["profile"]) for i in ids}

KIDS = [{"age": 13, "college": True, "college_type": "public", "college_source": "you said"},
        {"age": 10, "college": True, "college_type": "private", "college_source": "you said"},
        {"age": 6, "college": True}]

def example_full(spend="$5,000 a month"):
    """The example as the audit saw it: children and college kept even if the intake loses them."""
    p = example(spend)
    if not p.get("children"):
        p["children"] = copy.deepcopy(KIDS)
        p.setdefault("sources", {})["children"] = "you said"
    return p
