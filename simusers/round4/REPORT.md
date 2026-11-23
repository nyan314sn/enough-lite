# Round 4: simulated users on the redesigned app (R26)

2026-11-22. App at localhost:8020, test mode, Claude Haiku 5.5. Simulator and intake judge Haiku; R26 lens judge claude-sonnet-5-5. Files: `run_round4.py`, `analyze.py`, `make_hs.py`, `runs/`, `runs_early/`, `judged*/`, `plans/`, `lens/`, `tally.json`; hurried personas in `simusers/personas_hs.json`. Cost about $0.31.

## What ran
- **Normal path:** the same 24 users as `eval/model_compare` (20 personas + 4 hard) through intake to a built plan.
- **Early-build path:** 8 of the 24 plus 2 hurried personas give 1–2 answers, press Build, accept the check step.
- **R26 lens:** 6 new hurried high-school-graduate personas (short answers, "idk", slang, typos). A judge reads only the plan's top text (verdict, shortfall line, needs/wants/wishes rows, headline, first move) and answers: (a) can I retire when I want? (b) how short or ahead am I? (c) what do I do first?

## Before → after (the 24)

| Measure | Before | After (redesign) | Early path (10) |
|---|---|---|---|
| Reached a built plan | 22 of 24 | **24 of 24** | 10 of 10 |
| Turns to ready (mean) | 8.4 | 9.3 | **2.5** |
| Profile fields correct | 93.9% | **96.8%** | 61.2% (typical figures, by design) |
| Wrong fields the person never gave | 11 | **4** | 41 (all marked typical/estimate or not shown) |
| Wrong fields tagged "you said" | 5 | 4 | **0** |
| Judge P0 / P1 (raw) | 6 / 10 | 5 / 5 | 0 / 0 |

Hurried 6 on the normal path: 6 of 6 reached a plan, 90.8% fields correct, 0 P0/P1.

## R26 lens: can a hurried reader answer the three questions from the top of the plan?

| Group | n | (a) retire when I want | (b) how short/ahead | (c) first thing to do | All three | Reading grade |
|---|---|---|---|---|---|---|
| Hurried 6, normal | 6 | 0 | 5 | 1 | 0 | 1.0 |
| All plans | 40 | 11 (28%) | 38 (95%) | 22 (56%) | 7 (18%) | 1.4 |

By verdict: "on track" plans pass all three (7 of 9); "Close" and "Not yet" plans almost never answer (a), because the top never names the person's own retirement age; "needs safe" plans fail (c) 9 of 9, because first-move titles name a goal ("Make your needs safe first") rather than an action with a number. Reading grade is not the problem (≤ 2.2); the words judged hardest were "market tests", "Wishes", "safe level" and "Wants: $0".

## Issues (hand-checked)

- **P0** A What If asked during intake ("what if I save an extra 1,000 a month?") was read as a savings change ("Change your savings from $188,000 to $80,000?").
- **P1** The verdict never ties to the person's retirement age (all 22 Close/Not-yet plans).
- **P1** First-move titles are goals, not actions with a number.
- **P1** Early build assumed retirement at 65 without asking (7 of 10 early runs).
- **P1** "Why do you need my age?" got a canned reply with no reason.
- **P1** Retirement spending was lowered with no mention in one hard case.
- **P2** No state row when state is assumed; "idk what to say" gets no example; hardest words as above.

Rejected judge findings (read by hand): 4 of the 5 raw P0s were judge errors (figures correct, or differences on purpose).

## Caveats
Small samples, one run per persona; the lens reads text rebuilt from plan JSON, not a screenshot (no ring, bar or badges shown to the judge); the simulated reader is a model role-playing, not a person. No plan chat or What If was re-run this round.
