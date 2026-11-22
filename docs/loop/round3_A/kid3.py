import sys, copy, asyncio
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE))
import hh2, get_plans as G
from app import pipeline
A = dict(G.H); A.update(hh2.N)
for n in ("n15_low_income_parent","n01_single_parent","h08_low_income_low_savings","h04_renter_loans","h13_kids_pets","h05_couple_mortgage","n16_widower_kids","h01_single_young"):
    p = pipeline.prepare(copy.deepcopy(A[n]))
    b, _ = asyncio.run(pipeline.tools_only_plan(p))
    kids = [c.model_dump() for c in p.children] + [{"age": 0}]
    q, notes = pipeline.apply_whatif(pipeline.prepare(copy.deepcopy(A[n])), {"children": kids})
    pl, _ = asyncio.run(pipeline.tools_only_plan(q))
    d = (pl["wants"]["per_year"] - b["wants"]["per_year"]) / max(1, b["wants"]["per_year"])
    print(f"{n:30s} base {b['wants']['per_year']:>8,.0f} +baby {pl['wants']['per_year']:>8,.0f} ({d:+.1%}) spend_now {p.spending_now_per_year}->{q.spending_now_per_year} | {notes.get('after')}", flush=True)
