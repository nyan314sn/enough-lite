import json, collections
from mc_common import *
r = json.load(open("raw/judge_pairs.json")); P = {a: load_plans(a) for a in ("anthropic","openai")}
def src(a,i): return "template" if str(P[a][i]["plan"].get("text_source")).startswith("template") else "ai"
groups = collections.defaultdict(list)
for i,x in r.items():
    if x["identical"]: continue
    groups[(src("anthropic",i), src("openai",i))].append(x)
for g,xs in groups.items():
    c = collections.Counter(); n_=collections.Counter()
    for x in xs:
        for crit in ("overall","numbers_right"):
            v = x.get(crit)
            w = "tie" if v not in ("A","B") else (x["A_is"] if v=="A" else ("openai" if x["A_is"]=="anthropic" else "anthropic"))
            (c if crit=="overall" else n_)[w]+=1
    print("anthropic=%s openai=%s n=%d overall=%s numbers_right=%s" % (g[0],g[1],len(xs),dict(c),dict(n_)))
