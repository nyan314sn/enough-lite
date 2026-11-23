# Enough Lite

Can I retire when I want, and what should I do first? A small team of AI agents answers for one household, in plain words.

## Run it (about 2 minutes)

You need Python 3.11 or later (tested on 3.14). You do not need Node or npm: the web app is already built in `web/dist`.
Run these from the repository folder.

1. Make a virtual environment and install:

   ```
   python -m venv .venv
   .venv\Scripts\activate          (macOS or Linux: source .venv/bin/activate)
   python -m pip install -r requirements.txt
   ```

   The install takes about a minute and a half. On macOS or Linux, use `python3` if `python` is not found. If PowerShell blocks `activate`, run `Set-ExecutionPolicy -Scope Process RemoteSigned` first, or use cmd.

2. Make a file named `.env` in this folder, or in the folder above it. Copy `.env.example` (`copy .env.example .env` on Windows, `cp .env.example .env` on macOS or Linux) and fill in one key. Either one works:

   ```
   OPENAI_API_KEY=your-key       # the app uses gpt-6-luna
   ANTHROPIC_API_KEY=your-key    # or: the app uses Claude Haiku 5.5 (wins if both are set)
   ```

   **Teaching staff:** your `.env` one folder up, with `OPENAI_API_KEY`, is enough; the app then runs on `gpt-6-luna`. (The course `PORTKEY_API_KEY` is not used: the one given to the student was rejected by Portkey, "Invalid API Key".)

3. Start the app:

   ```
   python run.py
   ```

4. Open http://localhost:8020.

Without a key the app still runs: the tools work out every number, and plain templates replace the AI's wording.
To check that the key was found, open http://localhost:8020/api/health: `ai_available` is true, and `provider` and `model` say which one is in use.

## Settings (.env)

One key is needed: `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. The rest are optional.

| Name | What it does |
|---|---|
| `ANTHROPIC_API_KEY` | An Anthropic key. When set, the app uses Claude Haiku 5.5. |
| `OPENAI_API_KEY` | An OpenAI key. Used when there is no Anthropic key; the model is `gpt-6-luna`. |
| `ANTHROPIC_MODEL`, `OPENAI_MODEL` | Model names. Defaults `claude-haiku-5-5` and `gpt-6-luna`. Set in one place: `app/config.py`. |
| `ENOUGH_PROVIDER` | `anthropic` or `openai`, to force one when both keys are set. |
| `ENOUGH_RUN_BUDGET_USD` | Hard spending cap for one plan or question. Default 0.05. |
| `ENOUGH_SESSION_BUDGET_USD` | Hard cap for one session (header `X-Session-Id`, else the IP address). Default 0.50. |
| `ENOUGH_TOTAL_BUDGET_USD` | Hard cap for the whole server process. Default 5.00. |
| `ENOUGH_RATE_PER_MINUTE`, `ENOUGH_RATE_PER_DAY` | Per-IP limits on `/api/plan` and `/api/ask`. Defaults 6 and 60. |
| `ENOUGH_TRUST_PROXY` | Set to 1 behind a proxy, so the limit uses `X-Forwarded-For`. |
| `ENOUGH_RUN_LOG` | Set to 0 to stop writing token counts to `runs/usage.jsonl`. |
| `PORT` / `BACKEND_PORT` / `HOST` | `PORT` is for hosting services (the app then listens on all interfaces). Default port 8020. |
| `ENOUGH_TEST_MODE` | Test only. Set to 1 to let the header `X-Enough-Test: 1` skip the rate limit (dollar caps still apply). The eval and attack tests need it. |
| `ENOUGH_APP_URL`, `EVAL_RUNS_DIR`, `JUDGE_MODEL` | Test only. Where `simusers` finds the app, where `eval` saves runs, and the model that judges. |

`.env` is read from this folder first, then up to three parent folders. A variable already set in the environment wins.
Never commit `.env`; `.env.example` lists the names only.

## Tests

```
python -m pytest tests -q
```

The tests never call the real model. They take about a minute.

## Eval, simulated users and attack tests

These run against a live app and call the real model, so they cost money. Start the app first (`python run.py`). To
run them with the rate limit off, start it with `ENOUGH_TEST_MODE=1` and add the header shown. The app's dollar caps
still apply.

| Folder | Command | Cost |
|---|---|---|
| `eval/` | `python eval/run_eval.py --header X-Enough-Test=1 --limit 3` (all 480 runs: drop `--limit`) | about $0.002 a plan; `--max-usd` stops it (default 8) |
| `eval/` | then `python eval/checks.py`, `python eval/judge.py`, `python eval/report.py` | the judge is paid; the others are free |
| `simusers/` | `python simusers/run_sims.py --first 3` | `--stop-usd` stops it (default 2) |
| `safety_tests/` | `python safety_tests/run_attacks.py --header "X-Enough-Test:1"` (`--dry-run` sends nothing) | a few cents |

Saved results are in the repository (`eval/EVAL_REPORT.md`, `simusers/SIM_REPORT.md`, `safety_tests/RESULTS.md`), so you
can read them without running anything. The raw per-run files (`eval/runs*`, `simusers/runs`) are not kept. The
benchmark against the full optimizer (`eval/benchmark.py`, `eval/make_cases.py`) needs files from the old full app that
are not in this repository; its results are saved in `eval/benchmark_results.json`.

## Layout

| Path | What it holds |
|---|---|
| `run.py` | Starts the app. |
| `app/` | The backend (FastAPI): `agents/`, `tools/`, `data/` (small data files; `data/SOURCES.json` says where each came from). |
| `web/` | The React app. `web/dist` is the built copy the backend serves; `web/src` is the source (rebuilding needs Node: `npm install`, `npm run build`). |
| `tests/` | Unit and API tests. |
| `eval/` | 300 households run through the app, with checks, a judge and a report. |
| `simusers/` | Simulated users who try the app. |
| `safety_tests/` | 74 attacks and their results. |
| `report/` | Scripts that build the report and slides from the logs. |
| `docs/` | Security review, UX review, research notes, screenshots. |
| `PLAN.md` | The build plan and API contract. |

## The model: two providers

The class default is `gpt-6-luna` through Portkey. The course Portkey key given to the student was rejected ("Invalid API Key"), so the app calls the model providers directly:

- **`ANTHROPIC_API_KEY` set:** Claude Haiku 5.5, the student's choice. It was used for development, and every measured cost and eval in the report is from Haiku.
- **Else `OPENAI_API_KEY` set:** `gpt-6-luna` on the OpenAI Responses API, the course model. Checked live: one intake turn and one full plan, all seven agents, no fallback, about 20 s a plan.
- **No key:** the app still runs; the tools work out every number and plain templates replace the AI's wording.

The provider is chosen in one place (`app/config.py`) and the model is built in one place (`app/llm.py`), so `requirements.txt` uses `pydantic-ai-slim[anthropic,openai]`. Neither model gets a temperature (Haiku 5.5 rejects sampling settings; gpt-6-luna is a reasoning model). The simple agents use effort "low" and the adviser "medium", passed to gpt-6-luna as reasoning effort. Price for both: $0.10 per million input tokens and $0.50 per million output tokens (cache reads $0.01).

## Put it online

One command starts it: `python run.py`. It reads `PORT` from the environment. Set `ANTHROPIC_API_KEY` as a secret on
the host, and `ENOUGH_TRUST_PROXY=1` if the host puts a proxy in front. The dollar caps and the rate limit protect the key.
Logs hold token counts only, never prompts or keys.

## How it works

- **Intake** turns plain sentences into a profile. A rule parser runs first; the model runs only when the parser finds
  little, and any number it returns must appear in what the person wrote. Pay, Social Security and spending are
  estimated and marked for the person to check.
- **Specialists** each call one pure-Python tool (`app/tools`): longevity (life table), family (children, college, pets,
  basics), tax, research (official passages) and markets (2,000 seeded scenarios, then the strategies of the 5 most
  similar households in a library of 467 optimized plans, plus the rule of thumb, scored on the person's own numbers).
- **The adviser** writes needs, wants, wishes and three actions. A number check rejects any figure that is not in the
  tools' output; it retries once, then uses a template.
- **Safety:** typed and pasted text is cleaned of hidden text and wrapped as data; a guard flags instructions to the
  model; requests to hide assets for Medicaid or SSI are refused; dollar caps stop spending.

API: `GET /api/health`, `POST /api/intake`, `POST /api/plan` (Server-Sent Events), `POST /api/ask`, `GET /api/costs`.
See `PLAN.md` for the contract.

## Use Enough from your AI assistant (MCP)

Ask a chatbot about retirement and it will often make up the numbers. This optional server lets your own assistant (Claude Desktop, Claude Code, or any MCP client) call Enough's checked calculations instead. It gets the same figures the web app shows, with sources. No AI model runs inside it: it is plain code, with the same engine and the same seed as the app. Nothing you send is stored or logged. The web app does not need it.

Tools:

- `plan_check`: a household in, what it can count on a year (90 of 100 scenarios), how many of 100 scenarios pay the basics, a verdict, the gap to the spending goal, the planning age, the Social Security used, the main assumptions, and a list of the inputs it had to assume.
- `social_security_estimate`: a benefit from pay and claiming age, at every age from 62 to 70.
- `tax_estimate`: federal, state and payroll tax on pay; optionally a typical retirement year.
- `life_expectancy`: the age to plan to and the chance someone is alive then.
- `family_costs`: children, college and pets, year by year.
- `search_rules`: the cited official passages that answer a rules question, or "no source".

It refuses what the app refuses: hiding money to qualify for Medicaid or SSI, and single-stock or crypto picks. Emergencies get the 911 and 988 text. Ages and money amounts are range-checked.

Run it:

```
pip install -r requirements-mcp.txt
python mcp_server.py                # stdio, for assistants
python mcp_server.py --http 8765    # optional: streamable HTTP (not ports 8000, 8010, 8020)
```

Config for Claude Desktop (`claude_desktop_config.json`) or a Claude Code `.mcp.json`. Use your own Python and the full path to the file:

```json
{
  "mcpServers": {
    "enough": {
      "command": "/path/to/python",
      "args": ["/path/to/enough-lite/mcp_server.py"]
    }
  }
}
```

Claude Code can also add it with `claude mcp add enough -- /path/to/python /path/to/enough-lite/mcp_server.py`.

A recorded session (tool list, a plan check, a rules search, a refusal) is in `docs/mcp/demo_transcript.md`; `docs/mcp/demo_client.py` makes it. Tests: `python -m pytest tests/test_mcp_server.py -q`.

## For developers: sample households (hidden page)

Not part of the app a user sees: nothing links to it. Typing `/admin` after the address opens a developer page with 15 sample households in three tiers (comfortable, average, struggling; `app/data/sample_households.json`). Each can be opened in the app with every figure filled in, or built straight away; **Run all** builds every plan, and **Save as before** keeps those results so the next run shows before and after side by side. It also shows the Claude Haiku 5.5 vs gpt-6-luna comparison (`eval/model_compare/`). With `ENOUGH_TEST_MODE=1` on the server, a tab opened there is not held to the per-minute plan limit; the dollar caps still apply.

