# Enough Lite: simulated-user test report

Claude Haiku played 48 people (personas.json); a second Haiku judged each exchange. Runs: `simusers/runs/`, verdicts: `simusers/judged/`.

## Completion

- Reached a plan: **48 of 48** (100%).
- Average intake turns to a plan: **8.0** (median 8.0, max 15).
- Did not reach a plan: none.

## Profile accuracy (final profile against the hidden truth)

- Share of checked fields correct: **95%** (over 48 personas).

| Field | Correct | Share |
|---|---|---|
| savings_total | 41/48 | 85% |
| partner_pay | 7/8 | 87% |
| pension_per_year | 43/48 | 89% |
| mortgage_balance | 39/43 | 90% |
| pay_per_year | 44/48 | 91% |
| retire_age | 46/48 | 95% |
| home_owns | 46/48 | 95% |
| children | 46/48 | 95% |
| partner_age | 47/48 | 97% |
| pets | 47/48 | 97% |
| debts_total | 47/48 | 97% |
| spending_now | 47/48 | 97% |
| age | 48/48 | 100% |
| state | 48/48 | 100% |

Why fields were wrong (judge's cause): 11 never_asked, 6 person_never_said, 4 app_misparsed, 4 assumed_default, 2 correction_lost, 2 simulator_inconsistent

## Issues by type

| Type | Total | P0 | P1 | P2 | Personas hit |
|---|---|---|---|---|---|
| dead_end | 18 | 3 | 14 | 1 | 16 |
| unstated_assumption | 10 | 0 | 6 | 4 | 10 |
| confusing | 7 | 0 | 2 | 5 | 6 |
| misunderstanding | 5 | 4 | 0 | 1 | 5 |
| contradiction | 2 | 0 | 2 | 0 | 2 |
| ignored_correction | 1 | 1 | 0 | 0 | 1 |
| repeated_question | 1 | 0 | 1 | 0 | 1 |

### dead_end

- P0 p14 a4: "From the source: "We call this annual limit the contribution and benefit base."" (The reply repeats the same irrelevant quote from a3 and does not answer whether the $49,200 includes Social Security or give the split, so the person is stuck.)
- P0 p38 a1: "[HTTP 0] connection failed" (The user asked for a credit card payoff what-if and got no result or explanation, leaving them stuck.)
- P0 p39 a1: "[HTTP 0] connection failed" (The app returned a connection error, so the person's question about claiming Social Security at 70 got no answer and she has no next step.)
- P1 h04 a1: "I can't run that one as asked." (A 6,000-a-year spending increase is a supported What If (the reply lists 'spending'), yet the app refuses without saying why and offers unrelated buttons.)
- P1 h04 a3: "I can't run that one as asked." (The long-term care question gets the same generic refusal and copied buttons, without saying why it cannot be modelled or what similar scenario it could run.)

### unstated_assumption

- P1 h07 i7: "I noted that you own your home, with a payment of $1,800 a month." (The mortgage balance and home value were never given and remain estimated, but the reply does not say so, even though the plan depends on them.)
- P1 p08 i1: "Until you tell me otherwise, I use typical figures for the rest" (Social security of $27,900 a year at 67 was assumed, but the reply never names it, only saying 'the rest' and '3 more'.)
- P1 p26 i4: "a 5% mortgage rate, which sets when the mortgage ends." (The app set the mortgage to end in 2031 and cut costs by about $3,600 a year, but the reply never states the end date or the cost drop in plain words.)
- P1 p27 a4: "The plan says your spending goal of $80,000 a year already works." (The $80,000 retirement spending was an app assumption the user never confirmed, and the reply presents it as the user's goal without saying so.)
- P1 p29 i6: "a 5% mortgage rate, which sets when the mortgage ends" (The 5% rate was assumed, not given by the person, and the reply presents it as a settled fact without saying it is an estimate.)

### confusing

- P1 p14 a4: "This amount is also commonly referred to as the taxable maximum. For earnings in 2027, this base is $192,300." (The quoted Social Security wage-base jargon is unrelated to the question and is hard for an ordinary person to act on.)
- P1 p24 a2: "If you retire at 62, you can count on $69,800 a year, safe in 90 of 100 scenarios" (The reply never says whose retirement age changed or that partner retirement timing is not modelled, so the user cannot tell what the number means.)
- P2 p04 i5: "Thanks. I noted that you have no children. Next I need when you want to retire." (The user asked whether they still need to say what they want to see at the end, and the reply skipped that question without answering it.)
- P2 p06 a4: "the other scenarios still vary as before" (The reply uses scenario-count jargon without explaining what the 90 of 100 and 27 of 100 numbers mean for the user's risk question.)
- P2 p08 i1: "spending in retirement at $35,400 a year and 3 more" (The 'and 3 more' leaves the person without a clear list of the other assumed figures to check.)

### misunderstanding

- P0 p06 a4: "If stocks fall 80% this year, you can count on $44,600 a year" (The user gave a stock allocation (about 80% or 60% in stocks), not a market drop of 80%, so the app ran the wrong scenario.)
- P0 p24 a2: "If you retire at 62, you can count on $69,800 a year" (The user asked what happens if her husband Dave retires at 62, but the app applied a retirement age of 62 to Gail herself, changing the wrong input.)
- P0 p38 i7: "Got it: savings of $16,000, not $150,000." (The user's split (130k + 10k + 6k) totals $146,000, but the app echoes $16,000, a wrong figure stored or confirmed to the user.)
- P0 p39 i3: "your spending in retirement is $37,000 a year" (The person corrected only current spending to $33,000. The app moved retirement spending from $30,000 to $37,000, copying the old current figure, and did not flag the change.)
- P2 p21 i10: "I didn't catch a figure there. A rough number is fine, or type skip." (The person answered the retirement-age question with "58k", which plainly means age 58, but the app rejected it as not a figure and asked again.)

### contradiction

- P1 p27 a4: "The plan figures do not test a goal of 60, so I cannot name the single biggest change for it." (The user stated retiring at 60, which the app stored, so saying the plan does not test 60 contradicts the user's own input and confuses the question.)
- P1 p38 i7: "Your accounts add to $146,000, so I used that, not $150,000." (This contradicts the echoed '$16,000' in the same reply and never states plainly that the Roth amount is now zero.)

### ignored_correction

- P0 p08 i5: "How much is left, and at what rate?" (The user explicitly retracted the car loan (truck paid off, no debts), but the app ignored that and asked for the balance and rate as if the 4k debt still existed.)

### repeated_question

- P1 p25 a1: "At what age? Name it and I will run it, for example: what if I retire at 59." (The user already said retire at 62 and asked for a 10% 401k increase, so asking for the age again is redundant.)

## Five worst examples

- P0 dead_end (p14 a4): "From the source: "We call this annual limit the contribution and benefit base."" The reply repeats the same irrelevant quote from a3 and does not answer whether the $49,200 includes Social Security or give the split, so the person is stuck.
- P0 dead_end (p38 a1): "[HTTP 0] connection failed" The user asked for a credit card payoff what-if and got no result or explanation, leaving them stuck.
- P0 dead_end (p39 a1): "[HTTP 0] connection failed" The app returned a connection error, so the person's question about claiming Social Security at 70 got no answer and she has no next step.
- P0 ignored_correction (p08 i5): "How much is left, and at what rate?" The user explicitly retracted the car loan (truck paid off, no debts), but the app ignored that and asked for the balance and rate as if the 4k debt still existed.
- P0 misunderstanding (p06 a4): "If stocks fall 80% this year, you can count on $44,600 a year" The user gave a stock allocation (about 80% or 60% in stocks), not a market drop of 80%, so the app ran the wrong scenario.

## Plan page

Reply kinds: whatif 80, answer 79, clarify 25, error 2.

## Top 10 fixes, ranked

1. Never end a reply without a specific next question or option; add a fallback question with chips. (18 issues)
2. Check parsed figures against the message (totals, who earns what, what is spending vs pay) before echoing them. (5 issues)
3. Say every assumed or estimated figure in the reply, in plain words, when it is first used. (10 issues)
4. Get 'savings_total' right: 7 of 48 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
5. Get 'pension_per_year' right: 5 of 48 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
6. Replace jargon and bare statistics (such as '0 of 100 scenarios') with one plain sentence. (7 issues)
7. Get 'pay_per_year' right: 4 of 48 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
8. Get 'mortgage_balance' right: 4 of 43 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
9. Apply a stated correction on the spot (and echo the new value); never ask the old question again. (1 issues)
10. Do not store or show a figure that differs from what the person said. (2 issues)

## Tokens and cost

- App (sum of each persona's /api/costs): $0.3422, 4,266,866 tokens.
- Simulator: 608 calls, 888,607 in / 37,852 out, $0.1078 (at the app's Haiku prices of $0.10 in and $0.50 out per million).
- Judge: 241 calls, 828,044 in / 217,079 out, $0.1913 (at the app's Haiku prices of $0.10 in and $0.50 out per million).
- **Total: $0.6413** (budget $1.50, stop at $2).
