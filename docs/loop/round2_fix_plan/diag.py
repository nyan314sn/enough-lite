"""Round 2 plan fix: build the B journeys' households through the intake (no AI), then the plan (no AI), and print the
panel's figures beside the plan's. Usage: diag.py [name ...]"""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["PORTKEY_API_KEY"] = ""
os.environ["ENOUGH_RUN_LOG"] = "0"
LITE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(LITE))

from app import pipeline  # noqa: E402
from app.agents import intake  # noqa: E402
from app.agents.base import RunCtx  # noqa: E402

J = {
    "bus": "I'm 52, a bus driver in Detroit Michigan, divorced, two kids 16 and 14. I make $52,000 and spend $4,200 a month. I have $30,000 saved. I want to retire at 58.",
    "retired": "I'm 71, retired, married, my wife is 69. We live in Florida. I already collect Social Security, $2,900 a month, and she gets $1,100. We have $640,000 saved and spend $6,000 a month. We own our house with no mortgage. No kids.",
    "parent2": "I'm 38, a single mom in Texas with two kids, 6 and 9. I work as a dental hygienist and make $74,000. I have $22,000 saved and spend $4,500 a month. I rent. I want to retire at 65.",
    "parent_skip": "I'm 38, a single mom in Texas with two kids, 6 and 9. I work as a dental hygienist and make $74,000. I have $22,000 saved. I rent. I want to retire at 65.",
    "teacher": "I'm 47, a teacher in Ohio, married, my husband is 49 and works as an electrician. I make $68,000, he makes $82,000. We have $210,000 saved, spend $6,500 a month. I have a state teacher pension of about $3,000 a month starting at 60. Retire at 60. Two kids, 15 and 12.",
    "swe": "I'm 30, a software engineer in Austin Texas, I rent. I make $95,000 and my employer matches 4% of my 401k. I have $45,000 in student loans at 6.5% and $8,000 saved. Retire at 65.",
    "long": "Hi, I'm Maria, 43, a pediatrician in Massachusetts, married to David who's 46 and is a high school teacher. We have three kids aged 12, 9 and 5 and a golden retriever and a cat. I earn $240,000 and he earns $72,000. We have about $650,000 saved, mostly in 401(k)s, plus $40,000 in a bank account. We spend roughly $11,000 a month. We own our house worth $900,000 with a $450,000 mortgage at 3.5%. I have $30,000 of student loans at 5%. We want to retire when I am 62. We want the kids to go to private college and we'd like to travel. David will get a teacher pension of about $2,500 a month at 60.",
}


def answer(q) -> str:
    t = (q.text if q else "").lower()
    chips = q.quick_answers if q else []
    if re.search(r"mortgage payment|a month on the mortgage", t):
        return "$2,900 a month"
    if re.search(r"spend", t):
        return "skip"
    pick = next((c for c in chips if re.search(r"about right|no children|none|rent|skip|same|typical", c, re.I)), None)
    return pick or (chips[0] if chips else "skip")


async def household(name: str) -> dict:
    r = await intake.run(J[name], {}, use_ai=False)
    for _ in range(14):
        if r.ready and not r.missing and (r.question is None or "more" in (r.profile.get("asking") or "")):
            break
        r = await intake.run(answer(r.question), r.profile, use_ai=False)
    return r


async def main(names):
    for n in names:
        r = await household(n)
        f = {x.key: x for x in r.fields}
        p = pipeline.prepare(r.profile)
        ctx = RunCtx(profile=p, use_ai=False)
        plan = await pipeline.run_plan(ctx)
        print("=" * 30, n, "verdict", plan["verdict"])
        for k in ("save_rate", "spending_now_per_year", "spending_per_year", "social_security_per_year", "contributions"):
            if k in f:
                print(f"  panel {k}: {f[k].display} [{f[k].source}]")
        print("  profile spend_now", r.profile.get("spending_now_per_year"), "ss", r.profile.get("social_security_per_year"))
        print("  plan headline:", plan["headline"])
        print("  plan ss", plan["social_security_per_year"], "now_per_year", plan["costs_by_age"]["now_per_year"], "saving", plan["saving"])
        print("  wants:", plan["wants"]["line"])
        print("  wishes:", plan["wishes"]["line"])
        print("  actions:", json.dumps(plan["actions"], indent=0))
        print("  starting:", json.dumps(plan["starting_points"], indent=0))
        print("  levers:", [(x["title"], x["whatif_text"]) for x in plan["levers"]])
        print("  moments:", plan["family_moments"])
        print("  horizon:", plan["horizon_text"])
        for a in plan["assumptions"]:
            print("   -", a)
        if plan.get("consistency"):
            print("  consistency:", plan["consistency"])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(J)))
