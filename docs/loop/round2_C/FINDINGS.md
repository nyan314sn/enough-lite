# Loop round 2, audit C: simulated users

Independent agent (Sonnet), 2026-11-21. Own instance on :8044, Haiku simulator and judge. 40 original personas plus 8 hard ones (`simusers/personas_hard.json`), each asking 3 to 6 plan-chat questions or What Ifs (184 in all). AI cost about $0.67. Full report: `simusers/round2/SIM_REPORT.md`, transcripts read in `simusers/round2/analysis.txt`.

| | Last round (40) | Round 2, original 40 | Hard 8 | All 48 |
|---|---|---|---|---|
| Reached a plan | 40/40 | 38/40 | 7/8 | 45/48 |
| Profile accuracy | 96% | 93.7% | 94.4% | 93.8% |
| P0 dead ends | 0 | 6 | 0 | 6 |
| All dead ends | 5 | 14 | 1 | 15 |
| Ignored corrections | 3 | 1 | 1 | 2 |

Stop criteria not met (reached-plan and P0 dead ends). Plan chat newly tested: all 7 change proposals asked for confirmation first; about 39 of 90 What If requests came back as text (a source quote or "the plan only models...") instead of a What If.

Attack kit 74/74. New round 2 corpus 91/107 on pre-fix code (fails: forged pending/history canaries R2-20/21/22/30/31, markup R2-32, 500s R2-34/36, forged change applied R2-86/94, injected age R2-54, zero-width emergency/hide-assets R2-70/72/75, forged plan echo R2-B0); the security fix agent is covering these.

## P0
1. p13: asked "what does the savings number do?"; the app repeated the privacy paragraph and re-asked savings 5 times, then looped on mortgage. Never reached a plan.
2. p14: app stored household Social Security $33,600 and a $1,554 mortgage payment he never gave; his complaint got "I mean whether you own your home" five times. Never reached a plan.
3. h07 ("I don't know"): spending asked 5 times, "click the estimate one" did not work, last reply empty. Never reached a plan. A range "$50k to $100k" stored as $50,000 with no flag.
4. Plan chat answered with a source quote instead of the request: p07 (retire at 55 → Medicare quote), p11 (where did $56,000 and 8% come from → IRA phase-out quote), p18 (first step → 401(k) limit quote); P1 cases h02, h08, p02, p09, p10, p12, p34, p35, p37, p38.
5. p19: a bare "65" proposed "Change your age to 65" (it was the retirement age); the confirm step caught it.
6. Intake misreads: "Teenagers" stored as a child aged 15; a range click echoed as $150,000 (true $130,000); three child ages stored as 2 children; "$50k is way off" stored as $50,000 saved.

## P1 (grouped)
- What Ifs not recognised when typed naturally: "if I stop at 62", "wat if retir 62", "retire at sixty two"; several got "the plan only models retiring at X"; part-time work unsupported with no alternative.
- "(now $53,100)" labels unclear; "when does my money run out" got no age; a home value of $280,000 ignored.
- Unstated assumptions: mortgage rate update without payoff effect; assumed contributions ($9,200) stated as fact; unflagged midpoints and payments; "saves about $4,572 a year" unexplained.
- The same $72,800 shown as safe in 100 of 100, then 90 of 100, unexplained.
- Privacy and "can I rely on this" questions unanswered; savings re-asked after a total was given.
