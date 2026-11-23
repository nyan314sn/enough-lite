"""Build the six hurried high-school-graduate personas (R26 lens) into ../personas_hs.json."""
import json
from pathlib import Path

def P(id, name, personality, goal, **t):
    base = dict(age=None, partner_age=None, state="", retire_age=None, job="", pay_per_year=0, partner_pay_per_year=None,
                savings=dict(pretax=0, roth=0, taxable=0, cash=0),
                home=dict(owns=False, value=0, mortgage_balance=0, mortgage_payment_month=0, rent_month=0),
                children_ages=[], pets=[], debts=[], pensions=[], spending_now_per_year=0, notes="")
    base.update(t)
    return dict(id=id, name=name, personality=personality, goal=goal, whatif="", correction="", truth=base)

STY = "A hurried high-school graduate typing on a phone: very short answers (1 to 6 words), lowercase, slang, typos, says 'idk' or 'around' for things you are unsure of, never explains. "
ps = [
 P("s01", "Jaylen", STY + "Works at a warehouse; has never thought about retirement.", "see if he can stop work at 62",
   age=29, state="OH", retire_age=62, job="warehouse worker", pay_per_year=41000, savings=dict(pretax=6000, roth=0, taxable=0, cash=2500),
   debts=[dict(kind="car", balance=9000)], home=dict(owns=False, value=0, mortgage_balance=0, mortgage_payment_month=0, rent_month=950), spending_now_per_year=33000),
 P("s02", "Kayla", STY + "Cashier and part-time cosmetologist; unsure of her numbers, says idk to savings.", "know if she's ok for retiring at 65",
   age=34, state="GA", retire_age=65, job="cashier", pay_per_year=35000, savings=dict(pretax=3000, roth=0, taxable=0, cash=1200),
   children_ages=[6], home=dict(owns=False, value=0, mortgage_balance=0, mortgage_payment_month=0, rent_month=1100), spending_now_per_year=31000),
 P("s03", "Tyler", STY + "Roofer, 45, owns a small house; uses 'bro' and 'lol'.", "see when he can quit roofing",
   age=45, state="FL", retire_age=60, job="roofer", pay_per_year=58000, savings=dict(pretax=40000, roth=0, taxable=5000, cash=6000),
   home=dict(owns=True, value=190000, mortgage_balance=88000, mortgage_payment_month=1050, rent_month=0), children_ages=[13, 16], spending_now_per_year=50000),
 P("s04", "Destiny", STY + "Medical assistant, newly married, answers for both of them in fragments.", "check if they can retire at 63",
   age=40, partner_age=41, state="TX", retire_age=63, job="medical assistant", pay_per_year=44000, partner_pay_per_year=52000,
   savings=dict(pretax=28000, roth=0, taxable=4000, cash=8000), home=dict(owns=True, value=230000, mortgage_balance=170000, mortgage_payment_month=1400, rent_month=0),
   children_ages=[3], spending_now_per_year=68000),
 P("s05", "Mike", STY + "Truck driver, 52, a bit suspicious of apps, gets impatient with questions.", "find out if he can retire at 62",
   age=52, state="PA", retire_age=62, job="truck driver", pay_per_year=64000, savings=dict(pretax=75000, roth=0, taxable=10000, cash=9000),
   home=dict(owns=True, value=210000, mortgage_balance=60000, mortgage_payment_month=900, rent_month=0), debts=[dict(kind="credit card", balance=6500)], spending_now_per_year=54000),
 P("s06", "Brianna", STY + "Barista and student, 24; replies 'dunno' to anything she has not looked up.", "see if she can retire at 60",
   age=24, state="CA", retire_age=60, job="barista", pay_per_year=32000, savings=dict(pretax=1500, roth=0, taxable=0, cash=900),
   debts=[dict(kind="student loan", balance=18000)], home=dict(owns=False, value=0, mortgage_balance=0, mortgage_payment_month=0, rent_month=1300), spending_now_per_year=30000),
]
Path(__file__).resolve().parent.parent.joinpath("personas_hs.json").write_text(json.dumps(ps, indent=1), encoding="utf-8")
print(len(ps))
