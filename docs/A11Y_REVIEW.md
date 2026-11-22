# Accessibility and visual-polish review: Enough Lite

Scope: the React frontend in `web/src`, run live on http://localhost:8020 (test mode) in Microsoft Edge with Playwright.
Tool: axe-core (npm `axe-core`, dev dependency), all default rules including best practice, run on seven states at 1280 px and 390 px.
States: page 1 empty, page 1 midway, page 1 with an inline editor open, the phone "Your numbers" sheet (390 only), the plan while the advisers work, the finished plan with the team panel, and a What If view.
Live cost of the audit: a few plans at about $0.002 each, well under the $0.05 cap.

## 1. Automated results

Before (counts are failing nodes):

| Impact | Rule | Where | Nodes |
|---|---|---|---|
| serious | nested-interactive | The section headers on page 1 (`<summary>` held the Reset and pen buttons). 1280 and 390 sheet | 9 |
| serious | scrollable-region-focusable | The chat log on page 1 could scroll but not take focus | 1 |
| serious | listitem | Team talk: `<ol role="log">` made its items orphans. Plan screen, both widths | 9 to 12 |
| serious | label-content-name-mismatch | The one-line plan bar on a What If: label "Show my plan again" hid the visible words | 1 |
| moderate | heading-order | What If view: `h4` straight after `h2` | 1 |
| minor | aria-allowed-role | Team talk `role="log"` on an `ol` | 1 |

Page 1 empty: no violations. Finished plan at 390: none. 

After: **0 violations in every state at 1280 and 390** (serious 0, moderate 0, minor 0). Screenshots: `docs/screens/a11y-before-*` and `a11y-after-*`.

## 2. Manual checks

| Check | Before | After |
|---|---|---|
| Keyboard, whole flow | Tab order is logical and every control shows a 3 px teal ring. Gaps: the phone sheet let Tab leave it (escaped after 27 presses), Esc worked only when focus sat inside it, and closing it dropped focus to the page. Closing an editor (Esc, Save, Cancel) dropped focus to the page. Typing fields showed only a faint 20% halo. | Sheet keeps Tab inside, Esc closes it from anywhere, focus returns to "Your numbers". Closing an editor returns focus to its pen. Esc inside an editor in the sheet closes only the editor. Text fields use the same solid teal ring. The chat log is now a tab stop (it scrolls). |
| Enter and Esc on editors and chips | Enter opens an editor and focuses its first field; Enter on a chip sends it; Esc closes the editor. | Same, plus the focus return above. |
| Portraits | Decorative SVG (`aria-hidden`); each button is named "Name, finished/working/waiting. Role." | Same. Fixed a stray ": " that was read aloud before the status. |
| Chips and buttons | All are real buttons with names; pressed and expanded states are set. | Same. |
| Charts | Savings chart was labelled by its title only. Costs chart had a full sentence. Both have a table or text version. | Savings chart now carries a spoken summary: start, retirement, peak, end and range. "See the numbers" table stays. The household picture was read twice (image label plus caption); the image is now hidden and the caption carries the text. |
| Live regions | Chat log `aria-live`, team status `role="status"`, "Working now" status, tool and What If updates `role="status"`, errors `role="alert"`. | Same; the chat log is now a named `role="log"`. |
| Colour contrast | Measured every visible text node against its real background, with opacity (all states at 1280 and 390). | **0 failures.** Lowest ratios: 4.90 (idle adviser badge, 11.7 px, needs 4.5), 4.94 (large score), 4.97 ("basics same"), 5.2 to 5.5 for the muted and footer text. The adviser badge text grew from 10.8 to 11.7 px. |
| Touch targets (390) | Start over 34, chips 36, pens 34, small buttons 34, Reset 26, Send 40, ask box 43, step link 17 px tall. | All 44 px or more. Reset and "Change my answers" keep their look and get a larger invisible hit area. Measured: no interactive element under 44 px at 390. |
| Reduced motion | CSS shortened animations, but scrolling was always smooth. | Smooth scrolling also turns off (`scrollBehavior()`). Measured with reduced motion on: 0 running animations while the advisers work. |
| Zoom 200% and reflow | n/a | 1280 px at 200% is a 640 px layout; at 400% it is 320 px. At 640, 320 and 390: no horizontal scroll, no element past the right edge. |

## 3. Visual polish

Looked at every screenshot. Spacing, type scale (eyebrow 11 to 12 px, body 15 px, headline 18 px, score 30 px) and alignment are consistent. Things checked:

- No orphaned headings; heading order is now h1, h2, h3 everywhere.
- Empty, working and error states: the plan placeholder has a progress bar and the wait text; errors give "Try again". They look intentional.
- Chart labels are 11.5 px and readable at both widths; ticks thin out on phone.
- At 1280 px the team panel (340 px) sits beside the plan without crowding it; the plan text keeps a 75-character line.
- At 390 px nothing is cut off. The chip rows scroll sideways on purpose.
- Fixed: on a phone the "Worth trying" label wrapped to two lines in the ask bar; it now stays on one line.

## 4. Fixes (all in `web/src`)

1. `LivePanel.tsx`: section headers are a toggle button with sibling Reset and pen buttons (was `<details>`/`<summary>` with buttons inside). Editor close returns focus to the pen.
2. `IntakeScreen.tsx`: phone sheet focus trap, document-level Esc, focus return, `aria-haspopup`; the chat log is a labelled, focusable `role="log"`.
3. `FieldEditor.tsx`: Esc inside an editor stops there.
4. `TeamPanel.tsx`: Team talk is a `div role="log"` around a plain `ol`; no stray colon in the adviser label.
5. `TeamScreen.tsx`: removed the misleading `aria-label` on the plan bar; smooth scroll respects reduced motion.
6. `WhatIf.tsx`: `h4` to `h3`.
7. `SavingsChart.tsx`: spoken chart summary (`chartSummary`).
8. `Household.tsx`: picture hidden from screen readers (caption has the text).
9. `format.ts`, `App.tsx`, `AskBox.tsx`: `scrollBehavior()`.
10. `styles.css`: toggle styles, solid focus rings on text fields, 44 px touch targets on phones and coarse pointers, larger badge text, one-line "Worth trying" label.

Not touched: `app`. The team panel and plan card were re-read before editing; only the small changes above were made.

## 5. Tests

New `src/a11y.test.tsx` (8 tests): section toggles hold no nested controls; Esc closes an editor and returns focus to its pen; the phone sheet traps Tab, closes on Esc from anywhere and returns focus; Esc in a sheet editor leaves the sheet open; Team talk and chat log are labelled focusable logs around real lists; the chart summary text; What If heading order and the hidden household picture; reduced-motion scrolling. One existing test (`v4.test.tsx`) was moved from `<details open>` to `aria-expanded`.

Result: `tsc --noEmit` clean, vitest 71 of 71 pass, `npm run build` done (dist is current and served by 8020).

## 6. Left as is

- The chat log is now one extra Tab stop on page 1. It is needed so a keyboard user can scroll long chats.
- The savings chart tooltip works by pointer only; the table under "See the numbers" and the spoken summary give the same figures to the keyboard.
- The last 1280 axe run came before two later edits (Esc in an editor stops there; phone-only CSS). Both were covered by tests and the 390 run, not by a second 1280 run.
