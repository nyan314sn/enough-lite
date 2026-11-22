# What If phrasing: does the chat understand people's own words?

PLAN.md item 3b, 2026-11-22. The aim was the chat's reading of What Ifs in general, not one sentence ("what if I have 5 dogs").

## Method

**The set** (`cases.jsonl`, written by `make_cases.py`): 413 What If messages, each tied to a household from `app/data/sample_households.json` and an expected outcome: the change in plain terms (`{"retire_age": 64}`, or `{"pets": {"dog": 5}}` meaning 5 dogs after the change), `"clarify"`, or `"refuse"`.

- **Tune set, 324 cases.** The rules were built against these. They cover every change the plan can test: retirement age (including relative ages, "now", "next year"), the partner's retirement, Social Security age, saving, spending (goal, now, dollars, percent, fractions), part-time work, a move, children, college per child, pets (in all, more, fewer), debts, pensions, a market fall, inflation, a bad decade, and the investing mix. They also include several changes in one message, past and conditional tense, typos, numbers in words, and 42 near-misses (Medicaid and SSI hiding, stock picks, injection, retiring at 30, "what if I'm 30", pay rises, divorce, a new loan, a pension, 50 dogs).
- **Held-out set, 89 cases.** Written after the rules were built and not used to tune them. They measure wordings the reader was not built for ("pull the plug on work at 61", "squirrel away another 800 a month", "the kids talk me into two hamsters", "the S&P drops 25%").

**Scoring** (`run.py`). The rules path follows `pipeline.ask` in order: safety refusals, then `parse_whatif`, then `apply_whatif`'s own checks. A change dict is correct only if every key matches, within 1%. A change the plan then turns down ("your savings do not cover the card") scores as read correctly. The AI mode calls `whatif_ai.fallback` where `pipeline.ask` does, and scores the What If in its confirm chip as the rules read it back. "Before" is a copy of `app/` with the morning's `whatif_read.py`, `pipeline.py` and `ask_intent.py`. The AI runs used Claude Haiku 5.5 at low effort (the provider the `.env` picks), with the app's limits and caps.

## Results

| | Tune set (324) | Held-out set (89) | Held-out, changes only |
|---|---:|---:|---:|
| Before (old rules) | 206 (64%) | 39 (44%) | 19 of 69 (28%) |
| Rules now, no model | 324 (100%) | 52 (58%) | 32 of 69 (46%) |
| Rules + AI, first live run (clean) | 322 (99%) | 81 (91%) | 63 of 70 (90%) |
| Rules + AI, final | 324 (100%) | 87 (98%) | 67 of 69 (97%) |

- **The tune-set figure for the rules is not a fair measure**: the rules were built on those cases. The held-out column is the honest one: the new rules alone read 58%, up from 44%; with the AI reader the first live run read 91%.
- **The final run is not clean.** After the first live run, its failures were fixed (earlier/later checked against the words, "halve" as 50%, one more child or pet needing no number, a pet's kind taken from the words, market tests only when markets or prices are named, "double" removed as a number), and two wrong expected outcomes were corrected. Read 98% as the score after fixes, not a fresh test.
- **Wrong readings matter more than misses**, because a rules reading runs at once. Across all 413 cases the old rules read 27 messages wrongly, for example "save twenty dollars a week more" → saving 30% of pay; "save 10 grand more" → $10; "spend 10% more in retirement" → saving 20%; "3 dogs in total" → 5 dogs; "retire at 62 and get 5 dogs" → the age only. The new rules read 2 wrongly, both held-out. A model reading never runs without a yes.
- **Near-misses and refusals:** 63 of 63 in the final run, 62 of 63 in the first (the model turned "what if gas prices double" into doubling spending; the person would have seen "you spend 100% more" and could say no; "double" is no longer accepted as a number).

Per change type: `table.md`. On the held-out set the AI reader made the biggest difference for retirement age (2 of 10 → 10 of 10), moves (0 of 5 → 5 of 5), debts (1 of 4 → 4 of 4) and markets (0 of 5 → 4 of 5).

**Cost and speed.** The model is called only where the rules find nothing (and the message looks like a What If) or clearly read only part of it: 58 of 413 messages. First run $0.0067, final run $0.0041: about $0.0001 and 1.2 seconds a call.

## What changed

**Rules** (`app/whatif_read.py`, deterministic): number words before what they count, and typos; pets in all, more and fewer (at most 10 of a kind); children; relative retirement ages; Social Security forms; spending percents, fractions and per week; part-time "for N years after I retire".

**Change parsing** (`app/pipeline.py`): saving (week, less, "stop saving", "by 3%", "to 20%"); debts ("cleared", "paid the house off", "debt free"); markets (tank, collapse, "a crash", "inflation runs at 6%", "prices keep going up", "returns are bad"); moves (relocate, "retire to", "moved in with my sister in Ohio"); the investing mix (conservative, aggressive, "play it safe"); college ("neither kid goes to college").

**AI fallback** (`app/whatif_ai.py`). The model maps the message to a typed `WhatIfRead`. Code checks each change: only known fields; every number must appear in the message; retirement ages from the person's age to 70; Social Security from 62 (or their age) to 70; at most 10 pets of a kind and 4 new children; dollar sums in sane ranges; states named in the message; earlier or later matching the words; market tests only when markets or prices are named. A change that passes becomes a plain sentence built in code and is offered for a yes ("I read that as: you have 5 dogs in all (2 now). Shall I run this What If?"). A yes runs the sentence through the rules like typed text; no runs nothing. If the rules read part of a message, their reading wins and the model adds only the missing part; with the model off, the answer says which part was left out. Refusals are answered before any model call. If the model is unavailable, the reply is the earlier clarify text.

**"Can't model that" replies.** Pensions, pay changes, job loss, new loans, buying a home, the person's age, illness, taxes, divorce or a death, and Social Security cuts each get a plain line saying what the plan can test instead, with 2–3 chips and no model call.

## Remaining failures

- "Stocks lose a third of their value the year I retire": the rules read a 30% fall, not 33% (the rules catch it first, so the model never sees it).
- "My wife stops at 60 and I keep going until 65": only the wife's age is read.
- Partial readings are found by topic words; a part in words the topic list does not know ("doggos") is not noticed.
- One person wrote the set, and the held-out set is small (89 cases, 69 changes). Treat the percentages as rough.

Tests: `tests/test_whatif_phrasing.py` (378 tests, model mocked); 1,105 passed, 2 skipped across the 20 related test files.
