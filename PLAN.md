# Enough Lite: the class submission (MGT 409 final project, due Mon Nov 23 2026, 11:59 PM)

Brief: "Build an AI agent app that does something useful for real people. Then show how it works, what it costs, and how you kept it safe."
Full brief: ../../Homework - Instructions/final_project.md (the course's Homework - Instructions folder).

## The person and the job
"Can I retire when I want, and what should I do first?" For one real household, in plain words, in a few minutes.

## Hard constraints (from the brief)
- Staff run it from a fresh clone in under 10 minutes: `pip install -r requirements.txt` then one command. No npm on their machine: the React build (web/dist) is committed.
- Model (decided by the user 2026-11-20): Anthropic Claude Haiku 5.5 (`claude-haiku-5-5`) with `ANTHROPIC_API_KEY`, through PydanticAI's Anthropic model (`pydantic-ai-slim[anthropic]`). No Portkey. The model name sits in ONE place, settable by `ANTHROPIC_MODEL`. This departs from the brief's course default (Portkey gpt-6-luna); the brief says an app needing another key should be put online, so the app is built deploy-ready (PORT from env, budget caps, per-IP rate limit) and the report says so.
- `.env` is read from the app's own folder and one level up. `.env.example` has names only. Never print or commit keys.
- Small, focused dependencies. No use of the old full app's `engine/` or `backend/` code: lite has its own small tools. Data files may be copied in (small, with sources).
- Black-and-pink style (near-black background, bright pink accents, light text), responsive, accessible, clear loading and error states.
- Plain English everywhere (short words, active voice, no jargon).

## Layout
```
hw-Final-2/   (the project root)
  app/                  FastAPI backend + PydanticAI agents (Python)
    main.py             FastAPI app; serves web/dist at /; API under /api
    config.py           settings, .env loading (own folder, then one up), model name
    llm.py              model factory (portkey default, anthropic dev switch), usage + cost meter, budget cap
    agents/             intake.py, longevity.py, markets.py, family.py, tax.py, research.py, adviser.py (lead)
    tools/              pure-Python tools the agents call (no LLM): lifetable.py, simulate.py, family_costs.py, tax.py, sources.py, neighbors.py
    data/               small data files with sources (life table, family/pet costs, tax brackets, source passages, households library)
    safety.py           input sanitizing, prompt-injection guard, number check
  web/                  React + Vite + TypeScript frontend; built to web/dist (committed)
  tests/                pytest
  run.py                one command: `python run.py` -> http://localhost:8020
  requirements.txt, .env.example, README.md
```

## API contract (backend and frontend build against this)
- `GET /api/health` -> `{status, provider, model, ai_available}`
- `POST /api/intake` `{text, profile_so_far, reset?:[section|"all"]}` -> `{profile, fields:[{key,label,section,value,display,source:"you said"|"estimate"|"assumed",note,editable}], missing:[key], question:{text, quick_answers:[str]}|null, reply, ready}`
  Stateless: the profile travels with every request. `reset` clears sections first ("Household", "Work & pay", "Saving", "Home & debts", "Pensions & income", "Insurance", "Goals", "Health", "Costs", or "all"); a section the page simply removes from `profile_so_far` counts as empty. `missing` lists only the essentials, in this order: age, partner_age, state, pay_per_year (only when there is no job), savings, children (ages), home, retire_age, spending_now_per_year. The plan can be built without anything else.
  **Empty state (2026-11-21):** `sections_status:[{section, status:"added"|"default"}]` lists all nine sections. `added` means at least one field in it is the person's own word (`source:"you said"`); `default` means nothing there is theirs yet, so the panel can show "Not added, using typical". Fields of optional groups the person has not touched (debts, pension, saving detail, insurance, goals, health and sex, costs detail: budget, emergency fund, part-time work, inheritance) come back with `source:"default"` instead of "assumed"; "Skip, use typical" leaves them `default`; a plain "No pension" makes that field "you said". `source` therefore has four values: "you said", "estimate", "assumed", "default". Every field has a non-empty plain `display` (pension: "You: $24,000 a year from 65, rises with prices"; home: "Own, $100,000 left on the mortgage, $1,500 a month, value not given"; `value.value` is null when the home value is not given).
  **Pending question** (2026-11-21): the message is first judged against the question just asked (`profile.asking`). It answers it only when it holds a figure of that question's kind inside its range. Otherwise it is read as a new fact (without the question's context, so "we owe 30k on student loans at 6%" at a spending-share confirm is a debt, not "6%"), a stray chip from another question (nothing changes; reply "That answers a different question..."), an edit, or a question; the pending question is then asked again and a confirm stays open. Numbers inside 401(k), 403(b), 457(b) and 529 are never amounts. With empty `text` and `reset`, the reply is only "Cleared your <sections>." (or "Cleared all your answers.") and the next question.
  **fields** are grouped by `section` (Household, Work & pay, Saving, Home & debts, Pensions & income, Insurance, Goals, Health, Costs). `display` is a ready-to-show string. `source` is the person's own word, an estimate, or an assumption; a value stays "assumed" until they confirm or edit it (a savings total with the split assumed is "assumed"; "That's about right" or an edit makes it "you said"). `editable` says how to edit inline: `{kind:"split", ask:"savings_split", parts:[pretax,roth,taxable,cash]}`, `{kind:"money", ask, per}`, `{kind:"number", ask, min, max}`, `{kind:"choice", ask, options}`, `{kind:"text", ask}`, `{kind:"group", ask}` (opens a question group) or null (read-only). When the page sends "Updated your <label>: ..." with the edited profile, the edit is kept as "you said".
  **Question flow** (`profile.asking` names the question just asked; the page sends the answer as `text`). 1) The essentials, one question each. 2) A stated assumption with chips, once each: `confirm_split` ("I split your $750,000 as 60% pre-tax ... Is that about right?" with "That's about right", "Mostly in a 401(k)", "Mostly in a bank account", "Change the split"), then `confirm_pay`, `confirm_spending_later` (80% of now), `confirm_ss`, `confirm_risk`. 3) `more`: chips "Add debts", "Add a pension", "Add saving", "Add insurance", "Add goals", "Add health", "Add costs", "Skip, use typical" (finished groups drop off). Each group is one or two short questions (`debts`, `debts_detail`, `pension`, `saving`, `insurance`, `goals`, `health`, `sex`, `costs`, `spending_later`). Free text works everywhere ("we owe 30k on student loans at 6%", "I get a $2,000 a month pension at 65", "my company matches 50% up to 6%"). 4) Edit intents ("need to adjust pay", "my pay is wrong") get a targeted question with chips (the current value, "Use typical for my job", "Type an amount"). The reply is never a dead end: it says what was understood, or asks one question with chips.
  **Safety on intake**: tags such as `</user_text>` and `<system>...</system>`, and everything after a closing user tag, are removed before parsing (no figure inside is read). Requests to list money as zero or park it with someone else for Medicaid or SSI are refused and the true figures kept. Values outside plausible ranges (age 18-110, retire age 30-80, children 0-15, savings up to $50 million, and so on) are not stored; the reply asks what was meant.
  Profile fields (new ones are optional, each with a typical default marked in `sources`): age, partner_age|null, state, retire_age, partner_retire_age (default: retire together), pay_per_year, partner_pay_per_year, job, partner_job, sex and partner_sex ("male"|"female", only to pick the life table; unknown = average of both), health and partner_health ("excellent"|"good"|"fair"|"poor", default good), savings{pretax,roth,taxable,cash}, save_rate, saving{contrib_you, contrib_partner (a year; default save_rate x pay), match_rate (0.5 = 50 cents per dollar), match_cap (share of pay; 0.06 when only a rate is given), other_per_month}, emergency_months (default: cash divided by a month of spending), home{owns, value, mortgage_balance, mortgage_payment (a month), mortgage_rate (default 5%), rent}, debts:[{kind:"student"|"car"|"credit_card"|"other", balance, rate (a fraction), monthly_payment, assumed:[...]}] (a missing rate or payment is assumed from the kind), pensions:[{who:"you"|"partner", per_year, start_age (default 65), inflation_adjusted (default false), survivor_share (default 0.5), assumed:[...]}], social_security_per_year|null (estimated if missing), insurance{life_kind:"none"|"term"|"whole", life_face, life_premium, disability:bool, ltc:bool}, goals{legacy, big_costs:[{label, amount, year}], parents_per_year, parents_years}, children:[{age, college:bool, college_type:"public"|"private"|"none" (default public), college_share (0 to 1, default 1)}], pets:[{kind:"dog"|"cat"|"other", count}], part_time{per_year, until_age (default 70)}, inheritance{amount, year, count (default false: counted only if the person says to count it)}, spending_now_per_year (estimated from take-home pay less saving, or added up from `budget`), budget{housing, food, transport, health, childcare, debt, other} (a month), retire_spend_ratio (default 0.8, assumed), spending_per_year|null (spending in retirement), risk:"careful"|"balanced"|"growth", offered:[groups already asked].
- `POST /api/reset` -> `{ok, session, cleared_entries, profile:{}, spent_usd, session_cap_usd}`: clears the session's cost log and plan history only. The spend counter and the dollar caps stay (reset never gives budget back). The server holds no draft.
- `POST /api/plan` `{profile}` -> Server-Sent Events stream:
  - `{type:"agent_start", agent, label}`
  - `{type:"handoff", from, to, message}`: the lead assigns work to a specialist, or one agent's output feeds another (from/to are agent names: adviser, longevity, family, tax, research, markets). Order: adviser assigns; specialists work (tool events); findings pass on to markets, then to the adviser; the adviser combines. Messages are built from tool outputs only.
  - `{type:"tool", agent, tool, summary}` (each tool call, for the live panel)
  - `{type:"agent_done", agent, finding:{headline, details:[str], numbers:{...}}, tokens:{input, cached, output}, cost_usd}`
  - `{type:"plan", plan:{needs:{basics_per_year, paid_of_100, line}, wants:{per_year, line}, wishes:{line}, actions:[{title, why}] (3), family_moments:[str], neighbors:{used:bool, note}, chart:{ages:[], median:[], low:[], high:[]}, costs_by_age:{ages:[], total:[], basics:[], events:[{age, year, label, change_per_year|null, one_off?}], now_per_year, retired_per_year, now_source, retired_source, retire_age, notes:[str]}, levers:[{key:"debt"|"match"|"emergency"|"life"|"disability"|"ltc", title, why, whatif_text}], headline}}`
  - `wants` (2026-11-21, changed): `wants.per_year` is what you can count on a year, safe in 90 of 100 scenarios, basics included (as in the full app's scorecard); it equals `count_on_per_year` and the headline's figure. `wants.above_basics_per_year` is the part above the basics. `needs.basis` says where the basics came from: typical figures, the person's budget (housing and health as given; food and transport up to the typical figure), and never more than the spending goal. `verdict` (round 1 fix) has four values with one meaning each: `falls_short` only when the basics are paid in fewer than 90 of 100 scenarios; with the basics safe, `works` (count-on at or above the goal), `close` (within 10%) or `below_goal`; `verdict_words` gives plain words. `claim_age` and `partner_claim_age` are each 62 to 70, each person at their own age (`already_claiming` when you already claim; the stated claiming age is kept, and no claiming advice is given). Levers are ranked by dollars a year: the gap to the goal (`key:"goal"`) first when the goal falls short, then high-rate debt (7% or more, `config.HIGH_RATE_DEBT`) and the match by size, then the emergency fund, then cover; no match or disability lever with under two working years left. What Ifs also take market shocks: "markets fall 30%" (now, or "when I retire"), "high inflation for a decade", "a bad first decade". Model calls stop about 24 s into a plan (`llm.PLAN_AI_SECONDS`); templates fill the rest.
  - `headline` (2026-11-21): one plain sentence built in code, e.g. "You can count on $50,400 a year, about your basics. There is little room above them yet." (room above the basics under 5% of them; "less than your basics of $X" when safe spending is below them; else "...: $B for basics and $W for the rest."). When the room is thin, `wants.line` equals it. Each lever's `whatif_text` ("What if I pay off my credit card") is sent to /api/ask as is and returns a `whatif`.
  - `costs_by_age` (today's dollars, your age to the planning horizon): `total` is what the household spends each year, now and later (before retirement your spending now; after it your retirement spending plus the known changes); `basics` is housing, food, transport and health care. `events` are labelled changes: "Mortgage paid off 2041" (negative `change_per_year`), "Children's costs end 2038", "College 2032-2036", "Debts paid off 2037", big costs and "Helping your parents ends 2031" (`one_off:true` for a single cost), "You retire at 62", "Medicare starts for you 2039" (health cover before 65 is an assumed $10,000 a person a year), "Health costs rise again at 85" (CMS). `notes` carries long-term care (CareScout 2025 nursing home median, ACL average length of care) as a risk, not a forecast. The family and markets findings quote the changes ("Your costs fall by about $16,500 a year when the mortgage ends in 2033"). `levers` are the actions the person's own inputs call for (high-rate debt, the full employer match, a 3-month emergency fund, gaps in life, disability or long-term care cover); the adviser uses them first.
  - `{type:"cost", total_tokens, total_usd, budget_usd}` and `{type:"error", message}` / `{type:"done"}`
- `POST /api/ask` `{question, profile, plan, pending_change?}` -> `{kind, text, citations:[{title,url}], quick_answers?:[str], tokens, cost_usd, ...}`. Rules read the intent first; one small model call classifies only what the rules cannot. Kinds:
  - `"answer"`: a rule question (cited sources) or a question about the plan (answered from the plan's own lines and fixed definitions; no invented figures). A rule question with no source ends with "I don't have a source for that." and offers chips (change an answer, try a What If, explain my plan).
  - `"whatif"`: a hypothetical; returns `plan`, `profile`, `changes`. It does not replace the baseline. Understood: retire at N, spend $X (a month or a year), save a percent of pay ("save 15%", "5% more") or dollars as extra saving ("save $250 more a month", "an extra $3,000"), move to a state, another child or pet, a risk mix, and the plan's levers: pay off a named debt ("the credit card", "my student loans", "my high-rate debts", "the mortgage"; paid from savings, cash first), an emergency fund of N months (moved from other savings into cash), disability, life or long-term care cover (the figures do not move, and the answer says why), saving to the full 401(k) match, downsizing the home (needs the home value; assumes the new home costs 60% of the old, 6% selling costs), and claiming Social Security at N (62 to 70; profile field `claim_age`, kept when the neighbour strategies are tested). A What If that cannot run (no such debt, no home value, no match given) returns a `clarify` that says what is missing.
  - `"change"`: a correction ("my pay is $210,000 now", "we have 2 kids now", "adjust pay"). `status:"confirm"` proposes it ("Change your pay to $210,000 and rebuild your plan?", chips "Yes, rebuild" / "No") with `pending_change:{facts}`. `status:"ask"` asks one targeted question with chips and `pending_change:{ask}` when no value was given. Send `pending_change` back with the person's reply. On "Yes, rebuild": `status:"applied"` with `profile` and a rebuilt `plan` that REPLACE the baseline. On "No": `status:"cancelled"`.
  - `"clarify"`: the intent is unclear ("this is wrong", "huh?"); says what was understood and offers 3 or 4 chips ("Change an answer", "Try a What If", "Explain my plan").
  - `"refused"`: hiding assets, instructions inside a question, emergencies.
- `GET /api/costs` -> per-agent token and cost log for this session (for the cost meter and the report)

## Agents (each returns a Pydantic model; numbers only from tools)
- Intake: text -> profile fields (rule parser first, model only when needed); estimates pay from job + state, family/pet costs, Social Security; everything shown for confirmation.
- Longevity: life table tool -> planning horizon (e.g. age 95 for a couple with 25% chance one lives past it).
- Markets: simulation tool (simple Monte Carlo, ~2,000 paths, stock/bond mix by risk and age) -> chance the money lasts at the goal, the most spending that lasts in 90 of 100 scenarios, median/low/high wealth by age.
- Family: children's costs by age until they leave home, college if wanted, pet costs, partner effects -> yearly cost path and "family moments".
- Tax: simple federal + state effective rates, withdrawal order (taxable, pre-tax, Roth) -> after-tax figures.
- Research: rule questions answered only from cited source passages (retrieval); otherwise "I don't have a source for that".
- Adviser (lead): reads the findings (and, if the neighbour check says it helps, strategies from similar households in the library) -> needs / wants / wishes, three actions, family moments. Never invents numbers: a number check rejects any figure not in the tools' outputs.

## Safety (show it working for the report)
- Prompt injection: user text and any uploaded or pasted document are wrapped as untrusted data; a guard flags instructions inside them; a test with hidden-text injection shows it blocked.
- Number check on every adviser answer. Refuse advice on hiding assets for Medicaid/SSI.
- Cost: per-run and per-session USD budget caps (hard stop), meter shown in the UI.

## Queue after the first working build (user, 2026-11-20)
1. Independent UX agent (fresh, no build context) walks the live app at 1280 and 390 px as a real user: does each screen make sense, are the steps and results reasonable, is anything confusing or wrong. Fix P0/P1, then re-check.
1b. Stricter UX audit checklist (user, 2026-11-21: the first audit would likely have missed "need to adjust pay" hitting a dead end, and no way to change an assumed savings split). The audit must also try:
   - corrections ("my pay is wrong", "actually 2 kids", "change the split", changing one's mind twice);
   - every ✎, every assumed or estimate tag, every Reset and Start over;
   - typos, half-sentences, several facts at once, contradictions, and questions in the middle of intake.
   Any reply that neither moves forward nor asks one specific question is a P0 dead end.
1c. Simulated-user tester: Claude Haiku role-plays about 40 different people (a careless typer, a corrector, someone who doesn't know their numbers, a skeptic who asks "why?", a couple who disagree, and so on). Each has a goal and talks freely for 10-20 turns through /api/intake, then the plan and What Ifs. A second Haiku judges every exchange for dead ends, ignored corrections, unstated assumptions, repeated questions and confusing replies. The results are saved as evidence for the report. Budget about $1.
1d. Security pass after all features land (user, 2026-11-21: "protect against code/prompt injection as well"):
   - **Prompt injection:** rerun all 50 attacks, and add new cases for the new paths: corrections through the plan-page chat (`change_input`), assumption-adjust chips, inline editors, the split parser, and multi-turn attacks (a harmless first turn, then an injected instruction).
   - **Code injection and web security** (independent review agent plus tests):
     - XSS: model or user text rendered as HTML; names and labels holding `<script>` or onerror attributes; check React never uses dangerouslySetInnerHTML on untrusted text;
     - no eval, exec, pickle or shell calls on input;
     - path traversal on static files (/../, encoded);
     - mass assignment: a chat or edit may only set allowed profile fields, with validated types and ranges;
     - oversized or deeply nested JSON (request size limits);
     - ReDoS in the parser regexes (time-limit test);
     - header and log injection (newlines in input);
     - CORS limited to same origin;
     - security headers (CSP, nosniff, frame-ancestors);
     - no secrets in responses, errors or logs;
     - dependency check (pip-audit / npm audit).
   - Fix the findings, add regression tests, and keep before/after results for the report's safety section.
2. Hundreds of test cases on the recommendations:
   - Run the lite app end to end on ~300 synthetic households (scripts/synth_users.py personas plus typed cases), resumable, saved per household.
   - Automated checks: needs, wants and wishes consistent; no invented numbers; family and pet costs present when stated; no retirement age past 70 suggested; directions sensible (more savings never lowers what you can count on; retiring later rarely lowers it); refusals where they should be.
   - Benchmark against the full optimizer's saved results for the same households (output/synth_tree): how far the lite advice falls from the optimized answer.
   - An AI judge reads a sample and flags advice that a careful planner would call unreasonable.
   - Cost: Haiku at about $0.01-0.02 a household, so about $3-6 in total; log real tokens (also evidence for the report's tokenomics).
   - A test mode lifts the per-IP rate limit, but keeps the dollar cap.

## Self-improving loop (user, 2026-11-21)
Run several rounds of: audit, then fix, then audit again. Start a round only once all fix agents have finished and the app on :8020 is restarted.

Each round runs 3 audits in parallel (independent agents with no build context, judging the live app):
- **A. Logic, math and reasoning audit.** Recompute key figures by hand or with an independent script for about 15 diverse households (the doctor, a teacher with a pension, a renter with loans, a couple with a mortgage, a retiree past 70, low and high savings), and check:
  - tax, Social Security and pensions, the costs timeline, the simulation's yearly cash flow, and safe spending;
  - the invariants (more income, savings or later retirement never lowers count-on; headline = wants; What If baseline = plan);
  - that the advice follows from the numbers (the right top actions, sensible verdicts);
  - that every assumption is stated and reasonable.
  Also compare with the optimizer library, and run the 300-household eval (eval) for regressions.
- **B. UI/UX audit:** the strict checklist (docs/UX_REVIEW.md style): 8 journeys at 1280 and 390 px, every correction, editor, reset and assumption, no dead ends, and look and feel.
- **C. Simulated users:** simusers, 40 personas, judged.

Each audit writes findings ranked P0/P1/P2 with reproduction steps. A fix pass assigns the findings to fix agents by area (intake, engine and plan, frontend), each with tests, then the app is restarted.

Stop when, in one round:
- 0 P0 and at most 3 P1 across A and B;
- simulated-user profile accuracy of at least 92%, 0 P0 dead ends, and at least 39/40 reaching a plan;
- the eval core checks are 100%;
- the attack kit is at 74/74.
Run at most 3 rounds (deadline Mon 11:59 PM). Budget about $6 a round in live AI spend. Keep a round log at docs/LOOP_LOG.md: each round's findings counts, what was fixed, and the metrics. This is also evidence for the report.

## Product rules audit (user, 2026-11-21): the final gate before the move
The user's rules are listed in `docs/PRODUCT_RULES.md` (R1 to R25). The user found a rule broken by hand that three audit rounds had missed ("Not sure, estimate it" left the mortgage blank), so every rule now gets an explicit pass/fail check.
1. **Code coverage (running):** map each rule to the tests that enforce it. Write outcome tests where coverage is weak or missing (`tests/test_product_rules.py`, `web/src/productRules.test.tsx`). Tests that fail today are real gaps and go to fix agents.
2. **Live rules audit (after the round 3 fixes land):**
   - A fresh agent with no build context walks the live app at 1440 and 390, rule by rule, R1 to R25. It clicks every chip and button at least once.
   - Each rule gets pass or fail, with a screenshot or transcript as evidence. Rules that cannot be checked in the app (R24 fresh clone, R25 realistic tests) point to where their evidence lives.
   - It writes the evidence into the Coverage table in PRODUCT_RULES.md.
3. **Fix any failures, then re-run only the failed rules.**
4. **Order of work:** the report and slides get the final rules table, then the folder move follows.
Future audit briefs must list these rules as pass/fail checks.

## Final step (user, 2026-11-20): one clean project folder
Done on 2026-11-22. hw-Final-2 now holds only this app at its top level. The old `lite/` folder was moved up and the old full app was deleted (the user keeps a backup outside OneDrive). Paths in text were fixed, and the tests were rerun from the new layout.
- Packaging check (2026-11-21, docs/REPO_PLAN.md):
  - a fresh install took about 1.5 minutes;
  - the repo is about 27 MB without ignored folders;
  - no secrets found.
  Before publishing:
  - strip absolute paths containing the username from eval/EVAL_REPORT*.md, PLAN.md, docs/SECURITY_REVIEW.md, safety_tests/README.md and RESULTS.md, report/build_*.py and eval/make_cases.py;
  - make eval/common.py and judge.py load ROOT/.env and stop pointing at old-app output/ (keep the saved benchmark_results.json);
  - note that make_cases.py needs the old app's synth_users.py, or copy that generator in;
  - optionally trim docs/screens (22 MB).

## Evidence to collect (report needs it)
Real token counts per agent from logs (input, cached, output), cost per run / per user-month / at 100 and 10,000 users, caching before and after; one traced run with screenshots; attacks and defenses with screenshots or tests; a real user's run and time.

- Second plan-fix pass (2026-11-21): `plan.worth_checking: [{kind:"term_life"|"disability"|"income_annuity", title, why}]` (may be empty) lists products to look into, from the person's answers (dependants and no life or disability cover; a single person with savings of $200,000 or more who may outlive them). Plain text, not priced, marked "not a recommendation". Actions: no action repeats another; a high-rate debt or an uncaptured match always gets a slot beside the goal. A Social Security figure the person gave is read as the benefit at 67 (`household.stated_ss_at_claim`), so a start after 67 earns the delayed credits and retiring later never lowers it.

- Round 1 engine fix (2026-11-21):
  - Social Security per person (`app/tools/socialsec.py`, `household.ss_people`): each benefit starts at its own claiming age with its own factor; a spousal top-up is half the worker's full-age benefit, reduced before 67, with no delayed credit, and starts once the worker claims; after the first expected death (shorter life expectancy) the survivor keeps the larger benefit. Estimates use years worked from about 22 to retirement (fewer than 35 years averaged over 35). Optional profile field `partner_claim_age`.
  - Working-year tax: head of household for single parents, the child tax credit (`tax_rules.json` child_tax_credit), 401(k) saving before tax. Retirement tax grosses withdrawals up properly; states listed in `state_tax.json` taxes_social_security are the only ones taxing it.
  - The strategy test always scores a fixed grid beside the 5 similar households: the simple plan with each claiming age 62 to 70 and its stock path 15 points lower and higher.
  - New plan fields: `assumptions:[str]` (plain sentences with the figures used; shown under an "Assumptions" expander), `saving:{per_year, accounts_per_year, match_per_year, other_per_year, unspent_pay_per_year, field}`, `horizon_text` ("to age 95", or "until your partner is 94" when your own age would pass 100), `already_retired`, `starting_points:[{title, result, whatif_text, paid_of_100, count_on_per_year}]` (only when the basics are not safe: retire up to 2 years later but never past 70, save a tenth of pay more, claim at 70; each worked out on the person's numbers), `social_security_per_year`, `verdict_words`. `needs.line` is built in code from `paid_of_100`. The headline says when count-on is below gross Social Security and why. `costs_by_age.now_per_year` is the spending-now figure the answers panel shows.
  - Already retired: retirement spending equals spending now unless a ratio is given. Spending below a quarter of the typical basics is set aside as a slip and estimated again (noted in the assumptions).
- Round 2 plan fix (2026-11-21):
  - One figure everywhere: `costs.saving_now` is the yearly saving the plan uses (401(k) or IRA, match, other, take-home pay left after spending; below zero when spending now is above take-home pay, which is then drawn from savings). The panel's "Yearly saving" shows it with its parts (its pen opens the saving questions); `plan.saving` adds `assumed`. "Costs now" is `spending_now_per_year` in both. Social Security: the panel shows the figure with the age it is read at ("$33,000 a year at 67"); when the kept plan starts it at another age, the headline says "(starting at 69 in this plan)" and the assumptions name both figures. `plan.consistency:[str]` is a code check (empty when the plan's saving, spending now and Social Security agree with the answers; a disagreement is logged).
  - Starting points (falls_short only): retire 1 or 2 years later (then the nearest of 62, 65, 67, 70 that helps, never past 70), spend a tenth less now ("Spend $X a year less now"), save a twentieth of pay more ("Save $X a month more"), claim at 70, a smaller goal; each run through the What If parser and kept only when it pays the basics more often or adds 5% (and $500) to count-on; tried together when none alone makes the basics safe. New field `makes_basics_safe`; `result` gives "(now ...)". The headline says "would make the basics safe" only when one does.
  - Levers: no What If with a retirement age already passed or past 70, none about retiring once retired, no "another child" past 50; no match lever under $500 a year; the catch-up action only near the 401(k) limit.
  - Engine (audit 2A): Social Security already being paid counts in working years; after the first death of a couple spending and the basics fall to `config.SURVIVOR_SPEND_SHARE` (75%); the additional Medicare tax (0.9% above $200,000 / $250,000); the 401(k) catch-up of $11,750 at 60 to 63; Colorado exempts Social Security from 65 (other states' income limits noted in `state_tax.json`); a new child in a What If adds its first-year cost to spending now.
  - Copy: assumptions in order of importance in plain words; one horizon sentence (longevity headline built in code); no debts among family moments; the wishes line is code-built unless the plan works; the adviser's finding is one headline and two short sentences; assumed saving is named "assumed" to the models.

- The analysis (2026-11-21): `plan.analysis` (schemas.Analysis, web types `Analysis`; null for market What Ifs and nested reruns) is built in code by `app/analysis.py` on the kept strategy, the same 2,000 paths and seed, in a thread beside the adviser's model call (about 0.5 to 1.7 s of CPU). `how_sure`: safe spending at 50/75/90/95 of 100 (90 is the plan's count-on), from each scenario's own most-it-can-spend (`simulate.max_spend_by_path`), and a curve of scenarios that last against spending. `stresses.rows`: a poor first decade (stocks 5 points lower for 10 years of retirement), prices 1.5 points higher for 10 years (savings earn that much less; pensions and annuities with no cost-of-living rise buy less), living to 100 (each person), and for couples the first death 10 years early or late (never before both stop work); each with count-on and basics paid and the change against the plan. `levers.rows`: one change at a time (retire a year later, never past 70; claim at 70; save $100 a month more; spend $1,000 a year less now; pay off high-rate debt; the full match), rerun through the plan's tools with the kept strategy, sorted by effect. `sources`: each year's spending split into pay, Social Security for each person, pensions, annuity, savings (middle path) and any part not covered; parts add up to spending plus `surplus`. `costs_by_age.parts`: each year's total in parts that add up to it (basics, mortgage, children and college, pets, health cover before Medicare, more care from 85, debts, big costs, parents, other). `_run` reads its year figures as floats and the growth matrix once per simulate() call: same figures, about 40% faster. Social Security has the earnings test (`socialsec.EARNINGS_TEST_LIMIT`).

## To do (user, 2026-11-22)

Done today: "How Enough works" (folds to one line), "Baseline plan" naming, loud shortfalls, Token costs under Team talk, admin mode (`/?admin`, 15 sample households, before/after runs), pinned household picture, two providers (ANTHROPIC_API_KEY or OPENAI_API_KEY with gpt-6-luna), Royal Indigo theme + dark mode (`docs/THEME_ROYAL_INDIGO.css`), report sections on AI vs code, the harness, simulating not optimizing, and what the plan considers.

**How to run these (user, 2026-11-22): use several agents in parallel wherever the work splits cleanly, to save time.** Split by files so agents never edit the same file: e.g. scenario tabs (web/ only) ‖ What If understanding (app/whatif_read.py, ask parsing) ‖ model comparison (eval/ only, read-only on app/) ‖ report/slides. Within a task, fan out independent runs (households, phrasing sets, both models) across agents or processes. Cheaper models (Sonnet) for building and checking; one agent per shared file; a final merge-and-full-test step by the lead.

Open, in order:
1. Reasonableness audit (running): 300+ baselines x ~20 What Ifs, tools only; fix the logic; report in `eval/reasonableness/REPORT.md`.
2. Demo video (running): nova voice (OpenAI TTS, key `OPENAI_TTS_API_KEY`), app only, no name or course; `demo/enough_demo.mp4`.
3. **What If as scenario tabs (designed, NOT to be built until the user says go):**
   - Tabs above the plan: `Baseline` · one tab per What If · `+ What if…`; switch back and forth; the baseline folds to its tab.
   - Every What If is built on the baseline only, never on another What If (one change each).
   - Each tab shows the full plan view, the same as the baseline, with small "vs baseline" markers on the key figures, one line saying what changed, and a ✕ to remove it.
   - A secondary "Compare" button: a side-by-side table of all tabs.
   - No "Make this my baseline" (changing the baseline stays: edit answers, then rebuild).
   - The team panel (findings, Team talk, Token costs) follows the selected tab.
   - About 5 What Ifs at most; the same chat box and Worth trying chips create them.
   - After it is built: re-record the video's What If segment.
3b. **Make the What If chat understand people's own words (user, 2026-11-22; NOT to be built until the user says go).** The point is the chat's input understanding in general, not one example.
   - Symptom found by the user: "what if I have 5 dogs" (also "we get 5 dogs", "had five dogs") answers "I did not find a change… a child or pet…", though pets are supported. Cause: the What If readers (`app/whatif_read.py`, `pipeline` change parsing) are narrow regexes: fixed counts (two/three), a fixed verb list, no numbers in words, no "have N in all" vs "N more".
   - Approach: rules first for the common, exact cases; when the rules find nothing (or only part), ask the model to turn the message into the same typed change (a Pydantic object: field, new value or delta, in-all vs more) with the person's current profile as context; code then validates it (ranges, caps such as ages ≤ 70, ≤ 10 pets) and proposes it for confirmation as now ("Change … and rebuild?"). Never apply a model-read change without the confirm step; numbers in the reply still come from the tools.
   - Cover the families of phrasing, not single sentences: counts in digits and words, "in all" vs "more" vs "fewer", relative changes ("20% less", "$500 more a month", "two years later"), several changes in one message (say which one is modelled, or offer each), past/conditional tense ("had", "were to"), and clear "can't model that" answers that name what can be modelled.
   - Evidence: a phrasing test set (a few hundred What If messages across every change type, written as people talk, plus near-misses), measured before and after; add it to the reasonableness audit's What If list.
3c. **Compare the two models: Claude Haiku 5.5 (Anthropic) vs gpt-6-luna (OpenAI) (user, 2026-11-22; NOT to be run until the user says go).** Which one gives better, more reasonable results overall?
   - Same households, both models, everything else fixed (`ENOUGH_PROVIDER=anthropic|openai`, same seed). The plan numbers come from code, so they should match; the comparison is about what the AI does.
   - Measure: intake accuracy (fields right on the simulated users, `simusers/`), What If and question understanding (the phrasing test set from 3b), plan text quality (number-check pass rate, template fallbacks, jargon, an AI judge reading a sample blind, plus a human read of a few), refusals and injection tests (the attack kit), speed (median and slowest plan) and cost (tokens and dollars per plan, per user per month).
   - Sample: about 50–100 households from `eval/cases.jsonl` plus the 15 admin samples; report per tier (comfortable, average, struggling).
   - Output: a short table and a recommendation in `eval/model_compare/REPORT.md`, and a paragraph in the report's tokenomics or testing section. Budget: a few dollars at most; ask before the run.
3d. **MCP server: Enough's checked math for any AI assistant (user, 2026-11-22).** Product reason, not just the class concept: people already ask ChatGPT or Claude about retirement and get made-up numbers; an MCP server lets their own assistant call Enough's tools and get the same checked figures, with sources.
   - New `mcp_server.py` at the project root (FastMCP; `mcp` 2.3.0 and `fastmcp` 4.1.6 are already in the conda Python), stdio transport, wrapping the existing plain-Python tools, no AI inside: `plan_check` (a household → count on, basics paid of 100, verdict, short of goal; the same engine and seed as the app), `social_security_estimate`, `tax_estimate`, `life_expectancy` (planning age), `family_costs` (children, college, pets by year), `search_rules` (the 37 cited passages). Typed inputs and outputs; the same validation, caps and refusals as the app (no Medicaid/SSI hiding, no stock picks); no personal data stored.
   - Kept out of the web app's own path (the agents still call the tools directly: faster, no extra moving part). Optional: `requirements-mcp.txt`, so the fresh-clone install for the web app stays quick.
   - Evidence: tests calling each tool through an in-memory MCP client; a screenshot or transcript of Claude Desktop / Claude Code using it ("what can a 58-year-old with $400k count on?"); README section "Use Enough from your AI assistant" with the config snippet; a short report paragraph and diagram box.
3e. **Admin: hidden route and model-comparison results (user, 2026-11-22).**
   - Admin opens only by typing `/admin` in the address bar (e.g. http://localhost:8020/admin), not `?admin`. No "Admin" button or link anywhere in the app's header or screens; normal users never see a trace of it. From an opened household, getting back to the list is the browser's Back button or typing `/admin` again. The test-header logic in web/src/api.ts follows the new path.
   - The admin page shows the model comparison (item 3c): the one-screen table (metric × Haiku 5.5 / gpt-6-luna, with n and the winner per row), the recommendation, cost and date, read from `eval/model_compare/` results through a read-only admin endpoint (e.g. GET /api/admin/model-compare, served only when the file exists; no secrets, no per-user data).
   - Tests: no Admin button in the header in any mode; `/admin` renders the household list and the comparison; `?admin` no longer opens admin.
4. Restart the app; full test suite.
5. Public GitHub repo `enough-lite` (nyan314sn); commit and push.
6. Fresh-clone test with only `OPENAI_API_KEY` one folder up; time it (10-minute rule).
7. Final report and slides pass (must include, per the user: the MCP server — what it is for, its tools, a diagram box and the demo transcript, in both the report and the slides; the scenario tabs; the What If understanding results; the model comparison; the reasonableness audit): audit results, repo link, clone time, retake the 6 teal screenshots (and update the run walkthrough numbers), trim to 15 pages.
8. From the user: real-user test (one person, 15 minutes, a quote); Canvas upload (repo link, report.html, slides.html, video).
