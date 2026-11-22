# Loop round 1, audit A: logic, math and reasoning

Independent auditor (Sonnet), 2026-11-21. Own instance on :8030, 16 households plus 480 eval runs. AI cost about $1.21.
Scripts and raw data in this folder.

**Counts: P0 1, P1 9, P2 12.**

## What held up
- Tax recompute (federal, state, FICA) matches the app to the dollar for all 16 households (same data files, so it proves the code, not the sources).
- Social Security matches exactly, including the reduction before 67, 8%/year after 67, the wage-base cap and a stated figure with retirement past 67.
- Costs timeline matches the recompute to the dollar (h13, ages 40 to 62).
- An independent 20,000-path Monte Carlo lands within 1.5% of the app's safe spending for all 16; goal-lasts and basics-paid within 3 points.
- 152 no-AI perturbations: savings +20% and retire +2 never lowered count-on; pay +20% and claim +2 each did twice (F5).
- 480 runs: verdict, headline, wants.per_year, above_basics and count_on always agree; no duplicate actions; debt or match lever always has an action; "Worth checking" never fires outside its rules; every AI dollar figure is in tool outputs (except code-built three-month emergency targets); What If baseline equals the plan.

## P0
- **F1. Partner Social Security starts too early and spousal benefits get delayed credits; headline overstated 6 to 11%.**
  - Households: h11 (58/52), h14, h05, a 62/37 couple with a non-working partner, eval E01_age_gap_25.
  - h11: $89,900 correct (each person's benefit starts at their own 67) vs $95,300 app (+5.7%); $98,400 shown after choosing claim 69.
  - Gap-25 couple: $43,800 vs $49,200 (+11%). It also pays a 37-year-old a spousal benefit at 42 and plans to age 119.
  - Cause: one household `ss_age` (`markets.py:26-33`). The younger partner's benefit is computed at your claim factor but paid years before they reach that age (`household.py:121-129`, `neighbors.py:152-160`). `_ss_for` scales the spousal share by the delayed credit.
  - Fix: a separate start age per person; spousal at a flat 50% with no delayed credit.

## P1
- **F2. Wrong claim age shown when already claiming.** h06 (72, said 67) shows 70; h07 (68, said 66) shows 68, and its action says "review when to start Social Security". Cause: `markets.py:27-28` overwrites `ss_age` with the current age; that value is reported (`markets.py:166-167`, `adviser.py:88-100`). Fix: carry the stated age through; no claiming advice when `already_claiming`.
- **F3. Estimated Social Security assumes 35 full years at today's pay.** Age 35, retire 45, pay $150k: $48,300 vs about $39,500 (+22%). Cause: no years-worked dilution (`estimates.py:52-60`).
- **F4. Working-year tax ignores the child credit, head of household and 401(k) deduction.** h13 (3 children): federal $10,504, about $6,000 too high, cutting saving to $11,008. A single parent with 2 children: $4,952 vs about $0. Cause: `tax.py:20-30` and `tax.py:55-65`. Not stated.
- **F5. Count-on is not monotone.** Pay +20%: r02 −5.7%, r11 −6.0%. Claim +2: h15 −6.9%, h16 −3.3%. Age 21 to 22: +61% ($12,700 to $20,500). Cause: the set of 5 nearest households changes with small input changes, and `pick` takes the best on the same paths (`neighbors.py:183-230`). Fix: always score a fixed grid (rule with claim 62 to 70, a few stock paths) alongside the neighbours.
- **F6. No assumptions statement, and "today's dollars" appears nowhere.** Unstated: real returns 5.0% stocks and 1.8% bonds; 2.5% inflation (used only for pensions and annuities); no pay growth; Social Security from today's pay; standard deduction only; 85% of Social Security taxed; no survivor step-down. Fix: `plan.assumptions` behind an expander, and "today's dollars" by the headline.
- **F7. All leftover take-home pay is assumed saved, and it is not stated.** Pay +20% moves count-on 6 to 61% (h01 +47%, h13 +61%). Cause: `costs.py:318-333` and `costs.py:357`.
- **F8. `falls_short` means two things.** It fires when basics are paid in under 90 of 100, and also when count-on is under 90% of the goal with basics fully paid. That is 101 of 480 runs (21%). Example: h05 has basics 100/100 and $34,300 above basics but reads `falls_short`. Cause: `adviser.py:52-64`.
- **F9. Actions drop real levers for filler.** 92 of 480 show "Check your plan once a year" while the emergency-fund lever is dropped (33 also drop a life-cover lever). Examples: h04, E08. Cause: slot 3 never takes `ranked[2:]` (`adviser.py:212-238`).
- **F10. The needs line implies basics are paid when they are not.** h07 and h08 have basics paid 0/100 but read "you pay them every year". 125 of 480 lines use similar words. The AI writes it with no tie to `paid_of_100`.

## P2
- **F11.** Arrays stop at 71 years (`costs.py:20`), so for under-25s the timeline ends early (age 90 for a 20-year-old, horizon 95) and the sim loses the late-life health extra ($4,740 a year).
- **F12.** Delayed credit on the spousal share adds about 7% to household SS when a non-earning partner claims at 70 (see F1).
- **F13.** No survivor step-down; couples plan to the last survivor (h11 to 100, gap-25 to 119, shown to the user).
- **F14.** Withdrawal tax uses the average rate at the net need, then grosses up (`tax.py:103-106`). h09: $26,573 vs about $33,000 (−24%). State tax is charged on SS, which most states exempt.
- **F15.** h01 tax text says "pretax first is a common order"; the tool order is taxable, then pre-tax, then Roth.
- **F16.** Close-verdict text says "falls short" (h01, h14). 50 of 480 `wants.line` say "little room above the basics" when above-basics is 25% or more of basics (h01 28%). The code threshold for thin is 5%.
- **F17.** h13's cost timeline drops to $24,272 at 62, then $77,644 at 65; the chart is hard to believe.
- **F18.** Template grammar: "The chance that you reaches 90" (`longevity.py`). The life table is generous (44% of 28-year-olds reach 90), and this is not stated.
- **F19.** Status lines used as actions: "Keep your spending goal at or below $55,000" (h03), "Keep saving toward age 70" (h10). A $600 gap (h14) still ranks first.
- **F20.** Emergency shortfall is computed from rounded months (`costs.py:425-427`): h12 $12,750 vs $12,500 exact.
- **F21.** Count-on is below gross SS in h07 ($20,300 vs $22,000) and h08 ($18,400 vs $19,600) with no explanation. h15's "similar household" is 68 against the user's 61.
- **F22.** 162 of 480 adviser texts needed a retry. Template fallbacks: 2 adviser, 6 longevity, 5 tax, 1 markets, 1 research. Safe, a quality cost only.

## Eval comparison
- 480 runs (300 base plus 180 direction perturbations): all ok, 0 errors, $1.164.
- Core checks 300/300. All six direction checks 30/30 (retire-later was 28/30 before).

| Measure | EVAL_REPORT.md | This run |
|---|---|---|
| Median gap to optimizer | −2.9% | −1.7% |
| Within 25% of optimizer | 58% | 56% |
| Verdict agreement | 83% | 82.7% |

- Against the saved runs of the same 480 cases, none fell more than 5%. 74 plans differ (mean count-on +2.25%); 10 verdicts changed, all toward better. No regression.
