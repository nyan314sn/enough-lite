import sys
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE))
import invariants2 as I
base = I.random_profiles(20, seed=77)
res = []
for name, prof in base.items():
    c0 = I.count(prof)["wants"]["per_year"]; line = f"{name} base {c0:>9,.0f}"
    for kind in ("pay+20%", "savings+20%", "retire+2", "claim+2", "partner_claim+2", "kid+1(down)"):
        q = I.perturb(prof, kind)
        if q is None: continue
        c1 = I.count(q)["wants"]["per_year"]; d = (c1 - c0) / max(c0, 1)
        bad = d > 0.03 if kind.startswith("kid") else d < -0.03
        line += f" | {kind} {d:+.1%}{' <<<' if bad else ''}"; res.append((name, kind, c0, c1, d, bad))
    print(line, flush=True)
print("TOTAL", len(res), "VIOLATIONS", [r[:5] for r in res if r[5]])
