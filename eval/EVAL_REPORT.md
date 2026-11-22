# Enough Lite: evaluation report

Generated 2026-11-21 23:22 from `eval/runs` (480 saved runs).

## Final run (2026-11-21 evening)

480 live runs (300 base, 180 direction) on a fresh instance (port 8098, test mode, 3 workers), 480 ok and 0 errors. The earlier runs are kept in `eval/runs_before_final/`. Optimizer plans read from the old app's `output` folder (set `ENOUGH_OLD_APP` to that folder).

| Measure | Morning run | Final run |
|---|---|---|
| Passed every core check | 300 of 300 | 300 of 300 (295 of 300 with the new-input checks; misses are 5 `match_lever`/`match_in_actions`) |
| Direction checks | 178 of 180 fail-free (2 retire-later) | 180 of 180 pass |
| Direction moved as expected (debt / pension / match / legacy) | 10 / 27 / 11 / 24 | 11 / 27 / 9 / 27 |
| Median gap to optimizer | -2.9% | -0.8% |
| Within 25% of optimizer | 58% | 60% |
| Verdict agreement | 83% | 85% |
| Cost per plan (mean) | $0.0024 | $0.0023 ($1.11 for 480 plans) |
| Template-fallback rate | not recorded | 20% of plans (96 of 480; 22% of base). 12 of these were number-check failures with no time for a second try |
| Time per run, median / p90 / max | 7.8 / 10.1 / 12.2 s | 11.0 / 32.6 / 91.5 s (bursts of slow AI replies with 3 workers; run alone the slowest cases took 14 to 20 s) |

The judge split and the Judge section further down are from the morning run (the judge was not re-run). The app's usage meter had one torn line from two writers; `common.read_jsonl` now skips such lines.

## Run overview

| Item | Value |
|---|---|
| Base households defined | 300 |
| Base households run | 300 |
| Runs ok / error (all kinds) | 480 / 0 |
| Perturbed runs (direction subset) | 180 |
| Time per run, median / p90 / max (s) | 11.0 / 32.6 / 91.5 |
| Server(s) | http://127.0.0.1:8098 |

## Before fixes / After fixes

Before: the 480 runs made before the engine fixes (kept in `eval/runs_v2_pre_fix/`; checks, benchmark and judge exactly as saved then, so the before wants figure meant the part above basics for lite and count-on for the optimizer). After: the same cases on the fixed engine, wants.per_year = count-on including basics, compared like for like.

| Measure | Before fixes (runs_v2_pre_fix) | After fixes |
|---|---|---|
| Base households run | 300 | 300 |
| Passed every core check | 277 of 300 | 300 of 300 |
| Lite wants = $0 (households) | 162 of 288 | 13 of 288 |
| Optimizer count-on = $0 (households) | 12 | 12 |
| Median gap to optimizer (all) | -100.0% | -0.8% |
| Median absolute gap | 100.0% | 17.7% |
| Within 25% of optimizer | 11% | 60% |
| Median gap, both above $0 | -52.4% (n=135) | +0.2% (n=279) |
| Verdict agreement (works or not) | 81% of 300 | 85% of 300 |
| Direction: +20% savings (wants must not fall) | 22 of 30 pass | 30 of 30 pass |
| Direction: retire 2 years later (must not fall) | 27 of 30 pass | 30 of 30 pass |
| Direction: add a $30k 7% debt (wants should fall) | 30 of 30 pass, 15 moved | 30 of 30 pass, 11 moved |
| Direction: add a $24k pension (wants should rise) | 17 of 30 pass, 17 moved | 30 of 30 pass, 27 moved |
| Direction: capture the full match (wants should rise) | 25 of 30 pass, 14 moved | 30 of 30 pass, 9 moved |
| Direction: add a $200k legacy (wants should fall) | 30 of 30 pass, 30 moved | 30 of 30 pass, 27 moved |
| Judge split | reasonable 6 / questionable 29 / wrong 5 | reasonable 1 / questionable 26 / wrong 13 |
| Cost per plan (run events) | $0.0021 | $0.0023 |
| Tokens per plan | 19,802 | 15,657 |

## Automated checks

300 base households checked. 300 passed every core check (100%); 295 passed every check including the new-input ones (98%).
New-input checks apply only to households whose profile has that input (the Applicable column).

| Check | What it tests | Pass | Fail | Applicable | Pass rate |
|---|---|---|---|---|---|
| `stream` | the stream ended with a plan and no error | 300 | 0 | 300 | 100% |
| `three_parts` | plan has needs, wants and wishes | 300 | 0 | 300 | 100% |
| `needs_range` | needs paid is 0 to 100 | 300 | 0 | 300 | 100% |
| `wants_bound` | wants within a sensible bound of income and savings | 300 | 0 | 300 | 100% |
| `number_check` | every number in the adviser's text is in a tool output or the profile | 300 | 0 | 300 | 100% |
| `family_pet` | family and pet costs appear when the profile has children or pets | 300 | 0 | 300 | 100% |
| `retire_cap` | retire_age kept as stated, claim ages 62 to 70, no age past 70 suggested | 300 | 0 | 300 | 100% |
| `actions` | three actions, no forbidden advice | 300 | 0 | 300 | 100% |
| `cost` | total cost under the budget cap | 300 | 0 | 300 | 100% |
| `contract` | verdict, goal, chart band and handoffs present and consistent with the markets numbers | 300 | 0 | 300 | 100% |
| `headline` | plan.headline is present and its dollar figures are the plan's own | 300 | 0 | 300 | 100% |
| `claim_age` | claim_age (and the partner's for a couple) present, 62 to 70 | 300 | 0 | 300 | 100% |
| `debt_lever` | a debt at 7% or more -> a debt lever in plan.levers | 160 | 0 | 160 | 100% |
| `debt_in_actions` | ...and the three actions name the debt | 160 | 0 | 160 | 100% |
| `match_lever` | an employer match not fully captured -> a match lever | 50 | 5 | 55 | 91% |
| `match_in_actions` | ...and the three actions name the match | 43 | 5 | 48 | 90% |
| `college_event` | a child with college -> a College event in costs_by_age | 34 | 0 | 34 | 100% |
| `mortgage_event` | a mortgage that ends in the horizon -> a 'Mortgage paid off' event | 78 | 0 | 78 | 100% |
| `debts_event` | debts with payments -> a 'Debts paid off' event | 182 | 0 | 182 | 100% |
| `big_cost_event` | a big cost with a year -> its own event | 43 | 0 | 43 | 100% |
| `parents_event` | parents' help -> a 'Helping your parents' event | 17 | 0 | 17 | 100% |
| `medicare_event` | under 65 -> a 'Medicare starts' event | 217 | 0 | 217 | 100% |
| `legacy_reflected` | a legacy goal appears in the markets finding or the wishes | 23 | 0 | 23 | 100% |
| `pension_reflected` | a pension appears in findings, tools or text | 28 | 0 | 28 | 100% |

### Failures by type

**`match_lever`** (5)
- `E08_sole_provider_3_kids` (Age 38, sole provider, 3 kids, one income): contrib 5,000 < 5,100; levers ['emergency', 'goal', 'life']
- `N06_divorced_receives_support` (Age 41, divorced, two children, receives alimony for 5 years and child support for 10): contrib 3,000 < 3,120; levers ['emergency', 'goal', 'life']
- `S069` (50M, $22k pay, own): contrib 1,200 < 1,320; levers ['debt', 'emergency']

**`match_in_actions`** (5)
- `E08_sole_provider_3_kids` (Age 38, sole provider, 3 kids, one income): actions do not name the match: make your basics safe first on your numbers your basics are paid in 0 of 100 scenarios. the starting points sh
- `N06_divorced_receives_support` (Age 41, divorced, two children, receives alimony for 5 years and child support for 10): actions do not name the match: make your basics safe first on your numbers your basics are paid in 0 of 100 scenarios. the starting points sh
- `S069` (50M, $22k pay, own): actions do not name the match: pay off your high-rate debt first you owe $2,100 at up to 20%. that costs about $410 a year in interest. build

### Direction checks (up to 30 pairs per kind)

Noise: 5% of wants or $500, and 3 points on the needs score. Fail means wants (or the needs score) moved the wrong way beyond noise. Moved means wants moved the expected way beyond noise.

| Perturbation | Pairs | Pass | Fail | Moved as expected |
|---|---|---|---|---|
| +20% savings (wants must not fall) | 30 | 30 | 0 | n/a |
| retire 2 years later (must not fall) | 30 | 30 | 0 | n/a |
| add a $30k 7% debt (wants should fall) | 30 | 30 | 0 | 11 |
| add a $24k pension (wants should rise) | 30 | 30 | 0 | 27 |
| capture the full match (wants should rise) | 30 | 30 | 0 | 9 |
| add a $200k legacy (wants should fall) | 30 | 30 | 0 | 27 |


## Benchmark against the full optimizer

300 households have both a lite plan and a saved optimizer plan (`output/synth_tree_full`, else `output/synth_tree`). Gap is (lite wants - optimal wants) / optimal wants; positive means lite promises more than the optimizer found safe.

| Wants gap | Value |
|---|---|
| Median | -0.8% |
| Mean | +4.7% |
| 10th to 90th percentile | -43.9% to +52.4% |
| Median absolute gap | 17.7% |
| Within 10% | 27% |
| Within 25% | 60% |
| Lite more than 25% above optimal | 22% |
| Lite more than 25% below optimal | 18% |

| Gap bucket | Households |
|---|---|
| < -50% | 22 |
| -50 to -25 | 31 |
| -25 to -10 | 51 |
| -10 to +10 | 77 |
| +10 to +25 | 45 |
| +25 to +50 | 28 |
| > +50% | 34 |

**Verdict (works or does not).** Lite works = wants at least the spending goal; optimizer works = its feasibility flag.

| Outcome | Households |
|---|---|
| Both say works | 54 |
| Both say does not work | 200 |
| Lite works, optimizer does not | 23 |
| Lite does not, optimizer works | 23 |

Agreement: 85% of 300.

**Claiming age.** The optimizer names one for 300 households; lite names one too for 300. Exact match 13%, within one year 22%.

**Products.** The optimizer includes a product for 44 households. Lite counts as naming a product when an action or line mentions it.

| Product | Both | Optimizer only | Lite only |
|---|---|---|---|
| annuity | 0 | 20 | 0 |
| disability | 0 | 4 | 0 |
| ltc | 0 | 0 | 3 |
| term_life | 0 | 22 | 0 |

**Wants is floored at zero.** Lite shows $0 of wants for 13 households and the optimizer for 12; for 9 lite says $0 where the optimizer found something above 0, so the gap above is dominated by that. Where both are above zero (279 households): median gap +0.2%, within 25% 62%.

**Without the 77 households that carry inputs the optimizer never had** (big costs, parents' help, part-time work, inheritance; the persona set holds none, so the harness adds them to a seeded share): 223 households, median gap -0.6%, median absolute gap 17.3%, within 25% 62%, verdict agreement 83%.

Note: the optimizer's retirement age differs from the profile's for 74 households.

## AI judge

Model `claude-haiku-5-5` rated 40 sampled households. Judge spend $0.0195 (cap $1.00).

| Verdict | Count |
|---|---|
| reasonable | 1 |
| questionable | 26 |
| wrong | 13 |

**Wrong**
- `S201` (76F, +partner 75, retired, own): The plan treats $51,500 as safe with basics paid in 100 scenarios while the household has only $14,300 in cash and no investments, so the stated income (Social Security plus pensions) and the claimed safe spending are inconsistent with the savings profile, and the advice to pay debt and build an emergency fund ignores that the household has almost no liquid reserves and faces a large long-term care gap.
- `S278` (76M, retired, own): The plan claims basics are fully covered and the $20,000 goal is met in 100 of 100 scenarios, yet the household has only $1,100 in cash and no investments, so it cannot fund $20,000 a year from savings; the $23,500 safe-spending figure ignores that the $9,500 pension is not inflation-adjusted and the ~$18,600 Social Security plus pension cannot cover the cost rise at 85, and the 0.5-month emergency fund and 100/100 success rate are contradicted by the profile.
- `E09_single_mom_2_kids` (Age 34, single parent, two kids, renting): The plan promises $29,500 a year while basics are paid in only 92 of 100 scenarios yet the stated goal of $40,000 lasts in just 38, and it recommends contributions and spending figures that are unreconciled with the $52,000 income, $2,500 cash, and $8,000 pretax savings, while the 'actions' duplicate each other and the $100,000 inheritance and $40,000 goal are mismatched with the stated low-confidence result.
- `S076` (25M, $67k pay, rent): The plan's wants figure of $14,400 a year is a single household-level number that ignores the $100,000 inheritance and $77,000 cash, and it cites a neighbor strategy from a 25-year-old with $88,000 saved (a mismatch with this profile's $88,000 in total savings but different allocation logic), while the 'fast' heuristic with a 50% stock share and a 25% basics-paid score produces a recommendation to cut spending to $14,000 that a careful planner would not endorse without a far fuller analysis.
- `S016` (51M, +partner 44, $68k pay, own): With only $52,700 in cash and no retirement accounts, the plan claims $78,000 a year is secure for 90 of 100 scenarios, which the savings cannot support; the median wealth chart shows depletion to zero by age 75, and the plan also gives duplicate, contradictory action advice while ignoring the $100,000 whole life policy's cash value and a spending goal of $95,000 that it admits falls short.
- `S048` (49F, $214k pay, own): The plan claims $104,500 a year is safely countable from only $73,500 in cash and no retirement accounts, which is implausible and contradicts the profile's savings, while its own neighbor simulations show a far lower safe amount (around $92,000-$105,000 only for households with much more saved) and the plan ignores that the household has no investments to support that income beyond Social Security of $49,600.
- `S068` (56F, $75k pay, rent): With $23,600 in cash and no investments, a $58,000 spending goal and basics of $38,400 are unsupported, and the plan's own numbers show basics paid in 0 of 100 scenarios, yet it presents a rule-of-thumb fallback as reasonable and never flags that the household's basics are unfunded in every scenario.
- `S067` (61M, retired, own): With only $53,000 in savings, a $15,000 spending goal, and basics paid in 0 of 100 scenarios, the plan presents an unsafe picture as workable and its actions are duplicated and incoherent (claiming Social Security at 62 for a $17,500 benefit, a 49% stock allocation, and a 'safe level' of $10,600 that the plan itself says fails), so a careful planner would not sign off on it.

**Questionable**
- `S049` (39F, +partner 40, $53k pay, rent): The plan is plausible but thin: it sets a spending goal above the safe level, duplicates the same action, and its verdict field reads 'close' rather than a clear sign-off, while the household's $29k median wealth and high-cost retirement assumptions leave little margin.
- `S261` (34F, +partner 36, $14k pay, rent): The plan is internally consistent and honest about the shortfall, but it leans on a rule-of-thumb strategy that gives basics only 42 of 100 odds, dismisses the long-term care gap with a vague claim-age review, and relies on a $10,000 pre-Medicare health cost assumption without much support.
- `S204` (68M, +partner 64, $30k pay, own): The plan is internally coherent and flags the basics shortfall honestly, but it leans on a loosely matched 'similar household' and rule-of-thumb benchmark, its life-cover advice is oddly justified for a 68-year-old couple with no children, and it never seriously tests cutting spending or delaying to shore up the 23-of-100 basics score.
- `S219` (60M, +partner 59, $50k pay, own): The plan is internally consistent and honestly flags the shortfall, but it leans on a rule-of-thumb strategy that fails the 90-of-100 basics threshold (88) and sets a $52,600 safe spend that the low-confidence flags and thin $44k-savings base make hard to rely on without a fuller review.
- `S184` (64F, +partner 69, retired, rent): The plan treats the $19,000 basics as fully covered by $30,000 Social Security with only $24,100 cash and a 24% credit card, ignoring that the household has no investment portfolio to draw on, sustaining 100% success is implausible at 95 with long-term care unfunded, and the cited 'works' verdict and 'rule of thumb' claims conflict with the stated figures.
- `S250` (26M, +partner 23, $48k pay, rent): The plan's headline figures are internally inconsistent (the stated $62,000 counts basics in 96 of 100 scenarios yet the wants text cites 90, and the chosen neighbor strategy assumes a 50% stock share with no clear basis), and the tax-free withdrawal estimate of $0 is unsupported despite 32% pretax savings and a $183,600 student loan not being addressed in the plan.
- `S120` (44F, +partner 46, 4 kids, $103k pay, own): The plan is broadly sound with 100% basics coverage and a 92,600 safe level, but it duplicates the spending-goal action, lists an odd 'close' verdict, ignores the partner's earlier retirement at 61 in the headline, and recommends delaying Social Security to 67 without weighing the couple's health and the $68,300 benefit against the stated retire age of 66.
- `S265` (60F, $74k pay, own): The plan's own figures show basics paid in only 65 of 100 scenarios and rely on a loosely matched neighbor household, but the core conclusion that spending must be cut is directionally supported by the profile's modest savings relative to a $42,000 spending goal.

## Tokens and cost

From `runs/usage.jsonl` (the app's own meter), sessions run_eval.py used (one per case, `eval-<case id>`) since this evaluation began; plans run twice appear twice.

| Item | Value |
|---|---|
| Plans metered | 480 |
| Agent calls | 2924 |
| Input tokens (uncached) | 62,788 |
| Cached input tokens (reads) | 6,583,992 |
| Cache-write tokens | 4,804,590 |
| Output tokens | 868,763 |
| Total tokens | 12,320,133 |
| App cost, all plans | $1.1071 |
| Cost per plan (mean / median / p90 / max) | $0.0023 / $0.0022 / $0.0029 / $0.0035 |
| Tokens per plan (mean) | 25,666 |
| Judge cost | $0.0195 |
| Total eval spend | $1.1266 |

| Agent | Calls | Input | Cached | Cache write | Output | Cost | Share | Cost per plan | Mean seconds |
|---|---|---|---|---|---|---|---|---|---|
| adviser | 524 | 7,336 | 715,987 | 1,555,116 | 273,250 | $0.3389 | 31% | $0.00071 | 2.5 |
| markets | 480 | 10,332 | 1,185,294 | 730,527 | 136,967 | $0.1727 | 16% | $0.00036 | 2.2 |
| tax | 480 | 12,480 | 1,412,802 | 688,434 | 118,241 | $0.1605 | 15% | $0.00033 | 2.3 |
| research | 480 | 7,680 | 644,764 | 628,838 | 134,468 | $0.1531 | 14% | $0.00032 | 2.1 |
| family | 480 | 12,480 | 1,282,098 | 615,918 | 105,609 | $0.1439 | 13% | $0.00030 | 2.4 |
| longevity | 480 | 12,480 | 1,343,047 | 585,757 | 100,228 | $0.1380 | 12% | $0.00029 | 2.3 |

From the saved run events (cost events; cache writes are not itemised there):

| Item | Value |
|---|---|
| Input tokens (uncached) | 62,788 |
| Cached input tokens | 6,583,992 |
| Output tokens | 868,763 |
| App cost, all runs | $1.1071 |
| Cost per household (mean / median / max) | $0.0023 / $0.0022 / $0.0035 |
| Cost per base household (mean) | $0.0023 |

## App issues to fix

Read after the 480-case rerun on the fixed engine (2026-11-21). The old list is kept in `runs_v2_pre_fix/app_issues.md`. Harness mistakes found in this pass (retire_cap flagged ages the person had stated, the horizon age and the claim age of someone already claiming; the judge prompt still described wants as the part above basics; a stale judge cache) are fixed in the harness and are not listed here.

1. **A duplicate action when the plan falls short.** 15 of 300 base households get two actions that say the same thing: the `goal` lever's "Set your spending goal nearer the safe level" and the template's "Set your spending goal nearer the safe level of $X." Examples: E07_widow_with_annuity, E09_single_mom_2_kids, E10_renter_growing_student_loan, E17_low_income, S044, S096, S098, S141, S142, S160, S201, S206. The AI judge also flagged it (S049, S187, S206, S237). Fix: drop a model or template action whose title matches an action already taken from a lever.
2. **The goal action crowds out the debt and match actions.** 8 households have a high-rate debt or an uncaptured match, yet the three actions name neither (debt_in_actions: S056, S071, S109, S220, S296; match_in_actions: S157, S258, S289). The levers list has them (S056 levers: goal, match, debt, emergency; actions: goal, match, goal). Fix: after the goal lever, fill the remaining slots from the other levers in order, and never repeat the goal.
3. **Retiring two years later lowers the basics score.** S033__retire_later: basics paid 43 to 18 of 100 (age 57, retire 68 to 70, claim age 69 to 70); S220__retire_later: 82 to 78. Count-on stays about equal (28,000 to 27,500; 13,900 to 13,800). Later retirement should not cut the basics score. Fix: check the engine's score for a retirement age change, in particular the claim age moving with it and the number of scenarios used (noise).
4. **Count-on far above the optimizer for a few low-savings households.** The five largest gaps: S197 (12,700 vs 2,700), S032 (31,200 vs 8,500), S137 (29,700 vs 10,300), S092 (47,100 vs 16,400), S128 (37,000 vs 13,500). Fix: compare the earnings and saving the lite engine counts before retirement with the optimizer's for these cases. The judge calls S092 and S201 unsafe.
5. **Verdict "works" where the optimizer finds the goal not feasible.** 26 households (for example E02_age_gap_25_older_partner, E14_age_79_retired, E28_couple_one_retired); the reverse, lite "falls short" where the optimizer says it works, holds for 24 (for example E22_legacy_goal, E27_max_contributions_high_earner, N02_business_owner_sale). Part of this is the 90 of 100 rule for basics (the optimizer's feasibility flag does not use it), so it is a difference of rule, not an error. Decide whether to align the two.
6. **The products the optimizer chooses (term life, annuity, disability) are never named in the lite text** for any of 44 households where the optimizer includes one.

