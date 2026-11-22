# Loop round 3, audit A: logic, math and reasoning

Independent auditor (Sonnet), 2026-11-21. Own instance on :8070. The live eval stalled (the machine was loaded, then the AI service returned errors), so it was stopped at 103 of 480 runs. All 480 cases were then run tools-only, in-process, with no AI. Counts, verdicts and starting points come from the tools; the AI writes text only. Text-quality checks on live AI output were not redone this round. AI cost about $0.30.

**Counts: P0 0, P1 0, P2 7.** Round 2: P0 0, P1 3, P2 12. Round 1: P0 1, P1 9, P2 12.

## Round 2 verification
- **Social Security in working years:** correct, with no double counting. For the 55/70 couple the app's $102,000 is backed by an independent simulation: $99,447 at claim 67, while the app picks claim 70.
- **Survivor spending at 75%:** within −0.4% to +1.5% of an independent simulation across 32 households.
- **Starting points:** `makes_basics_safe` matches "basics paid in 90 or more of 100" with 0 mismatches. None goes past 70, and the stated age is never moved. The headline's promise appears only when a safe point exists, with 0 violations over 220 falls-short runs.
- **Recomputed to the dollar:** the additional Medicare tax, the 401(k) catch-up at 60 to 63, and the Colorado exemption at 65 and over.
- **One figure everywhere:** 15 of 15 households agree, and `plan.consistency` is empty in all 480 runs.
- **Tax and Social Security:** zero difference from the independent recompute on 32 households. 0 verdict-rule mismatches. Direction checks: 180 of 180.

## P2
1. **No earnings test when someone claims early and keeps working.** The full benefit is counted. This is optimistic for early claimers who are still working. (`socialsec.py:57`, `simulate.py` `_run`)
2. **A deficit plus retiring later can lower count-on.** For example, q36 at retire+2 falls to $0, and q13 falls 17.9%. Each extra working year adds another year of the deficit. The numbers are consistent, but the plan should explain it.
3. **Low-income deficit cases fall to $0 and the wrong reason is given** (S006, S104 and others). The headline blames health costs when the cause is spending above pay. No starting points are offered. (`adviser.py` `_headline`)
4. **One combined starting point re-parses slightly differently.** S001 shows basics paid in 91 of 100 against 96 in the audit's recompute. Count-on matches.
5. **Starting points clutter.** S240 offers three "retire at N and spend $2,000 less" variants.
6. **Couples with an age gap of 6 or more years sit 24% above the optimizer**, against +1.9% for smaller gaps. The first death is fixed at the shorter life expectancy, and the survivor then spends 75% for decades.
7. **A child added in the answers editor raises count-on**, because only the child tax credit changes. The What If path is correct.

## Invariants
- **Round 2 set:** 292 checks, 11 violations over 3%: kid+1 ×5, claim+2 ×3, retire+2 ×2, partner claim+2 ×1.
- **20 new households:** 92 checks, 1 violation.

## Eval (tools-only, 288 benchmark rows)

| Measure | Round 2 | Round 3 |
|---|---|---|
| Median gap to optimizer | −6.8% | −0.8% |
| Couples | −8.3% | +3.4% |
| Singles | −5.8% | −6.2% |
| Median absolute gap | 19.2% | 17.7% |
| Within 25% | 59% | 60% |
| Verdict agreement | 84% | 84% |

**Judgement:** couples sitting above the optimizer is mostly a correction of round 2's −8% bias. Round 1 had couples at +4.9%. The exception is the age-gap group (P2-6).
