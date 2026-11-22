"""Free invariants: more income / savings / later retirement / later claim must not lower count-on. Tools only (no AI)."""
import sys, json, glob, os, asyncio, copy, random
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE))
from app import pipeline
import get_plans

async def plan_of(profile):
    p = pipeline.prepare(copy.deepcopy(profile))
    plan, ctx = await pipeline.tools_only_plan(p)
    return plan

def count(profile):
    return asyncio.run(plan_of(profile))

def random_profiles(n, seed=11):
    rnd = random.Random(seed)
    out = {}
    states = ["TX", "CA", "NY", "FL", "OH", "WA", "IL", "PA", "GA", "NC"]
    for i in range(n):
        age = rnd.randint(30, 66)
        couple = rnd.random() < .45
        retired = age >= 62 and rnd.random() < .35
        ret = age if retired else rnd.randint(max(age + 1, 58), 70)
        pay = 0 if retired else rnd.choice([35000, 55000, 80000, 120000, 200000])
        sv = rnd.choice([10000, 60000, 200000, 500000, 1200000])
        prof = dict(age=age, state=rnd.choice(states), retire_age=ret, pay_per_year=pay,
                    savings={"pretax": sv * .6, "roth": sv * .1, "taxable": sv * .2, "cash": sv * .1},
                    spending_per_year=rnd.choice([30000, 45000, 65000, 90000]), spending_now_per_year=rnd.choice([40000, 60000, 80000, 110000]))
        if couple:
            prof.update(has_partner=True, partner_age=age + rnd.randint(-6, 6), partner_pay_per_year=0 if retired else rnd.choice([0, 30000, 60000]))
        if retired:
            prof["social_security_per_year"] = rnd.choice([18000, 28000, 40000])
            prof["claim_age"] = rnd.choice([62, 65, 67, 70])
            prof["claim_age"] = min(prof["claim_age"], age) if age < 70 else prof["claim_age"]
        out[f"r{i:02d}"] = prof
    return out

def perturb(profile, kind):
    p = copy.deepcopy(profile)
    if kind == "pay+20%":
        if not (p.get("pay_per_year") or 0): return None
        p["pay_per_year"] *= 1.2
        if p.get("partner_pay_per_year"): p["partner_pay_per_year"] *= 1.2
    elif kind == "savings+20%":
        p["savings"] = {k: v * 1.2 for k, v in p["savings"].items()}
    elif kind == "retire+2":
        if p["retire_age"] <= p["age"]: return None
        p["retire_age"] += 2
        if p.get("partner_retire_age"): p["partner_retire_age"] += 2
    elif kind == "claim+2":
        c = p.get("claim_age")
        if c is None or c > 68 or p["age"] >= c: return None
        p["claim_age"] = c + 2
    return p

if __name__ == "__main__":
    base = dict(get_plans.H)
    base.update(random_profiles(int(sys.argv[1]) if len(sys.argv) > 1 else 40))
    res = []
    for name, prof in base.items():
        try:
            b = count(prof)
        except Exception as e:
            print(name, "BASE ERROR", type(e).__name__, str(e)[:100]); continue
        c0 = b["wants"]["per_year"]
        line = f"{name:30s} base {c0:>9,.0f} v={b['verdict']:11s}"
        for kind in ("pay+20%", "savings+20%", "retire+2", "claim+2"):
            q = perturb(prof, kind)
            if q is None: continue
            try:
                c1 = count(q)["wants"]["per_year"]
            except Exception as e:
                line += f" | {kind} ERR {str(e)[:40]}"; continue
            d = (c1 - c0) / max(c0, 1)
            flag = " <<<" if d < -0.03 else ""
            line += f" | {kind} {d:+.1%}{flag}"
            res.append((name, kind, c0, c1, d))
        print(line, flush=True)
    bad = [r for r in res if r[4] < -0.03]
    print("VIOLATIONS (drop >3%):", len(bad), "of", len(res))
    for r in bad: print("  ", r)
