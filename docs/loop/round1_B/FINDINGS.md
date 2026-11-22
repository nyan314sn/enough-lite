# Loop round 1, audit B: UI/UX (strict)

Independent auditor (Sonnet), 2026-11-21. Own backend on :8032 and Vite on :5182; Playwright (Edge) at 1440x900 and 390x844, with spot checks at 820 and 1100. 10 journeys. AI cost about $0.15. Scripts and screenshots in this folder.

**Counts: P0 4, P1 11, P2 11.** Axe: 0 violations at 1440 and 390. Keyboard order and focus ring fine. No sideways scroll at any width.

## P0
1. **A plan that falls short is a dead end with wrong advice.** Bus driver, 52, MI, $52k pay, spends $4,200/mo, $30k saved, retires at 58: "You can count on $0 a year", needs 0/100; action 1 says "...$0 a year. Start there"; 4 of 5 What Ifs read "$0 against $0"; only "retire at 67" helps, and the user must guess it. Should say once it does not work on their numbers and offer 2 or 3 starting points with results, keeping their age. (`j7.py`, `j7_plan_vp.png`)
2. **An already-retired couple (71/69, spend $6,000/mo) is planned at 80% of spending.** Panel shows $72,000 now but $57,600 in retirement (assumed); header says "retire at 71"; costs chart "Costs now: $57,600"; goal "short by $2,400" (about $16,800 at $72,000); "before Medicare at 65" footnote shown to a 71-year-old. (`j6_plan_vp.png`)
3. **A stated Social Security figure loses the partner's half.** "$2,900 a month, and she gets $1,100" becomes $34,800 a year; her $13,200 is gone. (intake)
4. **A missing spending figure becomes $100 a year** (age 30, Austin, $95k, loans, $8k saved). The plan shows "$162,900 a year, $100 for basics"; the text leaks "according to the tool output, though that figure looks wrong"; emergency fund "96 months". (`j5_sheet_phone.png`, `j5_plan_phone.png`)

## P1
1. Stale "Show this What If" buttons in chat do nothing after a change. (`j10_stale_show_vp.png`; TeamScreen.tsx, AskBox.tsx)
2. History chips say "basics same" when the main figure moves (retire at 65: $35,100 to $47,900). (`j1b_wi4_vp.png`)
3. A failed question has no retry, the box is cleared first, and raw server detail is shown. (AskBox.tsx)
4. "should I buy Tesla stock" returns the first action instead of "I don't give stock tips"; "What is my safe spending number?" gives a definition, not the figure.
5. What If chips ignore the person (a 71-year-old retiree gets "Retire at 60" and "Another child") and never show as already tried.
6. Change confirmation lists four unrelated IRS/SSA/Medicare links; awkward update text ("your pay to $150,000 a year").
7. Student-loan rate 6.5% shown as "6% (assumed)" while the loan is tagged "you said".
8. A nurse's pension (about $1,500/mo at 62) was not captured or asked; a teacher's was.
9. "Costs now" differs between panel and costs chart ($48,000 vs $48,641; $72,000 vs $57,600).
10. A stale plan stays interactive: the banner scrolls away and What Ifs still run on the old plan.
11. Jargon in plan text: "rule of thumb, a strategy from similar households... the one we used", "such households are rare in our library", "according to the tool output".

## P2
1. The sticky ask bar takes about 150 px of 900 (desktop) and 21% of a phone screen; chip rows are cut mid-word.
2. Empty "Family moments" heading for people with no family.
3. Every action in a What If is tagged "new" because titles are reworded.
4. Team talk panel's first line is clipped.
5. Adviser detail shows debug text (token counts, cost); the intake card says only "finished before the team started".
6. After "Change my answers" the old pending question and chips remain; each edit triggers an unrelated "is that about right?".
7. The "Change my answers" link is 17 px tall on phone.
8. Saving in the phone sheet hides the bot's reply behind the modal.
9. The header note repeats on every screen; on phone "Start over" wraps and the plan starts about 230 px down.
10. Rule answers drop the "$" sign ("666 per year").
11. Odd copy: "against 0 now", "1 family moments", "covered about 2 times over", "3 years without Medicare" repeated in two actions.

## What works
- What If collapse, "Back to my plan", history reopen, five What Ifs in a row.
- Change confirm Yes/No, editor validation, section Reset, stale banner, Start over.
- Plan and intake errors have a retry and a way back; the wait state has progress and a timer.
- Earlier plan-page P0s are fixed. The light navy style, portraits and green/amber are consistent.
