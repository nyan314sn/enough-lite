import json, statistics as st
from mc_common import *
import common as ec
R=json.load(open("results_plans.json"))["rows"]
for a in R:
    ok=[r for r in R[a].values() if r.get("text_source") and not r["adviser_template"]]
    print(a,"AI-written adviser plans",len(ok),"mean usd",st.mean(r["usd"] for r in ok),"median s",st.median(r["seconds"] for r in ok))
P={a:load_plans(a) for a in ("anthropic","openai")}
J=json.load(open("raw/judge_pairs.json"))
n=0
for i,x in J.items():
    if x.get("numbers_right") in("A","B") and n<3:
        win = x["A_is"] if x["numbers_right"]=="A" else ("openai" if x["A_is"]=="anthropic" else "anthropic")
        if win=="openai" and not str(P["openai"][i]["plan"].get("text_source")).startswith("template"):
            n+=1; print("\n#####",i,"overall",x["overall"],"A is",x["A_is"],"|",x["reason"])
            for a in ("anthropic","openai"):
                print("---",a,P[a][i]["plan"].get("text_source"));print(ec.plan_text(P[a][i]["plan"])[:1100])
