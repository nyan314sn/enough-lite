# Loop round 3, audit B: UI/UX (strict)

Independent auditor (Sonnet), 2026-11-21. Own backend on :8072 serving `web/dist`. Playwright (Edge) at 1440, 820 and 390; about 17 journeys. Axe found 0 violations; no sideways scroll. AI cost under $0.10. Scripts and screenshots are in this folder.

**Counts: P0 1, P1 6, P2 9.** Round 2: P0 1, P1 9, P2 10. Round 1: P0 4, P1 11, P2 11.

## P0
1. **The saving questions reject their own answers (a dead end).** Reached from "Add saving" or the pencil on Yearly saving. The chip "$10,000 a year", "$30,000 a year", "12000" and "$20,000" all get "I didn't catch that", then "I still need this one to go on". "10% of pay" is read as a change of pay. The pencil sits on the Yearly saving total ($28,981) but asks only about the 401(k) share. (`yearly_editor4.png`, `sav5.out`)

## P1
1. **"I don't know" or "skip" on the age question loops forever.** Only the age chips get out. (`idk2.out`)
2. **Skipped inputs leave a field blank (rule R1).**
   - Mortgage "Not sure, estimate it" gives a payment of $2,270 but no balance or rate, the reply names no number, and the header says "Not added, using typical".
   - Pension "Not sure, leave it out" replies "I will use a typical figure", yet no number appears.
   - "Skip, use typical" leaves Pensions, Insurance, Goals, Health and Costs detail with no figure, while the plan still uses typical values.
   - Chips that work: spending now, pay, Social Security, and the retirement-spending confirm.
3. **A confirmed mortgage payment of $12,500 a month gives retirement spending of "$-34,500 a year".** Retyping the same figure is refused. (`mort2.out`)
4. **A stated pension start age is ignored.** "David will get a teacher pension of about $2,500 a month at 60" shows as "Partner: $30,000 a year from 65 (assumed)", and the reply names the wrong person. (`long.out`)
5. **"Where did $X come from?" gives a non-answer.** Savings of $640,000 and $420,000 and a payment of $1,900 get "I can't trace $X". "Where did my Social Security come from?" lists unrelated items. (`nurse.out`)
6. **The headline adds a hard sentence about Social Security** ("less than your Social Security of $38,300 ... because of income tax on it, health costs ..."). It is jargon-heavy and compares a safe amount with gross Social Security. (`bus_plan.png`)

## P2
1. The panel's Social Security (at 67) and the plan's (at 69 or 70) still differ without a word in the panel or headline.
2. The "similar households" note is absurd for the widow: "a single person aged 62, still working, with about $4,350,000 saved".
3. Retiring earlier raises count-on (Maria and David: retire at 60 gives $148,800 against $137,300 at 62). Possible engine issue.
4. "asdf" gets a long plan summary, while "tell me a joke" gets a short reply.
5. Stale or odd labels:
   - the private-college row still says "Assumed public college";
   - "What is the monthly payment? What is the monthly mortgage payment?";
   - "Costs a year: assumed" next to "Spending now: you said";
   - the partner's retirement age is assumed to be 72 for a 55-year-old;
   - "about $4,319,000 is left at the end for wishes".
6. A "Worth trying" chip ("Make your basics safe first") runs "Retire at 70", shows "You asked: Retire at 70", and adds a duplicate What If chip.
7. A What If that matches the current plan (retire at 62 when the plan already does) is not flagged. "(your plan: 0)" lacks "of 100".
8. The pencil on a panel row during a pending confirm gives "That answers a different question".
9. At 820 the step buttons wrap unevenly and overlap.

## Fixed since round 2 (verified)
- **Fixed:** spend-less What Ifs; starting points (now one helpful, clickable point); retire chips for retirees; yearly saving and costs now agree; bare "62"; Start over; the invented loan; "skip" on the split question; the crypto reply; the second dog; the widow reply.
- **Partly fixed:** Social Security panel vs plan; the mortgage sanity check; Assumptions ordering; odd copy; first-reply length; the stepper at 820.
