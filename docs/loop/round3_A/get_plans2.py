import json, sys
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import get_plans as G
import hh2
G.URL = "http://127.0.0.1:8070"
OUT = HERE / "plans"; OUT.mkdir(exist_ok=True)
allh = dict(G.H); allh.update(hh2.N)
names = sys.argv[1:] or list(allh)
for n in names:
    prof = allh[n]
    ev = G.post(prof)
    (OUT / (n + ".json")).write_text(json.dumps({"profile": prof, "events": ev}, indent=1), encoding="utf-8")
    print(n, "plan" if any(e.get("type") == "plan" for e in ev) else "NOPLAN", flush=True)
