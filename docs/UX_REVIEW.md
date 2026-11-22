# Enough Lite: independent UX review

Reviewer ran Playwright (Edge, 1280 px and 390 px, header X-Enough-Test: 1) against http://localhost:8020. Total AI spend was about $0.03. Screens are in `docs/screens/ux-*.png`.

Coverage: journeys 1 (doctor: full build, What Ifs, corrections), 2 (widowed teacher, intake), 3 (28-year-old renter, intake), 5 (tap-only), 7 (typos), plus messy input and corrections on both chats. Journeys 4 (couple 55/50), 6 (vague) and 8 (serial corrector) were covered only through the correction and messy-input probes, not as full walks. Individual pencil editors, section Reset and out-of-date plan prompts were not exercised one by one. Treat those as untested.

## Verdict

Not ready. The look is clean, the advisers are charming, the plan page reads well, and the build wait is explained. But the intake chat misreads ordinary input and writes wrong facts into the household, tagged "you said". Corrections, which a worried user leans on, mostly fail. The plan page is better (rule questions with sources, What If comparisons), but one What If chip fails and some numbers disagree. A person could build a plan on a wrong age, job, debt or state without noticing.

## P0

**P0-1. "hi" sets the state to Hawaii.** Intake: "hi" gives "I noted that you live in Hawaii". Plan page: "hi" gives "Change your state to HI and rebuild your plan?". Screen: ux-jB-chat.png. Cause: "hi" is read as the postal code HI. Fix: match state codes only when upper-case or after "in"/"from"; answer a greeting with a greeting plus the pending question.

**P0-2. Corrections are mangled in the intake chat.** Screen: ux-j1-c.png.
- "I'm 40... actually 45" sets age 40.
- "no, make it 65" sets the job to "no, make it 65" (the pending question was the children's ages).
- "actually 2 kids, not 3" works, but silently replaces the stated ages 12, 9 and 5 with 6 and 9 (tagged assumed).
- "change the split" gets "That answers a different question, so I did not change anything", which fails the correction.
Fix: treat "actually/no/make it" as a replacement of the last fact. Never let free text fill a text slot (job) unless the question asked for it. Keep stated ages when the count changes.

**P0-3. Facts lost or miscopied from one message; typos not tolerated.** Screen: ux-j1-a.png.
- "I'm a doctor, 44, ..." leaves age missing; the bot asks "How old are you and your wife?".
- "3 kids aged 12, 9 and 5" is read as 4 children.
- Journey 3, "28, I rent in Austin... making 62k, 45k in student loans at 7%, 8k saved": age, pay and job lost, and the loan becomes $8,000 (the savings figure).
- Journey 7, "4o yrs", "6o": age and retirement age lost; the panel shows "2 children (, )".
- "my wife stays at home" is dropped (only "stay-at-home" sticks).
Fix: parse per fact, show what was captured as chips the user can fix, ask only for what is missing.

**P0-4. A question or an unrelated answer rewrites a saved figure.**
- "what's a Roth?" during intake gives "Sure, let's change your savings" and re-asks savings, abandoning the pending split question. In journey 3, the next message "I spend about 3k a month" was taken as savings of $36,000 and retirement spending of $36,000.
- "no mortgage, we rent" became "you own your home" (first doctor pass). "I own it with a mortgage" is recorded as "own your home".
- The plan page answers "what is a Roth?" well, so the capability exists. Intake should reuse it ("A Roth is... Back to your question: ...").
Fix: classify question vs answer first, answer questions in place, never reopen a figure unless the user says "change".

**P0-5. "Markets fall 30%" chip fails.** Plan page, Worth trying: clicking it gives "I am not sure what you want to do with that" (reproduced in two sessions; ux-jA-whatif2.png, ux-jB-whatif.png). "Another child" and typed "retire at 62" work. Fix: map every chip to a What If and add a test that clicks each chip.

**P0-6. Plan-page pay correction ignores the figure.** "my pay is wrong, it's $150,000" gives "What is your pay now?" with the $150,000 dropped; then "yes" gives "I did not catch a figure". Screen: ux-jA-pay.png. Use the amount in the first message, then confirm. By contrast "actually 2 kids, not 3" reaches a proper confirm step ("Yes, rebuild / No").

## P1

- **P1-1. Example chip fills silent facts.** Tapping "a doctor with 3 kids and 2 dogs" sets ages 45 and 43, retire at 62, Connecticut and a partner, all tagged "you said"; the job "doctor" is lost and asked again. Screen: ux-j5-a.png. Show the example as editable text, or tag the values assumed.
- **P1-2. Wrong "you said" tags.** "Spending in retirement $168,000" is tagged "you said" though the user never gave it, and the chat offers no way to adjust it. The tap-only path does offer "Same as now / Less / A set figure"; the typed path should too.
- **P1-3. Panel "Costs now" wrong or inconsistent.** Tap-only: user said $72,000 a year now; the panel's "Costs now" shows $57,600 (the retirement figure). Journey 2 shows "Short each year $42,000" while a $28,800 pension and Social Security exist.
- **P1-4. Numbers disagree on the plan page.** Doctor plan: goal $168,000, "costs in retirement about $211,318", basics $86,100, "safe $67,600" while Social Security alone is $81,900. The What If table says "You can count on $0 a year" under Your plan; the headline says $67,600. Explain or reconcile each figure (ux-j1-plan.png).
- **P1-5. Action order.** Action 1 is a $1,400 emergency-fund gap while the plan misses its goal by $100,400 a year. Lead with the largest gap. The "Retire at 60" chip is offered when the plan already says 60.
- **P1-6. Widowed teacher.** Pay was never asked (set to $0 while still working); "retired teacher soon" became the job "teacher soon"; widowhood and survivor benefits are not mentioned.
- **P1-7. "Not added, using typical" shows no figure** for six groups. Show the figure used.
- **P1-8. Build wait varies.** First doctor plan took about 90 s; one rerun over 200 s; others 14 s. The wait is explained ("5 of 7 advisers finished"), which is good, but give an estimate.

## P2

- Quick-reply ages (35/45/55/65) invite taps on figures that are not the user's; offer ranges or a typed box.
- Off-topic reply ("weather in Paris") says the plan page can answer it later; say plainly that Enough only covers retirement.
- "Change my answers" opens a long transcript with the household behind a "Your numbers" toggle that is easy to miss. No out-of-date plan prompt was seen after edits; verify.
- The sticky chat bar overlaps content in full-page captures (ux-j1-plan.png).
- Palette is teal on light grey, not the project's black-and-pink default.

## What works

- Clear promise and three-step header; plan headline, needs/wants/wishes cards and "Three things to do" read plainly.
- What If "retire at 62" gives a before/after table with deltas, "Back to my plan" and a history list.
- Rule questions ("what is a Roth?") on the plan page get a plain answer with IRS sources and cost shown.
- Wait states are explained (per-adviser status); AI cost meter shows $0.002 to $0.004 a plan.
- Family moments and the costs timeline (college 2032-2042, children's costs end, Medicare at 65, health costs at 85) are sensible for the doctor.
- Plan-page confirm step ("Change the number of children to 2 and rebuild? Yes / No").
- No sideways scroll at 390 px (scrollWidth 390); no console errors in the runs.
