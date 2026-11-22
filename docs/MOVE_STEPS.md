# Move steps: lite/ becomes the repository root (hw-Final-2/)

Status: the move is done (2026-11-22). The text below is the record of the plan, so it still says `lite/`.

Do not run these until the other agents have finished editing `app`, `web/src` and `tests`. Written 2026-11-21. Names below: `H2` is `...\Homework\hw-Final-2`; `LITE` is `H2\lite`.

## Facts that shape the steps

- `H2` is not a git repository today (no `.git` in it or above). The repo is made after the move.
- `H2` already holds a real `.env` (one variable, `ENOUGH_SEC_CONTACT`), `.env.example`, `.gitignore`, `README.md`, `PLAN.md`, `requirements.txt`, `docs/`, `tests/` and `.pytest_cache`. Copying `LITE` over `H2` without deleting first would mix the two apps. Lite's `.env.example` and `.gitignore` must win; the old `.env` stays (it is git-ignored).
- The working key is in the course-level `.env`, two folders above `H2`. `app/config.py` finds it (three levels up); `eval/judge.py` and `simusers` look only in `H2` and `Homework/`.
- OneDrive: pause sync while `.venv` or `node_modules` exist, and run the clone test outside OneDrive.

## Steps

1. **Freeze.** Confirm no agent is writing to `LITE`. Stop any server on port 8020 (`netstat -ano | findstr :8020`, `taskkill /PID <pid> /F`). Check free space on C: (at least 2 GB; C: has been nearly full).
2. **Final checks in LITE, before any move.** `python -m pytest tests -q`; `python docs\packaging_scripts\scan_paths_secrets.py` (expect only the provenance lines in `PACKAGING_CHECK.md`); `python report\build_report.py` then `python report\build_slides.py` so `report.html` loses the old `lite/` wording. Open both HTML files by double-click and look.
3. **Back up the old app outside OneDrive.** `robocopy "H2" "C:\backup\hw-Final-2-full" /E /XD lite node_modules .venv`. The backup holds `.env`; keep it private. Check `engine`, `backend`, `frontend`, `scripts`, `output` are in it.
4. **Delete the old app from H2.** Delete everything in `H2` except `lite` and `.env`: `AI_prompts.md PLAN.md README.md RESEARCH.md RIGOR_REVIEW.md backend check_env.py data docs e1_p1.json e1_p7.json e1_p8.json engine frontend mcp_server output requirements-dev.txt requirements.txt scripts tests var .pytest_cache .env.example .gitignore`. Do not delete `lite` yet.
5. **Move the contents up.** `robocopy "LITE" "H2" /E /MOVE /XD node_modules .venv __pycache__ .pytest_cache`. After it, `H2` must hold: `app/ web/ tests/ eval/ simusers/ safety_tests/ report/ user_test/ docs/ run.py requirements.txt .env.example .gitignore README.md PLAN.md report.html slides.html` (and `runs/`, `eval/runs*`, `simusers/runs`, which are git-ignored and not published). `web/node_modules` (119 MB) need not move; delete it, or move it by hand if you still want to rebuild the web app.
6. **Prune scratch before the first commit.** Delete `docs\loop\` (11 MB) or add `docs/loop/` to `.gitignore`. Delete `docs\packaging_scripts\` if unwanted. Trim `docs\screens\` (26 MB, 101 PNG) only if repo size matters.
7. **Remove the empty `LITE` folder** once `H2` holds every item from step 5. Compare file counts before and after (ignored folders excluded).
8. **Fix names that point at `lite/` or `hw-Final-2`** (list below).
9. **.gitignore check** in `H2`: `.env`, `.env.*`, `.venv/`, `node_modules/`, `__pycache__/`, `.pytest_cache/`, `*.log`, `runs/`, `eval/runs*/`, `simusers/runs/` present. Then `git init`, `git add -A`, `git status --short`, `git ls-files | findstr /i "\.env"` (expect only `.env.example` and `web/.env.mock`), `git ls-files | findstr /i "node_modules .venv __pycache__"` (expect nothing). Check no tracked file is over 5 MB.
10. **.env.example check:** every line is `NAME=` with an empty value; the first line says "in this folder or the folder above it".
11. **Secret scan on the final tree:** `python docs\packaging_scripts\scan_paths_secrets.py`. Expect no `SECRET?` line except the `email` false positives, and no `PATH` lines except provenance text. Confirm `grep -c "lite/" report.html` is 0.
12. **Commit and push.** Create the GitHub repo (public, or private with `zlisto` added as collaborator), push, put the URL in the report's title block and rebuild `report.html` and `slides.html` if it is not there.
13. **README run instructions to verify** (README.md, "Run it"): `python -m venv .venv`; activate; `python -m pip install -r requirements.txt`; copy `.env.example` to `.env` with one key; `python run.py`; open http://localhost:8020; `/api/health` shows `ai_available: true`. Also the Tests section (`python -m pytest tests -q`) and the `eval/`, `simusers/`, `safety_tests/` command table.
14. **Fresh-clone test with timing, outside OneDrive.** In a new folder such as `C:\clonetest`:
    ```
    $t = Get-Date
    git clone <repo-url> enough
    cd enough
    python -m venv .venv
    .venv\Scripts\activate
    python -m pip install -r requirements.txt     # about 1.5 minutes last time
    copy .env.example .env                        # put the key in this .env, or in C:\clonetest\.env (one level up)
    python run.py                                 # second window; wait for "Uvicorn running"
    ```
    Then open http://localhost:8020, load the example household, build a plan, ask one question, open What If, check `/api/health`. Record the time of clone, venv, pip, first start and first plan, and the total (target under 10 minutes; the 2026-11-21 dry run took about 2). Repeat once with the key one folder above the clone, and once with no key (templates only). Stop the server and confirm no Python process still owns port 8020.
15. **Clean up.** Delete `C:\clonetest`. Keep the step 3 backup until you are sure you do not need the old app.

## Places that name `lite/` or `hw-Final-2`, or depend on folder depth (step 8)

Code, depth-dependent:
- `app/config.py:15-16,22,29`: `LITE_DIR = APP_DIR.parent`; `.env` read there and in three parents. Works after the move without change. To match the brief exactly set `ENV_LEVELS_UP = 1` (then the owner's key must move to `hw-Final-2\.env`). Owned by another agent.
- `run.py:12`, `tests/conftest.py:7`, `tests/test_security.py:15`: relative to their own file. Safe.
- `eval/common.py` (`REPO = EVAL_DIR.parent`), `simusers/common.py:8,23`, `report/build_report.py:27-30`, `user_test/impact_summary.py:15`, `safety_tests/run_attacks.py:21`: relative to the script. Safe. `eval/make_cases.py` and `eval/benchmark.py` need the old app (`ENOUGH_OLD_APP`); the repo does not need them (`cases.jsonl` and `benchmark_results.json` are committed).
- `docs/loop/*`: scripts assume the old layout; delete the folder.

Text only:
- `app/data/SOURCES.json:2`, `app/tools/neighbors.py:5`, `app/config.py:3,15,16,29`, `web/src/mock.ts:1` (names `lite/PLAN.md`): comments.
- `PLAN.md:10,19,30,117-119,128,131`: layout block starts with `lite/`, `python lite/run.py`, the move paragraph. Rewrite or delete after the move.
- `docs/REPO_PLAN.md`: first paragraph and the table of outside paths (partly done, see `PACKAGING_CHECK.md`).
- `report.html`: rebuild (step 2) so the nine `lite/` mentions go.
