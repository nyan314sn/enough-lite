# Loop round 2, audit B: UI/UX (strict)

Independent auditor (Sonnet), 2026-11-21. Own backend on :8042 serving the rebuilt `web/dist`; Playwright (Edge) at 1440, 820, 390. 14 journeys. AI under $0.50. Scripts and screenshots in this folder.

**Counts: P0 1, P1 9, P2 10** (round 1: P0 4, P1 11, P2 11). Axe 0 violations at all widths; no sideways scroll.

## P0
1. **"Spend less" What Ifs are misread.** "spend $500 less a month" (retired couple, $72,000 goal) answers "If you spend $6,000 a year ... $61,200 (now $61,200)" with no change; the bus driver's starting point "Spend $5,000 a year less" is worded "If you spend $5,000 a year". (`bus_s1.png`, `retired_s3.png`; ask_intent / What If parser)

## P1
1. Falls-short starting points: 2 of 3 give $0 and 0/100 (spend less, claim at 70); only "retire at 67" helps; not clickable; action 1 repeats the box. (`e1_plan.png`)
2. "Retire at 60" for a 71-year-old (or 62 for a 66-year-old) runs a What If instead of saying they are already retired; same for "Another child" at 71. (`v3_retire60.png`)
3. Assumed yearly saving: panel "$15,000 (typical)" vs Assumptions "$51,123 a year: $15,000 ... $36,123 of take-home pay left". (`v1.py`)
4. "Costs now" panel $69,000 (estimate) vs plan $72,000 when spending is skipped. (`v2_plan.png`)
5. Social Security panel $33,000 (estimate) vs headline $38,300 (single parent). (`parent2_plan.png`)
6. A bare "62" answering the mortgage-payment question set age to 62.
7. After Start over, "Your plan is kept..." reappears; plan-page What If chips show in the intake chat after "Change my answers". (`v4_startover.png`)
8. No sanity check on a $12,500/month mortgage payment; count-on $170,600 includes a payment that ends in 2028; one run errored.
9. "I have $8,000 saved and student loans" invented an $8,000 loan tagged "you said".

## P2
1. Chip row still cut mid-word at 1440 ("Markets fall 3"); ask bar about 120 px.
2. Team talk first line still clipped (scrolled to a half row). (`v1_talk.png`)
3. Adviser detail technical ("Tested 21 strategies...", monospace, token count). (`v1_adviser.png`)
4. Assumptions expander: 12 jargon-heavy lines.
5. Odd copy: "this is about the basics, with $39,000 above them"; "a 1 in 4 chance your partner reaches 104"; a debt under "Family moments"; wish text that contradicts itself ("below what lasts, so the goal is above what is safe").
6. "skip" not accepted on the investment-split question.
7. Crypto reply duplicated ("We can't help with that. I can't help with that."); bitcoin gets the single-stock text.
8. "Get a second dog" not understood.
9. First intake reply 120–150 words; savings total read as $690k vs $650k on two runs.
10. Small: stepper hides step 3 at 820; Assumptions summary 21 px tall on phone; widow told "If you tell me his age, I can check it"; college row "private, you pay 100%" with a stale "Assumed public college" note.

## Checked and fine
Widow never asked a partner's age; intake replies say what was recorded and ask one question; retiree view consistent with no Medicare-at-65 note; today's-dollars line; Assumptions expander; stale banner; retry; history chips; change confirmations; phone layout. Verdict words "close" and "below your goal" were not seen in the UI.

## Round 1 verification
Fixed: P0-2, P0-3, P0-4, P1-1, P1-2, P1-3, P1-6, P1-8, P1-10, P2-2, P2-8, P2-9, P2-10.
Partly or mostly: P0-1 (see P1-1), P1-4, P1-5, P1-7 (new P1-9), P1-9, P1-11, P2-1, P2-3, P2-5, P2-6, P2-11.
Not fixed: P2-4 (reproduced). Not seen: P2-7.

## Frontend fixes done (round 2 UI fixer)
Fixed: P1-1 (UI: "Try this" buttons), P1-2 (UI: chips and typed retire ages), P1-7, P2-1, P2-2, P2-3, P2-10, Assumptions shows 4 then "More assumptions". vitest 94, tsc clean, axe 0, web/dist rebuilt.

Backend still needed:
1. Every starting point needs a `whatif_text` ("Spend $5,000 a year less now and save it" has none).
2. Action 1 still carries a "Starting points: ..." tail (frontend hides it).
3. Do not offer lever What Ifs with a past retire age, or "another child" over 50.
4. Order the assumptions by importance and simplify their wording.
5. Shorten adviser finding text.
