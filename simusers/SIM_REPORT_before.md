# Enough Lite: simulated-user test report

Claude Haiku played 40 people (personas.json); a second Haiku judged each exchange. Runs: `simusers/runs/`, verdicts: `simusers/judged/`.

## Completion

- Reached a plan: **36 of 40** (90%).
- Average intake turns to a plan: **7.7** (median 7.0, max 15).
- Did not reach a plan: p11 (done, 18 turns), p12 (done, 18 turns), p13 (done, 18 turns), p27 (done, 18 turns).

## Profile accuracy (final profile against the hidden truth)

- Share of checked fields correct: **75%** (over 40 personas).

| Field | Correct | Share |
|---|---|---|
| partner_pay | 0/5 | 0% |
| mortgage_balance | 8/36 | 22% |
| savings_total | 17/40 | 42% |
| children | 21/40 | 52% |
| pay_per_year | 29/40 | 72% |
| debts_total | 29/40 | 72% |
| spending_now | 30/40 | 75% |
| retire_age | 35/40 | 87% |
| pets | 35/40 | 87% |
| pension_per_year | 36/40 | 90% |
| state | 37/40 | 92% |
| home_owns | 37/40 | 92% |
| age | 38/40 | 95% |
| partner_age | 38/40 | 95% |

Why fields were wrong (judge's cause): 40 app_misparsed, 39 never_asked, 9 assumed_default, 5 person_never_said, 5 correction_lost, 1 simulator_inconsistent

## Issues by type

| Type | Total | P0 | P1 | P2 | Personas hit |
|---|---|---|---|---|---|
| dead_end | 46 | 29 | 12 | 5 | 11 |
| misunderstanding | 21 | 17 | 4 | 0 | 13 |
| unstated_assumption | 14 | 8 | 6 | 0 | 9 |
| ignored_correction | 9 | 9 | 0 | 0 | 7 |
| repeated_question | 6 | 0 | 6 | 0 | 5 |
| confusing | 3 | 0 | 2 | 1 | 3 |
| contradiction | 1 | 1 | 0 | 0 | 1 |

### dead_end

- P0 p11 i7: "The plan page can answer it once your plan is made." (The reply gives no answer, no next question, and no options, leaving the person stuck.)
- P0 p11 i8: "That is a good question. The plan page can answer it once your plan is made." (The user asked directly whether $14k/$3k/$28k debt is a lot or a little, and the app repeated the same non-answer.)
- P0 p11 i9: "That is a good question. The plan page can answer it once your plan is made." (The user asked how to reach the plan page and for a plain answer, and the app again gave no navigation, answer, or question.)
- P0 p11 i13: "That is a good question. The plan page can answer it once your plan is made." (The reply gives no next step, does not say where the plan button is, and does not answer whether she is behind, so she stays stuck.)
- P0 p11 i14: "That is a good question. The plan page can answer it once your plan is made." (The user explicitly asked where to click; the app repeats the same non-answer for the fourth time without pointing to any button or action.)

### misunderstanding

- P0 p01 i5: "Thanks. I noted that you have saved $57,000." (The four amounts the person gave total $267,000, but the app echoed $57,000, which is only the non-pre-tax portion, and did not explain the difference.)
- P0 p02 a2: "Change your pay to $150,000 a year and rebuild your plan?" (The user corrected pre-tax savings to $150,000, but the app proposed changing pay instead, which is the wrong field.)
- P0 p02 a5: "Change your retirement age to 60 and rebuild your plan?" (The user asked whether the plan says retire at 60 and what the 12900 figure is based on. They did not ask to change retirement age, and it was already 60.)
- P0 p03 i3: "Thanks. I noted that you have saved $550,000." (The person gave a clear breakdown totaling about $365k, but the app echoed $550,000, a wrong figure stored silently.)
- P0 p03 i9: "Thanks. I noted that you have saved $220." (The person clearly gave a 365k total with a breakdown, but the app echoes $220, a wrong figure that is stored silently.)

### unstated_assumption

- P0 p01 i6: "Thanks. I noted that you own your home." (The app silently stored an estimated $2,155/month mortgage payment (true is $1,450) and a guessed home value without telling the person or asking for the mortgage balance and payment.)
- P0 p03 i1: "Thanks. I noted that you are 40 and your pay is $145,000 a year." (The app silently stored a retirement age of 65 and other estimated figures without telling the person; the true target is 60, so the plan would be built on wrong data.)
- P0 p03 i2: "Thanks. I noted that you live in California." (The app stored estimated spending of $87,000 (and $71,000 later spending) without mentioning it, while the person's true spending is about $95,000.)
- P0 p20 i2: "Thanks. I noted that you are 52." (The app silently stored assumed pay ($50,980), retirement age (65), risk level, and spending figures without telling the person, and the pay and spending values are wrong for this person.)
- P0 p20 i3: "Thanks. I noted that you live in Wisconsin." (The reply does not mention the estimated spending figures (about $37,000 a year) that were stored, which differ from the person's actual spending, so wrong money data is stored without disclosure.)

### ignored_correction

- P0 p03 i7: "wait it says 550k?? i said 365k lol. fix that pls." (The app never acknowledges the 550k error or confirms it will change it; it just re-shows the generic change menu, so the wrong savings figure stays stored.)
- P0 p04 i4: "Its sixty five thousand, not 62." (The app never acknowledged the pay correction from $62,000 to $65,000, and no reply mentions it.)
- P0 p04 i5: "Thanks. I noted that you own your home." (The user explicitly asked to fix the savings figure to $363,000, but the reply ignores it and does not mention the $210k home value.)
- P0 p07 i1: "I noted that you have 3 children and you want to retire at 62." (Hannah corrected the count to two, but the app echoed three and stored the wrong number of children.)
- P0 p11 i7: "That is a good question. The plan page can answer it once your plan is made." (The user said 'I already told you that' and restated $14k 401k and $3k checking, but the app neither stored nor acknowledged these figures.)

### repeated_question

- P1 p07 i2: "How many children do you have?" (Hannah already stated the answer ("it's two, not three"), so asking again instead of confirming it is friction.)
- P1 p07 i3: "How old are you?" (The user already gave both ages (44 and 42) in the previous message, and the app ignored them and asked again.)
- P1 p08 a1: "About how much have you saved in all, counting 401(k)s, IRAs, other investments and cash?" (The user already gave a savings figure of about $500,000 in the intake, and the app asks for it again.)
- P1 p20 i11: "About how much does your household spend in a year now, all in?" (After the person chose 'Estimate it for me' and the app produced a figure, it asks the same spending question again.)
- P1 p23 a4: "Change pets and rebuild your plan?" (Pets were already corrected and confirmed as one dog, so asking to change pets again is a repeated, unnecessary prompt.)

### confusing

- P1 p13 i5: "I did not match that to a figure, so here is the question again." (Saying the message was not matched to a figure is unclear to an ordinary person and does not explain the failure.)
- P1 p26 a5: "I could not find a passage that defines a mortgage balance versus a payment, so I cannot explain those terms from sources here." (The user asked a plain question and got a refusal about sources, not a clear explanation; the actual definition follows only after this hedge.)
- P2 p40 a6: "Your plan was updated: your pay to $260,000 a year." (The message is ungrammatical and does not clearly confirm the stored pay now reads $260,000, which the user had asked to verify.)

### contradiction

- P0 p28 i5: "I noted that you own your home." (The person stated a $2,900 monthly mortgage payment, but the app stored an estimated $3,160 a month without telling her, so the stored data conflicts with what she said.)

## Five worst examples

- P0 contradiction (p28 i5): "I noted that you own your home." The person stated a $2,900 monthly mortgage payment, but the app stored an estimated $3,160 a month without telling her, so the stored data conflicts with what she said.
- P0 dead_end (p11 i7): "The plan page can answer it once your plan is made." The reply gives no answer, no next question, and no options, leaving the person stuck.
- P0 dead_end (p11 i8): "That is a good question. The plan page can answer it once your plan is made." The user asked directly whether $14k/$3k/$28k debt is a lot or a little, and the app repeated the same non-answer.
- P0 dead_end (p11 i9): "That is a good question. The plan page can answer it once your plan is made." The user asked how to reach the plan page and for a plain answer, and the app again gave no navigation, answer, or question.
- P0 dead_end (p11 i13): "That is a good question. The plan page can answer it once your plan is made." The reply gives no next step, does not say where the plan button is, and does not answer whether she is behind, so she stays stuck.

## Plan page

Reply kinds: change 86, answer 33, whatif 23, clarify 10.

## Top 10 fixes, ranked

1. Never end a reply without a specific next question or option; add a fallback question with chips. (46 issues)
2. Check parsed figures against the message (totals, who earns what, what is spending vs pay) before echoing them. (21 issues)
3. Get 'mortgage_balance' right: 28 of 36 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
4. Say every assumed or estimated figure in the reply, in plain words, when it is first used. (14 issues)
5. Get 'savings_total' right: 23 of 40 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
6. Apply a stated correction on the spot (and echo the new value); never ask the old question again. (9 issues)
7. Get 'children' right: 19 of 40 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
8. Get 'pay_per_year' right: 11 of 40 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
9. Get 'debts_total' right: 11 of 40 personas ended with a wrong or missing value (ask for it, or parse the message correctly).
10. Get 'spending_now' right: 10 of 40 personas ended with a wrong or missing value (ask for it, or parse the message correctly).

## Tokens and cost

- App (sum of each persona's /api/costs): $0.1905, 2,282,836 tokens.
- Simulator: 644 calls, 830,146 in / 46,257 out, $0.1061 (at the app's Haiku prices of $0.10 in and $0.50 out per million).
- Judge: 252 calls, 707,349 in / 229,284 out, $0.1854 (at the app's Haiku prices of $0.10 in and $0.50 out per million).
- Test: 1 calls, 17 in / 4 out, $0.0000 (at the app's Haiku prices of $0.10 in and $0.50 out per million).
- **Total: $0.4821** (budget $1.50, stop at $2).
