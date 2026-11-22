# Enough Lite: simulated-user test report

Claude Haiku played 40 people (personas.json); a second Haiku judged each exchange. Runs: `simusers/runs/`, verdicts: `simusers/judged/`.

## Completion

- Reached a plan: **40 of 40** (100%).
- Average intake turns to a plan: **7.9** (median 8.0, max 13).
- Did not reach a plan: none.

## Profile accuracy (final profile against the hidden truth)

- Share of checked fields correct: **96%** (over 40 personas).

| Field | Correct | Share |
|---|---|---|
| pension_per_year | 35/40 | 87% |
| pay_per_year | 36/40 | 90% |
| retire_age | 37/40 | 92% |
| savings_total | 37/40 | 92% |
| children | 38/40 | 95% |
| debts_total | 38/40 | 95% |
| pets | 39/40 | 97% |
| spending_now | 39/40 | 97% |
| age | 40/40 | 100% |
| partner_age | 40/40 | 100% |
| state | 40/40 | 100% |
| home_owns | 40/40 | 100% |
| mortgage_balance | 36/36 | 100% |
| partner_pay | 5/5 | 100% |

Why fields were wrong (judge's cause): 7 app_misparsed, 6 never_asked, 3 person_never_said, 2 simulator_inconsistent, 1 correction_lost, 1 person_guessed_wrong, 1 assumed_default

## Issues by type

| Type | Total | P0 | P1 | P2 | Personas hit |
|---|---|---|---|---|---|
| unstated_assumption | 8 | 0 | 5 | 3 | 7 |
| misunderstanding | 8 | 4 | 3 | 1 | 8 |
| confusing | 7 | 0 | 4 | 3 | 7 |
| dead_end | 5 | 0 | 4 | 1 | 5 |
| ignored_correction | 3 | 2 | 1 | 0 | 3 |
| repeated_question | 1 | 0 | 1 | 0 | 1 |
| contradiction | 1 | 1 | 0 | 0 | 1 |

### unstated_assumption

- P1 p01 i4: "I updated the typical figures: a 5% mortgage rate." (The panel assumes the mortgage is paid off in 2037, cutting costs by about $8,500 a year, but the reply never says so.)
- P1 p08 i4: "I noted that you owe $12,000 in car debt." (The user said it was about 12k or possibly 9k and would check the statement, but the app stored $12,000 without saying the figure was uncertain.)
- P1 p20 i10: "I noted that you have 1 child, aged 15." (The person only picked the 'Teenagers' bucket, and the app stored an exact age of 15 without saying it was a guess (the true age is 17).)
- P1 p29 i2: "I noted that your pay is $75,000 a year." (The person picked a $50k to $100k range, but the app stored an exact $75,000 as if it were their figure, without saying it was a midpoint estimate. Spending was also re-estimated from it without saying so.)
- P1 p34 i6: "Thanks. I noted that your pay is $75,000 a year." (The user picked a $50k to $100k range, but the app stated a precise $75,000 as if the user had said it, and Social Security was derived from that guess.)

### misunderstanding

- P0 p10 i8: "Thanks. I noted that you spend $84,000 a year now." (The user gave a range of 6 to 7 thousand a month ($72k to $84k a year), but the app stored only the top of the range as fact without saying so.)
- P0 p11 i8: "your spending in retirement is $13,200 a year" (The person never gave a retirement spending figure, and $13,200 appears from nowhere and is stored and echoed as if it were theirs.)
- P0 p19 i7: "I will use a typical figure for your savings, marked so you can change it." (The person already gave $160,000 in savings, and the app replaces that stored figure with a typical one instead of confirming the user's number.)
- P0 p38 i3: "The accounts you named add to $0, and you said $150,000 in all, so I put the other $150,000 in taxable investments." (The user said most of the savings is in a 401(k), but the app ignored that and stored the full $150,000 as taxable, which is wrong money data, though it does invite correction.)
- P1 p05 a3: "From the source: "Under a change made in SECURE 2.0, a higher catch-up contribution limit applies for employees aged 60, 61, 62 and 63..."" (The user asked whether the retire-at-58 change took effect in the plan, and the reply answers an unrelated question about contribution limits.)

### confusing

- P1 p05 a3: "For 2027, this higher catch-up contribution limit is $11,750 instead of the $8,500 noted above." (Dense regulatory jargon with no plain-language explanation is hard for an ordinary person to act on.)
- P1 p25 a2: "in N of them the money lasted. Markets are uncertain, so these are chances, not promises." (The user asked directly whether they would run out at 55. The reply explains the metric but never says plainly that the plan fails in 98 of 100 paths.)
- P1 p26 a3: "I don't have a source for that." (This is an unclear non-answer to a plain question about what the mortgage balance and payment mean, which the app had already explained in turn i2.)
- P1 p33 a2: "For 2027, this higher catch-up contribution limit is $11,750 instead of the $8,500 noted above." (A dense regulatory quote about contribution limits is jargon-heavy and unrelated to the ordinary person's question about the 55 vs 60 tradeoff.)
- P2 p07 a3: "Please ask your adviser to confirm what the $110,000 includes, and where the 3 came from." (The reply sends the couple to an outside adviser without offering an in-app next step, and phrases like 'do not break that down by person' are hard to act on.)

### dead_end

- P1 p05 a3: "From the source: "Under a change made in SECURE 2.0, a higher catch-up contribution limit applies..."" (The reply gives no answer about whether the plan reflects retirement at 58 and offers no next step or option.)
- P1 p26 a3: "I don't have a source for that. I can still change an answer, try a What If, or explain your plan." (The reply does not answer the user's mortgage question and only offers generic menu options.)
- P1 p30 a3: ""N of 100" means this: we ran your plan through 100 different paths that markets might take" (The reply explains the 'N of 100' odds but never answers why the $45,300 figure differs from her $85,000 spending, which was her actual question.)
- P1 p33 a2: "From the source: "Under a change made in SECURE 2.0, a higher catch-up contribution limit applies for employees aged 60, 63"" (The reply does not answer which number to trust or what would keep the goal at 60, so the person is left with no next step.)
- P2 p04 i3: "Thanks. I noted that you have no children." (The reply confirms children but silently skips the 'no pets' answer, so the pets field is not acknowledged.)

### ignored_correction

- P0 p11 i9: "I noted that your pay is $52,000 a year." (The person asked why retirement spending was $13,200 and said they never gave that figure; the reply ignores the question and does not fix or explain the stored value.)
- P0 p26 a2: "Your retirement age is already 66 and your pre-tax savings is already $230,000" (The user said the plan shows 63 after the what-if, but the app insisted nothing needed changing and did not explain or fix the 63 that the plan displays.)
- P1 p07 a2: "Your children's ages is already 8, 5, so there is nothing to change." (The user said the plan still shows 3 children, but the reply only mentions ages and never confirms the child count was checked or corrected.)

### repeated_question

- P1 p04 i3: "At what age do you want to stop working?" (The person already said in turn i1 that they want to leave work at 65, so this asks for something already given.)

### contradiction

- P0 p09 i7: "I will use a typical figure for your partner's age, marked so you can change it." (The person said she is widowed and has no partner, yet the app still treats a partner's age as needed, so the stored partner data (age 58, pay, retirement age) was never cleared.)

## Five worst examples

- P0 contradiction (p09 i7): "I will use a typical figure for your partner's age, marked so you can change it." The person said she is widowed and has no partner, yet the app still treats a partner's age as needed, so the stored partner data (age 58, pay, retirement age) was never cleared.
- P0 ignored_correction (p11 i9): "I noted that your pay is $52,000 a year." The person asked why retirement spending was $13,200 and said they never gave that figure; the reply ignores the question and does not fix or explain the stored value.
- P0 ignored_correction (p26 a2): "Your retirement age is already 66 and your pre-tax savings is already $230,000" The user said the plan shows 63 after the what-if, but the app insisted nothing needed changing and did not explain or fix the 63 that the plan displays.
- P0 misunderstanding (p10 i8): "Thanks. I noted that you spend $84,000 a year now." The user gave a range of 6 to 7 thousand a month ($72k to $84k a year), but the app stored only the top of the range as fact without saying so.
- P0 misunderstanding (p11 i8): "your spending in retirement is $13,200 a year" The person never gave a retirement spending figure, and $13,200 appears from nowhere and is stored and echoed as if it were theirs.

## Plan page

Reply kinds: answer 68, whatif 35, change 2.

## Top 10 fixes, ranked

1. Check parsed figures against the message (totals, who earns what, what is spending vs pay) before echoing them. (8 issues)
2. Say every assumed or estimated figure in the reply, in plain words, when it is first used. (8 issues)
3. Apply a stated correction on the spot (and echo the new value); never ask the old question again. (3 issues)
4. Replace jargon and bare statistics (such as '0 of 100 scenarios') with one plain sentence. (7 issues)
5. Get 'pension_per_year' right: 5 of 40 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
6. Never end a reply without a specific next question or option; add a fallback question with chips. (5 issues)
7. Get 'pay_per_year' right: 4 of 40 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
8. Get 'retire_age' right: 3 of 40 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
9. Get 'savings_total' right: 3 of 40 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
10. Do not store or show a figure that differs from what the person said. (1 issues)

## Tokens and cost

- App (sum of each persona's /api/costs): $0.2482, 2,985,028 tokens.
- Simulator: 1618 calls, 2,418,052 in / 119,389 out, $0.3015 (at the app's Haiku prices of $0.10 in and $0.50 out per million).
- Judge: 681 calls, 2,075,263 in / 600,933 out, $0.5080 (at the app's Haiku prices of $0.10 in and $0.50 out per million).
- **Total: $1.0577** (budget $1.50, stop at $2).
