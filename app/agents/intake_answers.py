"""Short, honest answers to questions asked in the middle of the intake. Fixed text only: no invented figures.

Each answer is followed by the next question, so a question never ends the chat. The topic comes from the model's
TurnRead when the AI is on, or from simple word patterns when it is not.
"""
from __future__ import annotations

import re

from app import safety

GLOSSARY = {
    "roth": "A Roth account (Roth IRA or Roth 401(k)) is saved from pay after tax. The money grows, and withdrawals in retirement are tax-free if the rules are met.",
    "401(k)": "A 401(k) is a retirement account through your employer. You save from your pay before tax, often with a match from the employer, and pay tax when you take the money out. A 403(b) or 457(b) works much the same way.",
    "ira": "An IRA is an individual retirement account you open yourself. A traditional IRA is usually saved before tax and taxed when you take money out; a Roth IRA is the reverse.",
    "pre-tax": "Pre-tax means the money went in before income tax, as in a 401(k) or traditional IRA. You pay the tax when you take it out.",
    "taxable": "A taxable account is an ordinary investment account, such as a brokerage account. It has no special tax shelter.",
    "brokerage": "A brokerage account is an ordinary investment account for stocks and funds. It has no special tax shelter.",
    "mortgage balance": "The mortgage balance is what you still owe on the loan. The payment is what you pay each month. The balance tells the plan when the mortgage ends; the payment tells it what you spend until then.",
    "mortgage payment": "The mortgage payment is what you pay the lender each month. The balance is what you still owe in total.",
    "medicare": "Medicare is the federal health insurance for people 65 and older. Before 65, retirees pay for their own cover, which the plan counts as a cost.",
    "social security": "Social Security is the monthly benefit from the federal government, based on your earnings record. The later you claim, up to 70, the bigger the check. Your own estimate is at ssa.gov/myaccount.",
    "pension": "A pension is a regular payment from a former employer for life, usually from a set age. It is different from a 401(k), which is a pot of savings.",
    "scenario": "A scenario is one possible path for markets over your life. The plan tries many and counts how often your money lasts, so its answers are chances, not promises.",
    "match": "An employer match is money your employer adds to your 401(k) when you save, for example 50 cents per dollar up to a share of pay. It is the best return most people can get.",
    "emergency fund": "An emergency fund is cash set aside for surprises, such as a job loss or a big repair, so you do not have to sell investments at a bad time.",
    "annuity": "An annuity is a contract with an insurer: you pay a sum and get a regular income back, often for life.",
    "required minimum distribution": "A required minimum distribution is the amount you must take out of pre-tax accounts each year from a set age.",
    "net worth": "Net worth is what you own minus what you owe.",
}
ALIASES = {"roth ira": "roth", "roth 401k": "roth", "401k": "401(k)", "403b": "401(k)", "403(b)": "401(k)", "457": "401(k)", "traditional ira": "ira",
           "balance": "mortgage balance", "rmd": "required minimum distribution", "employer match": "match", "social security": "social security",
           "ss": "social security", "scenarios": "scenario", "pretax": "pre-tax", "taxable account": "taxable"}

WHY = {
    "age": "Your age sets how many years you have left to save and how long the money must last.",
    "partner_age": "Your partner's age sets how long the money must last for both of you.",
    "state": "Your state sets your taxes and the typical cost of living, which the plan uses for your basics.",
    "pay_per_year": "Your pay sets your taxes, how much you can save, and your Social Security.",
    "partner_pay_per_year": "Your partner's pay adds to what you can save and to the household's Social Security.",
    "savings": "Your savings are the money the plan draws on once you stop working.",
    "children": "Children's ages tell the plan when their costs end and when college comes.",
    "home": "Housing is most people's biggest cost. A mortgage ends; rent does not.",
    "mortgage": "The balance and the payment tell the plan when the mortgage ends and your costs fall.",
    "debts": "Debts cost interest and take part of your pay until they are paid off.",
    "retire_age": "It is the goal the plan tests: whether your money lasts if you stop then.",
    "spending_now_per_year": "Spending is what your money must cover, now and in retirement.",
}
PRIVACY = ("Your answers live in this browser tab. The server uses them only to read your messages and build your plan, and writes no copy "
           "to disk; its log holds token counts and costs. Yes, an outside company reads your messages: each one is sent to an AI "
           "model, Claude, run by Anthropic, so it can be understood. Leave out names and account numbers; rough figures are enough.")
ADVICE = ("No. This is an education tool, not financial advice. It shows what your own numbers suggest, in plain words. For big decisions, "
          "talk to a fee-only adviser who must act in your interest.")


def _plain_list(keys: list[str]) -> str:
    names = {"age": "your age", "partner_age": "your partner's age", "state": "your state", "pay_per_year": "your pay",
             "partner_pay_per_year": "your partner's pay", "savings": "your savings", "children": "your children's ages", "home": "your home",
             "mortgage": "your mortgage", "debts": "any debts", "retire_age": "when you want to retire", "spending_now_per_year": "your spending", "children_count": "whether you have children"}
    xs = [names.get(k, k.replace("_", " ")) for k in keys]
    return ", ".join(xs[:-1]) + " and " + xs[-1] if len(xs) > 1 else (xs[0] if xs else "")


def glossary(term: str | None, text: str = "") -> str | None:
    hay = f"{term or ''} {text}".lower()
    if re.search(r"balance", hay) and re.search(r"payment", hay):
        return GLOSSARY["mortgage balance"]
    for k in sorted(set(GLOSSARY) | set(ALIASES), key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", hay):
            return GLOSSARY[ALIASES.get(k, k)]
    return None


def topic_from_text(text: str) -> str | None:
    """Keyless: a rough topic from the words of a question."""
    low = (text or "").lower()
    if re.search(r"who (?:sees|can see|gets)|my data|privacy|private|stored?|share my|sell my", low):
        return "privacy"
    if re.search(r"\b(?:is this|is it) (?:financial )?advice\b|\badvis[eo]r\b|\bfiduciary\b", low):
        return "is_advice"
    if re.search(r"where (?:do i|is the|can i)|how do i (?:get|see|build|make)|button|click|see (?:my|the) plan|get to (?:the|my) plan", low):
        return "how_to_plan"
    if re.search(r"\b(?:behind|on track|enough|ahead)\b", low):
        return "am_i_behind"
    if re.search(r"\b(?:a lot|too much|normal|bad|high|low)\b", low) and re.search(r"\d|debt|owe|loan|sav", low):
        return "is_it_a_lot"
    if re.search(r"\bwhat(?:'s| is| are| does)\b.*\b(?:mean|is|are)\b|\bwhat(?:'s| is| are) an? \b|\bdefine\b|\bdifference between\b", low) and glossary(None, low):
        return "term"
    if re.search(r"\bwhy\b|what (?:is|does) (?:it|that|this) (?:for|used for|change)|what for\b|used for", low):
        return "why_needed"
    if re.search(r"what(?:'s| is| happens)? next|what now|then what", low):
        return "what_next"
    return None


def answer(topic: str | None, question: str, term: str | None, asking: str | None, missing: list[str]) -> str:
    """One to three plain sentences. Never a bare 'good question'."""
    left = _plain_list(missing)
    n = len(missing)
    low = (question or "").lower()
    if safety.is_single_investment(question or ""):
        return safety.STOCK_REPLY
    if re.search(r"\bskip\b|leave (?:it|that|the \w+|this)? ?(?:blank|out|empty)|do i (?:have|need) to (?:answer|say|give)|is that enough|"
                 r"good enough|close enough|rough (?:number|figure|guess)|(?:don'?t|do not) (?:really )?know", low) and topic not in ("privacy", "is_advice", "am_i_behind", "how_to_plan"):
        return ("A rough figure is fine. If you don't know one, type skip and I will use a typical figure, marked so you can change it."
                + (" " + MEANS[asking] if asking in MEANS and topic == "term" else ""))
    if topic == "term":
        g = glossary(term, question)
        if g:
            return g
        if asking in MEANS:
            return MEANS[asking]
        return "Each question asks for a rough figure from your own life. Answer in your own words; I will say what I understood."
    if topic == "privacy":
        return PRIVACY
    if topic == "is_advice":
        return ADVICE
    if topic == "why_needed":
        key = asking if asking in WHY else next((k for k in WHY if k.replace("_", " ").split()[0] in question.lower()), None)
        return WHY.get(key or "", "Each answer changes your plan: what you can count on and what is safe to spend.") + \
            (" If you'd rather not say, type skip and I will use a typical figure, marked so you can change it." if key else "")
    if topic == "am_i_behind":
        return ("I can't tell yet. The plan answers that by comparing what you have with what your spending needs, year by year. "
                + (f"I still need {left}." if n else "I have what I need, so you can build your plan now."))
    if topic == "is_it_a_lot":
        low = question.lower()
        if re.search(r"debt|owe|loan|credit|card", low):
            return ("It depends on the interest rate and your pay. High-rate debt, such as a credit card, is usually worth paying down first; "
                    "low-rate loans can be paid on schedule. Your plan will show what your debts do to your numbers.")
        if re.search(r"sav|401|ira|have|put away", low):
            return "It depends on your age, pay and spending. Your plan will compare what you have with what you need, which answers it better than a rule of thumb."
        return "It depends on the rest of your situation. Your plan will show whether it matters for you."
    if topic == "how_to_plan":
        return (f"The Build my plan button sits under your family picture (at the bottom of the screen on a phone). It works once I have the essentials. I still need {left}. Or press "
                "'Build my plan with typical numbers for the rest' to make it now." if n else
                "You have given me enough. Check the figures on the right, then press Build my plan under your family picture (on a phone, at the bottom of the screen).")
    if topic == "what_next":
        return (f"Next I need {left}. Then I build your plan: what you can count on, what is safe to spend, and three things to do first."
                if n else "Next, press Build my plan. It shows what you can count on, what is safe to spend, and three things to do first.")
    g = glossary(term, question)
    if g and re.search(r"\bwhat\b|\bmean\b|\bdefine\b", question.lower()):
        return g
    if asking in MEANS:
        return MEANS[asking]
    return "Your plan will answer that with your own numbers. It needs a few more answers first."


MEANS = {
    "spending_now_per_year": "I mean everything the household pays for in a normal year: rent or mortgage, food, car, insurance, health care and the rest. A rough monthly figure is fine.",
    "spending_per_year": "I mean what you expect to spend each year once you stop working, in today's dollars.",
    "savings": "I mean everything put away: 401(k)s, IRAs, other investments and cash in the bank, added up. A rough total is fine.",
    "savings_split": "I mean how your savings divide between pre-tax accounts like a 401(k), Roth accounts, ordinary investment accounts and cash.",
    "confirm_split": "I mean how your savings divide between pre-tax accounts like a 401(k), Roth accounts, ordinary investment accounts and cash.",
    "debts": "I mean any loan or card balance besides the mortgage: student loans, a car loan, credit cards. A rough balance is enough.",
    "debts_detail": "I mean how much is still owed on that loan. If you don't know the rate, leave it out and I will use a typical one.",
    "mortgage": "I mean how much you still owe on the mortgage, and what you pay each month.",
    "pay_per_year": "I mean your pay from work before tax, for a year. A rough figure is fine.",
    "confirm_pay": "I mean your pay from work before tax, for a year. A rough figure is fine.",
    "partner_pay_per_year": "I mean your partner's pay from work before tax, for a year. If they don't work, say so.",
    "retire_age": "I mean the age at which you would like to stop working. The plan tests whether that works.",
    "home": "I mean whether you own your home, with or without a mortgage, or rent it.",
    "children": "I mean each child's age now, for example 12, 9 and 5.",
}


OFF_TOPIC = "I can only help with your retirement plan here."
