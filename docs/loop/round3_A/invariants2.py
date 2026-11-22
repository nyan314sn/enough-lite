"""Free invariants (tools only): pay, savings, retire age, own claim age, partner claim age up must not lower count-on;
one more child must not raise it. Households: round 1's 16, the 16 new ones, 40 random (seed 21)."""
import sys, json, asyncio, copy, random
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE))
import get_plans, hh2
from app import pipeline


async def plan_of(profile):
    p = pipeline.prepare(copy.deepcopy(profile))
    plan, ctx = await pipeline.tools_only_plan(p)
    return plan


def count(profile):
    return asyncio.run(plan_of(profile))


def random_profiles(n, seed=21):
    rnd = random.Random(seed)
    out = {}
    states = ["TX", "CA", "NY", "FL", "OH", "WA", "IL", "PA", "GA", "NC", "CO", "MN"]
    for i in range(n):
        age = rnd.randint(30, 66)
        couple = rnd.random() < .55
        retired = age >= 62 and rnd.random() < .3
        ret = age if retired else rnd.randint(max(age + 1, 58), 70)
        pay = 0 if retired else rnd.choice([35000, 55000, 80000, 120000, 200000])
        sv = rnd.choice([10000, 60000, 200000, 500000, 1200000])
        prof = dict(age=age, state=rnd.choice(states), retire_age=ret, pay_per_year=pay,
                    savings={"pretax": sv * .6, "roth": sv * .1, "taxable": sv * .2, "cash": sv * .1},
                    spending_per_year=rnd.choice([30000, 45000, 65000, 90000]), spending_now_per_year=rnd.choice([40000, 60000, 80000, 110000]))
        if rnd.random() < .3:
            prof["children"] = [{"age": rnd.randint(0, 16)} for _ in range(rnd.randint(1, 3))]
        if couple:
            prof.update(has_partner=True, partner_age=age + rnd.randint(-10, 10), partner_pay_per_year=0 if retired else rnd.choice([0, 30000, 60000]))
            if not retired and rnd.random() < .4:
                prof["claim_age"] = rnd.choice([62, 65, 67])
                prof["partner_claim_age"] = rnd.choice([62, 65, 67, 68])
                if prof["partner_age"] < 62 and prof["partner_claim_age"] < prof["partner_age"]:
                    prof["partner_claim_age"] = 67
        if retired:
            prof["social_security_per_year"] = rnd.choice([18000, 28000, 40000])
            prof["claim_age"] = rnd.choice([62, 65, 67, 70])
            prof["claim_age"] = min(prof["claim_age"], age) if age < 70 else prof["claim_age"]
        out[f"q{i:02d}"] = prof
    return out


def perturb(profile, kind):
    p = copy.deepcopy(profile)
    if kind == "pay+20%":
        if not (p.get("pay_per_year") or 0):
            return None
        p["pay_per_year"] *= 1.2
        if p.get("partner_pay_per_year"):
            p["partner_pay_per_year"] *= 1.2
    elif kind == "savings+20%":
        p["savings"] = {k: v * 1.2 for k, v in p["savings"].items()}
    elif kind == "retire+2":
        if p["retire_age"] <= p["age"]:
            return None
        p["retire_age"] += 2
        if p.get("partner_retire_age"):
            p["partner_retire_age"] += 2
    elif kind == "claim+2":
        c = p.get("claim_age")
        if c is None or c > 68 or p["age"] >= c:
            return None
        p["claim_age"] = c + 2
    elif kind == "partner_claim+2":
        c = p.get("partner_claim_age")
        if c is None or c > 68 or not p.get("has_partner"):
            return None
        p["partner_claim_age"] = c + 2
    elif kind == "kid+1(down)":      # one more child: count-on must not rise
        p["children"] = list(p.get("children") or []) + [{"age": 5}]
    return p


if __name__ == "__main__":
    base = dict(get_plans.H); base.update(hh2.N); base.update(random_profiles(int(sys.argv[1]) if len(sys.argv) > 1 else 40))
    res = []
    for name, prof in base.items():
        try:
            b = count(prof)
        except Exception as e:
            print(name, "BASE ERROR", type(e).__name__, str(e)[:100]); continue
        c0 = b["wants"]["per_year"]
        line = f"{name:30s} base {c0:>9,.0f} v={b['verdict']:11s}"
        for kind in ("pay+20%", "savings+20%", "retire+2", "claim+2", "partner_claim+2", "kid+1(down)"):
            q = perturb(prof, kind)
            if q is None:
                continue
            try:
                c1 = count(q)["wants"]["per_year"]
            except Exception as e:
                line += f" | {kind} ERR {str(e)[:40]}"; continue
            d = (c1 - c0) / max(c0, 1)
            bad = d > 0.03 if kind.startswith("kid") else d < -0.03
            line += f" | {kind} {d:+.1%}{' <<<' if bad else ''}"
            res.append((name, kind, c0, c1, d, bad))
        print(line, flush=True)
    print("TOTAL checks", len(res))
    bad = [r for r in res if r[5]]
    print("VIOLATIONS (>3% wrong way):", len(bad))
    for r in bad:
        print("  ", r[:5])
    import collections
    print(collections.Counter(r[1] for r in res), collections.Counter(r[1] for r in bad))
