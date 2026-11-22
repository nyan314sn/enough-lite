# Loop round 2, audit A: logic, math and reasoning

Independent auditor (Sonnet), 2026-11-21. Own instance on :8040; 32 households (16 from round 1, 16 new), 292 perturbation checks on 72 households, and 480 eval runs. AI cost about $1.5. Scripts and data are in this folder.

**Counts: P0 0, P1 3, P2 12.** Round 1 had P0 1, P1 9, P2 12.

## What held up
- Working-year tax (head of household, child credit, 401(k) deduction) matches an independent recompute to the dollar.
- The Social Security schedule matches with zero difference: per-person start, spousal at 50% with no delayed credit, partner claim age, survivor step-down.
- The withdrawal rate is within 0.1 point.
- A 12,000-path simulation is within about 1.5% (worst −4.2%).
- 0 verdict-rule mismatches over 480 runs.
- Starting points reproduce exactly.

## P1
1. **Social Security is dropped in working years when a household member already claims.** A 55/70 couple, partner claiming $28,526, you retiring at 65: count-on $71,231 against about $81,700. Cause: `tools/simulate.py` `_run` adds Social Security only in the retired branch.
2. **The survivor step-down cuts Social Security but not spending.** Couples are 11% lower than in round 1, and 21 couples flipped to falls_short (S181: basics paid 100 → 0). This bias explains most of the −6.8% median gap. Cause: no spending step after the first death (`adviser.py:509`, `simulate.py`).
3. **The headline promises the starting points fix the plan.** In 121 of 185 falls_short plans, no starting point makes the basics safe. Cause: `adviser.py` `_headline`, and `starting_points` keeping any change that raises safe spending by 5%.

## P2
- "Retire later" jumps to 67 (`max(ra+2, 67)`).
- F15 (tax text order) and F17 (timeline jump at 65) are still open.
- No additional Medicare tax of 0.9%.
- Colorado taxes Social Security at 65 and over, though it is exempt there.
- 401(k) catch-up at 60 to 63 is missing; all saving is treated as pre-tax.
- A deficit (spending above take-home pay) is ignored.
- Status-line actions remain (52 of 480).
- Low-value actions.
- Adding a child raises count-on for single parents.
- Code-built dollar figures appear in actions (234 of 480).
- F21 is partly fixed.
- Template fallbacks (23%) came from audit load, not a regression.

## Round 1 verification
- **Fixed:** F1, F2, F3, F4, F6, F7, F8, F9, F10, F11, F12, F14, F20.
- **Partly or mostly fixed:** F5 (6 of 292 over 3%), F13 (no spending step), F16, F18, F21, F22.
- **Open:** F15, F17, F19.

## Eval (480 runs, 0 errors)

| Measure | Round 1 | Round 2 |
|---|---|---|
| Median gap to optimizer | −1.7% | −6.8% |
| Within 25% | 56% | 59% |
| Median absolute gap | 22.1% | 19.2% |
| Verdict agreement | 82% | 84% |

- Direction checks: 179 of 180.
- Couples' median gap went from +4.9% to −8.3%; singles from −8.1% to −5.8%.
- `eval/checks.py` reported 0 of 300 applicable on these runs (to investigate).
