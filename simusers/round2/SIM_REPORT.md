# Enough Lite: simulated-user test report

Claude Haiku played 48 people (personas.json); a second Haiku judged each exchange. Runs: `simusers/runs/`, verdicts: `simusers/judged/`.

## Completion

- Reached a plan: **45 of 48** (93%).
- Average intake turns to a plan: **7.8** (median 7, max 18).
- Did not reach a plan: h07 (done, 18 turns), p13 (done, 18 turns), p14 (done, 18 turns).

## Profile accuracy (final profile against the hidden truth)

- Share of checked fields correct: **94%** (over 48 personas).

| Field | Correct | Share |
|---|---|---|
| partner_pay | 6/8 | 75% |
| savings_total | 40/48 | 83% |
| pay_per_year | 41/48 | 85% |
| retire_age | 44/48 | 91% |
| partner_age | 45/48 | 93% |
| children | 45/48 | 93% |
| spending_now | 45/48 | 93% |
| mortgage_balance | 41/43 | 95% |
| age | 46/48 | 95% |
| debts_total | 46/48 | 95% |
| pension_per_year | 46/48 | 95% |
| pets | 47/48 | 97% |
| state | 48/48 | 100% |
| home_owns | 48/48 | 100% |

Why fields were wrong (judge's cause): 8 app_misparsed, 7 never_asked, 5 correction_lost, 3 simulator_inconsistent, 3 assumed_default, 2 person_never_said

## Issues by type

| Type | Total | P0 | P1 | P2 | Personas hit |
|---|---|---|---|---|---|
| dead_end | 15 | 6 | 8 | 1 | 11 |
| unstated_assumption | 11 | 0 | 9 | 2 | 10 |
| misunderstanding | 8 | 7 | 1 | 0 | 5 |
| confusing | 6 | 0 | 4 | 2 | 5 |
| repeated_question | 3 | 0 | 2 | 1 | 3 |
| ignored_correction | 2 | 1 | 1 | 0 | 2 |
| contradiction | 1 | 0 | 1 | 0 | 1 |

### dead_end

- P0 p07 a4: "If you miss your 7-month Initial Enrollment Period, you may have to wait to sign up and pay a monthly late enrollment penalty" (The reply is an unrelated Medicare enrollment quote that does not give the age-55 plan result or say what to do first, leaving the couple stuck after a third request.)
- P0 p11 a6: "From the source: "For single taxpayers covered by a workplace retirement plan, the phase-out range is increased to between $83,000 and $93,000..."" (The reply quotes IRA phase-out rules that do not answer where the $56,000 and 8% come from or what the plan assumes about pay, spending, and retirement age.)
- P0 p13 i10: "Your answers live in this browser tab. The server uses them only to read your messages" (The reply repeats the privacy paragraph and never says what the savings figure does or whether the person sees it first, so the person is stuck in a loop.)
- P0 p13 i11: "Your answers live in this browser tab. The server uses them only to read your messages" (Second time the person asked the same question; the app repeats the same paragraph and the same savings question without answering, leaving them stuck.)
- P0 p13 i12: "About how much have you saved in all, counting 401(k)s, IRAs, other investments and cash?" (Third repetition: the app ignores the explicit question about what the savings figure does and whether it is shown first, and re-asks the same savings question.)

### unstated_assumption

- P1 h05 i7: "I updated the typical figures: a 5% mortgage rate." (The panel marks a mortgage payoff in 2033 with about $13,500 a year in costs falling away, but the reply never mentions this assumption.)
- P1 p02 i3: "I updated the typical figures: a 5% mortgage rate." (The reply does not mention the new assumed mortgage payoff in 2035 and the roughly $7,700 a year drop in costs, which changes the plan.)
- P1 p06 a4: "Your plan shows $9,200 a year in contributions now, well below those limits." (The person never gave contributions; this is the app's assumed 10% of pay, and the reply presents it as the plan's actual figure.)
- P1 p20 i5: "I noted that your pay is $75,000 a year." (The person picked a $50k to $100k band, but the app stated a specific $75,000 figure as fact without saying it was a midpoint estimate, and the figure feeds the plan.)
- P1 p20 i9: "your mortgage payment at about $1,688 a month, typical for your state." (The app stored a $1,688 monthly mortgage payment the person never gave (the true payment is $1,050), and the reply presents it as a typical figure rather than a placeholder to be replaced.)

### misunderstanding

- P0 h07 i4: "I noted that you work as a project manager and your pay is $50,000 a year." (The person gave a range ($50k to $100k) and said the wife knows the exact figure, but the app stored $50,000 as a fact without flagging it as a guess.)
- P0 p19 a1: "Change your age to 65 and rebuild your plan?" (The person is 60 and 65 is their stated retirement age, so the app proposes setting the wrong field (age instead of retire_age).)
- P0 p20 i13: "I noted that you have 1 child, aged 15." (The person only said 'Teenagers'; the app invented the age 15 and stored it, which is wrong (the true age is 17).)
- P0 p21 i3: "I noted that your pay is $150,000 a year." (The person clicked a $100k to $200k range, and the true pay is $130,000. The app stored an invented midpoint as the person's actual pay, and the reply does not say it was a guess.)
- P0 p21 i11: "I noted that you have 2 children." (The user entered three ages (11, 9, 6), so the app stored and echoed the wrong child count.)

### confusing

- P1 h04 a4: "you can count on $53,100 a year (now $53,100)" (The reply repeats figures with '(now ...)' labels that mean nothing to an ordinary person and do not explain the result.)
- P1 p11 a6: "From the source: "For married couples filing jointly, if the spouse making the IRA contribution is covered by a workplace retirement plan..."" (Dense legal text about married-couple IRA rules is unrelated to a single person with a student loan and would confuse an ordinary user who knows little about money.)
- P1 p18 a4: ""The annual contribution limit for employees who participate in 401(k), 403(b), governmental 457 plans..."" (A pasted regulatory excerpt about contribution limits is jargon-heavy and gives an ordinary couple nothing they can act on.)
- P1 p24 a3: "about $32,000 a year of it sits above the basics" (The user asked whether the $20k pension is on top, but the reply never says whether the pension is counted, and terms like 'basics' and 'N of 100' are unexplained.)
- P2 p11 i4: "Is that something I can find on my statement?" (The person asked a direct question about finding the interest rate on a statement, and the reply never answers it.)

### repeated_question

- P1 p19 i6: "About how much have you saved in all, counting 401(k)s, IRAs, other investments and cash?" (The person already gave the $168,000 total in i4, and the app asks for it again instead of the split amounts.)
- P1 p21 i11: "How old are your children?" (The user had just given the children's ages in the same message, so the app asked for them again.)
- P2 p39 i3: "Do you have children, or pets at home?" (The person already said she has a cat, and the app had just echoed '1 cat', so asking about pets again is redundant.)

### ignored_correction

- P0 p11 a6: "From the source: "For single taxpayers covered by a workplace retirement plan, the phase-out range is increased..."" (The user said the loan is $28,000 at 5.5%, but the reply neither acknowledges the correction nor fixes the stored $56,000 and 8% figures.)
- P1 h04 i5: "Just tell me the home is worth about 280,000 if that matters for the plan." (The app neither stored nor acknowledged the $280,000 home value the person gave, and its reply only mentions the mortgage and debts.)

### contradiction

- P1 p24 a3: "You can count on $72,800 a year, safe in 90 of 100 scenarios" (Turn a1 gave the same $72,800 figure as 100 of 100 safe, and this turn changes it to 90 without saying why.)

## Five worst examples

- P0 dead_end (p07 a4): "If you miss your 7-month Initial Enrollment Period, you may have to wait to sign up and pay a monthly late enrollment penalty" The reply is an unrelated Medicare enrollment quote that does not give the age-55 plan result or say what to do first, leaving the couple stuck after a third request.
- P0 dead_end (p11 a6): "From the source: "For single taxpayers covered by a workplace retirement plan, the phase-out range is increased to between $83,000 and $93,000..."" The reply quotes IRA phase-out rules that do not answer where the $56,000 and 8% come from or what the plan assumes about pay, spending, and retirement age.
- P0 dead_end (p13 i10): "Your answers live in this browser tab. The server uses them only to read your messages" The reply repeats the privacy paragraph and never says what the savings figure does or whether the person sees it first, so the person is stuck in a loop.
- P0 dead_end (p13 i11): "Your answers live in this browser tab. The server uses them only to read your messages" Second time the person asked the same question; the app repeats the same paragraph and the same savings question without answering, leaving them stuck.
- P0 dead_end (p13 i12): "About how much have you saved in all, counting 401(k)s, IRAs, other investments and cash?" Third repetition: the app ignores the explicit question about what the savings figure does and whether it is shown first, and re-asks the same savings question.

## Plan page

Reply kinds: answer 125, whatif 51, change 7, clarify 1.

## Top 10 fixes, ranked

1. Never end a reply without a specific next question or option; add a fallback question with chips. (15 issues)
2. Check parsed figures against the message (totals, who earns what, what is spending vs pay) before echoing them. (8 issues)
3. Say every assumed or estimated figure in the reply, in plain words, when it is first used. (11 issues)
4. Get 'savings_total' right: 8 of 48 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
5. Get 'pay_per_year' right: 7 of 48 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
6. Replace jargon and bare statistics (such as '0 of 100 scenarios') with one plain sentence. (6 issues)
7. Get 'retire_age' right: 4 of 48 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
8. Apply a stated correction on the spot (and echo the new value); never ask the old question again. (2 issues)
9. Get 'partner_age' right: 3 of 48 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
10. Get 'children' right: 3 of 48 personas ended with a wrong or missing value (ask for it, or parse the message correctly).

## Tokens and cost

- App (sum of each persona's /api/costs): $0.3588, 4,499,561 tokens.
- Simulator: 591 calls, 944,610 in / 40,593 out, $0.1148 (at the app's Haiku prices of $0.10 in and $0.50 out per million).
- Judge: 235 calls, 855,424 in / 213,866 out, $0.1925 (at the app's Haiku prices of $0.10 in and $0.50 out per million).
- **Total: $0.6661** (budget $1.50, stop at $2).
