# Readability of the backend's words (R26)

2026-11-22, after the real-user feedback ("too complex; a high-school graduate must be able to use it").

**Measure.** Flesch-Kincaid grade with a simple syllable heuristic (no packages); a number such as $53,400 counts as one two-syllable word. Script: `eval/readability/measure.py`. Texts: every prose string of six words or more in `app/`; tools-only plans for the 15 admin samples; three What If replies each; four example intake chats; eleven plan-chat questions. Live AI text: `live_sample.py`, 5 plans, old and new code side by side.

## Code-built text: before → after

| Text type | Grade | Words/sentence | Longest sentence |
|---|---|---|---|
| Headline | 5.1 → 3.5 | 14.8 → 11.7 | 22 → 13 |
| Needs/wants/wishes lines | 5.6 → 3.2 | 12.3 → 9.7 | 22 → 17 |
| Action title | 2.8 → 2.6 | 7.1 → 6.8 | 9 → 8 |
| Action line | 4.6 → 3.0 | 11.5 → 7.8 | 27 → 13 |
| Analysis lines | 7.1 → 5.5 | 13.2 → 9.2 | 28 → 18 |
| Assumptions | 7.5 → 5.1 | 15.0 → 9.0 | 35 → 17 |
| What If replies | 12.0 → 4.7 | 26.0 → 13.8 | 39 → 23 |
| Intake replies | 3.9 → 3.0 | 10.5 → 9.0 | 60 → 19 |
| Templates in `app/` | 4.0 → 3.5 | 10.1 → 9.1 | 38 → 28 |
| **All text pooled** | **6.1 → 4.2** | **13.3 → 9.6** | **60 → 32** |

**Live AI text** (5 plans): specialist headlines grade 7.0 → 5.1 (longest 27 → 18 words); specialist details 6.9 → 5.7 (25 → 19); adviser lines 6.3 → 3.7 (29 → 16). No plan fell back to the template.

Still over 20 words: the What If head that names the change in full (23 words). Plan-chat answers that quote an official passage word for word stay near grade 12 (the source's own text, by design).

## What changed (no calculation changed)

- **One vocabulary:** needs, wants, wishes; "market tests" for the simulated futures; no "basics" or "scenarios" in plan text (JSON keys unchanged).
- **AI instructions:** reading grade 8, sentences of 15 words or fewer (20 at most), most important fact first, a word budget; the number check is untouched.
- **What If replies:** "you can count on $X a year, up from $Y" instead of "(baseline plan: …)" chains.
- **Headline:** one short first sentence; the reason moved to a separate field, `headline_why`, shown folded.
- **Actions:** titles of 8 words or fewer with a one-line reason. **Assumptions** rewritten in short sentences. **Intake replies:** "Got it: …" with the main facts.

## Five examples

1. **Headline.** Before: "You can count on $67,700 a year: $39,900 for basics and $27,800 for the rest. That is less than your Social Security of $78,900 a year (starting at 69 for each of you in this plan). That is because your savings must pay for the years before it starts and health costs come on top of your spending." After: "You can count on $67,700 a year: $39,900 for needs, $27,800 for wants. That is less than your Social Security of $78,900 a year. It starts at 69 for each of you in this plan."
2. **What If reply** (grade 14, 67 words → grade 5). Before: "If you save $6,000 more a year and spend that much less now (about $96,634 a year saved in all, 31% of pay), you can count on $115,200 a year, safe in 90 of 100 scenarios (baseline plan: $111,600). Your basics are paid in 100 of 100 scenarios (baseline plan: 100 of 100), and your spending goal lasts in 96 of 100 (baseline plan: 94 of 100)." After: "If you save $6,000 more a year and spend that much less now, you can count on $115,200 a year, up from $111,600. Your goal lasts in 96 of 100 market tests, up from 94. That makes about $96,634 a year saved in all, 31% of pay."
3. **Intake reply** (one 60-word sentence → none over 19 words): "Got it. I noted 10 facts from your message. Check them in the panel on the right. The main ones: you are 45, your pay is $310,000 a year and you want to retire at 62. … I filled in 8 more with typical figures. Each is marked in the panel, so you can change it."
4. **Action.** Before: "Your goal is about $7,700 a year above what lasts in 90 of 100 scenarios, $91,300 a year. Start there and raise it as savings grow." After: "You are $7,700 a year over the safe $91,300. Raise your goal as savings grow."
5. **Analysis line.** Before: "In half of the scenarios you could spend $115,300 a year. To be sure in 90 of 100 it is $91,300, and in 95 of 100, $86,400." After: "In half of the market tests you could spend $115,300 a year. To be sure in 90 of 100, spend $91,300. For 95 of 100, spend $86,400."

Tests: `tests/test_readability.py` keeps it this way (grade and sentence-length caps on templates and on tools-only plans). Full suite 1,424 passed, 2 skipped.
