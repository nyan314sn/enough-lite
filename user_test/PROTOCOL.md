# Enough Lite: real-user test guide

One page. One person, about 25 minutes (task about 10, form about 5). You are the note-taker, not the guide.

## Before they arrive
1. Start the app (`python run.py`). Open http://localhost:8020 and check it loads.
2. Open `FEEDBACK_FORM.html` in a second browser tab. Do not show it yet.
3. Copy the blank session block in `SESSION_LOG.md`. Give the session an ID (S1, S2).
4. Have a stopwatch ready (a phone is fine).

## Consent (read aloud)
"I am testing a retirement-planning app for a class project. I am testing the app, not you. You do not need to give a real name, account number or any private detail. Use rough or made-up figures if you like. I will time you and write notes. If you agree, I will record the screen only. I will keep your words without your name. You can stop at any time and I will delete your notes. Is that all right?"

Record yes or no for the recording. If no, take notes only.

## The task (read aloud, then say nothing)
"Find out whether you could retire when you would like, and what to do first. Think aloud as you go."

## What to time
- **Time to first plan.** Start the stopwatch when they first touch the keyboard or mouse in the app. Stop it when a plan with a verdict is on screen.
- **Time to one What If.** Ask them to try one change (retire later, spend less, save more). Start when you ask. Stop when they have read the new result.

Write the times in minutes. If they give up, write the time and "gave up".

## Baseline: how it is done today
After the task, the form (section D) also asks for this in writing. Ask aloud and note it in the log:
1. "Before today, how would you have answered this question? A spreadsheet, an adviser, an online calculator, a guess, or not at all?"
2. "How long would that take you, start to finish?"
3. "What would it cost you, in money?"

Write their words and their own estimates. Do not correct them. These are guesses, and the report must say so. For your own context, not to be told to them: the research file puts a human plan at about $2,926 flat and roughly 10 to 15 hours of adviser work. Both figures are rough.

## What to note
- Where they paused for more than five seconds.
- What they misread or asked about.
- What they said aloud, word for word where you can. Mark good quotes.
- Anything that broke.
- What they did that you did not expect.

## Do-not-help rules
- Do not explain a screen, a word or a button.
- Do not point, and do not say "try the button on the left".
- Do not answer "what does this mean?" Say: "What do you think it means?"
- If they are stuck for two full minutes, say "What would you do next if I were not here?" If still stuck, mark it "stuck", note the screen, and tell them what to click. Let the clock run.
- Do not defend the app, and do not say it is "still rough".
- Do not enter their figures for them.

## Comprehension check (before they can scroll back)
When the plan is on screen and they have tried a What If, ask these three aloud, then have them look away or minimise the plan:
1. "Can you retire at the age you wanted?"
2. "How much are you short or ahead each year?"
3. "What is the first thing you would do?"
Write their words in the log. Then check each against the screen and mark it right, partly or wrong. (Section C of the form asks the same three in writing, from memory: tell them not to scroll back.)

## After
1. Give them the laptop with `FEEDBACK_FORM.html` (about 5 minutes). Look away while they fill it in. They enter the session ID (S1, S2, ...). If they tick the screenshot box, take a screenshot of their plan with no personal details.
2. They press Save. A JSON file downloads. Move it into `user_test/responses/`.
3. Fill in the session block in `SESSION_LOG.md` within the hour, while you remember.
4. Run `python user_test/impact_summary.py` (use the conda Python). Paste the output into the report's Impact section.

## Say these limits in the report
One or two people is an anecdote, not a sample. The tester may be a friend and may be polite. Baseline times are their own guesses.
