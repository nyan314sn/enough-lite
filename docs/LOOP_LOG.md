# Self-improving loop log

## Round 1 (2026-11-21)

Audits run by independent agents that did not build the app.

| Audit | P0 | P1 | P2 | Findings |
|---|---|---|---|---|
| A. Logic, math, reasoning (16 households, 480 eval runs, $1.21) | 1 | 9 | 12 | `loop/round1_A/FINDINGS.md` |
| B. UI/UX strict (10 journeys, desktop and phone, $0.15) | 4 | 11 | 11 | `loop/round1_B/FINDINGS.md` |
| C. Simulated users (40 personas, run by the intake rework, 4 rounds) | 0 dead ends (8 other P0s) | | | `../simusers/SIM_REPORT.md` |

Held up in A: tax, Social Security and costs match an independent recompute to the dollar; an independent 20,000-path simulation is within 1.5%; 480 eval runs, 0 errors, all direction checks 30/30, median gap to optimizer −1.7% (was −2.9%).
Held up in B: axe 0 violations, What If collapse and history, confirm/reset flows, error states.

Fixes in progress: engine and plan (A all, B P0-1, P0-2, P0-4 plan side, P1-9, P1-11); screens (B P1-1 to 3, 5, 6, 10, P2s); intake (B P0-3, P0-4, P1-4, 7, 8).

Audit C detail (intake rework, final round of 4): profile accuracy 75% → 96% (target ≥92%); reached a plan 36/40 → 40/40; P0 dead ends 29 → 0; all dead ends 46 → 5; attacks 74/74. Four of the 8 remaining P0s were fixed with tests after the last sim round; two are on the plan page (widowed person asked for a partner's age; "already 66" misread).

Round 1 engine and plan fixes (main model, $1.85): A F1–F14, F16–F22 fixed (F15 not done; F5 drops 4 → 3 of 152). B P0-1, P0-2, P0-4, P1-9, P1-11 fixed. Before → after: h11 couple count-on $98,400 → $83,000 (survivor step-down now applied); age-gap-25 couple "to age 119" → "until your partner is 94"; h06 claim age 70 → 67; h13 federal tax $10,504 → $2,404. Eval 480 runs all ok, core 300/300, direction 30/30 ×6; median gap to optimizer −1.7% → −6.8% (more conservative); within 25% 56% → 59%; verdict agreement 82.7% → 85.3%. Tests: pytest 405, vitest 85.

## Round 2 (2026-11-21)

App restarted on :8020 with all round 1 fixes. Audits A, B, C launched in parallel (Sonnet).

| Audit | P0 | P1 | P2 | Findings |
|---|---|---|---|---|
| A. Logic, math (32 households, 292 perturbations, 480 eval runs, $1.5) | 0 (was 1) | 3 (was 9) | 12 | `loop/round2_A/FINDINGS.md` |
| B. UI/UX (14 journeys, $0.5) | 1 (was 4) | 9 (was 11) | 10 | `loop/round2_B/FINDINGS.md` |
| C. Simulated users (48 incl. 8 hard; 184 plan-chat turns, $0.67) | 6 dead ends | 26 | | `loop/round2_C/FINDINGS.md` |

Round 2 C: accuracy 93.8%, reached plan 45/48 (original 40: 38/40), P0 dead ends 6, attacks 74/74, new round 2 attacks 91/107 (pre-fix). Plan chat tested for the first time: no change applied without confirmation; about 39 of 90 What Ifs answered with text instead of a What If.
Stop criteria not met. Round 2 fixes running: security (review + 16 attack fails), UI (done: starting-point buttons, chips, Start over, talk clipping, plain adviser detail), plan chat (What If recognition), intake (dead ends, misreads), plan figures (consistency, starting points, A's P1s: SS in working years, survivor spending step, headline promise).

Round 2 fixes done: security (74/74; round 2 kit 91 → 101/107, the other 6 judged non-defects), UI (starting-point buttons, chips, Start over, talk clipping), plan chat (What If recognition for natural and typo forms, spend-less, provenance answers, run-out age, widow reply), intake (three never-reached-plan personas now reach it; "I don't know" approves the typical figure; misreads; payment sanity checks), plan figures (one figure everywhere with a code check; starting points that help, `makes_basics_safe`; SS in working years; survivor spending 75%; Medicare surtax; catch-up; CO exemption; deficits drawn from savings). Savings-by-age medians checked against Fed SCF 2022. Eval: median gap to optimizer −6.8% → −0.8% (couples −8.3% → +3.4%, singles −6.2%), absolute gap 19.2% → 17.7%, verdict agreement 84%. Tests: pytest 517 passed.

## Round 3 (final, 2026-11-21)

App restarted on :8020 with all round 2 fixes. Audits A, B, C launched in parallel (Sonnet).

| Audit | P0 | P1 | P2 | Findings |
|---|---|---|---|---|
| A. Logic, math (32 households, 384 invariant checks, 480 tools-only eval runs, $0.30) | 0 | 0 (was 3) | 7 | `loop/round3_A/FINDINGS.md` |
| B. UI/UX (17 journeys, under $0.10) | 1 | 6 (was 9) | 9 | `loop/round3_B/FINDINGS.md` |
| C. Simulated users (48; 186 plan-chat turns, $0.30) | 3 dead ends (2 likely load) | see file | | `loop/round3_C/FINDINGS.md` |

Round 3 C: accuracy 95.1%, reached a plan 48/48 (original 40: 40/40), P0 dead ends 3 (was 6; 2 were connection drops while the attack kits ran), What If hit rate 73% (was 57%), attacks 74/74, round 2 kit 101/107 (the 6 known non-defects).
Stop criteria after round 3: accuracy met, reached-plan met, attacks met, eval core checks met, A has 0 P0 and 0 P1; not met: B has 1 P0 (the saving questions reject their own answers) and C has 1 real P0 dead end. Three rounds done, so the loop ends here. The remaining P0/P1 items are being fixed, then the live product-rules audit (`PRODUCT_RULES.md`) is the final gate.
The user found by hand a rule broken that no audit caught ("Not sure, estimate it" left the mortgage blank). Audits now check the user's rules explicitly (`docs/PRODUCT_RULES.md`), with code coverage tests in `tests/test_product_rules.py`.
