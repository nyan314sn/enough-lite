"""Different words for the same input: does the intake chat store the right figure?

Each probe sends one message after a short starting conversation (a couple, or a single person) and checks one field of the
profile that comes back. Runs against a live server (default http://localhost:8020, ENOUGH_TEST_MODE=1); each probe uses its
own session id. Writes results.json next to this file and prints the misses.

    python eval/phrasing_inputs/probe.py [URL]
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8020"
HERE = pathlib.Path(__file__).resolve().parent
COUPLE = "I'm 55 and my partner is 53. We live in Ohio. I earn $90,000 and we have $300,000 saved. I want to retire at 65."
SINGLE = "I'm 55 and single. I live in Ohio, earn $90,000 and have $300,000 saved. I want to retire at 65."


def near(want: float, tol: float = 0.03):
    return lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v - want) <= max(1.0, tol * abs(want))


def eq(want):
    return lambda v: v == want


# (base, message, field path, check, what we expect in words)
PROBES: list[tuple[str, str, str, object, str]] = [
    # partner: any word for a partner, any relationship
    ("single", "I have a girlfriend, she's 52", "partner_age", eq(52), "partner 52"),
    ("single", "My boyfriend is 57", "partner_age", eq(57), "partner 57"),
    ("single", "My husband is 58", "partner_age", eq(58), "partner 58"),
    ("single", "My significant other is 50", "partner_age", eq(50), "partner 50"),
    ("single", "My fiancé is 49", "partner_age", eq(49), "partner 49"),
    ("single", "I have a common-law partner who is 51", "partner_age", eq(51), "partner 51"),
    ("single", "My other half is 54", "partner_age", eq(54), "partner 54"),
    ("single", "Actually I'm married, my wife is 52", "partner_age", eq(52), "partner 52"),
    ("couple", "We're divorced now, it's just me", "has_partner", eq(False), "no partner"),
    ("couple", "My partner passed away last year", "has_partner", eq(False), "no partner"),
    ("couple", "We split up, so plan for me alone", "has_partner", eq(False), "no partner"),
    ("couple", "My partner is actually a man", "partner_sex", eq("male"), "partner male"),
    ("couple", "My spouse is a woman", "partner_sex", eq("female"), "partner female"),
    ("couple", "My partner is 51, not 53", "partner_age", eq(51), "partner 51"),
    # own age and sex
    ("couple", "Sorry, I just turned 57", "age", eq(57), "age 57"),
    ("couple", "I was born in 1968", "age", eq(58), "age 58"),
    ("couple", "I'm actually fifty-six", "age", eq(56), "age 56"),
    ("couple", "I'm a guy", "sex", eq("male"), "male"),
    ("couple", "I'm a woman", "sex", eq("female"), "female"),
    # retirement age
    ("couple", "I want to stop working at 62", "retire_age", eq(62), "retire 62"),
    ("couple", "I'd like to hang it up at 63", "retire_age", eq(63), "retire 63"),
    ("couple", "I'd like to retire in 7 years", "retire_age", eq(62), "retire 62"),
    ("couple", "Planning to call it quits at 64", "retire_age", eq(64), "retire 64"),
    ("couple", "I want out of work by 60", "retire_age", eq(60), "retire 60"),
    ("couple", "Make my retirement age 67", "retire_age", eq(67), "retire 67"),
    ("couple", "My partner wants to retire at 62", "partner_retire_age", eq(62), "partner retire 62"),
    # pay
    ("couple", "Actually I make 95k", "pay_per_year", near(95000), "pay 95k"),
    ("couple", "My salary is $95,000", "pay_per_year", near(95000), "pay 95k"),
    ("couple", "I earn $45 an hour full time", "pay_per_year", near(93600, 0.05), "pay ~94k"),
    ("couple", "My income is 95 grand", "pay_per_year", near(95000), "pay 95k"),
    ("couple", "I'm paid $8,000 a month before tax", "pay_per_year", near(96000), "pay 96k"),
    ("couple", "My gross pay is $100,000 a year", "pay_per_year", near(100000), "pay 100k"),
    ("couple", "My wages are about 88,000", "pay_per_year", near(88000), "pay 88k"),
    ("couple", "My partner makes 60k", "partner_pay_per_year", near(60000), "partner pay 60k"),
    ("couple", "My spouse earns $60,000 a year", "partner_pay_per_year", near(60000), "partner pay 60k"),
    ("couple", "My partner brings in about 60 grand", "partner_pay_per_year", near(60000), "partner pay 60k"),
    ("couple", "My partner doesn't work", "partner_pay_per_year", eq(0), "partner pay 0"),
    ("couple", "My partner is a stay-at-home parent", "partner_pay_per_year", eq(0), "partner pay 0"),
    # savings
    ("couple", "Actually it's $200k in my 401k and nothing else", "savings.pretax", near(200000), "pre-tax 200k"),
    ("couple", "We have $250k in a 403(b) and $50k in a Roth IRA", "savings.roth", near(50000), "Roth 50k"),
    ("couple", "We have $250k in a 403(b) and $50k in a Roth IRA", "savings.pretax", near(250000), "pre-tax 250k"),
    ("couple", "Our nest egg is about 400k", "savings_total", near(400000), "total 400k"),
    ("couple", "We've got half a million saved", "savings_total", near(500000), "total 500k"),
    ("couple", "We have 1.2 million in retirement accounts", "savings_total", near(1200000), "total 1.2M"),
    ("couple", "Our savings are $280k in a TSP and $20k in the bank", "savings.cash", near(20000), "cash 20k"),
    ("couple", "$260k in a traditional IRA and $40k in a brokerage account", "savings.taxable", near(40000), "taxable 40k"),
    ("couple", "$270k in a 457 plan plus 30k in a checking account", "savings.cash", near(30000), "cash 30k"),
    ("couple", "$250k in retirement accounts and $50k in index funds outside them", "savings.taxable", near(50000), "taxable 50k"),
    ("couple", "$280k in my 401k and $20k in CDs", "savings.cash", near(20000), "cash 20k"),
    # spending
    ("couple", "We spend about $5,000 a month", "spending_now_per_year", near(60000), "spend 60k now"),
    ("couple", "Our monthly expenses are 5k", "spending_now_per_year", near(60000), "spend 60k now"),
    ("couple", "We live on about $60k a year", "spending_now_per_year", near(60000), "spend 60k now"),
    ("couple", "Our bills come to $4,500 per month", "spending_now_per_year", near(54000), "spend 54k now"),
    ("couple", "We go through roughly 70 grand a year", "spending_now_per_year", near(70000), "spend 70k now"),
    ("couple", "Our cost of living is around $6k/mo", "spending_now_per_year", near(72000), "spend 72k now"),
    ("couple", "In retirement we'd want to spend $50k a year", "spending_per_year", near(50000), "retire spend 50k"),
    # home
    ("couple", "We own our home, it's worth $400k", "home.value", near(400000), "home 400k"),
    ("couple", "Our house is valued at 400k", "home.value", near(400000), "home 400k"),
    ("couple", "Our condo is worth about 300k", "home.value", near(300000), "home 300k"),
    ("couple", "We rent for $1,800 a month", "home.rent", near(1800), "rent 1800"),
    ("couple", "We're renters, $1,800/mo", "home.rent", near(1800), "rent 1800"),
    ("couple", "I lease an apartment for $1,500 a month", "home.rent", near(1500), "rent 1500"),
    ("couple", "We owe $150k on the mortgage", "home.mortgage_balance", near(150000), "mortgage 150k"),
    ("couple", "We still have 150 grand left on our home loan", "home.mortgage_balance", near(150000), "mortgage 150k"),
    ("couple", "Our mortgage payment is $2,100 a month", "home.mortgage_payment", near(2100), "payment 2100"),
    ("couple", "We own the house outright", "home.mortgage_balance", eq(0), "no mortgage"),
    ("couple", "Our home is paid off", "home.owns", eq(True), "owns"),
    # debts
    ("couple", "I have $20k in student loans", "debt.student", near(20000), "student 20k"),
    ("couple", "I still owe 20 grand on my college loans", "debt.student", near(20000), "student 20k"),
    ("couple", "We have a car loan of $15k", "debt.car", near(15000), "car 15k"),
    ("couple", "Auto loan balance is 12k", "debt.car", near(12000), "car 12k"),
    ("couple", "There's $8k of credit card debt", "debt.credit_card", near(8000), "card 8k"),
    ("couple", "I owe 5k on my Visa", "debt.credit_card", near(5000), "card 5k"),
    ("couple", "We have $3k in medical bills", "debt.other", near(3000), "other 3k"),
    ("couple", "We're debt free", "debts", eq([]), "no debts"),
    # children
    ("couple", "We have two kids aged 10 and 13", "children.ages", eq([10, 13]), "kids 10, 13"),
    ("couple", "I've got a son, 12", "children.ages", eq([12]), "kid 12"),
    ("couple", "We have a daughter who's 8", "children.ages", eq([8]), "kid 8"),
    ("couple", "Three children: 5, 9 and 14", "children.ages", eq([5, 9, 14]), "kids 5, 9, 14"),
    ("couple", "We have twins, age 7", "children.ages", eq([7, 7]), "kids 7, 7"),
    ("couple", "My stepson is 15", "children.ages", eq([15]), "kid 15"),
    ("couple", "We don't have any kids", "children.ages", eq([]), "no kids"),
    # pets
    ("couple", "We have a dog", "pets.dog", eq(1), "1 dog"),
    ("couple", "We have two cats", "pets.cat", eq(2), "2 cats"),
    ("couple", "We have 5 dogs", "pets.dog", eq(5), "5 dogs"),
    ("couple", "We've got a couple of pups", "pets.dog", eq(2), "2 dogs"),
    # state
    ("couple", "Actually we live in Texas", "state", eq("TX"), "TX"),
    ("couple", "We're in NYC", "state", eq("NY"), "NY"),
    ("couple", "We're based in California", "state", eq("CA"), "CA"),
    ("couple", "We moved to Florida", "state", eq("FL"), "FL"),
    ("couple", "We live in Boston", "state", eq("MA"), "MA"),
    ("couple", "We're in PA", "state", eq("PA"), "PA"),
    ("couple", "We live in Washington state", "state", eq("WA"), "WA"),
    # health
    ("couple", "I'm in great health", "health", eq("excellent"), "excellent"),
    ("couple", "My health is poor", "health", eq("poor"), "poor"),
    ("couple", "My health is so-so", "health", eq("fair"), "fair"),
    ("couple", "My partner's health is excellent", "partner_health", eq("excellent"), "partner excellent"),
    # risk
    ("couple", "I'm a conservative investor", "risk", eq("careful"), "careful"),
    ("couple", "I don't like risk", "risk", eq("careful"), "careful"),
    ("couple", "I'm an aggressive investor", "risk", eq("growth"), "growth"),
    ("couple", "Moderate risk is fine", "risk", eq("balanced"), "balanced"),
    ("couple", "I can stomach big swings for higher returns", "risk", eq("growth"), "growth"),
    # Social Security and pensions
    ("couple", "My Social Security will be $2,500 a month", "social_security_per_year", near(30000), "SS 30k"),
    ("couple", "My SS estimate is 30k a year", "social_security_per_year", near(30000), "SS 30k"),
    ("couple", "My benefits statement says $2,200/mo", "social_security_per_year", near(26400), "SS 26.4k"),
    ("couple", "I'll get a pension of $1,500 a month", "pension.you", near(18000), "pension 18k"),
    ("couple", "My teacher's pension pays 30k a year", "pension.you", near(30000), "pension 30k"),
    ("couple", "I have a defined benefit plan paying $2k monthly", "pension.you", near(24000), "pension 24k"),
    # job
    ("couple", "I'm a nurse", "job", lambda v: isinstance(v, str) and "nurse" in v, "nurse"),
    ("couple", "I work as a software engineer", "job", lambda v: isinstance(v, str) and "software" in v, "software engineer"),
    ("couple", "I teach high school", "job", lambda v: isinstance(v, str) and "teacher" in v, "teacher"),
    ("couple", "I'm a self-employed plumber", "job", lambda v: isinstance(v, str) and "plumber" in v, "plumber"),
    # ---- round 2: harder wording
    ("single", "I'm a woman and my wife is 50", "partner_age", eq(50), "partner 50"),
    ("single", "I'm a woman and my wife is 50", "partner_sex", eq("female"), "partner female"),
    ("single", "I'm a man and my husband is 60", "partner_sex", eq("male"), "partner male"),
    ("single", "My partner and I are 55 and 54", "partner_age", eq(54), "partner 54"),
    ("single", "We're domestic partners; she is 52", "partner_age", eq(52), "partner 52"),
    ("single", "I live with my partner, who is 48", "partner_age", eq(48), "partner 48"),
    ("couple", "I'm widowed", "has_partner", eq(False), "no partner"),
    ("couple", "My ex and I separated, it's just me now", "has_partner", eq(False), "no partner"),
    ("couple", "I pull in about 110k", "pay_per_year", near(110000), "pay 110k"),
    ("couple", "I'm on a salary of 72,000", "pay_per_year", near(72000), "pay 72k"),
    ("couple", "My partner makes $30 an hour", "partner_pay_per_year", near(62400, 0.05), "partner pay ~62k"),
    ("couple", "My 401(k) balance is $210,000 and that's all we have", "savings_total", near(210000), "total 210k"),
    ("couple", "$250k in my IRA and 50k in a Roth 401k", "savings.roth", near(50000), "Roth 50k"),
    ("couple", "$260k in a 401k and about 40k in a high-yield savings account", "savings.cash", near(40000), "cash 40k"),
    ("couple", "$285k in retirement plans and a $15k emergency fund", "savings.cash", near(15000), "cash 15k"),
    ("couple", "We have $350,000 put away for retirement", "savings_total", near(350000), "total 350k"),
    ("couple", "Our nest egg is 1.5M", "savings_total", near(1500000), "total 1.5M"),
    ("couple", "We budget $4k/month", "spending_now_per_year", near(48000), "spend 48k now"),
    ("couple", "Our monthly outgoings are about 4,200", "spending_now_per_year", near(50400), "spend 50.4k now"),
    ("couple", "Our annual expenses are $65k", "spending_now_per_year", near(65000), "spend 65k now"),
    ("couple", "We need around 5 grand a month to live", "spending_now_per_year", near(60000), "spend 60k now"),
    ("couple", "Our place is worth 550 thousand", "home.value", near(550000), "home 550k"),
    ("couple", "We pay $2,000 in rent each month", "home.rent", near(2000), "rent 2000"),
    ("couple", "We have a $1,200 monthly mortgage", "home.mortgage_payment", near(1200), "payment 1200"),
    ("couple", "We still owe $90k on the house", "home.mortgage_balance", near(90000), "mortgage 90k"),
    ("couple", "I'm carrying about 6k on credit cards", "debt.credit_card", near(6000), "card 6k"),
    ("couple", "My car note has 18k left", "debt.car", near(18000), "car 18k"),
    ("couple", "We have a personal loan of $10k", "debt.other", near(10000), "other 10k"),
    ("couple", "Two teenagers, 15 and 17", "children.ages", eq([15, 17]), "kids 15, 17"),
    ("couple", "My kids are 4 and 6", "children.ages", eq([4, 6]), "kids 4, 6"),
    ("couple", "I have a 9 year old", "children.ages", eq([9]), "kid 9"),
    ("couple", "I'll draw a pension of 2k/month", "pension.you", near(24000), "pension 24k"),
    ("couple", "My state pension will be $28,000 annually", "pension.you", near(28000), "pension 28k"),
    ("couple", "Social security of about 1,900 per month", "social_security_per_year", near(22800), "SS 22.8k"),
    ("couple", "My SSA statement shows $2,100 a month at 67", "social_security_per_year", near(25200), "SS 25.2k"),
    ("couple", "I plan to retire around 66", "retire_age", eq(66), "retire 66"),
    ("couple", "I'd like to stop working when I'm 61", "retire_age", eq(61), "retire 61"),
    ("couple", "I hope to be done working at 64", "retire_age", eq(64), "retire 64"),
    ("couple", "My partner plans to stop working at 60", "partner_retire_age", eq(60), "partner retire 60"),
    ("couple", "I'm risk averse", "risk", eq("careful"), "careful"),
    ("couple", "I prefer safe investments", "risk", eq("careful"), "careful"),
    ("couple", "I'm comfortable with ups and downs", "risk", eq("growth"), "growth"),
    ("couple", "Middle of the road on risk", "risk", eq("balanced"), "balanced"),
    ("couple", "I'm healthy", "health", lambda v: v in ("good", "excellent"), "good or excellent"),
    ("couple", "I have some health issues", "health", lambda v: v in ("fair", "poor"), "fair or poor"),
    ("couple", "We're in the Bay Area", "state", eq("CA"), "CA"),
    ("couple", "I live in Chicago", "state", eq("IL"), "IL"),
    ("couple", "We're in Jersey", "state", eq("NJ"), "NJ"),
    ("couple", "We live in Atlanta", "state", eq("GA"), "GA"),
]


def post(path: str, body: dict, sid: str) -> dict:
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "X-Enough-Test": "1", "X-Session-Id": sid})
    return json.load(urllib.request.urlopen(req, timeout=180))


def field(p: dict, path: str):
    if path == "savings_total":
        return sum((p.get("savings") or {}).get(k) or 0 for k in ("pretax", "roth", "taxable", "cash"))
    if path.startswith("debt."):
        return sum(d.get("balance") or 0 for d in p.get("debts") or [] if d.get("kind") == path.split(".", 1)[1]) or None
    if path == "children.ages":
        return [c.get("age") for c in p.get("children") or []]
    if path.startswith("pets."):
        return sum(x.get("count") or 0 for x in p.get("pets") or [] if x.get("kind") == path.split(".", 1)[1]) or None
    if path.startswith("pension."):
        who = path.split(".", 1)[1]
        return sum(x.get("per_year") or 0 for x in p.get("pensions") or [] if x.get("who") == who) or None
    cur = p
    for part in path.split("."):
        cur = (cur or {}).get(part)
    return cur


def main() -> None:
    bases = {name: post("/api/intake", {"text": text, "profile_so_far": {}}, "probe-base-" + name)["profile"]
             for name, text in (("couple", COUPLE), ("single", SINGLE))}

    def one(pr):
        base, msg, path, check, want = pr
        try:
            sid = "probe-" + uuid.uuid4().hex[:12]
            r = post("/api/intake", {"text": msg, "profile_so_far": bases[base]}, sid)
            if r["profile"].get("asking") == "confirm_change":      # "Change your age from 55 to 57?": the person says yes
                r = post("/api/intake", {"text": "Yes", "profile_so_far": r["profile"]}, sid)
            got = field(r["profile"], path)
            return {"base": base, "message": msg, "field": path, "want": want, "got": got, "ok": bool(check(got)),
                    "reply": (r.get("reply") or "")[:240]}
        except Exception as e:      # noqa: BLE001
            return {"base": base, "message": msg, "field": path, "want": want, "got": None, "ok": False, "reply": f"ERROR {e}"}

    with ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(one, PROBES))
    (HERE / "results.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    bad = [r for r in rows if not r["ok"]]
    print(f"{len(rows) - len(bad)}/{len(rows)} right")
    for r in bad:
        print(f"MISS [{r['base']}] {r['message']!r} -> {r['field']}={r['got']!r} (want {r['want']}) | {r['reply'][:150]!r}")


if __name__ == "__main__":
    main()
