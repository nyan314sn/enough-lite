"""Round 4: re-check the redesigned Enough Lite (R26). Stages: run (normal intake+plan, 24 base + 6 hurried), early (Build early path),
judge (Haiku intake judge), lens (Sonnet R26 lens). Outputs under simusers/round4/.
Usage: python run_round4.py --stage run|early|judge|lens|all [--workers 4]"""
import argparse, inspect, json, random, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIM = HERE.parent
sys.path.insert(0, str(SIM))
sys.path.insert(0, str(SIM.parent / "eval" / "readability"))
import measure  # sets provider keys to "" in this process; common.load_env restores ANTHROPIC from .env
import common
common.load_env()
OUT = HERE
RUNS, JUDGED, ERUNS, EJUDGED, PLANS = OUT / "runs", OUT / "judged", OUT / "runs_early", OUT / "judged_early", OUT / "plans"
for d in (RUNS, JUDGED, ERUNS, EJUDGED, PLANS):
    d.mkdir(exist_ok=True)
common.RUNS, common.JUDGED, common.USAGE_FILE = RUNS, JUDGED, OUT / "usage.json"
APP = "http://localhost:8020"
LENS_MODEL = "claude-sonnet-5-5"
LENS_PRICE = (3.0, 15.0)   # assumed $/M in/out for Sonnet; conservative
COSTLOG = OUT / "cost_log.jsonl"
ESCAPE_TEXT = "Build my plan with typical numbers for the rest"
_l = threading.Lock()


def base_personas():
    ps = json.loads((SIM / "personas.json").read_text(encoding="utf-8"))
    hard = json.loads((SIM / "personas_hard.json").read_text(encoding="utf-8"))
    return ps[::2][:20] + hard[:4]          # same 24 as eval/model_compare


def hs_personas():
    return json.loads((SIM / "personas_hs.json").read_text(encoding="utf-8"))


def all_personas():
    return base_personas() + hs_personas()


common.load_personas = all_personas
import run_sims, judge  # noqa
run_sims.RUNS, run_sims.load_personas, run_sims.APP = RUNS, all_personas, APP
judge.load_personas = all_personas
src = inspect.getsource(run_sims.run_persona).replace('"sim-" + p["id"]', '"sim4-" + p["id"]')
exec(compile(src, "run_sims_patched4", "exec"), run_sims.__dict__)
run_sims.plan_intents = lambda p, rng: []     # intake to a built plan only; no plan chat this round
_orig_build = run_sims.build_plan


def build_and_save(cli, profile, hdr):
    plan, cost, err = _orig_build(cli, profile, hdr)
    if plan:
        (PLANS / (hdr["X-Session-Id"] + ".json")).write_text(json.dumps(plan), encoding="utf-8")
    return plan, cost, err


run_sims.build_plan = build_and_save


def early_ids():
    b = base_personas()
    return [b[i]["id"] for i in (1, 4, 7, 10, 13, 16, 20, 22)] + ["s01", "s05"]


def run_early(p):
    out = ERUNS / f"{p['id']}.json"
    if out.exists() and json.loads(out.read_text(encoding="utf-8")).get("status") == "done":
        return "skip"
    import httpx
    rng = random.Random("early" + p["id"])
    sid = "sim4e-" + p["id"]
    hdr = {"X-Enough-Test": "1", "X-Session-Id": sid}
    run = dict(persona_id=p["id"], name=p["name"], status="running", intake_turns=[], plan_turns=[], path="early", started=time.time())
    cli = httpx.Client()
    profile, last, transcript, prev_assumed = {}, None, [], {}
    k = rng.choice([1, 2])
    answers = escapes = 0
    try:
        n = 0
        while n < 10:
            n += 1
            if answers >= k and last is not None and not last["missing"]:
                break
            press = answers >= k and escapes < 4
            if press:
                text, clicked = ESCAPE_TEXT, None
                escapes += 1
            else:
                q = (last or {}).get("question") or {}
                text, clicked = run_sims.sim_message(p, run_sims.fmt_transcript(transcript), last["reply"] if last else None, q.get("text"), q.get("quick_answers"))
                answers += 1
            r = run_sims.post(cli, "/api/intake", {"text": text, "profile_so_far": profile}, hdr)
            if "_http" in r:
                run["intake_turns"].append(dict(n=n, user=text, clicked=clicked, reply=f"[HTTP {r['_http']}] {r['_body']}", error=True))
                run["status"] = "app_error"
                break
            profile = r["profile"]
            cur = run_sims.assumed_keys(r["fields"])
            new_assumed = [f"{kk}: {v[0]} ({v[1]})" for kk, v in cur.items() if prev_assumed.get(kk) != v]
            prev_assumed = cur
            run["intake_turns"].append(dict(n=n, user=text, clicked=clicked, reply=r["reply"], question=r.get("question"), missing=r["missing"],
                                            ready=r["ready"], new_assumed=new_assumed, early_press=press,
                                            fields=[[f["key"], f.get("display"), f.get("source")] for f in r["fields"]]))
            transcript.append(dict(user=text, app=r["reply"] + (" " + r["question"]["text"] if r.get("question") else "")))
            last = r
        run["final_profile"] = profile
        run["reached_missing_empty"] = bool(last) and not last["missing"]
        run["turns_to_plan"] = len(run["intake_turns"]) if run["reached_missing_empty"] else None
        run["person_messages"] = answers
        run["escape_presses"] = escapes
        if run["reached_missing_empty"]:
            plan, cost, err = run_sims.build_plan(cli, profile, hdr)    # the check step is accepted: build with what the panel shows
            run["plan_error"] = err
            run["plan_ok"] = bool(plan)
            if plan:
                run["plan"] = {kk: plan.get(kk) for kk in ("headline", "needs", "wants", "wishes", "actions")}
        if run["status"] == "running":
            run["status"] = "done"
    except Exception as e:
        run["status"] = "error"
        run["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    run["seconds"] = round(time.time() - run["started"], 1)
    out.write_text(json.dumps(run, indent=1), encoding="utf-8")
    return run["status"]


# ------------------------------------------------------------------ R26 hero text and lens
def usd(n):
    return "${:,.0f}".format(round(n))


def hero_text(plan):
    """What the plan hero shows (web/src/components/PlanHero.tsx, Ladder.tsx, readiness.ts), as plain text."""
    nd, wn = plan["needs"], plan["wants"]
    paid, v = nd["paid_of_100"], plan.get("verdict")
    hs = (plan.get("analysis") or {}).get("how_sure") or {}
    goal = hs.get("goal_per_year")
    countOn, needs = round(wn["per_year"]), round(nd["basics_per_year"])
    lvl_v = "short" if v in ("falls_short", "below_goal") else "close" if v == "close" else "ok"
    lvl_b = "short" if paid < 90 else "ok"
    level = ("short" if lvl_b == "short" else "ok") if v == "works" else ("short" if "short" in (lvl_v, lvl_b) else "close" if "close" in (lvl_v, lvl_b) else "ok")
    kind = "basics" if (paid < 90 or v == "falls_short") else {"ok": "works", "close": "close", "short": "short"}[level]
    verdict = {"works": "Yes, you're on track.", "close": "Close. A few changes get you there.", "short": "Not yet. Here's how to close the gap.", "basics": "Not yet. First, make your needs safe."}[kind]
    gap = max(0, round(goal - wn["per_year"])) if goal is not None else 0
    lines = []
    if goal is not None:
        share = min(100, int(100 * countOn // goal)) if goal else 100
        lines.append(f"Readiness: {min(share, 40) if kind == 'basics' else share} of 100")
    lines.append(verdict)
    lines.append((f"Short {usd(gap)} a year" if gap > 0 else "Falls short" if level == "short" else "Close to your goal") if level != "ok" else f"{usd(wn['per_year'])} a year you can count on.")
    wants = max(0, countOn - needs)
    wishes = max(0, round(goal) - max(countOn, needs)) if goal is not None else 0
    lines.append(f"Needs: {usd(needs)} a year. Paid in {paid} of 100 market tests. {'Safe' if paid >= 90 else 'Not safe yet'}.")
    sure = paid >= 90 and wants > 0
    lines.append(f"Wants: {usd(wants)} a year on top of your needs. You can count on {usd(countOn)} in all. Sure." if sure else
                 f"Wants: $0 a year. {'You can count on less than your needs.' if countOn < needs else 'Nothing above your needs yet.'} You can count on {usd(countOn)}. Not sure yet.")
    if goal is not None:
        covered = countOn >= goal
        lines.append("Wishes: $0 open. Your whole goal is covered." if covered else f"Wishes: {usd(wishes)} a year, the rest of your goal of {usd(goal)}. Only if markets help.")
    if plan.get("headline"):
        w = plan["headline"].split()
        lines.append(" ".join(w[:18]) + ("..." if len(w) > 18 else ""))
    acts = plan.get("actions") or []
    if acts:
        lines.append("First move: " + acts[0]["title"])
    return "\n".join(lines), kind, gap


LENS_SYS = ("You role-play a real person who has just built a retirement plan in an app and is looking at the top of the plan page. "
            "You are a hurried high-school graduate with no finance training. You read ONLY the text shown. Answer honestly: could you, from this text alone, tell:\n"
            "(a) whether you can retire when you want to (your wanted retirement age is given);\n"
            "(b) by how much you are short or ahead (a dollar amount per year, or a clear 'on track');\n"
            "(c) the first thing to do.\n"
            "Say yes only if the text states it in words you would understand; otherwise no. "
            'Output ONLY JSON: {"a":"yes|no","b":"yes|no","c":"yes|no","confusing":"the words or lines that lost you, under 20 words, or empty"}')


def sonnet(user, max_tokens=300):
    c = common.client()
    err = None
    for attempt in range(3):
        try:
            r = c.messages.create(model=LENS_MODEL, max_tokens=max_tokens, system=LENS_SYS, messages=[{"role": "user", "content": user}],
                                  extra_body={"output_config": {"effort": "low"}})
            u = r.usage.input_tokens * LENS_PRICE[0] / 1e6 + r.usage.output_tokens * LENS_PRICE[1] / 1e6
            with _l:
                with COSTLOG.open("a") as f:
                    f.write(json.dumps(dict(role="lens", model=LENS_MODEL, i=r.usage.input_tokens, o=r.usage.output_tokens, usd=round(u, 5))) + "\n")
            return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        except Exception as e:
            err = e
            time.sleep(3)
    raise RuntimeError(type(err).__name__)


def lens_one(p, path):
    sid = ("sim4e-" if path == "early" else "sim4-") + p["id"]
    pf = PLANS / (sid + ".json")
    out = OUT / "lens" / f"{sid}.json"
    out.parent.mkdir(exist_ok=True)
    if out.exists() or not pf.exists():
        return "skip"
    plan = json.loads(pf.read_text(encoding="utf-8"))
    text, kind, gap = hero_text(plan)
    t = p["truth"]
    user = (f"You are {p['name']}, age {t['age']}, {t['job']}. You wanted to retire at {t['retire_age']}. How you write: {p['personality']}\n\n"
            f"WHAT THE TOP OF THE PLAN PAGE SHOWS:\n{text}\n\nOutput the JSON.")
    res = common.parse_json(sonnet(user)) or {}
    st = measure.stats(text)
    out.write_text(json.dumps(dict(id=p["id"], path=path, kind=kind, gap=gap, text=text, result=res, grade=st["grade"], words=st["words"]), indent=1), encoding="utf-8")
    return "ok"


def pmap(fn, items, workers):
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(fn, items))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--ids")
    a = ap.parse_args()
    ps = all_personas()
    if a.ids:
        ps = [p for p in ps if p["id"] in a.ids.split(",")]
    eids = set(early_ids())
    if a.stage in ("run", "all"):
        pmap(lambda p: print("run", p["id"], run_sims.run_persona(p, False), flush=True), ps, a.workers)
    if a.stage in ("early", "all"):
        pmap(lambda p: print("early", p["id"], run_early(p), flush=True), [p for p in ps if p["id"] in eids], a.workers)
    if a.stage in ("judge", "all"):
        judge.RUNS, judge.JUDGED = RUNS, JUDGED
        pmap(lambda p: print("judge", p["id"], judge.judge_one(p, False), flush=True), ps, a.workers)
        judge.RUNS, judge.JUDGED = ERUNS, EJUDGED
        pmap(lambda p: print("judgeE", p["id"], judge.judge_one(p, False), flush=True), [p for p in ps if p["id"] in eids], a.workers)
    if a.stage in ("lens", "all"):
        pmap(lambda p: print("lens", p["id"], lens_one(p, "normal"), flush=True), ps, a.workers)
        pmap(lambda p: print("lensE", p["id"], lens_one(p, "early"), flush=True), [p for p in ps if p["id"] in eids], a.workers)
    print({k: v["usd"] for k, v in common.usage_cost().items()})


if __name__ == "__main__":
    main()
