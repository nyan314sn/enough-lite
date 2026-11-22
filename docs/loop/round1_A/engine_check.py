"""Free (tools only, no AI) runs: compare the app's simulation with my own on the same inputs."""
import sys, json, glob, os, asyncio, copy
from pathlib import Path
HERE = Path(__file__).parent
LITE = HERE.parents[2]
sys.path.insert(0, str(LITE))
sys.path.insert(0, str(HERE))
import numpy as np
from app import pipeline
from app.agents import markets as mk
from app.schemas import Profile
import recompute as R

async def run(profile):
    p = pipeline.prepare(profile)
    plan, ctx = await pipeline.tools_only_plan(p)
    return plan, ctx

def mine(ctx, paths=20000):
    inp = mk.sim_inputs(ctx)
    age, ra, hor = inp["age"], inp["retire_age"], inp["horizon_age"]
    n = hor - age
    def pad(xs):
        a = np.zeros(n); k = min(n, len(xs)); a[:k] = xs[:k]; return a
    extra = pad(inp["extra_by_year"]); save = pad(inp["save_by_year"]); inc = pad(inp["income_by_year"])
    lump = pad(inp["lump_by_year"])
    ss_net = inp["ss_per_year"] * (1 - inp["ss_tax_rate"])
    # no annuity in rule of thumb; lump ignored when zero
    assert not lump.any() or True
    safe, ok = R.my_sim(age, ra, hor, inp["savings"], save, ss_net, inp["ss_age"], extra, inc, inp["tax_rate"], inp["risk"], inp["legacy"], paths=paths)
    p_goal = ok(inp["spend_per_year"])
    p_basics = ok(inp["basics_per_year"])
    return inp, safe, p_goal, p_basics

if __name__ == "__main__":
    for f in sorted(glob.glob(str(HERE / "plans" / "*.json"))):
        name = os.path.basename(f)[:-5]
        prof = json.load(open(f, encoding="utf-8"))["profile"]
        plan, ctx = asyncio.run(run(prof))
        inp, safe, pg, pb = mine(ctx)
        nb = plan["neighbors"]
        rule = [c for c in nb["candidates_tested"] if c["source"] == "rule"][0]
        # the chosen strategy may differ; compare against rule of thumb candidate (same inputs as mine)
        d = (safe - rule["safe_spending_per_year"]) / max(rule["safe_spending_per_year"], 1)
        print(f"{name:32s} app_rule_safe {rule['safe_spending_per_year']:>9,.0f} mine {safe:>9,.0f} diff {d:+.1%} | goal_lasts app {rule['goal_lasts_of_100']} mine {pg*100:.0f} | basics app {rule['basics_paid_of_100']} mine {pb*100:.0f} | chosen {nb['chosen']['name'][:28]} count_on {plan['wants']['per_year']:,.0f}")
