import json
from hh import *
p = example_full()
keep = {k: v for k, v in p.items() if v not in (None, [], {}, "") and k not in ("history", "offered", "asking")}
print(json.dumps(keep)[:3000])
