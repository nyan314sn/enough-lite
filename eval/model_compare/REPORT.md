# Model comparison: Claude Haiku 5.5 vs gpt-6-luna

Run 2026-11-22. Raw data in this folder: `raw/`, `results_plans.json`, `results_pairs.json`, `results_qa_sims.json`, `cost_log.jsonl`.

## Method

- **Setup:** two private copies of the app, same code, test mode: port 8041 (`ENOUGH_PROVIDER=anthropic`, claude-haiku-5-5) and port 8042 (`ENOUGH_PROVIDER=openai`, gpt-6-luna). Code as of about 11:33 on 2026-11-22, so the What If reader tested is the version before the phrasing work (`eval/whatif_phrasing/`).
- **Plans:** 80 households (`selection.json`), seed 409: 48 stratified from `eval/cases.jsonl`, 17 edge cases, and the 15 admin samples. Tiers from the plan: struggling = basics paid in under 90 of 100 (31 plans); average = count-on under 90% of the goal (21); comfortable = the rest (28).
- **Plan text:** 40 blind pairs, A/B order random; judge claude-sonnet-5-5 (a third model).
- **Intake:** 24 simulated users (20 personas + 4 hard) through `simusers`; simulator and judge are Haiku in both arms; conversations are not identical across arms.
- **Questions:** 57 messages on 5 households' plans (12 rule questions, 8 plan questions, 20 What Ifs, 5 corrections, 10 refusals, 2 off-topic). Correct = the right reply kind and the judge says correct.
- **Safety:** the 74-attack kit.

## Results

| Metric | Haiku 5.5 | gpt-6-luna | n | Winner |
|---|---|---|---|---|
| Plan numbers identical across models | yes | yes | 80 | Tie (no differing figure) |
| Plans finished without error | 80 | 80 | 80 | Tie |
| Adviser text replaced by a template | 16 (20%) | 41 (51%) | 80 | **Haiku** |
| Plans with any agent on a template | 35 | 50 | 80 | Haiku |
| Jargon hits | 0 | 2 | 80 | Haiku (small) |
| Plan time, median / p90 / slowest | 11.0 / 36.4 / 69.2 s | 22.1 / 34.5 / 72.1 s | 80 | **Haiku** (2x faster at the median) |
| Template fallbacks, struggling tier | 16 of 31 | 25 of 31 | 31 | Haiku |
| Tokens per plan (input / cached / output) | 128 / 14,043 / 1,833 | 2,525 / 1,700 / 1,383 | 80 | Haiku caches far more |
| $ per plan (app prices) | $0.00229 | $0.00159 | 80 | gpt-6-luna (but see note) |
| Text quality, blind judge, overall | 11 wins | 15 wins (14 ties) | 40 | Tie |
| Text quality, both wrote AI text | 9 wins | 8 wins | 18 | Tie |
| Plain words / actionable / honest about shortfall | 7 / 11 / 2 | 9 / 13 / 2 | 40 | Tie |
| Intake: reached a plan | 22/24 | 22/24 | 24 | Tie |
| Intake: profile fields correct | 93.6% | 92.3% | 311 fields | Tie |
| Intake: wrong fields the person never gave | 11 | 17 | 311 | Haiku (small) |
| Questions and What Ifs handled correctly | 25/57 | 22/57 | 57 | Tie (misses are mostly the app's rules, same in both) |
| Refusals | 7/10 | 7/10 | 10 | Tie (refusals run in code before the model) |
| Attack kit | 74/74 | 74/74 | 74 | Tie (after an idle rerun of two load timeouts) |

**Dollar note.** gpt-6-luna looks cheaper partly because 51% of its plans fell back to free templates. Counting only plans where the AI wrote the adviser text: $0.00187 against $0.00243 for Haiku.

## Cost and speed per user

App prices (`llm.PRICES`; the gpt-6-luna price comes from the old app and may not be current). A user = 4 plans + 3 What Ifs a month; intake adds about $0.003–0.005 per user.

| | Per plan | Per user per month | 100 users | 10,000 users |
|---|---|---|---|---|
| Haiku 5.5 | $0.0023 | $0.014 | $1.43 | $143 |
| gpt-6-luna | $0.0016 | $0.010 | $1.00 | $100 |

Cost is small for both; speed decides. A What If took about 12 s on Haiku and 17–27 s on gpt-6-luna on an idle machine (small n).

## Examples

1. **Retired couple, 71 and 68.** Both: $111,300 a year. Haiku adds "set aside about $10,000 a year for health before Medicare at 65", which does not fit a couple past 65; gpt-6-luna writes "plan for a long retirement". Judge preferred gpt-6-luna.
2. **$2,700 card debt at 21%.** Both give $569 a year of interest. Haiku says health before Medicare is $10,800; gpt-6-luna says $10,000.
3. **$0 life cover.** Both write the same "$410,000 gap" action; gpt-6-luna also says "draw on taxable savings first", which the household cannot do.
4. **Speed.** For a couple of 60 and 59, Haiku wrote the adviser text in 5 s; gpt-6-luna's helpers took 8–12 s, the adviser was left too little of the 24 s plan limit, and the plan used the template. This is the pattern behind most gpt-6-luna fallbacks.
5. **Intake.** A person gave four exact savings amounts; gpt-6-luna invented a percentage split (judged a serious misunderstanding). Haiku's worst case stored a whole-life policy the person never mentioned.

## Caveats

- Small samples: 80 plans, 40 pairs (28 real comparisons), 24 users, 57 messages. A gap of 2–3 wins is noise.
- The judge (Sonnet) is a third model but from Anthropic, so it may lean to Claude's style; its "numbers right" calls are weak.
- Both models ran at once on one machine; question and attack timeouts were a load effect.
- The app's time caps (24 s a plan, 12 s a specialist) turn slow replies into templates; gpt-6-luna might do better with looser caps (not tested).
- One run per condition; test mode.

## Recommendation

**Use Claude Haiku 5.5 as the default.** Plan numbers are identical, the writing is about as good (a blind judge could not separate the two where both wrote AI text), safety is the same, and Haiku is twice as fast with far fewer template fallbacks (20% against 51%) and much better prompt caching.

**gpt-6-luna is fine as the staff fallback:** cheaper per plan at list price, equal on the attack kit and intake accuracy; the cost is slower plans and more template wording.

**Cost of this comparison:** about $2.60 (judge $1.11 plus $0.63 on a discarded first judge run; plans $0.31; simulated users about $0.45; questions and attacks about $0.10).
