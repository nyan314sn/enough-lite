"""Where does parser.parse spend 340 ms on 4,000 dots? Prints the top cumulative entries and the scaling by length."""
import cProfile
import pstats
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.agents import parser, parser_extra  # noqa: E402

for n in (1000, 2000, 4000, 8000):
    t = time.perf_counter()
    parser.parse("." * n, asking=None)
    print(n, "dots", round((time.perf_counter() - t) * 1000, 1), "ms")
pr = cProfile.Profile()
pr.enable()
parser.parse("." * 4000, asking=None)
pr.disable()
pstats.Stats(pr).sort_stats("cumulative").print_stats(8)
print("clauses:", len(parser_extra.clauses("." * 4000)))
import re as _re
import io
s = io.StringIO()
st = pstats.Stats(pr, stream=s)
st.print_callers("re.Pattern|search")
for line in s.getvalue().splitlines():
    if "parser" in line and "lite" in line:
        print(line.split("lite")[-1][:140])
