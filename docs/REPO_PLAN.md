# Repo plan: what goes on GitHub

The repository root is `hw-Final-2/`. The contents of the old `lite/` folder moved up on 2026-11-22. Written 2026-11-21.

## Goes in

`app/` (with `app/data/`), `web/src`, `web/dist` (pre-built, committed), `web/package.json`, `web/package-lock.json`, `web/*.ts`,
`web/index.html`, `web/.gitignore`, `web/.env.mock` (one line, `VITE_MOCK=1`), `tests/`, `eval/` (code, `cases*.jsonl`,
`*_results*.json`, `EVAL_REPORT*.md`), `simusers/` (code, `personas.json`, `judged/`, reports), `safety_tests/`
(corpus, results, summaries), `report/`, `docs/` (including `screens/`), `run.py`, `requirements.txt`, `.env.example`,
`.gitignore`, `README.md`, `PLAN.md`, `report.html`, `slides.html`.

## Stays out (in `.gitignore`)

`.env` and `.env.*` (except `.env.example`), `node_modules/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.log`,
`runs/` (app token log, live and tuning runs), `eval/runs/`, `eval/runs_*/`, `simusers/runs/`, `var/cache/`.

Sizes: whole tree 168 MB, of which `web/node_modules` 119 MB. A copy without ignored folders is 27 MB. No file is over
5 MB (the biggest are under 1 MB: `eval/cases.jsonl` 0.56 MB, `eval/checks_results.json` 0.77 MB, `app/data/households.json`).
`docs/screens` is 22 MB in 101 PNGs, each under 1 MB; trim it if the repo should be smaller.

## Paths that reach outside the project or to the old app

| File and line | What it does | Fix |
|---|---|---|
| `eval/common.py:12-16` | `ROOT = EVAL_DIR.parents[1]` (hw-Final-2 now; the folder above the repo after the move), `PERSONAS`, `BENCH_FULL`, `BENCH_TREE` point to `output/synth*` of the old app | Not needed to run the eval: `cases.jsonl` is committed. Only `benchmark.py` and `make_cases.py` use them. They skip cleanly or fail when `output/` is missing; saved results are in `eval/benchmark_results.json`. Either leave and document (done in README) or copy `output/synth_tree*/raw` into the repo. |
| `eval/common.py:13`, `eval/judge.py:102` | `COURSE_ROOT = ROOT.parents[1]`: loads the course-level `.env` | After the move this is two folders above the repo. Change to `load_env_file(ROOT / ".env")` and `ROOT = EVAL_DIR.parent`, or just export `ANTHROPIC_API_KEY`. Today judge.py only works if the key is in the shell or at that folder. |
| `eval/make_cases.py:52-55` | Imports `scripts/synth_users.py` from the old app when `personas.jsonl.gz` is missing | Old-app only. Mark as not runnable from the repo (README says so). |
| `eval/make_cases.py:3-4`, `eval/benchmark.py:3`, `eval/report.py:132` | Docstrings and report text name `output/synth*` | Wording only. |
| `simusers/common.py:23` | Searches `HERE`, `HERE.parent`, ... all parents for `.env` | Works from the repo folder or any parent. No change. |
| `app/data/SOURCES.json`, `app/data/households.json:1`, `app/data/basics.json:55`, `app/data/state_tax.json:12`, `app/agents/parser.py:3`, `app/tools/neighbors.py:5` | Notes say where data came from (`output/synth_tree`, `engine/basics_benchmark.py`, `scripts/build_state_tax.py`, `backend/agents/introduce.py`, `docs/LITE_NEIGHBOR_CHECK.md`) | Provenance text only; no code reads them. Leave. The old scripts are not in the repo. |
| `PLAN.md:4,100,102,108` | Mentions the brief, `scripts/synth_users.py`, `output/synth_tree` | Provenance text only. Leave, or trim before submitting. |
| `report/build_report.py:3`, `report/build_slides.py:3`, `eval/make_cases.py:19`, `safety_tests/README.md:9-12`, `safety_tests/RESULTS.md:40,107`, `docs/SECURITY_REVIEW.md:200-201` | Commands use `python lite\...` | Cosmetic. Change to `python <folder>\script.py` (no `lite\`). Not done (other agents own those files). |
| `eval/EVAL_REPORT.md:3`, `eval/EVAL_REPORT_mock.md:3`, `PLAN.md:4`, `docs/SECURITY_REVIEW.md:200` | Absolute `~\OneDrive...` paths | Personal path (username) in text. Remove before publishing. |
| `app/config.py` | `LITE_DIR = APP_DIR.parent`; `.env` from there and three parents | Fine after the move. |
| `tests/` | Only `parents[1]` of the tests folder | Fine. |

Nothing in `app/` or `run.py` imports from outside the repo. The fresh-clone test confirmed it.

## Secret scan (2026-11-21)

No `.env` inside `lite/` (only `.env.example`, empty values, and `web/.env.mock` with `VITE_MOCK=1`). No key-like strings
(`sk-ant-`, `sk-`, bearer tokens, PORTKEY) in the tree except as test fixtures and detection patterns:
`safety_tests/run_attacks.py:53-54` (regexes) and `tests/test_security.py:199` (a fake key built from `Z`s).
`ANTHROPIC_API_KEY=` appears with a value nowhere. No email address found. The user's name appears only as the Windows
username `Pi` in the absolute paths listed above.
