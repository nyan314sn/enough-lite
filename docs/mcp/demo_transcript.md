# Enough MCP server: demo session (2026-11-22)

A real MCP client (`docs/mcp/demo_client.py`, the `mcp` Python client over stdio) starts `mcp_server.py`, lists the tools and calls them. No AI model on either side: the figures are the app engine's (seed 409, 2000 market paths). Reproduce with `python docs/mcp/demo_client.py`.

## Tools offered by the `enough` server

- `plan_check`: Check what a household can count on in retirement, with the same engine and seed as the Enough app.
- `social_security_estimate`: Estimate a Social Security retirement benefit, in today's dollars a year, from pay and claiming age.
- `tax_estimate`: Estimate yearly tax with the app's 2027 federal brackets, standard deduction, state rates and payroll tax.
- `life_expectancy`: The age to plan to (the age at which about a 1 in 4 chance remains that anyone in the household is alive),
- `family_costs`: Yearly cost of raising children (to 18), their college (public in-state or private, ages 18 to 21, family
- `search_rules`: Find the cited public-source passages (IRS, SSA, Medicare and similar) that answer a rules question.

## Call 1: plan_check for "a 58-year-old in Ohio, $400k saved, $70k pay, retire at 65, spend $55k"

Arguments:

```json
{
  "household": {
    "age": 58,
    "state": "OH",
    "savings_total": 400000,
    "pay_per_year": 70000,
    "retire_age": 65,
    "spending_per_year": 55000
  }
}
```

### Result (key fields)

```json
{
  "status": "ok",
  "headline": "You can count on $45,900 a year: $28,200 for basics and $17,700 for the rest.",
  "count_on_per_year": 45900.0,
  "count_on_confidence": "90 of 100 scenarios",
  "basics_per_year": 28200.0,
  "basics_paid_of_100": 100,
  "verdict": "below_goal",
  "verdict_words": "below your goal",
  "spending_goal_per_year": 55000.0,
  "goal_line": "Your spending goal of $55,000 a year lasts in 38 of 100 scenarios. Your goal is above what lasts on these numbers, so wishes wait.",
  "short_of_goal_per_year": 9100.0,
  "retire_age": 65,
  "planning_age": 93,
  "social_security_per_year": 39300.0,
  "social_security_claim_age": 70,
  "notes": [],
  "engine": "Enough engine, 2000 market paths, seed 409; no AI model used.",
  "not_financial_advice": "Planning figures from public rules and fixed market assumptions, not a forecast and not financial, tax or legal advice. A licensed adviser can check them against your full picture."
}
```

### Inputs the server had to assume

```json
[
  {
    "field": "savings",
    "source": "assumed",
    "note": "You gave the total. The split is assumed: 60% pre-tax, 10% Roth, 20% taxable and 10% cash."
  },
  {
    "field": "risk",
    "source": "assumed",
    "note": "Stocks at 110 minus your age, at most 75%."
  },
  {
    "field": "save_rate",
    "source": "assumed",
    "note": "Assumed you save 10% of pay until you retire."
  },
  {
    "field": "social_security_per_year",
    "source": "estimate",
    "note": "Rough estimate from pay, claiming at 67. Get your real figure at ssa.gov/myaccount."
  },
  {
    "field": "health",
    "source": "assumed",
    "note": "Assumed good health, which leaves the life table as it is."
  },
  {
    "field": "spending_now_per_year",
    "source": "estimate",
    "note": "Estimated as your take-home pay less what you save, and no less than typical basics."
  },
  {
    "field": "emergency_months",
    "source": "estimate",
    "note": "Your cash savings divided by a month of spending."
  }
]
```

Main assumptions (first 4 of 8):

- All figures are in today's dollars: what money buys now, not the larger sums prices will reach.
- Savings grow on average 5.0% a year above inflation in stocks and 1.8% in bonds, with good and bad years. The plan tests many possible market paths. These are planning figures, not a forecast. They are fixed, so every plan is tested on the same markets; to see a bad stretch, try a What If such as markets fall 30%.
- Until you retire you save about $7,413 a year: $7,000 into a 401(k) or IRA (assumed: 10% of pay), $413 of take-home pay left after your spending, which the plan assumes you save. If that is wrong, change 'Yearly saving' in your answers.
- Pay stays at today's level until you retire, with no raises. This is fixed: raises are not certain, so the plan does not count on them. If your pay changes, change it in your answers.

## Call 2: search_rules("When can I sign up for Medicare?")

### Result

```json
{
  "status": "ok",
  "source": "SSA: Delayed retirement credits; CMS Medicare & You handbook; Medicare.gov: When does Medicare coverage start?",
  "passages": [
    {
      "title": "SSA: Delayed retirement credits",
      "url": "https://www.ssa.gov/benefits/retirement/planner/delayret.html",
      "text": "If you decide to delay your retirement, be sure to sign up for just Medicare at age 65 . If you do not sign up at age 65, in some circumstances your Medicare coverage may be delayed and cost more ."
    },
    {
      "title": "CMS Medicare & You handbook",
      "url": "https://www.medicare.gov/Pubs/pdf/10050-Medicare-and-You.pdf",
      "text": "Your monthly Part B premium may go up 10% for each full 12 months in the period that you could’ve had Part B, but didn’t sign up."
    },
    {
      "title": "Medicare.gov: When does Medicare coverage start?",
      "url": "https://www.medicare.gov/basics/get-started-with-medicare/sign-up/when-does-medicare-coverage-start",
      "text": "If you miss your 7-month Initial Enrollment Period, you may have to wait to sign up and pay a monthly late enrollment penalty for as long as you have Part B coverage. The penalty goes up the longer you wait."
    }
  ]
}
```

## Call 3: a refused request

### Result

```json
{
  "status": "refused",
  "message": "I can't help with hiding or moving money or property to qualify for Medicaid or SSI. I can plan with what you have, and an elder-law lawyer can explain the rules in your state.",
  "passages": [],
  "source": ""
}
```
