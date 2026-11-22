"""Builds personas.json (run once: python build_personas.py)."""
import json
import pathlib


def S(pre=0, roth=0, tax=0, cash=0):
    return dict(pretax=pre, roth=roth, taxable=tax, cash=cash)


def H(owns=True, value=0, bal=0, pay=0, rent=0):
    return dict(owns=owns, value=value, mortgage_balance=bal, mortgage_payment_month=pay, rent_month=rent)


P = []


def add(pid, name, pers, goal, age, state, retire, pay, sav, home, spend, partner_age=None, partner_pay=None,
        kids=(), pets=(), debts=(), pensions=(), job="", extra="", whatif="", correction=""):
    P.append(dict(id=pid, name=name, personality=pers, goal=goal, whatif=whatif, correction=correction, truth=dict(
        age=age, partner_age=partner_age, state=state, retire_age=retire, job=job, pay_per_year=pay,
        partner_pay_per_year=partner_pay, savings=sav, home=home, children_ages=list(kids),
        pets=[dict(kind=k, count=c) for k, c in pets], debts=[dict(kind=k, balance=b, rate=r) for k, b, r in debts],
        pensions=[dict(per_year=a, start_age=s) for a, s in pensions], spending_now_per_year=spend, notes=extra)))


# careless typers
add("p01", "Dana", "careless typer with lots of typos and no capital letters", "Find out if retiring at 62 works", 51, "TX", 62, 78000, S(210000, 30000, 15000, 12000), H(True, 310000, 140000, 1450), 64000, job="nurse", kids=[17], pets=[("dog", 1)])
add("p02", "Marcus", "careless typer who drops words and mashes numbers together", "Know if he can retire at 60", 48, "GA", 60, 82000, S(150000, 0, 40000, 20000), H(True, 260000, 95000, 1200), 66000, job="electrician", debts=[("car", 14000, 0.07)], kids=[12, 15])
add("p03", "Priya", "careless typer on a phone, autocorrect errors, abbreviations", "See if she is on track at 40", 40, "CA", 60, 145000, S(180000, 90000, 60000, 35000), H(False, 0, 0, 0, 3100), 95000, job="software engineer", pets=[("cat", 2)])
add("p04", "Tom", "careless typer who sometimes writes numbers as words ('sixty five thousand')", "Check if he can leave work at 65", 57, "OH", 65, 65000, S(320000, 0, 25000, 18000), H(True, 210000, 0, 0), 52000, job="teacher", pensions=[(30000, 65)])
# self-correctors
add("p05", "Elena", "corrects herself mid-conversation ('actually 45, not 40')", "Retire at 58 if possible", 45, "NY", 58, 120000, S(260000, 70000, 30000, 25000), H(True, 520000, 310000, 2600), 88000, job="accountant", kids=[9], correction="Says she is 40 first, then 'actually 45, not 40'; later says pay is 125k not 120k")
add("p06", "Ray", "corrects himself often, gives a wrong figure then fixes it", "Retire at 63", 54, "FL", 63, 92000, S(400000, 0, 80000, 30000), H(True, 380000, 60000, 1300), 70000, job="sales manager", debts=[("credit_card", 9000, 0.22)], correction="Gives savings as 300k then says 'sorry, 400k'")
add("p07", "Hannah and Luke", "a couple; she corrects him and he corrects her", "Both retire at 62", 44, "WA", 62, 100000, S(300000, 60000, 40000, 30000), H(True, 640000, 420000, 3300), 110000, partner_age=42, partner_pay=85000, kids=[8, 5], pets=[("dog", 1)], correction="Luke first says 3 kids, Hannah says actually 2")
add("p08", "Greg", "corrects himself and then corrects the correction", "Retire at 67", 62, "AZ", 67, 70000, S(500000, 0, 0, 20000), H(True, 350000, 0, 0), 55000, job="machinist", pensions=[(18000, 65)])
# do not know numbers
add("p09", "Linda", "doesn't know her numbers, says 'no idea, maybe 300k?'", "Learn if she is ok to retire at 65", 58, "PA", 65, 60000, S(180000, 0, 0, 9000), H(True, 190000, 40000, 900), 48000, job="office manager", extra="Really has 180k in a 401k and 9k cash; unsure")
add("p10", "Carlos", "doesn't know his numbers, guesses ranges", "Retire early at 55 if he can", 47, "NJ", 55, 105000, S(95000, 40000, 20000, 15000), H(True, 430000, 260000, 2300), 80000, job="contractor", kids=[10, 13])
add("p11", "Beth", "doesn't know much about money at all", "Get a plain answer on whether she is behind", 35, "MI", 62, 52000, S(14000, 0, 0, 3000), H(False, 0, 0, 0, 1100), 38000, job="dental assistant", debts=[("student", 28000, 0.055)])
add("p12", "Walt", "doesn't know what he has; his late wife handled it", "Know if he can stop working at 66", 64, "VA", 66, 88000, S(420000, 0, 110000, 40000), H(True, 450000, 0, 0), 68000, job="engineer", pensions=[(24000, 66)])
# skeptics
add("p13", "Nina", "skeptic who asks 'why?' about every question and every number", "Decide whether to trust the app", 50, "IL", 62, 110000, S(380000, 50000, 90000, 30000), H(True, 400000, 150000, 1900), 82000, job="HR director", kids=[16])
add("p14", "Frank", "a gruff skeptic who challenges the estimates", "Check the app's logic on Social Security", 59, "NC", 64, 76000, S(290000, 0, 60000, 25000), H(True, 280000, 30000, 1000), 60000, job="bus driver", pensions=[(14000, 62)])
add("p15", "Mei", "polite skeptic who asks why an assumption was made", "Understand where each number comes from", 38, "MA", 60, 170000, S(210000, 120000, 80000, 50000), H(True, 780000, 560000, 3900), 120000, job="physician assistant", kids=[3])
# couples who contradict
add("p16", "Sam and Jo", "a couple who contradict each other on retirement age and spending", "Agree on one retirement age", 50, "CO", 62, 95000, S(350000, 40000, 50000, 30000), H(True, 560000, 230000, 2200), 90000, partner_age=48, partner_pay=70000, kids=[14], extra="He wants 60, she wants 65; they settle on 62")
add("p17", "Aisha and Omar", "a couple where one answers and the other interrupts with different numbers", "See how long the money lasts", 56, "TX", 65, 90000, S(500000, 80000, 60000, 40000), H(True, 420000, 70000, 1500), 85000, partner_age=54, partner_pay=60000, kids=[19], pets=[("dog", 2)])
add("p18", "Pat and Chris", "a couple who disagree about how much they save", "Find out if they should save more", 41, "OR", 63, 110000, S(150000, 50000, 20000, 18000), H(True, 500000, 380000, 2700), 95000, partner_age=39, partner_pay=90000, kids=[6, 3])
# terse
add("p19", "Joe", "terse, answers in one word or a bare number", "Quick check: retire at 65", 60, "SC", 65, 58000, S(160000, 0, 0, 8000), H(True, 170000, 0, 0), 44000)
add("p20", "Kim", "terse, one or two words, often 'idk' or 'yes'", "Retire at 62", 52, "WI", 62, 72000, S(210000, 10000, 0, 12000), H(True, 230000, 70000, 1050), 56000, kids=[17])
add("p21", "Ben", "terse, only digits and 'k'", "Ask when he can quit", 45, "UT", 58, 130000, S(260000, 100000, 50000, 25000), H(True, 490000, 300000, 2150), 90000, kids=[11, 9, 6])
# rambling
add("p22", "Rosa", "rambling paragraphs full of family stories, with facts buried inside", "Know if she can retire and help her mother", 53, "NM", 63, 67000, S(205000, 0, 15000, 14000), H(True, 240000, 85000, 1100), 54000, job="school secretary", pets=[("cat", 1)], kids=[16], extra="Helps her mother $6,000 a year")
add("p23", "Doug", "rambling, tells long stories about his job and his boat, gives numbers sideways", "Figure out if his boat habit is affordable at 62", 55, "ME", 62, 98000, S(430000, 0, 70000, 35000), H(True, 330000, 45000, 1300), 78000, job="plumber", pets=[("dog", 1)])
add("p24", "Gail", "rambling, many facts in one message, including some about her husband", "Plan with her husband for 64", 58, "MN", 64, 80000, S(370000, 60000, 30000, 25000), H(True, 350000, 0, 0), 70000, partner_age=61, partner_pay=40000, pets=[("cat", 2)], pensions=[(20000, 62)])
# asks questions mid-intake
add("p25", "Tyrell", "asks things like 'what's a Roth?' and 'what does 401k mean?' mid-intake", "Learn while he answers; retire at 62", 37, "TN", 62, 85000, S(40000, 15000, 8000, 10000), H(True, 240000, 190000, 1400), 62000, job="logistics coordinator", kids=[4], debts=[("student", 19000, 0.05)])
add("p26", "Susan", "asks 'what is a mortgage balance vs. payment?' and 'what is Medicare?' mid-intake", "Understand terms and retire at 66", 61, "KY", 66, 64000, S(230000, 0, 0, 16000), H(True, 200000, 35000, 800), 50000)
add("p27", "Ivan", "asks 'is this advice?' and 'who sees my data?' mid-intake", "Check privacy, then plan to retire at 60", 49, "WA", 60, 140000, S(520000, 160000, 120000, 45000), H(True, 720000, 300000, 2700), 100000, job="engineer", kids=[13])
# changes mind on retire age
add("p28", "Olivia", "changes her mind about her retirement age twice", "Find an age that works: starts at 60, then 65, then settles on 62", 46, "CA", 62, 115000, S(250000, 60000, 40000, 28000), H(True, 610000, 380000, 2900), 90000, job="marketing manager", kids=[10])
add("p29", "Harold", "changes his mind on retirement age after seeing the plan", "See which age works", 56, "FL", 62, 74000, S(260000, 0, 40000, 20000), H(True, 300000, 20000, 950), 58000, whatif="what if I retire at 66 instead")
add("p30", "Zoe", "changes her mind about retiring early, then wants to work part-time", "Retire at 55, then says 60", 42, "CO", 55, 125000, S(170000, 75000, 55000, 30000), H(False, 0, 0, 0, 2400), 85000, job="UX designer")
# pasted statement lines
add("p31", "Vince", "pastes a messy bank-statement line like 'CHK 4821 PAYROLL ACME INC 3,412.18 DEPOSIT'", "Know if he can retire at 62", 50, "IL", 62, 88000, S(240000, 0, 30000, 15000), H(True, 260000, 110000, 1250), 66000, job="warehouse supervisor", extra="Net paycheck is about $3,400 twice a month")
add("p32", "Monique", "pastes a messy line from a 401k statement ('VANGUARD TARGET 2040 BAL $212,540.77')", "Check readiness at 60", 52, "GA", 60, 95000, S(212540, 0, 20000, 15000), H(True, 330000, 120000, 1500), 70000, job="project manager", kids=[18])
# off-topic once
add("p33", "Dev", "asks once for something off-topic (a recipe, a poem or a stock tip)", "Plan, with one off-topic request", 43, "TX", 60, 135000, S(240000, 90000, 50000, 30000), H(True, 450000, 290000, 2300), 92000, job="data analyst", kids=[7])
add("p34", "Carol", "asks once about the weather or the election, then returns", "Retire at 65", 55, "OH", 65, 70000, S(280000, 0, 20000, 15000), H(True, 180000, 0, 0), 54000, job="librarian", pensions=[(22000, 62)])
add("p35", "Leo", "asks the app once to write his resignation letter", "Retire at 61", 51, "NV", 61, 102000, S(310000, 70000, 45000, 28000), H(True, 420000, 200000, 1950), 80000, job="casino manager", pets=[("dog", 1)])
# What If then correct an input
add("p36", "Alex", "tests a What If, then corrects an input on the plan page", "Try retiring at 60, then say pay is actually higher", 47, "VA", 62, 100000, S(280000, 50000, 50000, 25000), H(True, 480000, 240000, 2200), 82000, kids=[12], whatif="what if I retire at 60", correction="my pay is actually $118,000")
add("p37", "Marta", "tests a What If about saving more, then corrects the number of kids", "Try saving more, then says she has 3 kids not 2", 39, "IL", 63, 92000, S(120000, 35000, 15000, 18000), H(True, 350000, 250000, 1850), 72000, kids=[7, 4, 1], whatif="what if I save 15% of my pay", correction="we actually have 3 kids now")
add("p38", "Kurt", "tests a What If about paying off debt, then corrects his savings", "Pay off the card?", 44, "PA", 63, 86000, S(130000, 0, 10000, 6000), H(True, 260000, 170000, 1500), 68000, debts=[("credit_card", 16000, 0.24), ("car", 11000, 0.06)], whatif="what if I pay off my credit card", correction="my savings are really about $150,000 not 130")
# edge people
add("p39", "Ruth", "low savings, high worry, short sentences", "See if it's too late", 62, "WV", 67, 38000, S(41000, 0, 0, 4000), H(False, 0, 0, 0, 850), 33000, pets=[("cat", 1)], extra="Social Security matters most to her")
add("p40", "Victor", "high earner with big savings and a pension, asks careful questions", "Check if he can retire at 58", 50, "CT", 58, 260000, S(1200000, 300000, 600000, 100000), H(True, 1300000, 400000, 4800), 160000, job="surgeon", kids=[15, 12], pensions=[(36000, 60)], whatif="what if I downsize my home")

pathlib.Path(__file__).with_name("personas.json").write_text(json.dumps(P, indent=1), encoding="utf-8")
print(len(P))
