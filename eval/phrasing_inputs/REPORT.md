# Different words for the same input

People describe the same fact in many ways: "my partner is actually a man", "I teach high school", "half a million saved", "$45 an hour", "we're in the Bay Area". This check sends 161 such messages to the live intake chat (Claude Haiku 5.5, after a short starting conversation) and checks that the right field gets the right value. When the app asks "Change X from A to B?", the probe answers Yes, as a person would.

Run it: `python eval/phrasing_inputs/probe.py` against the app on :8020 (ENOUGH_TEST_MODE=1). Results go to `results.json`.

| | Right |
|---|---|
| Before (first 112 phrasings) | 89 / 112 (79%) |
| After the fixes, first 112 | 112 / 112 |
| After the fixes, all 161 (49 harder ones added) | 161 / 161, on two separate runs |

## What was wrong

1. **The check on the model's reading was too literal.** The model often read the message right, but the guard dropped it:
   - "born in 1968" (no age written);
   - "half a million" (no digits);
   - "out of work by 60" (not on the list of retirement words);
   - "so-so" health, "low" or "aggressive" risk (not the exact allowed words);
   - "high school teacher" from "I teach high school";
   - the partner's sex (not on its list of fields at all).
2. **A leftover figure became the answer to the next question.** "I was born in 1968", "$3k in medical bills" and "we're renters, $1,800/mo" were each stored as the **partner's pay** ($1,968, $3,000, $21,600).
3. **Other misreadings:**
   - "make my retirement age 67" was read as the person's age and a child's age;
   - "$45 an hour" was stored as $45 a year;
   - "my spouse is male" changed the person's own sex;
   - medical bills and a "car note ... left" lost their amounts.
4. **Assumed a traditional couple.** Only "wife" and "husband" set the partner's sex, and the app called the partner "your wife" or "your husband" based on that.

## What changed

- **Any partner word works,** in any kind of couple: partner, spouse, wife, husband, boyfriend, girlfriend, fiancé(e), significant other.
  - "My partner is a man", "married to a woman" and "my partner is nonbinary" set the partner's life table. Nonbinary gives the average of the two tables.
  - Questions say "your partner".
  - Explicit words beat a contradicting model reading.
  - "My partner passed away", "we split up" and "my ex" mean planning for one person.
- **The model's instructions now list the allowed answers** for risk, health, sex and state, with everyday examples.
- **The guard maps everyday words to those answers:** "risk averse" is careful; "comfortable with ups and downs" is growth; "so-so" is fair; "healthy" is good.
- **Figures and ages written in other ways are worked out by the app itself, not taken from the model's arithmetic:**
  - birth years become ages;
  - "half a million" and "a quarter million" become numbers;
  - hourly pay becomes a year's pay: 2,080 hours full time, 1,040 part time.
  - A yearly pay under $1,000 is never stored.
- **A figure answers a money question only when its words fit that question.** Words about rent, birth, bills, loans and so on keep it away.
- **City and region names give a state,** for example the Bay Area, Jersey, Philly and the Twin Cities.

Tests: `tests/test_partner_sex.py`, `tests/test_input_phrasing.py`.

## Not covered

- **Take-home versus gross pay:** "I bring home $6,000 a month" is stored as stated.
- **The panel's partner-sex menu** offers only Male and Female. "Not given" is available through the chat.
