# Reasonableness audit of the plan engine

Date: 2026-11-22. Tools only: no model call, no token cost.

## Method

- **Baselines.** 315 households: the 300 base cases in `eval/cases.jsonl` and the 15 admin samples, loaded the way the admin screen loads them. Each plan is built the way the app builds it (`prepare`, then `run_plan` with `use_ai=False`). "How sure" comes from `analysis.how_sure`.
- **Variations.** Up to 24 per baseline, 6,117 in all.
  - What Ifs go through the plan chat path (`parse_whatif`, `apply_whatif`, `run_plan` with `kept_for`): retire 3 or 1 years earlier or later (never past 70); spend 10% or 20% less or more in retirement; a careful or growth mix; pay off the mortgage; pay off high-rate debt; add a child; partner stops work; claim Social Security at the retirement age.
  - Answer changes go through the change path (`checked_pending_facts`, `_apply_change`, then a fresh plan): savings −50%, −25%, +25%, +50% and +$100,000; pay −20% and +20%; spending now +10%; add a $300,000 mortgage; add $30,000 of card debt at 22%; add a $20,000 a year pension.
- **Noise.** Every run uses the fixed seed (409), the same 2,000 paths and the same horizon. Tolerance: $500 or 2% for count-on, 2 points for basics paid.
- **Before and after.** "Before" ran on a snapshot of the code taken before any fix; "after" on the fixed code.
- **Commands:**
  - `python eval/reasonableness/harness.py --tag after --workers 4` (about 50 minutes)
  - `python eval/reasonableness/check.py --tag after --compare before`

## Pass rates (fails / checked)

| Check | Before | After |
|---|---|---|
| Verdict consistent | 0 / 6,430 | 0 / 6,432 |
| Basics 0–100 | 0 | 0 |
| No NaN or negative money | 671 | 0 |
| "How sure" ordered | 0 / 315 | 0 / 315 |
| Direction "helps" (a change that should help never hurts) | 45 / 2,628 | 21 / 2,628 |
| Direction "hurts" (a change that should hurt never helps) | 17 / 2,739 | 16 / 2,744 |
| A new goal leaves count-on alone | 5 / 1,260 | 6 / 1,260 |
| +$100k magnitude | 4 / 315 | 4 / 315 |
| What If equals a fresh plan | 42 / 806 | 17 / 810 |
| Claiming age not beaten | 1 / 186 | 1 / 183 |
| Count-on below Social Security explained | 0 / 151 | 0 / 152 |
| Savings ±50% moves count-on | 28 / 299 | 28 / 299 |
| Crashes | 5 | 0 |

Mean effect of the fixed What Ifs:

- Pay off high-rate debt: count-on −$350 → +$95; it lowered count-on in 19 plans before, 2 after.
- Pay off the mortgage: count-on −$8,116 → −$4,841; basics −30.6 → −10.7 points.

## Findings and fixes

Each fix has a regression test in `tests/test_reasonableness_engine.py` (12 tests).

1. **P0. The savings chart went below zero** (671 plans). Fix: the balance is recorded at no less than 0; those years still count as short (`simulate._run`).
2. **P0. Paying off a debt or the mortgage while working saved nothing**, so "Pay off your high-rate debt first", the plan's own top action, lowered count-on. Fix: spending now falls by the payments that would still have been made before retiring, so the plan saves them ("While you work, the plan saves the payments that stop").
3. **P0. Paying off the mortgage put it back into the basics** (S092: basics paid 100 → 0). Fix: the budget's housing figure is reset to the owner costs the basics already used. Downsizing uses the same fix.
4. **P0. A partner who stopped work could improve the plan** (S019). Fix: a gap between spending and take-home pay stays a gap (`costs.unspent_pay`).
5. **P1. A What If kept a strategy the change had broken** (N01 add a child: $6,300 against $26,100 fresh). Fix: a fresh pick is also tested when the changed plan pays the basics in fewer than 90 of 100 (`neighbors.one_change`, `REPICK_BELOW`).
6. **P1. When nothing lasts, the plan claimed at 67.** Fix: it now takes the earliest claiming age (S089, retired at 61 with $2,200 saved, now claims at 62).
7. **P2. Crash for a partner under 30 who stops work.** Fix: a partner's retirement age is allowed from 18.
8. **Sample households.** Doctor: spending now $215,000 → $160,000 and goal $190,000 → $105,000; count-on $111,600, "works". e27: goal $180,000 → $110,000; count-on $122,600, "works".

## Claiming age: reasonable, no change

- The plan claims after retiring in 172 of 183 plans where the person can still choose, with a median gain of 6.2% in count-on over claiming at retirement.
- Claiming at retirement pays the basics more often in only 3 plans, all of them falls-short plans.
- The low-savings samples do bridge: e11 saves $3,464 a year for 21 years and holds $97,000 at 66 in the middle path; claiming at 68 gives $23,300 against $22,200 at 66 (basics 1 of 100 either way). e09 counts its $100,000 inheritance and holds $399,000 at 66; claiming at 70 pays the basics in 99 of 100, against 93 at 66.
- Count-on is below Social Security in 152 plans, always explained in the headline: health costs on top (99), the years before Social Security starts (65), spending above take-home pay (53), the survivor step-down (20), tax (10).

## Remaining issues (not changed)

- **R1.** Pre-retirement shortfalls are dropped (28 of 299 plans don't respond to savings ±50%). Proposed fix: carry them as debt at a loan rate.
- **R2.** A retiree's mortgage sits inside their spending (E20: adding $300k raises count-on from $111,300 to $164,800).
- **R3.** When a plan falls short, the picker maximises count-on, which can trade away basics.
- **R4.** A What If keeps the plan's strategy while the basics are safe, up to 15% below a fresh plan.
- **R5.** A partner's Social Security that starts before you retire is ignored.
- **R6.** Retiring later can lower count-on in plans with a spending gap or a falls-short re-pick (all 24 failures are falls-short plans).
- **R7.** The withdrawal tax is measured at the goal, so a new goal moves count-on by up to 3%.
- **R8.** A mortgage payment below the typical owner costs frees nothing when it ends (S083 basics 90 → 70).
- **R9.** Paying debts from pre-tax savings is untaxed.
- **R10.** Fixed payments are held level in today's dollars.
- **R11.** 4 magnitude failures, explained by R1 or by $0 → safe.
