# Enough Lite: evaluation report

Generated 2026-11-20 23:23 from `eval/runs_mock` (360 saved runs).

## Run overview

| Item | Value |
|---|---|
| Base households defined | 300 |
| Base households run | 300 |
| Runs ok / error (all kinds) | 360 / 0 |
| Perturbed runs (direction subset) | 60 |
| Time per run, median / p90 / max (s) | 0.1 / 0.1 / 0.2 |
| Server(s) | http://127.0.0.1:8791 |

## Automated checks

300 base households checked. 188 passed every check (63%).

| Check | What it tests | Pass | Fail | Pass rate |
|---|---|---|---|---|
| `stream` | the stream ended with a plan and no error | 300 | 0 | 100% |
| `three_parts` | plan has needs, wants and wishes | 300 | 0 | 100% |
| `needs_range` | needs paid is 0 to 100 | 283 | 17 | 94% |
| `wants_bound` | wants within a sensible bound of income and savings | 282 | 18 | 94% |
| `number_check` | every number in the adviser's text is in a tool output or the profile | 271 | 29 | 90% |
| `family_pet` | family and pet costs appear when the profile has children or pets | 292 | 8 | 97% |
| `retire_cap` | no retirement age past 70 suggested | 283 | 17 | 94% |
| `actions` | three actions, no forbidden advice | 263 | 37 | 88% |
| `cost` | total cost under the budget cap | 300 | 0 | 100% |

### Failures by type

**`needs_range`** (17)
- `E15_age_79_working` (Age 79, still working, wants to stop at 80): paid_of_100=140 basics=28600
- `E29_high_spender_low_income` (Age 36 wants $120k a year in retirement on a $70k salary): paid_of_100=140 basics=66000
- `S027` (73F, retired, own): paid_of_100=140 basics=15000

**`wants_bound`** (18)
- `E14_age_79_retired` (Age 79, retired, modest savings): wants=2144000 bound=82,000
- `E22_legacy_goal` (Age 60 who wants to leave $1M to children): wants=3912000 bound=420,000
- `S040` (51M, 2 kids, $86k pay, own): wants=1416000 bound=171,540

**`number_check`** (29)
- `E02_age_gap_25_older_partner` (Age 35 with a 60-year-old partner (partner older by 25)): not in tools or profile: 17.3%
- `E16_bracket_gains` (Age 62, high bracket with a large brokerage account and low basis): not in tools or profile: 17.3%
- `E19_young_start_22` (Age 22, first job, student loans, nothing saved): not in tools or profile: 75

**`family_pet`** (8)
- `S012` (77M, retired, rent): no family_moments, pets not mentioned
- `S038` (54F, 1 kids, $56k pay, own): no family_moments
- `S138` (57F, +partner 59, $29k pay, own): no family_moments, pets not mentioned

**`retire_cap`** (17)
- `E19_young_start_22` (Age 22, first job, student loans, nothing saved): past 70: ach $226,800 by 67. Retire at 75 Working l
- `N02_business_owner_sale` (Age 54, owns a business worth $1.4M, plans to sell it at 63): past 70: ach $924,200 by 63. Retire at 75 Working l
- `S006` (33F, 1 kids, $14k pay, rent): past 70: ach $208,500 by 68. Retire at 75 Working l

**`actions`** (37)
- `E09_single_mom_2_kids` (Age 34, single parent, two kids, renting): forbidden advice
- `S016` (51M, +partner 44, $68k pay, own): forbidden advice
- `S019` (49F, +partner 50, 1 kids, $48k pay, own): forbidden advice

### Direction checks (30-case subset)

More savings (+20%) or a later retirement (+2 years, up to 70) must not lower what you can count on (wants, beyond 5% or $500) or the needs score (beyond 3 points).

| Perturbation | Pairs | Pass | Fail |
|---|---|---|---|
| +20% savings | 30 | 27 | 3 |
| retire 2 years later | 30 | 27 | 3 |

- `S101__savings_up`: wants fell 1,581,300 (97.4%) (base [1624000, 83], variant [42700, 85])
- `S157__savings_up`: needs paid fell 40 points (base [86900, 140], variant [3812000, 100])
- `S187__savings_up`: needs paid fell 46 points (base [41500, 140], variant [43000, 94])
- `S101__retire_later`: wants fell 1,580,800 (97.3%) (base [1624000, 83], variant [43200, 85])
- `S157__retire_later`: needs paid fell 40 points (base [86900, 140], variant [96200, 100])

## Benchmark against the full optimizer

300 households have both a lite plan and a saved optimizer plan (`output/synth_tree_full`, else `output/synth_tree`). Gap is (lite wants - optimal wants) / optimal wants; positive means lite promises more than the optimizer found safe.

| Wants gap | Value |
|---|---|
| Median | +22.1% |
| Mean | +463.9% |
| 10th to 90th percentile | -29.5% to +174.2% |
| Median absolute gap | 33.1% |
| Within 10% | 20% |
| Within 25% | 38% |
| Lite more than 25% above optimal | 49% |
| Lite more than 25% below optimal | 12% |

| Gap bucket | Households |
|---|---|
| < -50% | 9 |
| -50 to -25 | 27 |
| -25 to -10 | 30 |
| -10 to +10 | 57 |
| +10 to +25 | 23 |
| +25 to +50 | 57 |
| > +50% | 85 |

**Verdict (works or does not).** Lite works = wants at least the spending goal; optimizer works = its feasibility flag.

| Outcome | Households |
|---|---|
| Both say works | 58 |
| Both say does not work | 157 |
| Lite works, optimizer does not | 66 |
| Lite does not, optimizer works | 19 |

Agreement: 72% of 300.

**Claiming age.** The optimizer names one for 300 households; lite names one too for 300. Exact match 27%, within one year 36%.

**Products.** The optimizer includes a product for 44 households. Lite counts as naming a product when an action or line mentions it.

| Product | Both | Optimizer only | Lite only |
|---|---|---|---|
| annuity | 0 | 20 | 0 |
| disability | 0 | 4 | 0 |
| term_life | 0 | 22 | 0 |

Note: the optimizer's retirement age differs from the profile's for 74 households.

## AI judge

Model `mock` rated 40 sampled households. Judge spend $0.0068 (cap $1.00).

| Verdict | Count |
|---|---|
| reasonable | 25 |
| questionable | 15 |
| wrong | 0 |

**Questionable**
- `S219` (60M, +partner 59, $50k pay, own): mock judge: compared wants with the spending goal
- `S201` (76F, +partner 75, retired, own): mock judge: compared wants with the spending goal
- `S092` (60M, +partner 63, $30k pay, own): mock judge: compared wants with the spending goal
- `E09_single_mom_2_kids` (Age 34, single parent, two kids, renting): mock judge: compared wants with the spending goal
- `S098` (39F, $78k pay, own): mock judge: compared wants with the spending goal
- `S127` (76F, retired, own): mock judge: compared wants with the spending goal
- `S076` (25M, $67k pay, rent): mock judge: compared wants with the spending goal
- `S016` (51M, +partner 44, $68k pay, own): mock judge: compared wants with the spending goal

## Tokens and cost

| Item | Value |
|---|---|
| Input tokens (uncached) | 1,908,000 |
| Cached input tokens | 900,000 |
| Output tokens | 284,400 |
| App cost, all runs | $0.5400 |
| Cost per household (mean / median / max) | $0.0015 / $0.0015 / $0.0015 |
| Cost per base household (mean) | $0.0015 |
| Judge cost | $0.0068 |
| Total eval spend | $0.5468 |

| Agent | Calls | Input | Cached | Output | Cost | Cost per call |
|---|---|---|---|---|---|---|
| adviser | 360 | 936,000 | 432,000 | 162,000 | $0.3240 | $0.00090 |
| family | 360 | 324,000 | 144,000 | 43,200 | $0.0720 | $0.00020 |
| markets | 360 | 648,000 | 324,000 | 79,200 | $0.1440 | $0.00040 |

