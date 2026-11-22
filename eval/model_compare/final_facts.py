import json, statistics as st, collections
from mc_common import *
import common as ec
pl = json.load(open("results_plans.json"))["summary"]
for a in ("anthropic","openai"):
    for t in ("all","comfortable","average","struggling"):
        s=pl["arms"][a][t]; print(a,t,"n",s["n"],"adv_tmpl",s["adviser_template"],"2nd",s["adviser_second_try"],"anyAgentTmpl",s["plans_with_any_agent_template"],"jarg",s["jargon_hits"],"med %.1f p90 %.1f max %.1f"%(s["sec_median"],s["sec_p90"],s["sec_max"]),"usd %.5f"%s["usd_per_plan_app"], "tok in/c/o %d/%d/%d"%(s["tok_in_per_plan"],s["tok_cached_per_plan"],s["tok_out_per_plan"]))
print(pl["tier_counts"], pl["both_ai_text"], len(pl["number_diffs"]))
# why openai templates
P={a:load_plans(a) for a in ("anthropic","openai")}
for a in P:
    c=collections.Counter(); 
    for r in P[a].values():
        ts=str(r["plan"].get("text_source")); c[ts[:60].split(":")[0]]+=1
    print(a,c)
# whatif cost
Q={a:json.load(open(f"raw/qa_{a}.json")) for a in P}
for a in Q:
    w=[r for r in Q[a].values() if r["kind"]=="whatif"]; print(a,"whatif n",len(w),"secs",[r["secs"] for r in w][:12],"cost",[r["cost_usd"] for r in w][:8],[r["tokens"] for r in w][:2])
    allc=[r["cost_usd"] or 0 for r in Q[a].values()]; print(a,"mean cost/msg",st.mean(allc),"sum",sum(allc))
    h=collections.Counter((r["cat"], bool(r["kind"] in r["expected_kinds"])) for r in Q[a].values()); 
J={a:json.load(open(f"raw/qa_judged_{a}.json")) for a in P}
for a in Q:
    tot=0;hc=0;cats=collections.defaultdict(lambda:[0,0])
    for k,r in Q[a].items():
        ok=bool((r["kind"] in r["expected_kinds"]) or (r["cat"]=="refuse" and r.get("emergency"))) and J[a][k]["verdict"]=="correct"
        cats[r["cat"]][0]+=1; cats[r["cat"]][1]+=ok; tot+=1; hc+=ok
    print(a,hc,"/",tot,dict(cats), collections.Counter(v["verdict"] for v in J[a].values()))
