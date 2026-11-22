"""Rerun the audit's monotonicity invariants (round1_A/invariants.py) on the current code. Usage: mono.py [n_random]"""
import sys
from pathlib import Path
HERE = Path(__file__).parent
A = HERE.parent / "round1_A"
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(A))
import invariants as I
import get_plans

base = dict(get_plans.H)
base.update(I.random_profiles(int(sys.argv[1]) if len(sys.argv) > 1 else 40))
res = []
for name, prof in base.items():
    b = I.count(prof)
    c0 = b["wants"]["per_year"]
    line = f"{name:30s} base {c0:>9,.0f} v={b['verdict']:11s}"
    for kind in ("pay+20%", "savings+20%", "retire+2", "claim+2"):
        q = I.perturb(prof, kind)
        if q is None:
            continue
        c1 = I.count(q)["wants"]["per_year"]
        d = (c1 - c0) / max(c0, 1)
        line += f" | {kind} {d:+.1%}" + (" <<<" if d < -0.03 else (" <" if d < 0 else ""))
        res.append((name, kind, c0, c1, d))
    print(line, flush=True)
print("VIOLATIONS (drop >3%):", sum(1 for r in res if r[4] < -0.03), "of", len(res))
print("ANY DROP:", sum(1 for r in res if r[4] < 0), "of", len(res))
for r in res:
    if r[4] < 0:
        print("  ", r)
