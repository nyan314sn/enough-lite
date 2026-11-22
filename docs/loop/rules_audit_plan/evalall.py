"""Tools-only plans (no AI) for every eval case, as round3_A/evalall3.py, into the folder named on the command line."""
import sys, json, copy, asyncio
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
HERE = Path(__file__).parent
EVAL = HERE.parent / "round3_A" / "evalcopy"
sys.path.insert(0, str(HERE.parents[2]))
OUT = HERE / (sys.argv[1] if len(sys.argv) > 1 else "runs_after")
def one(c):
    OUT.mkdir(exist_ok=True)
    f = OUT / (c["id"] + ".json")
    if f.exists(): return c["id"]
    from app import pipeline
    try:
        p = pipeline.prepare(copy.deepcopy(c["profile"]))
        plan, ctx = asyncio.run(pipeline.tools_only_plan(p))
        r = dict(id=c["id"], wants=plan["wants"]["per_year"], verdict=plan["verdict"], paid=plan["needs"]["paid_of_100"], goal=plan["spending_goal"],
                 consistency=plan["consistency"], headline=plan["headline"], sp=plan.get("starting_points"), ss=plan.get("social_security_per_year"))
    except Exception as e:
        r = dict(id=c["id"], error=repr(e)[:200])
    f.write_text(json.dumps(r), encoding="utf-8"); return c["id"]
if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    cases = [json.loads(l) for l in open(EVAL / "cases.jsonl", encoding="utf-8")]
    cases = [c for c in cases if c["kind"] in ("base","savings_up","retire_later","debt_add","legacy_add","match_full","pension_add")]
    print(len(cases), flush=True)
    with ProcessPoolExecutor(4) as ex:
        for i, x in enumerate(ex.map(one, cases)):
            if i % 50 == 0: print(i, flush=True)
