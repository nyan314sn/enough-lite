"""Write personas_hard.json: 8 hard-case personas for round 2 (ids h01..h08). Run: python build_hard_personas.py"""
import json
from pathlib import Path


def T(age, partner_age, state, retire, job, pay, ppay, sv, home, kids, debts=None, pensions=None, spend=0, notes="", pets=None):
    return dict(age=age, partner_age=partner_age, state=state, retire_age=retire, job=job, pay_per_year=pay,
                partner_pay_per_year=ppay, savings=dict(zip(("pretax", "roth", "taxable", "cash"), sv)), home=home,
                children_ages=kids, pets=pets or [], debts=debts or [], pensions=pensions or [],
                spending_now_per_year=spend, notes=notes)


def own(v, b, pay):
    return dict(owns=True, value=v, mortgage_balance=b, mortgage_payment_month=pay, rent_month=0)


def rent(r):
    return dict(owns=False, value=0, mortgage_balance=0, mortgage_payment_month=0, rent_month=r)


P = [
    dict(id="h01", name="Ruth", personality="a widow, 61, quiet and a little sad, answers briefly; mentions her late husband once; does not want a partner assumed",
         goal="See if she can stop work at 64 on her own", whatif="", correction="",
         plan_asks=["what if I stop at 62 instead", "will I get anything from my husband's Social Security", "what if I sell the house and rent", "how safe is my spending"],
         truth=T(61, None, "OH", 64, "school secretary", 52000, None, (180000, 20000, 25000, 30000), own(240000, 0, 0), [], spend=42000,
                 notes="widowed 3 years ago; late husband's survivor benefit may apply")),
    dict(id="h02", name="Tasha", personality="a single parent of two, always rushed, answers in few words, worries about money for the kids",
         goal="Know if she is on track and what college for the kids does to it", whatif="", correction="",
         plan_asks=["what if I put 300 a month into college savings", "what if I retire at 65 instead of 67", "what happens if I lose my job for a year", "what should I do first"],
         truth=T(38, None, "NC", 67, "dental hygienist", 74000, None, (42000, 0, 6000, 9000), rent(1650), [9, 12],
                 debts=[dict(kind="car", balance=11000)], spend=62000)),
    dict(id="h03", name="Hal and Bea", personality="a couple, he is 62 and she is 52; they answer together, one message may carry both of their facts",
         goal="Work out when he can stop and she keeps going", whatif="", correction="",
         plan_asks=["what if I retire at 64 but Bea keeps working to 62", "when can Bea claim Social Security", "what if Bea retires with me", "what if we pay off the mortgage first"],
         truth=T(62, 52, "MN", 64, "engineer", 135000, 70000, (520000, 90000, 110000, 40000), own(430000, 85000, 1900), [15], spend=96000,
                 notes="he retires at 64; she works to 62 per plan")),
    dict(id="h04", name="Walt", personality="already retired and collecting Social Security; practical, wants to know if his money lasts",
         goal="Check that his savings last for life now that he is claiming", whatif="", correction="",
         plan_asks=["what if I spend 6000 more a year", "what if I get a 3 percent lower return", "what if I need long term care", "when does my money run out if it does"],
         truth=T(68, None, "FL", 68, "retired machinist", 0, None, (310000, 0, 60000, 40000), own(280000, 0, 0), [],
                 pensions=[dict(label="union pension", per_year=14400)], spend=58000,
                 notes="retired at 65; claims Social Security now; about 2400 a month")),
    dict(id="h05", name="Gil", personality="gives ranges instead of exact numbers: says 'between X and Y', never one figure at first; will pick a midpoint if asked",
         goal="See if retiring at 63 works", whatif="", correction="",
         plan_asks=["what if I retire at 65", "what if my savings are at the low end of my range", "what if I spend 5000 less", "how sure is this"],
         truth=T(54, None, "AZ", 63, "sales manager", 110000, None, (330000, 40000, 50000, 20000), own(350000, 120000, 1700), [], spend=84000,
                 notes="says pay is between 100 and 120 thousand; says spending is between 7 and 8 thousand a month; midpoint is fine")),
    dict(id="h06", name="Ines", personality="keeps correcting herself: states a figure, then corrects it, then corrects it again; the last stated value is the true one",
         goal="Find out if she can retire at 62", whatif="",
         correction="Correct your savings TWICE during intake, ending on the true figure; correct your age once.",
         plan_asks=["what if I retire at 60", "what if I work until 65", "actually my pay is a bit lower, 88000", "what if I save 1000 more a month"],
         truth=T(57, None, "WA", 62, "pharmacist", 92000, None, (410000, 60000, 70000, 25000), own(520000, 190000, 2300), [], spend=70000)),
    dict(id="h07", name="Omar", personality="answers 'I don't know' or 'not sure' to most questions, even simple ones; only gives a number when the app offers a choice or a typical figure",
         goal="Get a rough idea if he is doing okay", whatif="", correction="",
         plan_asks=["I don't know what to ask. is this good", "what if I wait longer to retire", "what does the plan assume about me", "what should I do"],
         truth=T(45, 44, "VA", 65, "project manager", 98000, 55000, (120000, 15000, 20000, 15000), own(380000, 210000, 1800), [10, 7], spend=88000)),
    dict(id="h08", name="Kit", personality="writes in short fragments with typos, no punctuation, drops verbs: 'retir 65 maybe', 'sav 200k', 'wife 49'",
         goal="Is 65 ok", whatif="", correction="",
         plan_asks=["wat if retir 62", "wat if i sav 500 more per mnth", "how mch can i spnd", "wat shuld i do frst"],
         truth=T(53, 49, "TN", 65, "plumber", 85000, 40000, (140000, 10000, 20000, 18000), own(240000, 90000, 1250), [14], spend=70000)),
]
Path(__file__).with_name("personas_hard.json").write_text(json.dumps(P, indent=1), encoding="utf-8")
print(len(P), "personas written")
