# Demo v3 storyboard (redesigned app) - prepared, not yet recorded

Target about 2:50 (estimated 172 s from word count; the real length comes from the MP3s). One voice (nova), about the app only.
Rule: every spoken claim and number is visible on screen during its scene. Numbers are written as `{name}` in the script,
read from the live page by `--v3 figures`, and spoken as words. A check after recording enforces this (see the end).

## Household (typed in plain words)
"I'm 54 and my wife is 52, in Ohio. I make about $95,000 and she makes $60,000. We have about $520,000 saved. We owe $140,000 on our house.
Our son is 16. We'd like to retire at 60 and spend about $70,000 a year."
No follow-up answers are given: Build my plan is pressed right after the first reply, so the rest (split of savings, saving rate, college, etc.) are typical figures marked estimate.

Seen on the live app (4 plans, same numbers every time): readiness ring 70; "Short $20,900 a year"; goal $70,000; can count on $49,100;
needs $39,600 (97 of 100 tests, Safe); wants +$9,500 (Sure); wishes +$20,900 (Open). The move marked "Closes the gap" is
"Set your spending goal nearer the safe level" -> What If "Spend $49k": ring 100 (up 30 points vs baseline), "Level up: wishes covered now",
"This change closes the gap", goal lasts in 6 of 100 -> 90 of 100. Tick: "1 of 3 planned".

## Scenes
| # | id (mode) | On screen | Narration (numbers filled at record time) |
|---|---|---|---|
| 1 | title (card) | Card "Can we retire at 60?" | Can we retire at sixty? Every household asks. Enough is an AI retirement planner that gives an honest answer. |
| 2 | intro (cut) | Page 1, "How Enough works" open; cursor into the chat box; household typed | This is Enough. I tell it about a couple in plain words, the way I would tell a friend. They are in their fifties, and they want to retire at sixty. |
| 3 | send (fit) | Enter; the guide folds to one line; panel fills; estimate rows | The moment I send it, the guide folds into one line. The panel on the right fills in. Anything I did not say is a typical figure, marked estimate. |
| 4 | early (cut) | Cursor on the enabled "Build my plan" ("Check the figures, then build."); click | I do not have to answer every question. Build my plan works from the first answer, and typical figures fill in the rest. |
| 5 | check (cut) | Check step; yellow guessed rows; cursor on them; click "Looks right, build my plan" | Then Enough asks me to check its guesses. The rows marked estimate are what I left out. They look fair, so I confirm. |
| 6 | team (fit) | Advisers light up; plan arrives | Now the advisers get to work, one part each. Then the lead adviser writes the plan. |
| 7 | answer (cut) | Plan top: verdict, ring, "Short $X a year" | Here is the answer, in one glance. The verdict says not yet. The ring shows how ready they are: {ring0} out of one hundred. And they are short {gap} a year. |
| 8 | ladder (cut) | Cursor over Needs, Wants, Wishes rows | Below is the money ladder. Needs are safe, wants are sure, wishes are open. Needs are paid in {paid} of one hundred market tests. The couple can count on {counton} a year. The wishes are the rest of the goal. |
| 9 | moves (cut) | Scroll to "Your next moves"; cursor on "Closes the gap", then on Try it | Next come the moves. The first one says it closes the gap, so I press Try it. |
| 10 | try (fit) | Click Try it; wait; new tab appears | Enough runs the whole plan again with that one change. |
| 11 | tab (cut) | What If tab: "What changed" line, "Level up" on Wishes, "vs baseline" points, "closes the gap" | The result opens as its own tab. The change is to spend {newgoal} a year, not {goal}. Wishes are covered now, and the page says level up. Readiness rises {delta} points, to {ring1}. That is a trade, and the choice is theirs. |
| 12 | tick (cut) | Back to Baseline tab; tick "Mark as planned" on the closing move; meter | Back on the baseline, I tick the move as planned. The count moves to {done} of {total}, and the progress marks fill. |
| 13 | compare (cut) | Compare table (gap row, goal lasts in) | Compare puts them side by side. Before, they were short {gap} a year, and the goal lasted in {lasts0} of one hundred tests. After, there is no gap, and it lasts in {lasts1}. |
| 14 | rule (fit) | Ask "When can I sign up for Medicare?"; cited answer with Sources | I can also ask a rule question, like when I can sign up for Medicare. The answer comes with its source. |
| 15 | stock (fit) | Ask "Which stock should I buy?"; "We can't help with that." | Ask which stock to buy, and Enough politely declines. It plans. It does not pick stocks. |
| 16 | cost (cut) | Token costs block (This plan $0.00xx) | Every plan shows its token costs. This one used well under a cent. |
| 17 | end (card) | "Not financial advice." | Enough. Can you retire when you want? This is not financial advice. |

Dropped from v2 on purpose: old tiles, "Build with typical numbers" link, header How-it-works button, old What If layout, the pen edit, dark mode, the long analysis walk-through.

## Consistency check (demo/make_demo.py, after `--v3 record`)
- During each scene a snapshot of the visible text is taken every 0.45 s (not sr-only, not folded or hidden, inside the window, not covered by another element; typed text counts).
- Every number the narration says, as digits or words, must be a number in that scene's text; every `{figure}` too; a fit scene's numbers must be in the part played at normal speed.
- Each scene's listed phrases (e.g. "not yet", "level up", "closes the gap", "can't help") must be visible in that scene.
- 15 claims about the page (guide open then folded, Build enabled early, one closing move, level-up marker, cost under one cent, ...) must hold.
- Live figures must equal those the narration was voiced with (figures_v3.json); any mismatch, missing number or phrase prints the list and exits 1.
- The wording on screen is being rewritten: if a phrase check fails afterwards, edit the phrase in SCENES_V3, or the narration if the page changed meaning.

## Steps for the final record (after the backend wording lands)
1. `python demo\make_demo.py --v3 figures`  (about 3 live AI calls; rewrites figures_v3.json)
2. `python demo\make_demo.py --v3 tts`      (nova; only changed segments are made again)
3. `python demo\make_demo.py --v3 record`   (ends with the consistency check)
4. `python demo\make_demo.py --v3 assemble` (writes demo\enough_demo_v3.mp4; v2 file untouched)

## Update 2026-11-22 (final record, new UI)
Scenes now: title, intro, send, edit (state pencil, list opened then Esc), early (Build -> "When would you like to retire?" -> chip 60), check, team, answer
(verdict "Retire at 60? Not yet - short $20,900 a year"), ladder, moves (read only), whatif ("+ What if..." greys the plan; first "Worth trying" chip = the closing move),
run (team panel "Working on", "Re-running your plan with"), tab (level up, 30 points, closes the gap), compare (then back to Baseline), rule, stock, cost, end.
The household no longer says the retirement age in the typed text (the early Build asks it). Dropped: Try it, Mark as planned, tick scene.
Result: enough_demo.mp4 (project root), 167 s, 8.7 MB.
