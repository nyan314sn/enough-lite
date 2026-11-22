import sys
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "round1_A"))
import invariants as I1   # round 1's (seed 11)
import invariants2 as I2

R = I1.random_profiles(40)
bad = 0; tot = 0
for name in sorted(R):
    prof = R[name]
    c0 = I1.count(prof)["wants"]["per_year"]
    line = f"{name} base {c0:,.0f}"
    for kind in ("pay+20%", "savings+20%", "retire+2", "claim+2"):
        q = I1.perturb(prof, kind)
        if q is None:
            continue
        c1 = I1.count(q)["wants"]["per_year"]
        d = (c1 - c0) / max(c0, 1); tot += 1
        flag = d < -0.03
        bad += flag
        line += f" | {kind} {d:+.1%}{' <<<' if flag else ''}"
    print(line, flush=True)
print("round1 seed-11 randoms: checks", tot, "violations", bad)
