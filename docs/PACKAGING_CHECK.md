# Packaging check (2026-11-21)

> Note (2026-11-23): working files this check mentions (build scripts, packaging scripts, mock and v1 results) have since been moved out of the repo.

Scan script: `docs/packaging_scripts/scan_paths_secrets.py` (prints file:line and the kind, never a value). Run it again after any edit.
Scanned the whole project (then in `lite/`, now the root) except `.venv`, `node_modules`, `web/dist`, `docs/screens`, `report/img` (web/dist, screens, img, web/src and tests were grepped separately for `C:\Users`, `OneDrive` and `sk-ant-`: clean).

## Secrets

No secret found. No `.env` in the project (only `.env.example`, names only, and `web/.env.mock` = `VITE_MOCK=1`).
Key-like text appears only as detection patterns or fakes: `safety_tests/run_attacks.py:53-54` (regexes), `tests/test_security.py` (a fake key built from `Z`s), `docs/REPO_PLAN.md` (prose).
Scan hits of kind "email" are false positives (`reveal.js@5.1.0` in `report/build_slides.py:19`, `slides.html:3,82`).

## Absolute paths with the username or `C:\Users`: fixed

| File | Was | Now |
|---|---|---|
| `eval/common.py` | `ROOT = EVAL_DIR.parents[1]` (hw-Final-2), `COURSE_ROOT`, old-app paths | `REPO = EVAL_DIR.parent`; `ROOT` is the old app only if `ENOUGH_OLD_APP` is set; new `load_project_env()` |
| `eval/EVAL_REPORT.md:3`, `eval/EVAL_REPORT_mock.md:3`, `eval/runs_v2_pre_fix/EVAL_REPORT.md:3` | full `~\OneDrive...` path | `eval/runs` etc. (relative) |
| `eval/report.py` | wrote the absolute runs path into the report | writes it relative to the project (`_rel`) |
| `eval/make_cases.py:19`, `report/build_report.py:3`, `report/build_slides.py:3` | `python lite...` | `python <folder>\script.py` |
| `docs/loop/round1_A/evalcopy/common.py:12`, `make_cases.py:19` | absolute hw-Final-2 path, miniconda path | relative; old app via `ENOUGH_OLD_APP` |
| `safety_tests/README.md:9-12`, `safety_tests/RESULTS.md:40,107`, `docs/SECURITY_REVIEW.md:200-201` | miniconda command lines | `python ...` |
| `docs/SECURITY_REVIEW.md:35` | Temp scratchpad path with the username | "kept outside the project" |
| `PLAN.md:4` | full brief path | "the course's Homework - Instructions folder" |

Also removed the `lite/` prefix from commands and paths in text under `eval/`, `report/` (including `report_source.txt`), `safety_tests/`, `user_test/`, `docs/*_REVIEW.md`, the `run.py` docstring, and `.env.example` line 1.

## Absolute paths left (others to fix)

None in code. Provenance text that names the old app folder (no username):

- `app/data/SOURCES.json:2` and `app/tools/neighbors.py:5` mention `hw-Final-2` and `hw-Final-2/docs/LITE_NEIGHBOR_CHECK.md` (an old-app file). Words only.
- `PLAN.md` "Final step": rewritten on 2026-11-22 (move done).
- `docs/REPO_PLAN.md:3,26,33,34` describe these paths (rows 33-34 are now done, see above).
- `app/config.py` comments: fixed on 2026-11-22.

## Built outputs that said `lite/` (history; the move was done on 2026-11-22 and these were rebuilt)

`report.html` has 9 mentions: `lite/runs/usage.jsonl`, `lite/safety_tests/run_attacks.py`, `lite/user_test/`, `lite/eval/EVAL_REPORT.md`, "in `lite/` or one folder up", and `lite/requirements.txt` in the run row. The source (`report/report_source.txt`, `report/build_report.py`) is fixed. Run `python report\build_report.py` and `python report\build_slides.py` once (they need `markdown` and Pillow, which `requirements.txt` does not list; both are in miniconda).

## `.env` loading

| Script | Behaviour now |
|---|---|
| `app/config.py:22-39` (not edited) | Reads `.env` in the project root and up to THREE parent folders (`ENV_LEVELS_UP = 3`); nearer wins; the shell wins over files. This covers the brief's rule (own folder and one level up) and reads two levels more. After the move that reaches the course-level `.env`. Fine for the owner; staff will not have those files. |
| `eval/judge.py` | now `load_project_env()`: project folder, then one up |
| `simusers/common.py` (`load_env`, used by `run_sims.py`, `judge.py`) | now project folder, then one up (was every parent) |
| `eval/run_eval.py`, `checks.py`, `report.py`, `safety_tests/*`, `report/*`, `user_test/*` | need no key |

Risk: the key that works for the app today sits in the course-level `.env`, two folders above `hw-Final-2`. The app finds it (three levels up). `eval/judge.py` and `simusers` will not. Put `ANTHROPIC_API_KEY` in `hw-Final-2\.env` (git-ignored) or set it in the shell before running them. The old `hw-Final-2\.env` holds one variable, `ENOUGH_SEC_CONTACT`, which nothing in lite reads.

## .gitignore and .env.example

`.gitignore` covers `.env`, `.env.*` (keeps `.env.example` and `web/.env.mock`), `.venv/`, `venv/`, `node_modules/`, `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `*.log`, `runs/` (any depth), `var/cache/`, `eval/runs/`, `eval/runs_*/`, `simusers/runs/`. `web/dist` is not ignored (good, it is committed). `web/.gitignore` also ignores `node_modules`.

Gaps:
- `docs/loop/` (11 MB of scratch: helper scripts, plans, PNGs) is not ignored. Delete it or add `docs/loop/` to `.gitignore` before the commit.
- `docs/packaging_scripts/` is small; keep or delete.
- `eval/runs_v2_pre_fix/` is ignored by `eval/runs_*/`, so its `EVAL_REPORT.md` and `app_issues.md` will not be committed (fine unless the report links to them).
- `runs/usage.jsonl` is ignored, so the report cannot be rebuilt from a fresh clone. `report.html` already holds the numbers.

`.env.example`: names only, every value empty (`ANTHROPIC_API_KEY=` and 11 optional names). It does not list `ENOUGH_APP_URL`, `EVAL_RUNS_DIR`, `JUDGE_MODEL`, `SIM_MODEL`, `ENOUGH_OLD_APP`, the test-only names. Optional.

## Checks run

`py_compile` of every edited script and an import of `eval/common.py` and `eval/report.py` passed (`docs/packaging_scripts/check_imports.py`). No server started, no AI call.

## Fresh-clone timing (the 10-minute rule)

Cloned from the public GitHub repo into a new folder outside OneDrive, with a `.env` one folder up holding only `OPENAI_API_KEY`, then followed the README step by step.

| Date | Clone | Virtual environment | `pip install` | Serving | First full plan (gpt-6-luna) |
|---|---|---|---|---|---|
| 2026-11-22 | 4 s | 16 s | 3 min 3 s | 3 min 45 s | 4 min 16 s, no error |
| 2026-11-23 | | | | | 4 min 46 s, no error |
